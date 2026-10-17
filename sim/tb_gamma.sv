`timescale 1ns/1ps
module tb_gamma;
 reg clk=0;always #5 clk=~clk;
 reg resetn=0;reg [23:0] din=0;reg vin=0,uin=0,lin=0,ready=0;
 wire rin,vout,uout,lout;wire [23:0] dout;reg [31:0] cfg=1;
 reg we=0,commit=0;reg [7:0] index=0,ld=0;wire pending,bank;wire [31:0] count;
 reading_enhance #(.WIDTH(32)) dut(clk,resetn,din,vin,rin,uin,lin,dout,vout,ready,uout,lout,cfg,we,index,ld,commit,pending,bank,count);
 integer cycle=0,got=0,j,f,k,guard_before;reg [7:0] expected,pixel;reg block_output=0;
 always @(negedge clk)begin cycle=cycle+1;ready=resetn&&!block_output&&(cycle%9>2);end
 always @(posedge clk)if(vout&&ready)begin
  expected=(got<768)?(got%768)%256:255-(got%768)%256;
  if(dout!=={3{expected}})$fatal(1,"Gamma tearing/overwrite at %0d got=%h expected=%h",got,dout,{3{expected}});
  got=got+1;
 end
 initial begin
  repeat(5)@(negedge clk);resetn=1;
  for(f=0;f<3;f=f+1)for(j=0;j<768;j=j+1)begin
   @(negedge clk);pixel=j%256;din={3{pixel}};vin=1;uin=(j==0);lin=(j%32==31);
   @(posedge clk);while(!rin)@(posedge clk);
   @(negedge clk);vin=0;uin=0;lin=0;
  end
  wait(got==2304);if(!bank||pending||count!=3)$fatal(1,"Gamma final state");
  $display("PASS gamma inactive-bank-write SOF-atomic-switch pending-write-rejection");$finish;
 end
 initial begin
  wait(resetn);wait(got>=10);
  for(k=0;k<256;k=k+1)begin @(negedge clk);we=1;index=k;ld=255-k;end
  @(negedge clk);we=0;commit=1;@(negedge clk);commit=0;
  repeat(3)@(negedge clk);if(!pending)$fatal(1,"Commit applied midframe");
  we=1;index=7;ld=0;@(negedge clk);we=0;
 end
 initial begin
  // Immediately after SOF switches banks, old-frame pixels still own the old
  // table until their gamma lookups drain. Backpressure must freeze this guard.
  wait(bank);@(negedge clk);block_output=1;
  repeat(3)@(negedge clk);guard_before=dut.bank_guard;
  if(!pending||guard_before==0)$fatal(1,"Old gamma bank released before pipeline drained");
  we=1;index=255;ld=0;
  repeat(8)@(negedge clk);
  if(dut.bank_guard!=guard_before)$fatal(1,"Gamma guard advanced under output stall");
  we=0;block_output=0;
 end
 initial begin #300000;$fatal(1,"Gamma timeout");end
endmodule
