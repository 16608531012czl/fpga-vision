`timescale 1ns/1ps
module tb_reading;
 parameter WIDTH=32,HEIGHT=24,FRAMES=10;
 localparam N=WIDTH*HEIGHT*FRAMES;
 reg clk=0;always #5 clk=~clk;
 reg resetn=0;reg [23:0] din=0;reg vin=0,uin=0,lin=0,ready=0;
 wire rin,vout,uout,lout;wire [23:0] dout;
 reg [31:0] cfg=0;reg we=0,commit=0;reg [7:0] index=0,ld=0;
 wire pending,bank;wire [31:0] count;
 reading_enhance #(.WIDTH(WIDTH)) dut(clk,resetn,din,vin,rin,uin,lin,dout,vout,ready,uout,lout,cfg,we,index,ld,commit,pending,bank,count);
 reg [23:0] input_mem[0:N-1],expected_mem[0:N-1];reg [31:0] configs[0:FRAMES-1];reg [7:0] lut[0:255];
 integer i,j,f,got=0,cycles=0;reg [31:0] rng=32'h712f1a45;
 reg stalled=0;reg [25:0] held;
 always @(negedge clk)begin rng<={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};ready=resetn&&(rng[3:0]!=0);end
 always @(posedge clk)if(resetn)begin
  cycles=cycles+1;
  if(stalled&&{uout,lout,dout}!==held)$fatal(1,"Output changed under backpressure");
  stalled=vout&&!ready;held={uout,lout,dout};
  if(vout&&ready)begin
   if(got>=N)$fatal(1,"Extra output pixel");
   if(dout!==expected_mem[got])$fatal(1,"Pixel %0d got=%h expected=%h",got,dout,expected_mem[got]);
   if(uout!==(got%(WIDTH*HEIGHT)==0)||lout!==(got%WIDTH==WIDTH-1))$fatal(1,"Sideband mismatch %0d",got);
   got=got+1;
  end
 end
 initial begin
  $readmemh("input.mem",input_mem);$readmemh("expected.mem",expected_mem);$readmemh("config.mem",configs);$readmemh("gamma.mem",lut);
  repeat(6)@(negedge clk);resetn=1;
  for(i=0;i<256;i=i+1)begin @(negedge clk);we=1;index=i;ld=lut[i];end
  @(negedge clk);we=0;commit=1;@(negedge clk);commit=0;
  for(f=0;f<FRAMES;f=f+1)begin
   cfg=configs[f];
   for(j=0;j<WIDTH*HEIGHT;j=j+1)begin
    @(negedge clk);din=input_mem[f*WIDTH*HEIGHT+j];vin=1;uin=(j==0);lin=(j%WIDTH==WIDTH-1);
    @(posedge clk);while(!rin)@(posedge clk);
    @(negedge clk);vin=0;uin=0;lin=0;
    if(j==5)cfg=32'hdeadbeef; // must not take effect before next SOF
    if(j%17==0)repeat(2)@(negedge clk);
   end
  end
  wait(got==N);repeat(8)@(posedge clk);
  if(count!=FRAMES||pending||!bank)$fatal(1,"Configuration/gamma handshake mismatch");
  $display("PASS reading pixels=%0d frames=%0d cycles=%0d",got,count,cycles);$finish;
 end
 initial begin #400000000;$fatal(1,"Reading test timeout got=%0d",got);end
endmodule
