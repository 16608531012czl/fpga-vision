`timescale 1ns/1ps
module tb_encoder;
 reg clk=0;always #5 clk=~clk;
 reg resetn=0,a=1,b=1,key_n=1;
 wire [31:0] position,short_count,long_count,invalid_count;wire [2:0] status;
 encoder_input #(.CLOCK_HZ(1000000),.AB_US(3),.KEY_MS(1),.HOLD_MS(3)) dut(.*);
 task step(input [1:0] value);begin {a,b}=value;repeat(9)@(negedge clk);end endtask
 integer i;
 initial begin
  repeat(5)@(negedge clk);resetn=1;repeat(8)@(negedge clk);
  step(1);step(0);step(2);step(3);
  if(position!=1)$fatal(1,"Forward decode %h",position);
  step(2);step(0);step(1);step(3);
  if(position!=0)$fatal(1,"Reverse decode");
  // Contact bounce shorter than the stable filter must not count.
  repeat(4)begin a=0;@(negedge clk);a=1;@(negedge clk);end
  repeat(12)@(negedge clk);if(position!=0)$fatal(1,"Bounce counted");
  // Several different candidate states may not share one debounce interval.
  repeat(6)begin
   {a,b}=2'b01;repeat(2)@(negedge clk);
   {a,b}=2'b00;repeat(2)@(negedge clk);
   {a,b}=2'b10;repeat(2)@(negedge clk);
  end
  step(3);if(position!=0||invalid_count!=0)$fatal(1,"Unstable candidate accepted");
  step(0);step(3);if(invalid_count!=2||position!=0)$fatal(1,"Illegal transition accepted");
  key_n=0;repeat(1200)@(negedge clk);key_n=1;repeat(1200)@(negedge clk);
  if(short_count!=1||long_count!=0)$fatal(1,"Short press event");
  key_n=0;repeat(7000)@(negedge clk);key_n=1;repeat(1200)@(negedge clk);
  if(short_count!=1||long_count!=1)$fatal(1,"Long press repeated or released as short");
  // Gray-step contact bounce must cancel, not become a whole detent.
  step(1);step(3);step(1);step(0);step(2);step(3);
  if(position!=1)$fatal(1,"Quadrature contact bounce");
  $display("PASS encoder quadrature debounce reversal illegal short long");$finish;
 end
 initial begin #1000000;$fatal(1,"Encoder timeout");end
endmodule
