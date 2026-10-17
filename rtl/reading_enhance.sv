`timescale 1ns/1ps
// BGR888 AXIS. Causal (trailing) 3x3 denoise and 15x15 local mean;
// incomplete border windows fall back to the current gray pixel.
// Config: [2:0] mode 0 raw,1 enhanced gray,2 inverse,3 binary,4 color;
// [3] split-left-bypass [4] denoise [5] sharpen [7:6] local strength;
// [15:8] binary offset C. Config and gamma bank change at accepted SOF only.
module reading_enhance #(parameter WIDTH=1280)(
 (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 aclk CLK", X_INTERFACE_PARAMETER="ASSOCIATED_BUSIF s_axis:m_axis, ASSOCIATED_RESET aresetn" *) input wire aclk,
 (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 aresetn RST", X_INTERFACE_PARAMETER="POLARITY ACTIVE_LOW" *) input wire aresetn,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 s_axis TDATA" *) input wire [23:0] s_axis_tdata,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 s_axis TVALID" *) input wire s_axis_tvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 s_axis TREADY" *) output wire s_axis_tready,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 s_axis TUSER" *) input wire s_axis_tuser,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 s_axis TLAST" *) input wire s_axis_tlast,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 m_axis TDATA" *) output reg [23:0] m_axis_tdata,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 m_axis TVALID" *) output reg m_axis_tvalid=0,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 m_axis TREADY" *) input wire m_axis_tready,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 m_axis TUSER" *) output reg m_axis_tuser,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 m_axis TLAST" *) output reg m_axis_tlast,
 input wire [31:0] cfg_word,input wire lut_we,input wire [7:0] lut_index,lut_data,
 input wire lut_commit,output wire lut_pending,output reg lut_bank=0,
 output reg [31:0] frame_count=0);
 (* ram_style="block" *) reg [7:0] history15[0:WIDTH*15-1];
 (* ram_style="block" *) reg [7:0] history3[0:WIDTH*3-1];
 (* ram_style="block" *) reg [11:0] columns15[0:WIDTH-1];
 (* ram_style="block" *) reg [9:0] columns3[0:WIDTH-1];
 reg [11:0] horizontal15[0:14];reg [9:0] horizontal3[0:2];
 reg [15:0] total15=0;reg [11:0] total3=0;
 reg [7:0] gamma[0:511];integer k;
 initial for(k=0;k<512;k=k+1)gamma[k]=k%256;
 reg [15:0] x=0,y=0;reg [31:0] active_cfg=0;
 reg [3:0] ring15=0;reg [1:0] ring3=0;
 reg commit_wait=0;reg [3:0] bank_guard=0;
 assign lut_pending=commit_wait||(bank_guard!=0);
 wire advance=!m_axis_tvalid||m_axis_tready;
 assign s_axis_tready=aresetn&&advance;
 wire accept=s_axis_tvalid&&s_axis_tready;
 wire [15:0] xx=s_axis_tuser?0:x,yy=s_axis_tuser?0:y;
 wire [3:0] row15=s_axis_tuser?0:ring15;
 wire [1:0] row3=s_axis_tuser?0:ring3;
 wire take_bank=s_axis_tuser&&(bank_guard==0)&&(commit_wait||lut_commit);
 // Stage 0: register each constant product before the BRAM write path.
 (* use_dsp="no" *) reg [15:0] rp0,gp0,bp0;
 wire [15:0] gray_sum=rp0+gp0+bp0;
 reg v0=0,u0,l0,b0;reg [23:0] raw0;reg [31:0] cfg0;
 reg [15:0] x0,y0;reg [3:0] row15_0;reg [1:0] row3_0;
 // Stage 1: synchronous line-buffer reads.
 reg v1=0,u1,l1,b1;reg [7:0] g1,old15,old3;reg [11:0] c15;reg [9:0] c3;
 reg [15:0] x1,y1;reg [23:0] raw1;reg [31:0] cfg1;
 wire [12:0] vertical15=(y1==0?13'd0:{1'b0,c15})+{5'd0,g1}-(y1>=15?{5'd0,old15}:13'd0);
 wire [10:0] vertical3=(y1==0?11'd0:{1'b0,c3})+{3'd0,g1}-(y1>=3?{3'd0,old3}:11'd0);
 wire [15:0] wx1=(cfg1[3]&&x1>=WIDTH/2)?x1-WIDTH/2:x1;
 wire [16:0] window15=(wx1==0?17'd0:{1'b0,total15})+vertical15-(wx1>=15?horizontal15[14]:12'd0);
 wire [12:0] window3=(wx1==0?13'd0:{1'b0,total3})+vertical3-(wx1>=3?horizontal3[2]:10'd0);
 // Stage 2: window sums. No divider/comparison is chained after BRAM output.
 reg v2=0,u2,l2,b2,ok3_2,ok15_2;reg [7:0] g2;
 reg [16:0] sum15_2;reg [12:0] sum3_2;reg [15:0] x2;reg [23:0] raw2;reg [31:0] cfg2;
 // Stage 3: exact reciprocal products. For the full 13/17-bit domains,
 // floor(n/9)=(n*7282)>>16; floor(n/225)=(n*149131)>>25.
 reg v3=0,u3,l3,b3,ok3_3,ok15_3;reg [7:0] g3;
 (* use_dsp="yes" *) reg [34:0] product225_3;
 (* use_dsp="yes" *) reg [26:0] product9_3;
 reg [15:0] x3;reg [23:0] raw3;reg [31:0] cfg3;
 wire [7:0] small_mean3=product9_3[23:16];
 wire [8:0] noise_delta3=(g3>small_mean3)?({1'b0,g3}-{1'b0,small_mean3}):({1'b0,small_mean3}-{1'b0,g3});
 // Stage 4: means and edge-preserving denoise gate.
 reg v4=0,u4,l4,b4,ok3_4,ok15_4;reg [7:0] g4,base4,mean15_4,mean3_4;
 reg [15:0] x4;reg [23:0] raw4;reg [31:0] cfg4;
 // Stage 5: gamma lookup and bounded signed enhancement terms.
 reg v5=0,u5,l5,bypass5,binary5;reg [7:0] tone5,g5;
 reg signed [10:0] detail5;reg signed [8:0] sharp5;
 reg [23:0] raw5;reg [31:0] cfg5;
 wire signed [10:0] tone_term5=$signed({3'd0,tone5});
 wire signed [10:0] detail_term5=detail5>>>2;
 wire signed [10:0] sharp_term5=$signed(sharp5)>>>2;
 wire signed [10:0] result5=tone_term5+detail_term5+sharp_term5;
 function [7:0] clip(input signed [10:0] value);
 begin clip=(value<0)?0:((value>255)?255:value[7:0]);end endfunction
 // Stage 6: clip once before per-channel color reconstruction.
 reg v6=0,u6,l6,bypass6,binary6;reg [7:0] enhanced6,g6;
 reg [23:0] raw6;reg [31:0] cfg6;
 wire signed [9:0] delta6=$signed({2'd0,enhanced6})-$signed({2'd0,g6});
 wire signed [10:0] red6=$signed({3'd0,raw6[23:16]})+$signed(delta6);
 wire signed [10:0] green6=$signed({3'd0,raw6[15:8]})+$signed(delta6);
 wire signed [10:0] blue6=$signed({3'd0,raw6[7:0]})+$signed(delta6);
 reg [23:0] processed;
 always @* begin
  case(cfg6[2:0])
   1:processed={3{enhanced6}};
   2:processed={3{8'd255-enhanced6}};
   3:processed={3{binary6?8'd0:8'd255}};
   4:processed={clip(red6),clip(green6),clip(blue6)};
   default:processed=raw6;
  endcase
  if(bypass6)processed=raw6;
 end
 always @(posedge aclk)begin
  if(!aresetn)begin
   x<=0;y<=0;ring15<=0;ring3<=0;active_cfg<=0;commit_wait<=0;bank_guard<=0;lut_bank<=0;frame_count<=0;
   v0<=0;v1<=0;v2<=0;v3<=0;v4<=0;v5<=0;v6<=0;
   m_axis_tvalid<=0;m_axis_tdata<=0;m_axis_tuser<=0;m_axis_tlast<=0;total15<=0;total3<=0;
  end else begin
   if(lut_we&&!lut_pending)gamma[{!lut_bank,lut_index}]<=lut_data;
   if(lut_commit&&!lut_pending)commit_wait<=1;
   if(advance&&bank_guard!=0)bank_guard<=bank_guard-1;
   if(accept&&take_bank)begin lut_bank<=!lut_bank;commit_wait<=0;bank_guard<=8;end
   if(advance)begin
    m_axis_tvalid<=v6;
    if(v6)begin m_axis_tdata<=processed;m_axis_tuser<=u6;m_axis_tlast<=l6;end
    v6<=v5;
    if(v5)begin
     enhanced6<=clip(result5);g6<=g5;raw6<=raw5;cfg6<=cfg5;
     bypass6<=bypass5;binary6<=binary5;u6<=u5;l6<=l5;
    end
    v5<=v4;
    if(v4)begin
     tone5<=gamma[{b4,base4}];g5<=g4;raw5<=raw4;cfg5<=cfg4;u5<=u4;l5<=l4;
     detail5<=ok15_4?(($signed({1'b0,base4})-$signed({1'b0,mean15_4}))*$signed({1'b0,cfg4[7:6]})):0;
     sharp5<=(ok3_4&&cfg4[5])?($signed({1'b0,g4})-$signed({1'b0,mean3_4})):0;
     binary5<=$signed({2'd0,base4})<(ok15_4?($signed({2'd0,mean15_4})-$signed({2'd0,cfg4[15:8]})):10'sd128);
     bypass5<=cfg4[3]&&x4<WIDTH/2;
    end
    v4<=v3;
    if(v3)begin
     g4<=g3;base4<=(cfg3[4]&&ok3_3&&noise_delta3<=12)?small_mean3:g3;
     mean3_4<=small_mean3;mean15_4<=product225_3[32:25];ok3_4<=ok3_3;ok15_4<=ok15_3;
     raw4<=raw3;cfg4<=cfg3;x4<=x3;u4<=u3;l4<=l3;b4<=b3;
    end
    v3<=v2;
    if(v2)begin
     product225_3<=sum15_2*18'd149131;product9_3<=sum3_2*14'd7282;
     g3<=g2;raw3<=raw2;cfg3<=cfg2;x3<=x2;u3<=u2;l3<=l2;b3<=b2;ok3_3<=ok3_2;ok15_3<=ok15_2;
    end
    v2<=v1;
    if(v1)begin
     columns15[x1]<=vertical15[11:0];columns3[x1]<=vertical3[9:0];
     total15<=window15[15:0];total3<=window3[11:0];
     for(k=14;k>0;k=k-1)horizontal15[k]<=horizontal15[k-1];horizontal15[0]<=vertical15[11:0];
     for(k=2;k>0;k=k-1)horizontal3[k]<=horizontal3[k-1];horizontal3[0]<=vertical3[9:0];
     sum15_2<=window15;sum3_2<=window3;g2<=g1;ok3_2<=wx1>=2&&y1>=2;ok15_2<=wx1>=14&&y1>=14;
     cfg2<=cfg1;raw2<=raw1;x2<=x1;u2<=u1;l2<=l1;b2<=b1;
    end
    v1<=v0;
    if(v0)begin
     old15<=history15[row15_0*WIDTH+x0];history15[row15_0*WIDTH+x0]<=gray_sum[15:8];
     old3<=history3[row3_0*WIDTH+x0];history3[row3_0*WIDTH+x0]<=gray_sum[15:8];
     c15<=columns15[x0];c3<=columns3[x0];g1<=gray_sum[15:8];
     raw1<=raw0;x1<=x0;y1<=y0;u1<=u0;l1<=l0;cfg1<=cfg0;b1<=b0;
    end
    v0<=s_axis_tvalid;
    if(s_axis_tvalid)begin
     rp0<=16'd77*s_axis_tdata[23:16];gp0<=16'd150*s_axis_tdata[15:8];bp0<=16'd29*s_axis_tdata[7:0];
     raw0<=s_axis_tdata;x0<=xx;y0<=yy;row15_0<=row15;row3_0<=row3;u0<=s_axis_tuser;l0<=s_axis_tlast;
     cfg0<=s_axis_tuser?cfg_word:active_cfg;b0<=lut_bank^take_bank;
     if(s_axis_tuser)begin active_cfg<=cfg_word;frame_count<=frame_count+1;end
     if(s_axis_tlast)begin
      x<=0;y<=yy+1;ring15<=(row15==14)?0:row15+1;ring3<=(row3==2)?0:row3+1;
     end else begin x<=xx+1;y<=yy;ring15<=row15;ring3<=row3;end
    end
   end
  end
 end
endmodule
