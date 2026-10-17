`timescale 1ns/1ps
// Independent capture/control/display core, no MicroBlaze IOPs.
module visual_aid_core #(parameter WIDTH=1280,HEIGHT=720)(
 (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 aclk CLK", X_INTERFACE_PARAMETER="ASSOCIATED_BUSIF s_axi:m_axi:s_axis:m_axis, ASSOCIATED_RESET aresetn, FREQ_HZ 100000000" *) input wire aclk,
 (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 aresetn RST", X_INTERFACE_PARAMETER="POLARITY ACTIVE_LOW" *) input wire aresetn,
 input wire cam_pclk,cam_vsync,cam_href,
 input wire [7:0] cam_data,
 input wire [3:0] buttons,
 input wire [4:0] joy_n,
 inout wire cam_scl,cam_sda,sensor_scl,sensor_sda,
 output wire cam_resetn,cam_pwdn,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi AWADDR", X_INTERFACE_PARAMETER="PROTOCOL AXI4LITE, DATA_WIDTH 32, ADDR_WIDTH 8" *) input wire [7:0] s_axi_awaddr,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi AWPROT" *) input wire [2:0] s_axi_awprot,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi AWVALID" *) input wire s_axi_awvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi AWREADY" *) output wire s_axi_awready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi WDATA" *) input wire [31:0] s_axi_wdata,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi WSTRB" *) input wire [3:0] s_axi_wstrb,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi WVALID" *) input wire s_axi_wvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi WREADY" *) output wire s_axi_wready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi BRESP" *) output wire [1:0] s_axi_bresp,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi BVALID" *) output wire s_axi_bvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi BREADY" *) input wire s_axi_bready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi ARADDR" *) input wire [7:0] s_axi_araddr,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi ARPROT" *) input wire [2:0] s_axi_arprot,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi ARVALID" *) input wire s_axi_arvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi ARREADY" *) output wire s_axi_arready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi RDATA" *) output wire [31:0] s_axi_rdata,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi RRESP" *) output wire [1:0] s_axi_rresp,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi RVALID" *) output wire s_axi_rvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 s_axi RREADY" *) input wire s_axi_rready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi AWADDR", X_INTERFACE_PARAMETER="PROTOCOL AXI4, DATA_WIDTH 32, ADDR_WIDTH 32" *) output wire [31:0] m_axi_awaddr,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi AWLEN" *) output wire [7:0] m_axi_awlen,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi AWSIZE" *) output wire [2:0] m_axi_awsize,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi AWBURST" *) output wire [1:0] m_axi_awburst,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi AWCACHE" *) output wire [3:0] m_axi_awcache,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi AWPROT" *) output wire [2:0] m_axi_awprot,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi AWLOCK" *) output wire m_axi_awlock,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi AWVALID" *) output wire m_axi_awvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi AWREADY" *) input wire m_axi_awready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi WDATA" *) output wire [31:0] m_axi_wdata,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi WSTRB" *) output wire [3:0] m_axi_wstrb,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi WLAST" *) output wire m_axi_wlast,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi WVALID" *) output wire m_axi_wvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi WREADY" *) input wire m_axi_wready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi BRESP" *) input wire [1:0] m_axi_bresp,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi BVALID" *) input wire m_axi_bvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_axi BREADY" *) output wire m_axi_bready,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 s_axis TDATA" *) input wire [23:0] s_axis_tdata,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 s_axis TVALID" *) input wire s_axis_tvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 s_axis TREADY" *) output wire s_axis_tready,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 s_axis TUSER" *) input wire s_axis_tuser,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 s_axis TLAST" *) input wire s_axis_tlast,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 m_axis TDATA" *) output wire [23:0] m_axis_tdata,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 m_axis TVALID" *) output wire m_axis_tvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 m_axis TREADY" *) input wire m_axis_tready,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 m_axis TUSER" *) output wire m_axis_tuser,
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 m_axis TLAST" *) output wire m_axis_tlast);
wire enable,start,busy,done,error;wire [31:0] dst,cfg,frame_id,dma_errors,cam_frames,overflows,malformed,display_frames;
wire [5:0] gpio_out;wire [3:0] gpio_in;
wire cam_scl_in,cam_sda_in,sensor_scl_in,sensor_sda_in;
wire lut_we,lut_commit,lut_pending,lut_bank;wire [7:0] lut_index,lut_data;
wire [27:0] capture_data;wire capture_valid,capture_ready;
wire capture_resetn=aresetn&&enable;
(* ASYNC_REG="TRUE" *) reg [8:0] keys1=0,keys2=0;
(* ASYNC_REG="TRUE" *) reg [3:0] io1=0,io2=0;
always @(posedge aclk)begin
 if(!aresetn)begin keys1<=0;keys2<=0;io1<=0;io2<=0;end
 else begin keys1<={~joy_n,buttons};keys2<=keys1;io1<={sensor_sda_in,sensor_scl_in,cam_sda_in,cam_scl_in};io2<=io1;end
end
assign gpio_in=io2;
// Explicit pad buffers preserve bidirectional readback through BD/OOC synthesis.
IOBUF cam_scl_pad(.I(1'b0),.T(gpio_out[0]),.O(cam_scl_in),.IO(cam_scl));
IOBUF cam_sda_pad(.I(1'b0),.T(gpio_out[1]),.O(cam_sda_in),.IO(cam_sda));
IOBUF sensor_scl_pad(.I(1'b0),.T(gpio_out[2]),.O(sensor_scl_in),.IO(sensor_scl));
IOBUF sensor_sda_pad(.I(1'b0),.T(gpio_out[3]),.O(sensor_sda_in),.IO(sensor_sda));
assign cam_resetn=gpio_out[4];assign cam_pwdn=gpio_out[5];
assist_regs regs(.aclk(aclk),.aresetn(aresetn),
.s_axi_awaddr(s_axi_awaddr),
.s_axi_awprot(s_axi_awprot),
.s_axi_awvalid(s_axi_awvalid),
.s_axi_awready(s_axi_awready),
.s_axi_wdata(s_axi_wdata),
.s_axi_wstrb(s_axi_wstrb),
.s_axi_wvalid(s_axi_wvalid),
.s_axi_wready(s_axi_wready),
.s_axi_bresp(s_axi_bresp),
.s_axi_bvalid(s_axi_bvalid),
.s_axi_bready(s_axi_bready),
.s_axi_araddr(s_axi_araddr),
.s_axi_arprot(s_axi_arprot),
.s_axi_arvalid(s_axi_arvalid),
.s_axi_arready(s_axi_arready),
.s_axi_rdata(s_axi_rdata),
.s_axi_rresp(s_axi_rresp),
.s_axi_rvalid(s_axi_rvalid),
.s_axi_rready(s_axi_rready),
.capture_enable(enable),.capture_start(start),.destination(dst),.cfg_word(cfg),.gpio_out(gpio_out),.gpio_in(gpio_in),
.cap_status({29'd0,error,done,busy}),.frame_id(frame_id),.dma_errors(dma_errors),.camera_frames(cam_frames),.overflows(overflows),.malformed(malformed),
.display_frames(display_frames),.buttons(keys2),.lut_pending(lut_pending),.lut_bank(lut_bank),.lut_we(lut_we),.lut_commit(lut_commit),.lut_index(lut_index),.lut_data(lut_data));
dvp_capture #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) camera(
.pclk(cam_pclk),.cam_resetn(capture_resetn),.cam_data(cam_data),.vsync(cam_vsync),.href(cam_href),
.aclk(aclk),.aresetn(capture_resetn),.stream_data(capture_data),.stream_valid(capture_valid),.stream_ready(capture_ready),
.camera_frames(cam_frames),.overflow_frames(overflows),.malformed_frames(malformed));
frame_writer #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) writer(
.aclk(aclk),.aresetn(aresetn),.capture_enable(enable),.start(start),.destination(dst),.s_data(capture_data),.s_valid(capture_valid),.s_ready(capture_ready),
.busy(busy),.done(done),.error(error),.frame_id(frame_id),.error_count(dma_errors),
.m_axi_awaddr(m_axi_awaddr),
.m_axi_awlen(m_axi_awlen),
.m_axi_awsize(m_axi_awsize),
.m_axi_awburst(m_axi_awburst),
.m_axi_awcache(m_axi_awcache),
.m_axi_awprot(m_axi_awprot),
.m_axi_awlock(m_axi_awlock),
.m_axi_awvalid(m_axi_awvalid),
.m_axi_awready(m_axi_awready),
.m_axi_wdata(m_axi_wdata),
.m_axi_wstrb(m_axi_wstrb),
.m_axi_wlast(m_axi_wlast),
.m_axi_wvalid(m_axi_wvalid),
.m_axi_wready(m_axi_wready),
.m_axi_bresp(m_axi_bresp),
.m_axi_bvalid(m_axi_bvalid),
.m_axi_bready(m_axi_bready));
reading_enhance #(.WIDTH(WIDTH)) enhancement(.aclk(aclk),.aresetn(aresetn),
.s_axis_tdata(s_axis_tdata),
.s_axis_tvalid(s_axis_tvalid),
.s_axis_tready(s_axis_tready),
.s_axis_tuser(s_axis_tuser),
.s_axis_tlast(s_axis_tlast),
.m_axis_tdata(m_axis_tdata),
.m_axis_tvalid(m_axis_tvalid),
.m_axis_tready(m_axis_tready),
.m_axis_tuser(m_axis_tuser),
.m_axis_tlast(m_axis_tlast),
.cfg_word(cfg),.lut_we(lut_we),.lut_index(lut_index),.lut_data(lut_data),.lut_commit(lut_commit),.lut_pending(lut_pending),.lut_bank(lut_bank),.frame_count(display_frames));
endmodule
