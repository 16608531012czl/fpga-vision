`timescale 1ns/1ps
// EC11 A/B: 100us stable filter, legal Gray transitions, one count/full cycle.
// KEY: 25ms debounce; short release and one-second hold have separate counters.
module encoder_input #(
 parameter CLOCK_HZ=100000000, AB_US=100, KEY_MS=25, HOLD_MS=1000
)(input wire clk,resetn,a,b,key_n,
 output reg [31:0] position=0,short_count=0,long_count=0,invalid_count=0,
 output wire [2:0] status);
 localparam AB_CYCLES=(CLOCK_HZ/1000000*AB_US<1)?1:CLOCK_HZ/1000000*AB_US;
 localparam KEY_CYCLES=(CLOCK_HZ/1000*KEY_MS<1)?1:CLOCK_HZ/1000*KEY_MS;
 localparam HOLD_CYCLES=(CLOCK_HZ/1000*HOLD_MS<1)?1:CLOCK_HZ/1000*HOLD_MS;
 (* ASYNC_REG="TRUE" *) reg [2:0] sync1=3'b111,sync2=3'b111;
 reg [1:0] ab=2'b11,previous=2'b11,candidate_ab=2'b11;
 reg key=1,held=0;reg signed [3:0] quarter=0;
 reg [31:0] ab_timer=0,key_timer=0,hold_timer=0;
 wire [1:0] sampled={sync2[0],sync2[1]};
 assign status={~key,ab};
 reg signed [2:0] direction;
 always @* begin
  case({previous,ab})
   4'b1101,4'b0100,4'b0010,4'b1011:direction=1;
   4'b1110,4'b1000,4'b0001,4'b0111:direction=-1;
   default:direction=0;
  endcase
 end
 always @(posedge clk)begin
  if(!resetn)begin
   sync1<=7;sync2<=7;ab<=3;previous<=3;candidate_ab<=3;key<=1;held<=0;quarter<=0;
   ab_timer<=0;key_timer<=0;hold_timer<=0;
   position<=0;short_count<=0;long_count<=0;invalid_count<=0;
  end else begin
   sync1<={key_n,b,a};sync2<=sync1;
   if(sampled!=candidate_ab)begin candidate_ab<=sampled;ab_timer<=0;end
   else if(sampled==ab)ab_timer<=0;
   else if(ab_timer==AB_CYCLES-1)begin ab<=sampled;ab_timer<=0;end
   else ab_timer<=ab_timer+1;
   if(ab!=previous)begin
    previous<=ab;
    if(direction==0)begin quarter<=0;invalid_count<=invalid_count+1;end
    else if(ab==2'b11)begin
     if(quarter+direction>=4)position<=position+1;
     else if(quarter+direction<=-4)position<=position-1;
     quarter<=0;
    end else quarter<=quarter+direction;
   end
   if(sync2[2]==key)key_timer<=0;
   else if(key_timer==KEY_CYCLES-1)begin
    key<=sync2[2];key_timer<=0;hold_timer<=0;
    if(sync2[2])begin if(!held)short_count<=short_count+1;held<=0;end
    else held<=0;
   end else key_timer<=key_timer+1;
   if(!key&&!held)begin
    if(hold_timer==HOLD_CYCLES-1)begin long_count<=long_count+1;held<=1;end
    else hold_timer<=hold_timer+1;
   end
  end
 end
endmodule
