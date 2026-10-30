`timescale 1ns/1ps
// Causal 3x3 color-noise suppression, retaining current-pixel luminance.
// Low luma/chroma differences admit filtering; color boundaries and the raw
// comparison pane bypass. This is spatial filtering, not temporal compensation.
module chroma_filter #(parameter WIDTH=1280)(
 input wire clk,resetn,input wire [23:0] s_data,input wire s_valid,output wire s_ready,
 input wire s_user,s_last,input wire [31:0] cfg,quality,
 output reg [23:0] m_data=0,output reg m_valid=0,input wire m_ready,
 output reg m_user=0,m_last=0,output reg [31:0] m_cfg=0,m_quality=0);
 (* ram_style="block" *) reg [23:0] row1[0:WIDTH-1],row2[0:WIDTH-1];
 reg [23:0] north1,north2;
 reg [15:0] x=0,y=0;reg [31:0] active_cfg=0,active_quality=0;
 wire [15:0] xx=s_user?0:x,yy=s_user?0:y;
 wire [31:0] input_cfg=s_user?cfg:active_cfg,input_quality=s_user?quality:active_quality;
 wire advance=!m_valid||m_ready;assign s_ready=advance&&resetn;
 reg [5:0] v=0,u=0,last=0,ok=0;
 reg [23:0] raw[0:5];reg [31:0] configs[0:5],qualities[0:5];reg [7:0] lum[0:5];
 reg [15:0] x0,y0;
 wire [15:0] wx0=(configs[0][3]&&x0>=WIDTH/2)?x0-WIDTH/2:x0;
 wire [9:0] colr={2'b0,raw[0][23:16]}+{2'b0,north1[23:16]}+{2'b0,north2[23:16]};
 wire [9:0] colg={2'b0,raw[0][15:8]}+{2'b0,north1[15:8]}+{2'b0,north2[15:8]};
 wire [9:0] colb={2'b0,raw[0][7:0]}+{2'b0,north1[7:0]}+{2'b0,north2[7:0]};
 reg [9:0] pr1,pr2,pg1,pg2,pb1,pb2;reg [11:0] sr1,sg1,sb1;
 (* use_dsp="yes" *) reg [25:0] rr2,gg2,bb2;
 wire [7:0] meanr=rr2[23:16],meang=gg2[23:16],meanb=bb2[23:16];
 function [7:0] gray(input [23:0] rgb);
 reg [15:0] sum;begin sum=77*rgb[23:16]+150*rgb[15:8]+29*rgb[7:0];gray=sum[15:8];end endfunction
 function [11:0] abs12(input signed [11:0] n);begin abs12=n<0?-n:n;end endfunction
 function [7:0] clip(input signed [17:0] n);begin clip=n<0?0:n>255?255:n[7:0];end endfunction
 reg [7:0] mr3,mg3,mb3,my3;reg gate4,gate5;
 wire [3:0] strength=configs[3][20:17]>10?4'd10:configs[3][20:17];
 wire signed [11:0] diff_r=$signed({4'd0,mr3})-$signed({4'd0,my3})-$signed({4'd0,raw[3][23:16]})+$signed({4'd0,lum[3]});
 wire signed [11:0] diff_g=$signed({4'd0,mg3})-$signed({4'd0,my3})-$signed({4'd0,raw[3][15:8]})+$signed({4'd0,lum[3]});
 wire signed [11:0] diff_b=$signed({4'd0,mb3})-$signed({4'd0,my3})-$signed({4'd0,raw[3][7:0]})+$signed({4'd0,lum[3]});
 reg signed [11:0] dr4,dg4,db4;reg [3:0] strength4;
 (* use_dsp="yes" *) reg signed [16:0] dr5,dg5,db5;
 integer k;
 always @(posedge clk)begin
  if(!resetn)begin x<=0;y<=0;active_cfg<=0;active_quality<=0;v<=0;m_valid<=0;m_data<=0;m_user<=0;m_last<=0;m_cfg<=0;m_quality<=0;end
  else if(advance)begin
   v<={v[4:0],s_valid};u<={u[4:0],s_user};last<={last[4:0],s_last};ok<={ok[4:0],1'b0};
   for(k=5;k>0;k=k-1)begin raw[k]<=raw[k-1];lum[k]<=lum[k-1];configs[k]<=configs[k-1];qualities[k]<=qualities[k-1];end
   if(s_valid)begin
    raw[0]<=s_data;lum[0]<=gray(s_data);configs[0]<=input_cfg;qualities[0]<=input_quality;
    north1<=row1[xx];north2<=row2[xx];row1[xx]<=s_data;row2[xx]<=row1[xx];x0<=xx;y0<=yy;
    if(s_user)begin active_cfg<=cfg;active_quality<=quality;end
    if(s_last)begin x<=0;y<=yy+1;end else begin x<=xx+1;y<=yy;end
   end
   if(v[0])begin
    sr1<=colr+(wx0==0?0:pr1)+(wx0<2?0:pr2);
    sg1<=colg+(wx0==0?0:pg1)+(wx0<2?0:pg2);
    sb1<=colb+(wx0==0?0:pb1)+(wx0<2?0:pb2);
    pr2<=pr1;pr1<=colr;pg2<=pg1;pg1<=colg;pb2<=pb1;pb1<=colb;
    ok[1]<=wx0>=2&&y0>=2&&!(configs[0][3]&&x0<WIDTH/2);
   end
   if(v[1])begin rr2<=sr1*14'd7282;gg2<=sg1*14'd7282;bb2<=sb1*14'd7282;end
   if(v[2])begin mr3<=meanr;mg3<=meang;mb3<=meanb;my3<=gray({meanr,meang,meanb});end
   if(v[3])begin
    dr4<=diff_r;dg4<=diff_g;db4<=diff_b;strength4<=strength;
    gate4<=ok[3]&&qualities[3][8]&&configs[3][4]&&configs[3][2:0]==4&&!configs[3][16]&&strength!=0&&
      abs12($signed({4'd0,lum[3]})-$signed({4'd0,my3}))<=strength*3&&
      abs12(diff_r-diff_g)<=strength*6+8&&abs12(diff_b-diff_g)<=strength*6+8;
   end
   if(v[4])begin dr5<=dr4*$signed({1'b0,strength4});dg5<=dg4*$signed({1'b0,strength4});db5<=db4*$signed({1'b0,strength4});gate5<=gate4;end
   m_valid<=v[5];
   if(v[5])begin
    m_data<=gate5?{clip($signed({1'b0,raw[5][23:16]})+(dr5>>>4)),clip($signed({1'b0,raw[5][15:8]})+(dg5>>>4)),clip($signed({1'b0,raw[5][7:0]})+(db5>>>4))}:raw[5];
    m_user<=u[5];m_last<=last[5];m_cfg<=configs[5];m_quality<=qualities[5];
   end
  end
 end
endmodule
