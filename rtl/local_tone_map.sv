`timescale 1ns/1ps
// 8x6 bounded tile gains, bilinear interpolation between tile centers. CPU
// derives gains from once-per-capture ROI statistics. This is local tone
// mapping, not a full histogram CLAHE. Only luma changes; color follows later.
module local_tone_map #(parameter WIDTH=1280,HEIGHT=720,CONTEXT=108)(
 input wire clk,resetn,input wire [7:0] source_y,target_y,input wire [15:0] x,y,
 input wire [31:0] cfg,quality,input wire bypass,input wire [CONTEXT-1:0] context_in,
 input wire s_valid,output wire s_ready,input wire s_user,
 output reg [7:0] mapped_y=0,output reg [CONTEXT-1:0] context_out=0,
 output reg m_valid=0,input wire m_ready,
 input wire gain_we,gain_commit,input wire [5:0] gain_index,input wire [9:0] gain_value,
 output wire gain_pending);
 (* ram_style="distributed" *) reg [9:0] a[0:95],b[0:95],c[0:95],d[0:95];
 (* rom_style="block" *) reg signed [15:0] x_coordinates[0:WIDTH*2-1],y_coordinates[0:HEIGHT*2-1];
 integer j;initial begin
  for(j=0;j<96;j=j+1)begin a[j]=256;b[j]=256;c[j]=256;d[j]=256;end
  // Constant coordinate tables implement exactly floor(x*256/tile)-128.
  // The synchronous ROM read replaces long constant-divider carry chains.
  for(j=0;j<WIDTH;j=j+1)begin
   x_coordinates[j]=(j*256)/(WIDTH/8)-128;
   x_coordinates[WIDTH+j]=(j*256)/(WIDTH/16)-128;
  end
  for(j=0;j<HEIGHT;j=j+1)begin
   y_coordinates[j]=(j*256)/(HEIGHT/6)-128;
   y_coordinates[HEIGHT+j]=(j*256)/(HEIGHT/12)-128;
  end
 end
 reg bank=0,waiting=0;reg [2:0] guard=0;reg [31:0] active_quality=0;
 wire [31:0] q=s_user?quality:active_quality;
 wire advance=!m_valid||m_ready;assign s_ready=advance&&resetn;
 assign gain_pending=waiting||guard!=0;
 wire change=s_user&&(waiting||gain_commit)&&guard==0;
 reg [6:0] v=0;reg [CONTEXT-1:0] contexts[0:6];reg [7:0] targets[0:6],sources[0:6];
 reg [6:0] enabled=0;reg bank0,bank1,split0;
 reg [10:0] px0;reg [9:0] py0;reg signed [15:0] nx1,ny1;
 wire [15:0] pane_x=(cfg[3]&&x>=WIDTH/2)?x-WIDTH/2:x;
 wire in_rect=!cfg[3]||(y>=HEIGHT/4&&y<HEIGHT*3/4);
 wire [15:0] pane_y=cfg[3]?y-HEIGHT/4:y;
 wire [10:0] bounded_x=nx1<0?0:nx1>7*256?7*256:nx1[10:0];
 wire [10:0] bounded_y=ny1<0?0:ny1>5*256?5*256:ny1[10:0];
 wire [2:0] ix=bounded_x[10:8],iy=bounded_y[10:8];
 wire [2:0] right=ix==7?ix:ix+1,bottom=iy==5?iy:iy+1;
 wire [6:0] base=(bank1?7'd48:7'd0);
 reg [9:0] g00,g10,g01,g11;reg [7:0] fx2,fy2,fy3;
 reg [18:0] horizontal0,horizontal1;reg [27:0] interpolated4;
 reg signed [19:0] product5;
 wire signed [11:0] correction=product5>>>8;
 wire signed [11:0] bounded=correction>24?12'sd24:correction< -24?-12'sd24:correction;
 reg signed [16:0] scaled6;
 wire [5:0] shadow_weight=sources[5]<=24?0:sources[5]>=56?32:sources[5]-24;
 wire [5:0] light_weight=targets[5]<=192?32:targets[5]>=224?0:224-targets[5];
 wire [5:0] weight=shadow_weight<light_weight?shadow_weight:light_weight;
 wire signed [12:0] adjusted=$signed({1'b0,targets[6]})+$signed(scaled6>>>5);
 always @(posedge clk)begin
  if(!resetn)begin v<=0;enabled<=0;m_valid<=0;mapped_y<=0;context_out<=0;bank<=0;waiting<=0;guard<=0;active_quality<=0;end
  else begin
   if(gain_we&&!gain_pending&&gain_index<48)begin
    a[(!bank?48:0)+gain_index]<=gain_value<192?192:gain_value>384?384:gain_value;
    b[(!bank?48:0)+gain_index]<=gain_value<192?192:gain_value>384?384:gain_value;
    c[(!bank?48:0)+gain_index]<=gain_value<192?192:gain_value>384?384:gain_value;
    d[(!bank?48:0)+gain_index]<=gain_value<192?192:gain_value>384?384:gain_value;
   end
   if(gain_commit&&!gain_pending)waiting<=1;
   if(advance&&guard!=0)guard<=guard-1;
   if(s_valid&&s_ready&&change)begin bank<=!bank;waiting<=0;guard<=3;end
   if(advance)begin
    v<={v[5:0],s_valid};enabled<={enabled[5:0],q[7]&&!bypass&&in_rect&&source_y>=24&&target_y<224&&
             (cfg[2:0]==1||cfg[2:0]==2||cfg[2:0]==4)};
    for(j=6;j>0;j=j-1)begin contexts[j]<=contexts[j-1];targets[j]<=targets[j-1];sources[j]<=sources[j-1];end
    contexts[0]<=context_in;targets[0]<=target_y;sources[0]<=source_y;
    if(s_valid)begin
     if(s_user)active_quality<=quality;
     px0<=pane_x[10:0];py0<=in_rect?pane_y[9:0]:0;split0<=cfg[3];bank0<=bank^change;
    end
    if(v[0])begin
     nx1<=x_coordinates[(split0?WIDTH:0)+px0];
     ny1<=y_coordinates[(split0?HEIGHT:0)+py0];
     bank1<=bank0;
    end
    if(v[1])begin
     g00<=a[base+iy*8+ix];g10<=b[base+iy*8+right];
     g01<=c[base+bottom*8+ix];g11<=d[base+bottom*8+right];
     fx2<=bounded_x[7:0];fy2<=bounded_y[7:0];
    end
    if(v[2])begin
     horizontal0<=g00*(9'd256-{1'b0,fx2})+g10*fx2;
     horizontal1<=g01*(9'd256-{1'b0,fx2})+g11*fx2;fy3<=fy2;
    end
    if(v[3])interpolated4<=horizontal0*(9'd256-{1'b0,fy3})+horizontal1*fy3;
    if(v[4])product5<=$signed({1'b0,targets[4]})*($signed({1'b0,interpolated4[25:16]})-12'sd256);
    if(v[5])scaled6<=bounded*$signed({1'b0,weight});
    m_valid<=v[6];
    if(v[6])begin
     context_out<=contexts[6];
     mapped_y<=!enabled[6]?targets[6]:adjusted<0?0:adjusted>255?255:adjusted[7:0];
    end
   end
  end
 end
endmodule
