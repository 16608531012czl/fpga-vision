// PG020 Appendix C, frame-store size four: two Gray codes per frame.
module display_slot_decode(input wire [5:0] gray,output reg [5:0] slot);
 always @*case(gray)
  0,6:slot=0;1,7:slot=1;3,5:slot=2;2,4:slot=3;default:slot=63;
 endcase
endmodule
