`timescale 1ns/1ps
// Independent capture/control/display core, no MicroBlaze IOPs.
module visual_aid_core #(parameter WIDTH=1280,HEIGHT=720)(
 (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 aclk CLK", X_INTERFACE_PARAMETER="ASSOCIATED_BUSIF s_axi:m_axi:m_canvas:s_axis:m_axis, ASSOCIATED_RESET aresetn, FREQ_HZ 100000000" *) input wire aclk,
 (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 aresetn RST", X_INTERFACE_PARAMETER="POLARITY ACTIVE_LOW" *) input wire aresetn,
 input wire cam_pclk,cam_vsync,cam_href,
 input wire [7:0] cam_data,
 input wire [3:0] buttons,
 input wire [4:0] joy_n,
 input wire enc_a,enc_b,enc_key_n,
 inout wire cam_scl,cam_sda,sensor_scl,sensor_sda,
 output wire cam_resetn,cam_pwdn,
 input wire [5:0] display_slot,
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
 (* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 m_axis TLAST" *) output wire m_axis_tlast,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas AWADDR", X_INTERFACE_PARAMETER="PROTOCOL AXI4, DATA_WIDTH 64, ADDR_WIDTH 32" *) output wire [31:0] m_canvas_awaddr,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas AWLEN" *) output wire [7:0] m_canvas_awlen,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas AWSIZE" *) output wire [2:0] m_canvas_awsize,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas AWBURST" *) output wire [1:0] m_canvas_awburst,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas AWCACHE" *) output wire [3:0] m_canvas_awcache,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas AWPROT" *) output wire [2:0] m_canvas_awprot,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas AWLOCK" *) output wire m_canvas_awlock,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas AWVALID" *) output wire m_canvas_awvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas AWREADY" *) input wire m_canvas_awready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas WDATA" *) output wire [63:0] m_canvas_wdata,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas WSTRB" *) output wire [7:0] m_canvas_wstrb,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas WLAST" *) output wire m_canvas_wlast,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas WVALID" *) output wire m_canvas_wvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas WREADY" *) input wire m_canvas_wready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas BRESP" *) input wire [1:0] m_canvas_bresp,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas BVALID" *) input wire m_canvas_bvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas BREADY" *) output wire m_canvas_bready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas ARADDR" *) output wire [31:0] m_canvas_araddr,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas ARLEN" *) output wire [7:0] m_canvas_arlen,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas ARSIZE" *) output wire [2:0] m_canvas_arsize,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas ARBURST" *) output wire [1:0] m_canvas_arburst,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas ARCACHE" *) output wire [3:0] m_canvas_arcache,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas ARPROT" *) output wire [2:0] m_canvas_arprot,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas ARLOCK" *) output wire m_canvas_arlock,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas ARVALID" *) output wire m_canvas_arvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas ARREADY" *) input wire m_canvas_arready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas RDATA" *) input wire [63:0] m_canvas_rdata,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas RRESP" *) input wire [1:0] m_canvas_rresp,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas RLAST" *) input wire m_canvas_rlast,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas RVALID" *) input wire m_canvas_rvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 m_canvas RREADY" *) output wire m_canvas_rready);
wire enable,start,busy,done,error;wire [31:0] dst,cfg,frame_id,dma_errors,cam_frames,overflows,malformed,display_frames;
wire [5:0] gpio_out;wire [3:0] gpio_in;
wire cam_scl_in,cam_sda_in,sensor_scl_in,sensor_sda_in;
wire lut_we,lut_commit,lut_pending,lut_bank;wire [7:0] lut_index,lut_data;
wire [31:0] quality_word;
wire [31:0] canvas_destination,view_cfg,roi_cfg,canvas_source;wire canvas_start;
wire capture_ready;
wire [5:0] tile_read_index;wire [23:0] tile_sum;wire [15:0] tile_count;wire [31:0] tile_frame_id;
wire text_we,text_commit,text_enable,text_pending;wire [8:0] text_index;wire [7:0] text_data;
wire [31:0] display_cfg_word;
wire [5:0] display_index;
display_slot_decode display_pointer(.gray(display_slot),.slot(display_index));
wire gain_we,gain_commit,gain_pending;wire [5:0] gain_index;wire [9:0] gain_value;
wire [23:0] enhanced_data;wire enhanced_valid,enhanced_ready,enhanced_user,enhanced_last;
wire stats_ready_internal,stats_done;
reg stats_working=0;
wire raw_busy,raw_done,raw_error,raw_ready,canvas_busy,canvas_done,canvas_error,canvas_ready_internal;
wire [31:0] raw_errors,canvas_errors;
wire canvas_on=view_cfg[7];
wire canvas_ready=!canvas_on||canvas_ready_internal;
wire stats_ready=!canvas_on||stats_ready_internal;
assign capture_ready=raw_ready&&canvas_ready&&stats_ready;
assign busy=raw_busy||(stats_working&&!stats_done);
assign done=raw_done&&(!canvas_on||stats_done)&&!busy;
assign error=raw_error||canvas_error;assign dma_errors=raw_errors+canvas_errors;
always @(posedge aclk)begin
 if(!aresetn||!enable)stats_working<=0;
 else if(start&&canvas_on)stats_working<=1;
 else if(stats_done)stats_working<=0;
end
wire [27:0] capture_data;wire capture_valid;
reg [31:0] capture_diagnostic=0;
always @(posedge aclk)begin
 if(!aresetn||!enable)capture_diagnostic<=0;
 else if(capture_valid&&capture_ready&&capture_data[27])capture_diagnostic<={4'd0,capture_data};
end
wire [31:0] encoder_position,encoder_short,encoder_long,encoder_invalid;
wire [2:0] encoder_status;
encoder_input encoder(.clk(aclk),.resetn(aresetn),.a(enc_a),.b(enc_b),.key_n(enc_key_n),
 .position(encoder_position),.short_count(encoder_short),.long_count(encoder_long),
 .invalid_count(encoder_invalid),.status(encoder_status));
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
.display_frames(display_frames),.buttons(keys2),.lut_pending(lut_pending),.lut_bank(lut_bank),.lut_we(lut_we),.lut_commit(lut_commit),.lut_index(lut_index),.lut_data(lut_data),
.encoder_position(encoder_position),.encoder_short(encoder_short),.encoder_long(encoder_long),
.encoder_invalid(encoder_invalid),.encoder_status(encoder_status),.capture_diagnostic(capture_diagnostic),.quality_word(quality_word),.canvas_destination(canvas_destination),.view_cfg(view_cfg),.roi_cfg(roi_cfg),.canvas_status({29'd0,canvas_error,canvas_done,canvas_busy}),
.tile_read_index(tile_read_index),.tile_sum(tile_sum),.tile_count(tile_count),.tile_frame_id(tile_frame_id),
.text_we(text_we),.text_commit(text_commit),.text_enable(text_enable),.text_index(text_index),.text_data(text_data),.text_pending(text_pending),
.display_slot(display_index),.display_cfg_word(display_cfg_word),.gain_we(gain_we),.gain_commit(gain_commit),.gain_index(gain_index),.gain_value(gain_value),.gain_pending(gain_pending),
.canvas_source(canvas_source),.canvas_start(canvas_start));
dvp_capture #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) camera(
.pclk(cam_pclk),.cam_resetn(capture_resetn),.cam_data(cam_data),.vsync(cam_vsync),.href(cam_href),
.aclk(aclk),.aresetn(capture_resetn),.stream_data(capture_data),.stream_valid(capture_valid),.stream_ready(capture_ready),
.camera_frames(cam_frames),.overflow_frames(overflows),.malformed_frames(malformed));
frame_writer #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) writer(
.aclk(aclk),.aresetn(aresetn),.capture_enable(enable),.start(start),.destination(dst),.s_data(capture_data),.s_valid(capture_valid&&canvas_ready&&stats_ready),.s_ready(raw_ready),
.busy(raw_busy),.done(raw_done),.error(raw_error),.frame_id(frame_id),.error_count(raw_errors),
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

canvas_writer #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) canvas(
.clk(aclk),.resetn(aresetn),.enable(enable&&canvas_on),.start(canvas_start&&canvas_on),
.destination(canvas_destination),.view_cfg(view_cfg),.roi_cfg(roi_cfg),
.source_address(canvas_source),.source_done(1'b1),
.s_data(capture_data),.s_valid(capture_valid&&raw_ready&&stats_ready&&canvas_on),.s_ready(canvas_ready_internal),
.busy(canvas_busy),.done(canvas_done),.error(canvas_error),.errors(canvas_errors),
.awaddr(m_canvas_awaddr),
.awlen(m_canvas_awlen),
.awsize(m_canvas_awsize),
.awburst(m_canvas_awburst),
.awcache(m_canvas_awcache),
.awprot(m_canvas_awprot),
.awlock(m_canvas_awlock),
.awvalid(m_canvas_awvalid),
.awready(m_canvas_awready),
.wdata(m_canvas_wdata),
.wstrb(m_canvas_wstrb),
.wlast(m_canvas_wlast),
.wvalid(m_canvas_wvalid),
.wready(m_canvas_wready),
.bresp(m_canvas_bresp),
.bvalid(m_canvas_bvalid),
.bready(m_canvas_bready),
.araddr(m_canvas_araddr),.arlen(m_canvas_arlen),.arsize(m_canvas_arsize),.arburst(m_canvas_arburst),
.arcache(m_canvas_arcache),.arprot(m_canvas_arprot),.arlock(m_canvas_arlock),.arvalid(m_canvas_arvalid),.arready(m_canvas_arready),
.rdata(m_canvas_rdata),.rresp(m_canvas_rresp),.rlast(m_canvas_rlast),.rvalid(m_canvas_rvalid),.rready(m_canvas_rready));
frame_tiles #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) statistics(.clk(aclk),.resetn(aresetn),.enable(enable&&canvas_on),.start(start&&canvas_on),
.capture_ok(raw_done&&!raw_error),.roi_cfg(roi_cfg),.view_cfg(view_cfg),.capture_id(frame_id),
.s_data(capture_data),.s_valid(capture_valid&&raw_ready&&canvas_ready&&canvas_on),.s_ready(stats_ready_internal),
.read_index(tile_read_index),.read_sum(tile_sum),.sample_count(tile_count),.published_id(tile_frame_id),.done(stats_done));
wire [23:0] filtered_data;wire filtered_valid,filtered_ready,filtered_user,filtered_last;
wire [31:0] filtered_cfg,filtered_quality;
chroma_filter #(.WIDTH(WIDTH)) color_noise(.clk(aclk),.resetn(aresetn),
.s_data(s_axis_tdata),.s_valid(s_axis_tvalid),.s_ready(s_axis_tready),.s_user(s_axis_tuser),.s_last(s_axis_tlast),
.cfg(display_cfg_word),.quality(quality_word),.m_data(filtered_data),.m_valid(filtered_valid),.m_ready(filtered_ready),
.m_user(filtered_user),.m_last(filtered_last),.m_cfg(filtered_cfg),.m_quality(filtered_quality));
reading_enhance #(.WIDTH(WIDTH)) enhancement(.aclk(aclk),.aresetn(aresetn),
.s_axis_tdata(filtered_data),
.s_axis_tvalid(filtered_valid),
.s_axis_tready(filtered_ready),
.s_axis_tuser(filtered_user),
.s_axis_tlast(filtered_last),
.m_axis_tdata(enhanced_data),
.m_axis_tvalid(enhanced_valid),
.m_axis_tready(enhanced_ready),
.m_axis_tuser(enhanced_user),
.m_axis_tlast(enhanced_last),
.cfg_word(filtered_cfg),.quality_word(filtered_quality),.gain_we(gain_we),.gain_commit(gain_commit),.gain_index(gain_index),.gain_value(gain_value),.gain_pending(gain_pending),
.lut_we(lut_we),.lut_index(lut_index),.lut_data(lut_data),.lut_commit(lut_commit),.lut_pending(lut_pending),.lut_bank(lut_bank),.frame_count(display_frames));
status_overlay #(.WIDTH(WIDTH)) osd(.clk(aclk),.resetn(aresetn),.s_data(enhanced_data),.s_valid(enhanced_valid),.s_ready(enhanced_ready),
.s_user(enhanced_user),.s_last(enhanced_last),.m_data(m_axis_tdata),.m_valid(m_axis_tvalid),.m_ready(m_axis_tready),.m_user(m_axis_tuser),.m_last(m_axis_tlast),
.text_we(text_we),.text_commit(text_commit),.text_enable(text_enable),.text_index(text_index),.text_data(text_data),.text_pending(text_pending));
endmodule
