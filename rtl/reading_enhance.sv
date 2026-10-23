`timescale 1ns/1ps
// BGR888 AXIS. Causal (trailing) 3x3 denoise and 15x15 local mean;
// incomplete border windows fall back to the current gray pixel.
// Config: [2:0] mode 0 raw,1 enhanced gray,2 inverse,3 binary,4 color;
// [3] split-left-bypass [4] denoise [5] sharpen [7:6] local strength;
// [15:8] binary offset C. Config and gamma bank change at accepted SOF only.
// V4 [31] advanced, [30:29] off/USM/Laplacian/guided, [28:25] gain/8,
// [24:21] noise level, [20:17] denoise level, [16] Sobel diagnostic view.
// Window operators are explicitly trailing (same convention as local means).
module reading_enhance #(parameter WIDTH=1280)(
 (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 aclk CLK", X_INTERFACE_PARAMETER="ASSOCIATED_BUSIF s_axis:m_axis, ASSOCIATED_RESET aresetn" *) input wire aclk,
 (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 aresetn RST", X_INTERFACE_PARAMETER="POLARITY ACTIVE_LOW" *) input wire aresetn,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 s_axis TDATA" *) input wire [23:0] s_axis_tdata,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 s_axis TVALID" *) input wire s_axis_tvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 s_axis TREADY" *) output wire s_axis_tready,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 s_axis TUSER" *) input wire s_axis_tuser,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 s_axis TLAST" *) input wire s_axis_tlast,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 m_axis TDATA" *) output wire [23:0] m_axis_tdata,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 m_axis TVALID" *) output wire m_axis_tvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 m_axis TREADY" *) input wire m_axis_tready,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 m_axis TUSER" *) output wire m_axis_tuser,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 m_axis TLAST" *) output wire m_axis_tlast,
 input wire [31:0] cfg_word,input wire lut_we,input wire [7:0] lut_index,lut_data,
 input wire lut_commit,output wire lut_pending,output reg lut_bank=0,
 output reg [31:0] frame_count=0,input wire [31:0] quality_word,
 input wire gain_we,gain_commit,input wire [5:0] gain_index,input wire [9:0] gain_value,
 output wire gain_pending);
 (* ram_style="block" *) reg [7:0] history15[0:WIDTH*31-1];
 (* ram_style="block" *) reg [7:0] history3[0:WIDTH*3-1];
 (* ram_style="block" *) reg [7:0] edge_row1[0:WIDTH-1],edge_row2[0:WIDTH-1];
 reg [7:0] north1,north2,top1,top2,mid1,mid2,bot1,bot2;
 (* ram_style="block" *) reg [12:0] columns15[0:WIDTH-1];
 (* ram_style="block" *) reg [9:0] columns3[0:WIDTH-1];
 reg [12:0] horizontal15[0:30];reg [9:0] horizontal3[0:2];
 reg [17:0] total15=0;reg [11:0] total3=0;
 reg [7:0] gamma[0:511];integer k;
 initial for(k=0;k<512;k=k+1)gamma[k]=k%256;
 reg [15:0] x=0,y=0;reg [31:0] active_cfg=0;
 reg [4:0] ring15=0;reg [1:0] ring3=0;
 reg [31:0] active_quality_main=0;
 wire [31:0] input_cfg=s_axis_tuser?cfg_word:active_cfg;
 wire [31:0] input_quality=s_axis_tuser?quality_word:active_quality_main;
 wire large_window=input_quality[6]&&input_cfg[2:0]==3;
 reg large0,large1,large2,large2a,large3;
 reg commit_wait=0;reg [3:0] bank_guard=0;
 assign lut_pending=commit_wait||(bank_guard!=0);
 wire advance;
 assign s_axis_tready=aresetn&&advance;
 wire accept=s_axis_tvalid&&s_axis_tready;
 wire [15:0] xx=s_axis_tuser?0:x,yy=s_axis_tuser?0:y;
 wire [4:0] row15=s_axis_tuser?0:ring15;
 wire [1:0] row3=s_axis_tuser?0:ring3;
 wire take_bank=s_axis_tuser&&(bank_guard==0)&&(commit_wait||lut_commit);
 // Stage 0: register each constant product before the BRAM write path.
 (* use_dsp="no" *) reg [15:0] rp0,gp0,bp0;
 wire [15:0] gray_sum=rp0+gp0+bp0;
 reg v0=0,u0,l0,b0;reg [23:0] raw0;reg [31:0] cfg0;
 reg [15:0] x0,y0;reg [4:0] row15_0;reg [1:0] row3_0;
 // Stage 1: synchronous line-buffer reads.
 reg v1=0,u1,l1,b1;reg [7:0] g1,old15,old3;reg [12:0] c15;reg [9:0] c3;
 reg [15:0] x1,y1;reg [23:0] raw1;reg [31:0] cfg1;
 wire [13:0] vertical15=(y1==0?14'd0:{1'b0,c15})+{6'd0,g1}-(y1>=(large1?31:15)?{6'd0,old15}:14'd0);
 wire [10:0] vertical3=(y1==0?11'd0:{1'b0,c3})+{3'd0,g1}-(y1>=3?{3'd0,old3}:11'd0);
 wire [15:0] wx1=(cfg1[3]&&x1>=WIDTH/2)?x1-WIDTH/2:x1;
 // Use the existing stages 2/3/4 for side sums, signed differences, and
 // absolute magnitude. A BRAM output no longer crosses the entire Sobel
 // subtract/absolute/sum chain in one cycle. Pixel/control latency is unchanged.
 reg [9:0] gx_pos2,gx_neg2,gy_pos2,gy_neg2,lap_center2,lap_neighbors2;
 reg signed [10:0] gx3,gy3;
 wire [10:0] abs_gx3=gx3<0?-gx3:gx3,abs_gy3=gy3<0?-gy3:gy3;
 wire [11:0] edge_sum3={1'b0,abs_gx3}+{1'b0,abs_gy3};
 // Stage 2: window sums. No divider/comparison is chained after BRAM output.
 reg v2=0,u2,l2,b2,ok3_2,ok15_2;reg [7:0] g2;
 reg [18:0] sum15_2;reg [12:0] sum3_2;reg [15:0] x2;reg [23:0] raw2;reg [31:0] cfg2;
 // Stage 2a separates vertical BRAM accumulation from horizontal running sums.
 // All data, sidebands and gamma-bank tags advance together under backpressure.
 reg [12:0] vertical15_2;reg [9:0] vertical3_2;
 reg v2a=0,u2a,l2a,b2a,ok3_2a,ok15_2a;reg [7:0] g2a;
 reg [15:0] x2a;reg [23:0] raw2a;reg [31:0] cfg2a;
 reg [9:0] gx_pos2a,gx_neg2a,gy_pos2a,gy_neg2a,lap_center2a,lap_neighbors2a;
 wire [15:0] wx2=(cfg2[3]&&x2>=WIDTH/2)?x2-WIDTH/2:x2;
 wire [18:0] window15=(wx2==0?19'd0:{1'b0,total15})+{6'd0,vertical15_2}-(wx2>=(large2?31:15)?(large2?horizontal15[30]:horizontal15[14]):13'd0);
 wire [12:0] window3=(wx2==0?13'd0:{1'b0,total3})+{3'd0,vertical3_2}-(wx2>=3?horizontal3[2]:10'd0);
 reg [7:0] edge4,edge5,edge6;reg signed [11:0] lap3,lap4;
 // Stage 3: exact reciprocal products. For the full 13/17-bit domains,
 // floor(n/9)=(n*7282)>>16; floor(n/225)=(n*149131)>>25.
 reg v3=0,u3,l3,b3,ok3_3,ok15_3;reg [7:0] g3;
 (* use_dsp="yes" *) reg [36:0] product225_3;
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
 // Two extra elastic stages separate subtraction/gating, DSP multiply, clipping.
 reg v4a=0,v4b=0;reg [128:0] context4a,context4b;
 wire [128:0] context4={raw4,cfg4,base4,g4,mean3_4,mean15_4,edge4,lap4,ok3_4,ok15_4,x4,u4,l4,b4};
 wire [23:0] rraw;wire [31:0] rcfg;wire [7:0] rbase,rg,rm3,rm15,redge;
 wire signed [11:0] rlap;wire rok3,rok15,ru,rl,rb;wire [15:0] rx;
 assign {rraw,rcfg,rbase,rg,rm3,rm15,redge,rlap,rok3,rok15,rx,ru,rl,rb}=context4b;
 wire signed [11:0] signal4=(cfg4[30:29]==2)?(lap4>>>2):
                            ($signed({4'd0,g4})-$signed({4'd0,mean3_4}));
 wire [11:0] magnitude4=signal4<0?-signal4:signal4;
 wire [7:0] threshold4={2'b00,cfg4[24:21],2'b00};
 reg signed [11:0] delta4a;reg [3:0] gain4a;reg [1:0] shrink4a,shrink4b;
 (* use_dsp="yes" *) reg signed [16:0] product4b;
 function signed [8:0] finish_sharp(input signed [16:0] product,input [1:0] shrink);
 reg signed [16:0] scaled;
 begin
  scaled=product>>>3;
  if(shrink==2)scaled=0;else if(shrink==1)scaled=scaled>>>1;
  if(scaled>24)scaled=24;else if(scaled< -24)scaled=-24;
  finish_sharp=scaled<<<2;
 end endfunction
 wire signed [10:0] tone_term5=$signed({3'd0,tone5});
 wire signed [10:0] detail_term5=detail5>>>2;
 wire signed [10:0] sharp_term5=$signed(sharp5)>>>2;
 wire signed [10:0] result5=tone_term5+detail_term5+sharp_term5;
 function [7:0] clip(input signed [10:0] value);
 begin clip=(value<0)?0:((value>255)?255:value[7:0]);end endfunction
 // Stage 6: clip once before per-channel color reconstruction.
 reg v6=0,u6,l6,bypass6,binary6;reg [7:0] enhanced6,g6;
 reg [23:0] raw6;reg [31:0] cfg6;
 reg [15:0] xpipe[0:9],ypipe[0:9];reg [31:0] qpipe[0:9];integer coord;
 always @(posedge aclk)if(advance)begin
  xpipe[0]<=xx;ypipe[0]<=yy;qpipe[0]<=input_quality;
  for(coord=9;coord>0;coord=coord-1)begin xpipe[coord]<=xpipe[coord-1];ypipe[coord]<=ypipe[coord-1];qpipe[coord]<=qpipe[coord-1];end
 end
 wire [107:0] tone_context;wire [7:0] local_y;wire local_valid,color_ready;
 wire [23:0] color_raw;wire [7:0] color_source,color_edge;wire [31:0] color_cfg,color_quality;
 wire color_bypass,color_binary,color_user,color_last;
 assign {color_raw,color_source,color_cfg,color_quality,color_bypass,color_binary,color_edge,color_user,color_last}=tone_context;
 local_tone_map #(.WIDTH(WIDTH)) local_tone(.clk(aclk),.resetn(aresetn),.source_y(g6),.target_y(enhanced6),
 .x(xpipe[9]),.y(ypipe[9]),.cfg(cfg6),.quality(qpipe[9]),.bypass(bypass6),
 .context_in({raw6,g6,cfg6,qpipe[9],bypass6,binary6,edge6,u6,l6}),
 .s_valid(v6),.s_ready(advance),.s_user(u6),.mapped_y(local_y),.context_out(tone_context),
 .m_valid(local_valid),.m_ready(color_ready),.gain_we(gain_we),.gain_commit(gain_commit),.gain_index(gain_index),.gain_value(gain_value),.gain_pending(gain_pending));
 color_reconstruct reconstruction(.clk(aclk),.resetn(aresetn),.raw(color_raw),.source_y(color_source),.target_y(local_y),
 .cfg(color_cfg),.quality(color_quality),.bypass(color_bypass),.binary(color_binary),.edge_value(color_edge),
 .s_valid(local_valid),.s_ready(color_ready),.s_user(color_user),.s_last(color_last),.m_data(m_axis_tdata),.m_valid(m_axis_tvalid),
 .m_ready(m_axis_tready),.m_user(m_axis_tuser),.m_last(m_axis_tlast));
 always @(posedge aclk)begin
  if(!aresetn)begin
   x<=0;y<=0;ring15<=0;ring3<=0;active_cfg<=0;active_quality_main<=0;commit_wait<=0;bank_guard<=0;lut_bank<=0;frame_count<=0;
   v0<=0;v1<=0;v2<=0;v2a<=0;v3<=0;v4<=0;v4a<=0;v4b<=0;v5<=0;v6<=0;
   total15<=0;total3<=0;
  end else begin
   if(lut_we&&!lut_pending)gamma[{!lut_bank,lut_index}]<=lut_data;
   if(lut_commit&&!lut_pending)commit_wait<=1;
   if(advance&&bank_guard!=0)bank_guard<=bank_guard-1;
   if(accept&&take_bank)begin lut_bank<=!lut_bank;commit_wait<=0;bank_guard<=11;end
   if(advance)begin
    v6<=v5;
    if(v5)begin
     enhanced6<=clip(result5);g6<=g5;raw6<=raw5;cfg6<=cfg5;
     bypass6<=bypass5;binary6<=binary5;u6<=u5;l6<=l5;edge6<=edge5;
    end
    v5<=v4b;
    if(v4b)begin
     tone5<=gamma[{rb,rbase}];g5<=rg;raw5<=rraw;cfg5<=rcfg;u5<=ru;l5<=rl;
     detail5<=rok15&&!(rcfg[31]&&rcfg[30:29]==3&&redge<={2'b00,rcfg[24:21],2'b00})?
              (($signed({1'b0,rbase})-$signed({1'b0,rm15}))*$signed({1'b0,rcfg[7:6]})):0;
     sharp5<=rcfg[31]?finish_sharp(product4b,shrink4b):
             ((rok3&&rcfg[5])?($signed({1'b0,rg})-$signed({1'b0,rm3})):0);
     edge5<=redge;
     binary5<=$signed({2'd0,rbase})<(rok15?($signed({2'd0,rm15})-$signed({2'd0,rcfg[15:8]})):10'sd128);
     bypass5<=rcfg[3]&&rx<WIDTH/2;
    end
    v4b<=v4a;
    if(v4a)begin
     context4b<=context4a;product4b<=delta4a*$signed({1'b0,gain4a});shrink4b<=shrink4a;
    end
    v4a<=v4;
    if(v4)begin
     context4a<=context4;delta4a<=signal4;gain4a<=cfg4[28:25];shrink4a<=0;
     if(!ok3_4||!cfg4[5]||cfg4[30:29]==0)shrink4a<=2;
     else if(cfg4[30:29]==3)begin
      if(edge4<=threshold4||magnitude4<=({8'd0,cfg4[24:21]}<<1))shrink4a<=2;
      else if(edge4<threshold4+24||edge4>160)shrink4a<=1;
     end
    end
    v4<=v3;
    if(v3)begin
     g4<=g3;base4<=(cfg3[4]&&ok3_3&&noise_delta3<=(cfg3[31]?({5'd0,cfg3[20:17]}*3):9'd12))?small_mean3:g3;
     edge4<=ok3_3?(edge_sum3>>3):0;lap4<=ok3_3?lap3:0;
     mean3_4<=small_mean3;mean15_4<=large3?product225_3[34:27]:product225_3[32:25];ok3_4<=ok3_3;ok15_4<=ok15_3;
     raw4<=raw3;cfg4<=cfg3;x4<=x3;u4<=u3;l4<=l3;b4<=b3;
    end
    v3<=v2a;
    if(v2a)begin
     product225_3<=sum15_2*(large2a?18'd139665:18'd149131);product9_3<=sum3_2*14'd7282;large3<=large2a;
     gx3<=$signed({1'b0,gx_pos2a})-$signed({1'b0,gx_neg2a});
     gy3<=$signed({1'b0,gy_pos2a})-$signed({1'b0,gy_neg2a});
     lap3<=$signed({2'b0,lap_center2a})-$signed({2'b0,lap_neighbors2a});
     g3<=g2a;raw3<=raw2a;cfg3<=cfg2a;x3<=x2a;u3<=u2a;l3<=l2a;b3<=b2a;ok3_3<=ok3_2a;ok15_3<=ok15_2a;
    end
    v2a<=v2;
    if(v2)begin
     total15<=window15[17:0];total3<=window3[11:0];
     for(k=30;k>0;k=k-1)horizontal15[k]<=horizontal15[k-1];horizontal15[0]<=vertical15_2;
     for(k=2;k>0;k=k-1)horizontal3[k]<=horizontal3[k-1];horizontal3[0]<=vertical3_2;
     sum15_2<=window15;sum3_2<=window3;
     large2a<=large2;
     g2a<=g2;raw2a<=raw2;cfg2a<=cfg2;x2a<=x2;u2a<=u2;l2a<=l2;b2a<=b2;ok3_2a<=ok3_2;ok15_2a<=ok15_2;
     gx_pos2a<=gx_pos2;gx_neg2a<=gx_neg2;gy_pos2a<=gy_pos2;gy_neg2a<=gy_neg2;
     lap_center2a<=lap_center2;lap_neighbors2a<=lap_neighbors2;
    end
    v2<=v1;
    if(v1)begin
     top2<=wx1==0?0:top1;top1<=north2;
     mid2<=wx1==0?0:mid1;mid1<=north1;
     bot2<=wx1==0?0:bot1;bot1<=g1;
     gx_pos2<=({2'b0,north2}+{2'b0,g1})+{1'b0,north1,1'b0};
     gx_neg2<=({2'b0,top2}+{2'b0,bot2})+{1'b0,mid2,1'b0};
     gy_pos2<=({2'b0,bot2}+{2'b0,g1})+{1'b0,bot1,1'b0};
     gy_neg2<=({2'b0,top2}+{2'b0,north2})+{1'b0,top1,1'b0};
     lap_center2<={mid1,2'b00};
     lap_neighbors2<=({2'b0,top1}+{2'b0,bot1})+({2'b0,mid2}+{2'b0,north1});
     columns15[x1]<=vertical15[12:0];columns3[x1]<=vertical3[9:0];
     vertical15_2<=vertical15[12:0];vertical3_2<=vertical3[9:0];large2<=large1;
     g2<=g1;ok3_2<=wx1>=2&&y1>=2;ok15_2<=wx1>=(large1?30:14)&&y1>=(large1?30:14);
     cfg2<=cfg1;raw2<=raw1;x2<=x1;u2<=u1;l2<=l1;b2<=b1;
    end
    v1<=v0;
    if(v0)begin
     north1<=edge_row1[x0];north2<=edge_row2[x0];
     edge_row1[x0]<=gray_sum[15:8];edge_row2[x0]<=edge_row1[x0];
     old15<=history15[row15_0*WIDTH+x0];history15[row15_0*WIDTH+x0]<=gray_sum[15:8];
     old3<=history3[row3_0*WIDTH+x0];history3[row3_0*WIDTH+x0]<=gray_sum[15:8];
     c15<=columns15[x0];c3<=columns3[x0];g1<=gray_sum[15:8];
     large1<=large0;
     raw1<=raw0;x1<=x0;y1<=y0;u1<=u0;l1<=l0;cfg1<=cfg0;b1<=b0;
    end
    v0<=s_axis_tvalid;
    if(s_axis_tvalid)begin
     rp0<=16'd77*s_axis_tdata[23:16];gp0<=16'd150*s_axis_tdata[15:8];bp0<=16'd29*s_axis_tdata[7:0];
     raw0<=s_axis_tdata;x0<=xx;y0<=yy;row15_0<=row15;row3_0<=row3;u0<=s_axis_tuser;l0<=s_axis_tlast;
     cfg0<=s_axis_tuser?cfg_word:active_cfg;b0<=lut_bank^take_bank;
     large0<=large_window;
     if(s_axis_tuser)begin active_cfg<=cfg_word;active_quality_main<=quality_word;frame_count<=frame_count+1;end
     if(s_axis_tlast)begin
      x<=0;y<=yy+1;ring15<=(row15==(large_window?30:14))?0:row15+1;ring3<=(row3==2)?0:row3+1;
     end else begin x<=xx+1;y<=yy;ring15<=row15;ring3<=row3;end
    end
   end
  end
 end
endmodule
