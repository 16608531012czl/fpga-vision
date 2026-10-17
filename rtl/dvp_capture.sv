`timescale 1ns/1ps
// RGB565, MSB byte first, VSYNC active high blanking, HREF active high.
// FIFO word: [27] frame-end token, [26] token says frame is valid,
// [25] pixel EOL, [24] pixel SOF, [23:0] BGR888. End is certified only
// at the NEXT VSYNC, so extra rows/bytes cannot publish a corrupt last frame.
// The sensor cannot be stalled. Overflow/malformed input drops the remainder
// of the frame; the DMA never publishes a frame without all expected markers.
module dvp_capture #(parameter WIDTH=1280,HEIGHT=720,FIFO_ADDR=12)(
 input wire pclk,cam_resetn,input wire [7:0] cam_data,input wire vsync,href,
 input wire aclk,aresetn,output wire [27:0] stream_data,output wire stream_valid,
 input wire stream_ready,output reg [31:0] camera_frames=0,
 output reg [31:0] overflow_frames=0,malformed_frames=0);
 // Sensor 0x4740[5]=1 updates data at falling PCLK. Sample all pins
 // together at rising PCLK into IOB registers, then process one cycle later.
 (* IOB="TRUE" *) reg [7:0] data_q=0;
 (* IOB="TRUE" *) reg vsync_q=0,href_q=0;
 always @(posedge pclk)begin data_q<=cam_data;vsync_q<=vsync;href_q<=href;end
 (* ASYNC_REG="TRUE" *) reg [1:0] crst=0;
 always @(posedge pclk or negedge cam_resetn)
  if(!cam_resetn) crst<=0; else crst<={crst[0],1'b1};
 reg vs_d=0,href_d=0,half_byte=0,dropping=1;
 reg frame_open=0;
 reg [7:0] hi=0;
 reg [15:0] x=0,y=0;
 reg [31:0] frames_p=0,overflow_p=0,malformed_p=0;
 reg [31:0] fg=0,og=0,mg=0;
 // Register Gray codes before crossing; combinational binary-to-Gray can glitch.
 always @(posedge pclk)begin
  if(!crst[1])begin fg<=0;og<=0;mg<=0;end
  else begin fg<=(frames_p>>1)^frames_p;og<=(overflow_p>>1)^overflow_p;mg<=(malformed_p>>1)^malformed_p;end
 end
 (* ASYNC_REG="TRUE" *) reg [31:0] f1=0,f2=0,o1=0,o2=0,m1=0,m2=0;
 function [31:0] ungray(input [31:0] g);integer i;begin ungray[31]=g[31];for(i=30;i>=0;i=i-1)ungray[i]=ungray[i+1]^g[i];end endfunction
 always @(posedge aclk) begin
  if(!aresetn) begin f1<=0;f2<=0;o1<=0;o2<=0;m1<=0;m2<=0;camera_frames<=0;overflow_frames<=0;malformed_frames<=0;end
  else begin f1<=fg;f2<=f1;o1<=og;o2<=o1;m1<=mg;m2<=m1;camera_frames<=ungray(f2);overflow_frames<=ungray(o2);malformed_frames<=ungray(m2);end
 end
 wire full,empty;
 wire emit=crst[1] && !vsync_q && href_q && half_byte && !dropping && x<WIDTH && y<HEIGHT;
 wire end_emit=crst[1] && vsync_q && !vs_d && frame_open;
 wire good_end=!dropping && y==HEIGHT && x==0 && !half_byte;
 wire [15:0] rgb={hi,data_q};
 wire [23:0] bgr={{rgb[15:11],rgb[15:13]},{rgb[10:5],rgb[10:9]},{rgb[4:0],rgb[4:2]}};
 wire [27:0] packet=end_emit?{1'b1,good_end,26'd0}:{2'b0,(x==WIDTH-1),(x==0&&y==0),bgr};
 async_fifo #(.WIDTH(28),.ADDR(FIFO_ADDR)) fifo(
  .wr_clk(pclk),.wr_resetn(crst[1]),.wr_data(packet),.wr_en((emit||end_emit)&&!full),.full(full),
  .rd_clk(aclk),.rd_resetn(aresetn),.rd_data(stream_data),.rd_en(stream_valid&&stream_ready),.empty(empty));
 assign stream_valid=!empty;
 always @(posedge pclk) begin
  if(!crst[1]) begin vs_d<=0;href_d<=0;half_byte<=0;dropping<=1;frame_open<=0;x<=0;y<=0;hi<=0;frames_p<=0;overflow_p<=0;malformed_p<=0;end
  else begin
   vs_d<=vsync_q;href_d<=href_q;
   if(vsync_q) begin
    half_byte<=0;x<=0;y<=0;dropping<=0;
    if(!vs_d) begin
     frames_p<=frames_p+1;frame_open<=1;
     if(frame_open&&!dropping&&!good_end)malformed_p<=malformed_p+1;
     if(frame_open&&full&&!dropping)overflow_p<=overflow_p+1;
    end
   end else if(href_q) begin
    if(!half_byte) begin hi<=data_q;half_byte<=1;end
    else begin
     half_byte<=0;x<=x+1;
     if(!dropping) begin
      if(x>=WIDTH||y>=HEIGHT) begin dropping<=1;malformed_p<=malformed_p+1;end
      else if(full) begin dropping<=1;overflow_p<=overflow_p+1;end
     end
    end
   end else if(href_d) begin
    half_byte<=0;x<=0;y<=y+1;
    if(!dropping&&(half_byte||x!=WIDTH)) begin dropping<=1;malformed_p<=malformed_p+1;end
   end
  end
 end
endmodule
