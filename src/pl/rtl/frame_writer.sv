`timescale 1ns/1ps
// Single-shot DMA, 16 x 32-bit INCR bursts. CPU owns the completed buffer until
// the next explicit start. An incomplete/error frame is NEVER marked done.
// WIDTH*HEIGHT must be a multiple of 16; destination must be 64-byte aligned.
module frame_writer #(parameter WIDTH=1280,HEIGHT=720)(
 input wire aclk,aresetn,input wire capture_enable,start,input wire [31:0] destination,
 input wire [27:0] s_data,input wire s_valid,output wire s_ready,
 output reg busy=0,done=0,error=0,output reg [31:0] frame_id=0,error_count=0,
 output reg [31:0] m_axi_awaddr,output wire [7:0] m_axi_awlen,
 output wire [2:0] m_axi_awsize,output wire [1:0] m_axi_awburst,
 output wire [3:0] m_axi_awcache,output wire [2:0] m_axi_awprot,
 output wire m_axi_awlock,output wire m_axi_awvalid,input wire m_axi_awready,
 output wire [31:0] m_axi_wdata,output wire [3:0] m_axi_wstrb,
 output wire m_axi_wlast,m_axi_wvalid,input wire m_axi_wready,
 input wire [1:0] m_axi_bresp,input wire m_axi_bvalid,output wire m_axi_bready);
 localparam IDLE=0,WAIT_SOF=1,FILL=2,ADDRESS=3,DATA=4,RESP=5,WAIT_END=6;
 reg [2:0] state=IDLE;
 reg [23:0] pixels=0;
 reg [15:0] column=0; // Avoid a constant-division/modulo datapath in marker checking.
 reg [3:0] fill=0,send_index=0;
 reg [31:0] burst_data[0:15];
 reg frame_bad=0,final_burst=0,abort_pending=0;
 assign s_ready=capture_enable&&(state==IDLE||state==WAIT_SOF||state==FILL||state==WAIT_END);
 assign m_axi_awlen=15;assign m_axi_awsize=2;assign m_axi_awburst=1;
 assign m_axi_awcache=4'b0011;assign m_axi_awprot=0;assign m_axi_awlock=0;
 assign m_axi_awvalid=(state==ADDRESS);
 assign m_axi_wdata=burst_data[send_index];assign m_axi_wstrb=15;
 assign m_axi_wlast=(send_index==15);assign m_axi_wvalid=(state==DATA);
 assign m_axi_bready=(state==RESP);
 wire marker_bad=s_data[27]||s_data[26]||(s_data[25]!=(column==WIDTH-1)) ||
                 (s_data[24]!=(pixels==0));
 always @(posedge aclk) begin
  if(!aresetn) begin state<=IDLE;busy<=0;done<=0;error<=0;pixels<=0;column<=0;fill<=0;send_index<=0;frame_bad<=0;final_burst<=0;abort_pending<=0;m_axi_awaddr<=0;frame_id<=0;error_count<=0;end
  else begin
   // A software stop must NOT reset an AXI master independently of the
   // interconnect. Keep AW/W stable and finish the whole accepted burst,
   // including its B response, before dropping busy. Latch even a brief stop.
   if(!capture_enable&&(state==ADDRESS||state==DATA||state==RESP))abort_pending<=1;
   if(!capture_enable&&(state==IDLE||state==WAIT_SOF||state==FILL||state==WAIT_END))begin
    state<=IDLE;busy<=0;done<=0;error<=0;pixels<=0;column<=0;fill<=0;send_index<=0;
    frame_bad<=0;final_burst<=0;abort_pending<=0;
   end else case(state)
    IDLE: if(start) begin
     done<=0;error<=0;pixels<=0;column<=0;fill<=0;frame_bad<=0;final_burst<=0;abort_pending<=0;
     if(destination[5:0]!=0) begin error<=1;error_count<=error_count+1;end
     else begin busy<=1;m_axi_awaddr<=destination;state<=WAIT_SOF;end
    end
    WAIT_SOF: if(s_valid&&s_data[24]) begin
     burst_data[0]<={8'b0,s_data[23:0]};pixels<=1;column<=1;fill<=1;
     frame_bad<=s_data[25]||s_data[26];state<=FILL;
    end
    FILL: if(s_valid) begin
     // Unexpected SOF/EOF aborts before any unfilled burst is written.
     if(marker_bad) begin state<=IDLE;busy<=0;error<=1;error_count<=error_count+1;end
     else begin
      burst_data[fill]<={8'b0,s_data[23:0]};pixels<=pixels+1;column<=(column==WIDTH-1)?0:column+1;fill<=fill+1;
      if(fill==15) begin state<=ADDRESS;final_burst<=(pixels==WIDTH*HEIGHT-1);end
     end
    end
    ADDRESS: if(m_axi_awready) begin state<=DATA;send_index<=0;end
    DATA: if(m_axi_wready) begin send_index<=send_index+1;if(send_index==15)state<=RESP;end
    RESP: if(m_axi_bvalid) begin
     if(abort_pending||!capture_enable||m_axi_bresp!=0||frame_bad) begin error<=1;busy<=0;done<=0;state<=IDLE;error_count<=error_count+1;end
     else if(final_burst) state<=WAIT_END;
     else begin m_axi_awaddr<=m_axi_awaddr+64;fill<=0;state<=FILL;end
    end
    WAIT_END:if(s_valid) begin
     busy<=0;state<=IDLE;
     if(s_data[27]&&s_data[26]) begin done<=1;frame_id<=frame_id+1;end
     else begin error<=1;error_count<=error_count+1;end
    end
    default:state<=IDLE;
   endcase
  end
 end
endmodule
