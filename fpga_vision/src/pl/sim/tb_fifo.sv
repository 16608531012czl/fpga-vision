`timescale 1ns/1ps
module tb_fifo;
 reg wc=0,rc=0,wr_clock_running=1;always #7 if(wr_clock_running)wc=~wc;always #5 rc=~rc;
 reg wn=0,rn=0,we=0,re=0;reg [7:0] data=0;wire [7:0] q;wire full,empty;
 async_fifo #(.WIDTH(8),.ADDR(3)) dut(wc,wn,data,we,full,rc,rn,q,re,empty);
 task put(input [7:0] value);begin
  @(negedge wc);while(full)@(negedge wc);we=1;data=value;
  @(negedge wc);we=0;
 end endtask
 integer i,got=0;
 always @(posedge rc)if(rn&&re&&!empty)begin
  if(q!==8'h50+got)$fatal(1,"Stale data after stopped-clock reset got=%h",q);
  got=got+1;
 end
 initial begin
  repeat(5)@(negedge rc);wn=1;rn=1;
  for(i=0;i<6;i=i+1)put(i);
  wait(!empty);@(negedge wc);wr_clock_running=0;
  #2;wn=0;rn=0;#2;
  if(!empty||full)$fatal(1,"Async reset failed with camera clock stopped");
  repeat(5)@(negedge rc);wn=1;rn=1;
  repeat(6)@(negedge rc);if(!empty)$fatal(1,"Stale output without fresh writes");
  wr_clock_running=1;re=1;
  for(i=0;i<8;i=i+1)put(8'h50+i);
  wait(got==8);repeat(8)@(negedge rc);if(!empty)$fatal(1,"Extra FIFO data");
  $display("PASS fifo stopped-camera-clock reset no-stale-data asynchronous-order");$finish;
 end
 initial begin #100000;$fatal(1,"FIFO test timeout");end
endmodule
