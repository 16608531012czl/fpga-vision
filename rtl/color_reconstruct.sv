`timescale 1ns/1ps
// Bounded chroma compensation after tone/denoise. A common chroma gain is
// selected for all RGB channels; gamut overflow reduces that gain, never clips
// channels independently. Quality bit0 enables, bits5:1 strength 0..16.
// All context is elastic and SOF-latched. Raw/gray/binary/Sobel bypass intact.
module color_reconstruct(
 input wire clk,resetn,input wire [23:0] raw,input wire [7:0] source_y,target_y,
 input wire [31:0] cfg,quality,input wire bypass,binary,input wire [7:0] edge_value,
 input wire s_valid,output wire s_ready,input wire s_user,s_last,
 output reg [23:0] m_data=0,output reg m_valid=0,input wire m_ready,
 output reg m_user=0,m_last=0);
 reg [31:0] active_quality=0;
 wire [31:0] q=s_user?quality:active_quality;
 wire advance=!m_valid||m_ready;
 assign s_ready=advance&&resetn;
 reg v0=0,u0,l0,b0,bin0;reg [31:0] cfg0;reg [23:0] raw0;
 reg [7:0] y0,edge0;reg signed [9:0] cr0,cg0,cb0;
 reg [5:0] gain0;reg enabled0;
 wire [8:0] lift=target_y>source_y?{1'b0,target_y}-{1'b0,source_y}:0;
 wire [4:0] limit=q[5:1]>16?5'd16:q[5:1];
 wire [4:0] boost=source_y<16?(limit>4?5'd4:limit):limit;
 wire [4:0] amount=(lift>>2)>boost?boost:(lift>>2);
 reg v1=0,u1,l1,b1,bin1;reg [31:0] cfg1;reg [23:0] raw1;
 reg [7:0] y1,edge1;reg signed [9:0] cr1,cg1,cb1;reg enabled1;
 reg signed [16:0] pr1,pg1,pb1;
 wire signed [16:0] low1=-$signed({1'b0,y1,5'b0});
 wire signed [16:0] high1=$signed({1'b0,(8'd255-y1),5'b0});
 wire candidate_fits=(pr1>=low1&&pr1<=high1&&pg1>=low1&&pg1<=high1&&pb1>=low1&&pb1<=high1);
 wire one_fits=($signed(cr1)>=-$signed({2'b0,y1})&&$signed(cr1)<=$signed({2'b0,8'd255-y1})&&
                $signed(cg1)>=-$signed({2'b0,y1})&&$signed(cg1)<=$signed({2'b0,8'd255-y1})&&
                $signed(cb1)>=-$signed({2'b0,y1})&&$signed(cb1)<=$signed({2'b0,8'd255-y1}));
 wire half_fits=(($signed(cr1)>>>1)>=-$signed({2'b0,y1})&&($signed(cr1)>>>1)<=$signed({2'b0,8'd255-y1})&&
                 ($signed(cg1)>>>1)>=-$signed({2'b0,y1})&&($signed(cg1)>>>1)<=$signed({2'b0,8'd255-y1})&&
                 ($signed(cb1)>>>1)>=-$signed({2'b0,y1})&&($signed(cb1)>>>1)<=$signed({2'b0,8'd255-y1}));
 function [7:0] clip(input signed [17:0] value);
 begin clip=value<0?0:value>255?255:value[7:0];end endfunction
 reg [23:0] color;
 always @* begin
  if(!enabled1)color={clip($signed({1'b0,y1})+$signed(cr1)),clip($signed({1'b0,y1})+$signed(cg1)),clip($signed({1'b0,y1})+$signed(cb1))};
  else if(candidate_fits)color={clip($signed({1'b0,y1})+(pr1>>>5)),clip($signed({1'b0,y1})+(pg1>>>5)),clip($signed({1'b0,y1})+(pb1>>>5))};
  else if(one_fits)color={clip($signed({1'b0,y1})+$signed(cr1)),clip($signed({1'b0,y1})+$signed(cg1)),clip($signed({1'b0,y1})+$signed(cb1))};
  else if(half_fits)color={clip($signed({1'b0,y1})+($signed(cr1)>>>1)),clip($signed({1'b0,y1})+($signed(cg1)>>>1)),clip($signed({1'b0,y1})+($signed(cb1)>>>1))};
  else color={3{y1}};
 end
 always @(posedge clk)begin
  if(!resetn)begin v0<=0;v1<=0;m_valid<=0;m_data<=0;m_user<=0;m_last<=0;active_quality<=0;end
  else if(advance)begin
   v0<=s_valid;
   if(s_valid)begin
    if(s_user)active_quality<=quality;
    raw0<=raw;cfg0<=cfg;y0<=target_y;edge0<=edge_value;b0<=bypass;bin0<=binary;u0<=s_user;l0<=s_last;
    cr0<=$signed({2'b0,raw[23:16]})-$signed({2'b0,source_y});
    cg0<=$signed({2'b0,raw[15:8]})-$signed({2'b0,source_y});
    cb0<=$signed({2'b0,raw[7:0]})-$signed({2'b0,source_y});
    gain0<=6'd32+amount;enabled0<=q[0];
   end
   v1<=v0;
   if(v0)begin
    raw1<=raw0;cfg1<=cfg0;y1<=y0;edge1<=edge0;b1<=b0;bin1<=bin0;u1<=u0;l1<=l0;
    cr1<=cr0;cg1<=cg0;cb1<=cb0;enabled1<=enabled0;
    pr1<=cr0*$signed({1'b0,gain0});pg1<=cg0*$signed({1'b0,gain0});pb1<=cb0*$signed({1'b0,gain0});
   end
   m_valid<=v1;
   if(v1)begin
    case(cfg1[2:0])
     1:m_data<={3{y1}};
     2:m_data<={3{8'd255-y1}};
     3:m_data<={3{bin1?8'd0:8'd255}};
     4:m_data<=color;
     default:m_data<=raw1;
    endcase
    if(cfg1[31]&&cfg1[16]&&cfg1[2:0]!=0)m_data<={3{edge1}};
    if(b1)m_data<=raw1;
    m_user<=u1;m_last<=l1;
   end
  end
 end
endmodule
