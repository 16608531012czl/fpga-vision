`timescale 1ns/1ps
// Gray-pointer CDC FIFO. Assert reset in BOTH domains together; deassert locally.
module async_fifo #(parameter WIDTH=28, parameter ADDR=12)(
 input wire wr_clk,wr_resetn,input wire [WIDTH-1:0] wr_data,input wire wr_en,
 output wire full,input wire rd_clk,rd_resetn,output wire [WIDTH-1:0] rd_data,
 input wire rd_en,output wire empty);
 (* ram_style="block" *) reg [WIDTH-1:0] mem[0:(1<<ADDR)-1];
 reg [ADDR:0] wb=0,wg=0,rb=0,rg=0;
 (* ASYNC_REG="TRUE" *) reg [ADDR:0] rg1=0,rg2=0,wg1=0,wg2=0;
 wire [ADDR:0] wn=wb+1'b1;
 // Full compares the CURRENT write pointer: all 2**ADDR entries are usable.
 assign full=(wg=={~rg2[ADDR:ADDR-1],rg2[ADDR-2:0]});
 // Registered read port with one FWFT output register, separate from FIFO RAM.
 reg [WIDTH-1:0] out_data;
 reg out_valid=0;
 assign empty=!out_valid;
 wire mem_empty=(rg==wg2);
 wire fetch=(!out_valid || rd_en) && !mem_empty;
 assign rd_data=out_data;
 // External empty is based on the prefetched output, not the RAM pointer.
 // See fifo_valid below: a prefetched word must remain visible through stalls.
 always @(posedge wr_clk)begin
  if(wr_resetn&&wr_en&&!full)mem[wb[ADDR-1:0]]<=wr_data;
 end
 always @(posedge wr_clk or negedge wr_resetn) begin
  if(!wr_resetn) begin wb<=0;wg<=0;rg1<=0;rg2<=0;end
  else begin
   rg1<=rg;rg2<=rg1;
   if(wr_en&&!full) begin wb<=wn;wg<=(wn>>1)^wn;end
  end
 end
 always @(posedge rd_clk)begin
  if(rd_resetn&&fetch)out_data<=mem[rb[ADDR-1:0]];
 end
 always @(posedge rd_clk or negedge rd_resetn) begin
  if(!rd_resetn) begin rb<=0;rg<=0;wg1<=0;wg2<=0;out_valid<=0;end
  else begin
   wg1<=wg;wg2<=wg1;
   if(fetch) begin rb<=rb+1'b1;rg<=((rb+1'b1)>>1)^(rb+1'b1);out_valid<=1;end
   else if(rd_en) out_valid<=0;
  end
 end
endmodule
