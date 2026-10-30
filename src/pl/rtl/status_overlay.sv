`timescale 1ns/1ps
// Six 64-character rows, 2x original 5x7 font. Double-bank CPU text and SOF
// commit; no framebuffer stores and no CPU composition in the live path.
module status_overlay #(parameter WIDTH=1280)(
 input wire clk,resetn,input wire [23:0] s_data,input wire s_valid,output wire s_ready,
 input wire s_user,s_last,output reg [23:0] m_data=0,output reg m_valid=0,
 input wire m_ready,output reg m_user=0,m_last=0,
 input wire text_we,text_commit,text_enable,input wire [8:0] text_index,
 input wire [7:0] text_data,output wire text_pending);
 (* ram_style="block" *) reg [7:0] characters[0:1023];
 integer i;initial for(i=0;i<1024;i=i+1)characters[i]=32;
 reg bank=0,waiting=0,active_enable=0;reg [2:0] guard=0;
 reg [15:0] x=0,y=0;
 wire advance=!m_valid||m_ready;assign s_ready=advance&&resetn;
 assign text_pending=waiting||guard!=0;
 wire [15:0] xx=s_user?0:x,yy=s_user?0:y;
 wire [15:0] px=xx-12,py=yy-12;
 wire visible=xx>=12&&xx<1036&&yy>=12&&yy<108;
 wire [8:0] address={py[6:4],px[9:4]};
 wire change=s_user&&(waiting||text_commit)&&guard==0;
 reg v0=0,v1=0,u0,l0,u1,l1,mask0,draw1;reg [23:0] data0,data1;
 reg [7:0] char0;reg [2:0] row0,col0;wire font_lit;
 status_font font(.character(char0),.row(row0),.column(col0),.lit(font_lit));
 always @(posedge clk)begin
  if(!resetn)begin
   bank<=0;waiting<=0;active_enable<=0;guard<=0;x<=0;y<=0;v0<=0;v1<=0;m_valid<=0;m_user<=0;m_last<=0;m_data<=0;
  end else begin
   if(text_we&&!text_pending&&text_index<384)characters[{!bank,text_index}]<=text_data;
   if(text_commit&&!text_pending)waiting<=1;
   if(advance&&guard!=0)guard<=guard-1;
   if(s_valid&&s_ready&&change)begin bank<=!bank;waiting<=0;guard<=3;end
   if(advance)begin
    v0<=s_valid;v1<=v0;m_valid<=v1;
    if(s_valid)begin
     data0<=s_data;u0<=s_user;l0<=s_last;
     char0<=characters[{bank^change,address}];row0<=py[3:1];col0<=px[3:1];
     mask0<=visible&&(s_user?text_enable:active_enable);
     if(s_user)active_enable<=text_enable;
     if(s_last)begin x<=0;y<=yy+1;end else begin x<=xx+1;y<=yy;end
    end
    if(v0)begin data1<=data0;u1<=u0;l1<=l0;draw1<=mask0&&font_lit;end
    if(v1)begin m_data<=draw1?24'h00ff00:data1;m_user<=u1;m_last<=l1;end
   end
  end
 end
endmodule
