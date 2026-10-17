`timescale 1ns/1ps
module tb_registers;
 reg aclk=0;always #5 aclk=~aclk;
 reg aresetn=0;
 reg [7:0] s_axi_awaddr=0,s_axi_araddr=0;reg [2:0] s_axi_awprot=0,s_axi_arprot=0;
 reg s_axi_awvalid=0,s_axi_wvalid=0,s_axi_bready=0,s_axi_arvalid=0,s_axi_rready=0;
 wire s_axi_awready,s_axi_wready,s_axi_bvalid,s_axi_arready,s_axi_rvalid;
 reg [31:0] s_axi_wdata=0;reg [3:0] s_axi_wstrb=0;wire [31:0] s_axi_rdata;wire [1:0] s_axi_bresp,s_axi_rresp;
 wire capture_enable,capture_start,lut_we,lut_commit;wire [31:0] destination,cfg_word;wire [5:0] gpio_out;wire [7:0] lut_index,lut_data;
 reg [3:0] gpio_in=4'ha;reg [31:0] cap_status=3,frame_id=42,dma_errors=2,camera_frames=72,overflows=3,malformed=4,display_frames=100;
 reg [8:0] buttons=9'h155;reg lut_pending=0,lut_bank=0;
 assist_regs dut(.*);
 integer lut_writes=0,commits=0,starts=0;
 always @(posedge aclk)begin if(lut_we)lut_writes=lut_writes+1;if(lut_commit)commits=commits+1;if(capture_start)starts=starts+1;end
 task write_reg(input [7:0] addr,input [31:0] data,input [3:0] strb,input integer order,input [1:0] resp);
 reg [1:0] hold;begin
  fork
   begin
    if(order==1)repeat(6)@(negedge aclk);
    @(negedge aclk);s_axi_awaddr=addr;s_axi_awvalid=1;@(posedge aclk);while(!s_axi_awready)@(posedge aclk);
    @(negedge aclk);s_axi_awvalid=0;
   end
   begin
    if(order==0)repeat(5)@(negedge aclk);
    @(negedge aclk);s_axi_wdata=data;s_axi_wstrb=strb;s_axi_wvalid=1;@(posedge aclk);while(!s_axi_wready)@(posedge aclk);
    @(negedge aclk);s_axi_wvalid=0;
   end
  join
  wait(s_axi_bvalid);hold=s_axi_bresp;
  repeat(4)begin @(negedge aclk);if(!s_axi_bvalid||s_axi_bresp!==hold)$fatal(1,"B response unstable");end
  if(hold!==resp)$fatal(1,"BRESP mismatch");s_axi_bready=1;@(negedge aclk);s_axi_bready=0;
 end endtask
 task read_reg(input [7:0] addr,input [31:0] expected,input [1:0] resp);
 reg [31:0] hold;begin
  @(negedge aclk);s_axi_araddr=addr;s_axi_arvalid=1;@(posedge aclk);while(!s_axi_arready)@(posedge aclk);
  @(negedge aclk);s_axi_arvalid=0;wait(s_axi_rvalid);hold=s_axi_rdata;
  repeat(4)begin @(negedge aclk);if(!s_axi_rvalid||s_axi_rdata!==hold)$fatal(1,"R response unstable");end
  if(hold!==expected||s_axi_rresp!==resp)$fatal(1,"Read mismatch addr=%h got=%h expected=%h",addr,hold,expected);
  s_axi_rready=1;@(negedge aclk);s_axi_rready=0;
 end endtask
 initial begin
  repeat(5)@(negedge aclk);aresetn=1;
  read_reg(0,32'h56410300,0);read_reg('h3c,'h2f,0);
  write_reg('h10,'h12345680,15,0,0);read_reg('h10,'h12345680,0);
  write_reg('h10,'habcdef00,4'b0010,1,0);read_reg('h10,'h1234ef80,0);
  write_reg(4,1,1,1,0);read_reg(4,1,0);
  write_reg('h14,1,1,0,0);if(starts!=1)$fatal(1,"Start pulse not single cycle");
  write_reg('h30,'h000008d9,15,1,0);read_reg('h30,'h000008d9,0);
  read_reg('h18,3,0);read_reg('h1c,42,0);read_reg('h38,'h155,0);read_reg('h40,10,0);
  write_reg('h44,'h5a80,15,0,0);if(lut_writes!=1||lut_index!=128||lut_data!=90)$fatal(1,"Gamma write failed");
  write_reg('h48,1,1,1,0);if(commits!=1)$fatal(1,"Gamma commit failed");
  lut_pending=1;write_reg('h44,'h0000,15,0,0);if(lut_writes!=1)$fatal(1,"Pending LUT was overwritten");
  read_reg('hfc,0,2);write_reg('hfc,0,15,1,2);
  $display("PASS registers AW/W-independent WSTRB response-backpressure GPIO gamma errors");$finish;
 end
 initial begin #200000;$fatal(1,"AXI register timeout");end
endmodule
