`timescale 1ns/1ps
// 8x6 source-ROI statistics, once per captured frame, not per HDMI repeat.
// Double banks publish only after valid EOF and pipeline drain. The CPU mirror
// avoids a third BRAM port. Explicit write-first forwarding handles repeated
// accesses to the same tile and A/B/A read-modify-write hazards.
module frame_tiles #(parameter WIDTH=1280,HEIGHT=720)(
 input wire clk,resetn,enable,start,capture_ok,input wire [31:0] roi_cfg,view_cfg,capture_id,
 input wire [27:0] s_data,input wire s_valid,output wire s_ready,
 input wire [5:0] read_index,output reg [23:0] read_sum=0,
 output reg [15:0] sample_count=0,output reg [31:0] published_id=0,
 output reg done=0);
 (* ram_style="block" *) reg [23:0] sums[0:95],cpu_sums[0:95];
 reg published_bank=0,work_bank=1,clearing=0,receiving=0,armed=0,publish_wait=0;reg [5:0] clear_index=0;
 reg [15:0] x=0,y=0,rx=0,ry=0,rw=WIDTH,rh=HEIGHT,work_count=0;reg [1:0] zoom=0;
 reg v0=0,v1=0,v2=0;reg [15:0] nx0,ny0;reg [7:0] gray1,gray2;
 (* use_dsp="no" *) reg [15:0] rp0,gp0,bp0;
 wire [15:0] gray_sum=rp0+gp0+bp0;
 reg [6:0] addr1,addr2;reg [23:0] old2;
 reg [3:0] eof_pipe=0,good_pipe=0;
 wire hit=x>=rx&&x<rx+rw&&y>=ry&&y<ry+rh;
 wire [23:0] updated=old2+gray2;
 wire [6:0] cpu_addr=(published_bank?7'd48:7'd0)+(read_index<48?read_index:0);
 assign s_ready=enable&&!clearing;
 wire memory_we=resetn&&enable&&!start&&(clearing||v2);
 wire [6:0] memory_addr=clearing?((work_bank?7'd48:7'd0)+clear_index):addr2;
 wire [23:0] memory_value=clearing?24'd0:updated;
 // Bounded coordinate comparators avoid a full-width constant divider in
 // the RAM address path. Coordinates have already been normalized to ROI.
 function [2:0] tile_x(input [15:0] value);
 begin
  if(value<WIDTH/8)tile_x=0;else if(value<WIDTH/4)tile_x=1;
  else if(value<WIDTH*3/8)tile_x=2;else if(value<WIDTH/2)tile_x=3;
  else if(value<WIDTH*5/8)tile_x=4;else if(value<WIDTH*3/4)tile_x=5;
  else if(value<WIDTH*7/8)tile_x=6;else tile_x=7;
 end endfunction
 function [2:0] tile_y(input [15:0] value);
 begin
  if(value<HEIGHT/6)tile_y=0;else if(value<HEIGHT/3)tile_y=1;
  else if(value<HEIGHT/2)tile_y=2;else if(value<HEIGHT*2/3)tile_y=3;
  else if(value<HEIGHT*5/6)tile_y=4;else tile_y=5;
 end endfunction
 always @(posedge clk)begin
  if(memory_we)begin sums[memory_addr]<=memory_value;cpu_sums[memory_addr]<=memory_value;end
 end
 always @(posedge clk)begin
  read_sum<=cpu_sums[cpu_addr];
  if(!resetn)begin
   clearing<=0;receiving<=0;armed<=0;done<=0;publish_wait<=0;published_id<=0;sample_count<=0;published_bank<=0;work_bank<=1;
   v0<=0;v1<=0;v2<=0;eof_pipe<=0;good_pipe<=0;x<=0;y<=0;
  end else if(!enable)begin
   clearing<=0;receiving<=0;armed<=0;done<=0;publish_wait<=0;v0<=0;v1<=0;v2<=0;eof_pipe<=0;good_pipe<=0;
  end else if(start)begin
   work_bank<=!published_bank;clearing<=1;clear_index<=0;receiving<=0;armed<=1;done<=0;publish_wait<=0;
   rx<={5'd0,roi_cfg[10:0]};ry<={6'd0,roi_cfg[25:16]};
   zoom<=view_cfg[2:1];rw<=WIDTH>>view_cfg[2:1];rh<=HEIGHT>>view_cfg[2:1];
   work_count<=((WIDTH/8)>>view_cfg[2:1])*((HEIGHT/6)>>view_cfg[2:1]);
   v0<=0;v1<=0;v2<=0;eof_pipe<=0;good_pipe<=0;x<=0;y<=0;
  end else begin
   v0<=0;v1<=v0;v2<=v1;
   eof_pipe<={eof_pipe[2:0],1'b0};good_pipe<={good_pipe[2:0],1'b0};
   if(clearing)begin
    if(clear_index==47)clearing<=0;else clear_index<=clear_index+1;
   end
   if(v0)begin
    addr1<=(work_bank?7'd48:7'd0)+{1'b0,tile_y(ny0),tile_x(nx0)};gray1<=gray_sum[15:8];
   end
   if(v1)begin
    addr2<=addr1;gray2<=gray1;
    old2<=(v2&&addr2==addr1)?updated:sums[addr1];
   end
   if(s_valid&&s_ready)begin
    if(s_data[24]&&!s_data[27]&&armed&&!receiving)begin
     receiving<=1;x<=1;y<=0;
     if(rx==0&&ry==0)begin
      v0<=1;nx0<=0;ny0<=0;
      rp0<=16'd77*s_data[23:16];gp0<=16'd150*s_data[15:8];bp0<=16'd29*s_data[7:0];
     end
    end else if(receiving)begin
     if(s_data[27])begin
      receiving<=0;armed<=0;eof_pipe[0]<=1;good_pipe[0]<=s_data[26]&&x==0&&y==HEIGHT;
     end else begin
      if(hit)begin
       v0<=1;nx0<=(x-rx)<<zoom;ny0<=(y-ry)<<zoom;
       rp0<=16'd77*s_data[23:16];gp0<=16'd150*s_data[15:8];bp0<=16'd29*s_data[7:0];
      end
      if(s_data[25])begin x<=0;y<=y+1;end else x<=x+1;
     end
    end
   end
   if(eof_pipe[3])begin
    if(good_pipe[3])publish_wait<=1;else done<=1;
   end
   if(publish_wait&&capture_ok)begin
    published_bank<=work_bank;sample_count<=work_count;published_id<=capture_id;done<=1;publish_wait<=0;
   end
  end
 end
endmodule
