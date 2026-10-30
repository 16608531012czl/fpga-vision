`timescale 1ns/1ps
module tb_capture;
 parameter WIDTH=32,HEIGHT=20;
 reg clk=0,pclk=0;always #5 clk=~clk;always #5.952 pclk=~pclk;
 reg resetn=0,start=0,vs=0,href=0;reg [7:0] data=0;
 wire [27:0] packet;wire valid,ready;wire [31:0] frames,overflows,malformed;
 wire busy,done,error;wire [31:0] frame_id,errors;
 wire [31:0] awaddr,wdata;wire [7:0] awlen;wire [2:0] awsize,awprot;wire [1:0] awburst;wire [3:0] awcache,wstrb;
 wire awlock,awvalid,wlast,wvalid,bready;reg awready=0,wready=0,bvalid=0;reg [1:0] bresp=0;
 reg grant=1,inject_error=0;reg [31:0] rng=32'h8712ac43;
 reg [27:0] diagnostic=0;
 always @(posedge clk)if(valid&&ready&&packet[27])diagnostic<=packet;
 reg [31:0] memory[0:WIDTH*HEIGHT-1];reg [31:0] address=0;integer beat=0,writes=0;
 reg have_aw=0;reg held_w=0,held_aw=0;reg [36:0] saved_w;reg [31:0] saved_aw;
 dvp_capture #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.FIFO_ADDR(6)) capture(pclk,resetn,data,vs,href,clk,resetn,packet,valid,ready,frames,overflows,malformed);
 frame_writer #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) writer(clk,resetn,1'b1,start,32'h1000,packet,valid,ready,busy,done,error,frame_id,errors,
 awaddr,awlen,awsize,awburst,awcache,awprot,awlock,awvalid,awready,wdata,wstrb,wlast,wvalid,wready,bresp,bvalid,bready);
 always @(negedge clk)begin
  rng<={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
  awready=grant&&!have_aw&&!bvalid&&rng[0];wready=grant&&have_aw&&(rng[2:0]!=0);
 end
 always @(posedge clk)begin
  if(!resetn)begin have_aw<=0;bvalid<=0;beat<=0;writes<=0;held_w<=0;held_aw<=0;end
  else begin
   if(held_w&&{wlast,wstrb,wdata}!==saved_w)$fatal(1,"W changed while stalled");
   if(held_aw&&awaddr!==saved_aw)$fatal(1,"AW changed while stalled");
   held_w<=wvalid&&!wready;saved_w<={wlast,wstrb,wdata};held_aw<=awvalid&&!awready;saved_aw<=awaddr;
   if(awvalid&&awready)begin
    if(awlen!=15||awsize!=2||awburst!=1||awaddr[5:0]!=0||awaddr[11:0]>4032)$fatal(1,"Bad AXI burst");
    address<=awaddr;have_aw<=1;beat<=0;
   end
   if(wvalid&&wready)begin
    if(wlast!==(beat==15)||wstrb!=15)$fatal(1,"Bad WLAST/WSTRB");
    if((address-4096)/4+beat>=WIDTH*HEIGHT)$fatal(1,"DMA out of buffer bounds");
    memory[(address-4096)/4+beat]<=wdata;beat<=beat+1;writes<=writes+1;
    if(wlast)begin have_aw<=0;bvalid<=1;bresp<=inject_error?2:0;end
   end
   if(bvalid&&bready)bvalid<=0;
  end
 end
 function [15:0] pixel(input integer x,input integer y);begin pixel=((x*3+y)&31)<<11|((x+y*3)&63)<<5|((x*7+y*5)&31);end endfunction
 function [23:0] expanded(input [15:0] v);begin expanded={{v[15:11],v[15:13]},{v[10:5],v[10:9]},{v[4:0],v[4:2]}};end endfunction
 task arm;begin @(negedge clk);start=1;@(negedge clk);start=0;end endtask
 task sensor_frame(input integer extra);
 integer xx,yy;reg [15:0] p;begin
  @(negedge pclk);vs=1;href=0;repeat(5)@(negedge pclk);vs=0;repeat(3)@(negedge pclk);
  for(yy=0;yy<HEIGHT;yy=yy+1)begin
   for(xx=0;xx<WIDTH+((extra&&yy==HEIGHT-1)?1:0);xx=xx+1)begin
    p=pixel(xx,yy);href=1;data=p[15:8];@(negedge pclk);data=p[7:0];@(negedge pclk);
   end
   href=0;repeat(10)@(negedge pclk);
  end
  vs=1;repeat(6)@(negedge pclk);vs=0;
 end endtask
 task await_result;integer limit;begin
  limit=0;while(busy&&limit<100000)begin @(negedge clk);limit=limit+1;end
  if(busy)$fatal(1,"DMA completion timeout");
 end endtask
 integer x,y;
 initial begin
  repeat(10)@(negedge clk);resetn=1;repeat(6)@(negedge pclk);
  arm();sensor_frame(0);await_result();
  if(!done||error||frame_id!=1||writes!=WIDTH*HEIGHT)$fatal(1,"Valid frame not committed");
  if(diagnostic[25:23]!=0||diagnostic[22:12]!=HEIGHT||diagnostic[11:0]!=WIDTH)$fatal(1,"Wrong valid geometry diagnostic");
  for(y=0;y<HEIGHT;y=y+1)for(x=0;x<WIDTH;x=x+1)
   if(memory[y*WIDTH+x]!=={8'd0,expanded(pixel(x,y))})$fatal(1,"Pixel/color/order mismatch x=%0d y=%0d",x,y);
  $writememh("capture_actual.mem",memory);
  if(WIDTH<1280)begin
   arm();sensor_frame(1);await_result();
   if(done||!error||frame_id!=1)$fatal(1,"Malformed final line was published");
   repeat(20)@(negedge clk);
   if(diagnostic[25:23]!=3||diagnostic[22:12]!=HEIGHT-1||diagnostic[11:0]!=WIDTH)$fatal(1,"Missing first malformed line diagnostic");
   inject_error=1;arm();sensor_frame(0);await_result();
   if(done||!error||frame_id!=1)$fatal(1,"AXI error was ignored");inject_error=0;
   grant=0;arm();sensor_frame(0);grant=1;sensor_frame(0);await_result();
   if(done||!error||overflows==0)$fatal(1,"Overflow frame was published");
   arm();sensor_frame(0);await_result();if(!done||error||frame_id!=2)$fatal(1,"No recovery after bad frame");
  end
  $display("PASS capture pixels=%0d frame_id=%0d dma_errors=%0d overflow=%0d malformed=%0d",WIDTH*HEIGHT,frame_id,errors,overflows,malformed);$finish;
 end
 initial begin #150000000;$fatal(1,"Capture watchdog");end
endmodule
