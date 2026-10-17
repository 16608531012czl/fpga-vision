# Fresh standalone BD: PYNQ PS/DDR + official HDMI OUT + custom capture/reader.
set root [file normalize [file join [file dirname [info script]] ..]]
if {[version -short] ne "2018.3"} {error "Vivado 2018.3 required"}
set project_dir [file join $root build system]
if {[file exists [file join $project_dir visual_aid_v3.xpr]]} {error "System project exists. Use the existing project; do not overwrite it."}
create_project visual_aid_v3 $project_dir -part xc7z020clg400-1
set_property ip_repo_paths [list [file join $root vendor ip]] [current_project]
update_ip_catalog
add_files [glob [file join $root rtl *.sv]]
# Vivado 2018.3 BD module-reference requires a Verilog top, even with SV children.
set_property FILE_TYPE Verilog [get_files */visual_aid_core.sv]
update_compile_order -fileset sources_1
create_bd_design visual_aid
set script_folder [file join $root vendor]
source [file join $root vendor pynq_video_procs.tcl]
source [file join $root vendor pynq_ps7.tcl]
set_property -dict [list CONFIG.PCW_USE_M_AXI_GP1 0 CONFIG.PCW_USE_S_AXI_GP0 0 CONFIG.PCW_USE_S_AXI_HP2 0 CONFIG.PCW_EN_CLK1_PORT 0 CONFIG.PCW_EN_CLK2_PORT 0 CONFIG.PCW_EN_CLK3_PORT 0 CONFIG.PCW_USE_FABRIC_INTERRUPT 1 CONFIG.PCW_IRQ_F2P_INTR 1] [get_bd_cells ps7_0]
foreach intf {DDR FIXED_IO} {make_bd_intf_pins_external [get_bd_intf_pins ps7_0/$intf]}
set rst [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 reset_100m]
set one [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 one]
set_property CONFIG.CONST_VAL 1 $one
connect_bd_net [get_bd_pins ps7_0/FCLK_CLK0] [get_bd_pins reset_100m/slowest_sync_clk] [get_bd_pins ps7_0/M_AXI_GP0_ACLK] [get_bd_pins ps7_0/S_AXI_HP0_ACLK]
connect_bd_net [get_bd_pins ps7_0/FCLK_RESET0_N] [get_bd_pins reset_100m/ext_reset_in]
connect_bd_net [get_bd_pins one/dout] [get_bd_pins reset_100m/dcm_locked]
set ctrl [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 control_bus]
set_property CONFIG.NUM_MI 7 $ctrl
set mem [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 memory_bus]
set_property -dict [list CONFIG.NUM_SI 2 CONFIG.NUM_MI 1] $mem
set dma [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_vdma:6.3 display_vdma]
set_property -dict [list CONFIG.c_include_s2mm 0 CONFIG.c_include_mm2s 1 CONFIG.c_num_fstores 4 CONFIG.c_m_axis_mm2s_tdata_width 32 CONFIG.c_m_axi_mm2s_data_width 64 CONFIG.c_mm2s_linebuffer_depth 4096 CONFIG.c_include_mm2s_dre 1] $dma
create_hier_cell_hdmi_out / hdmi_out
set core [create_bd_cell -type module -reference visual_aid_core assist_core]
connect_bd_intf_net [get_bd_intf_pins ps7_0/M_AXI_GP0] [get_bd_intf_pins control_bus/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins memory_bus/M00_AXI] [get_bd_intf_pins ps7_0/S_AXI_HP0]
connect_bd_intf_net [get_bd_intf_pins assist_core/m_axi] [get_bd_intf_pins memory_bus/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins display_vdma/M_AXI_MM2S] [get_bd_intf_pins memory_bus/S01_AXI]
set slaves [list assist_core/s_axi display_vdma/S_AXI_LITE hdmi_out/S00_AXILite hdmi_out/S01_AXILite hdmi_out/S02_AXILite hdmi_out/S03_AXILite hdmi_out/S04_AXILite]
set n 0
foreach slave $slaves {connect_bd_intf_net [get_bd_intf_pins control_bus/M0${n}_AXI] [get_bd_intf_pins $slave];incr n}
connect_bd_intf_net [get_bd_intf_pins display_vdma/M_AXIS_MM2S] [get_bd_intf_pins hdmi_out/in_stream]
set old [get_bd_intf_nets -of_objects [get_bd_intf_pins hdmi_out/color_convert/stream_in_24]]
disconnect_bd_intf_net $old [get_bd_intf_pins hdmi_out/color_convert/stream_in_24]
connect_bd_intf_net [get_bd_intf_pins hdmi_out/axis_register_slice_0/M_AXIS] [get_bd_intf_pins assist_core/s_axis]
connect_bd_intf_net [get_bd_intf_pins assist_core/m_axis] [get_bd_intf_pins hdmi_out/color_convert/stream_in_24]
foreach cell {control_bus memory_bus} {
 foreach p [get_bd_pins -of_objects [get_bd_cells $cell] -filter {TYPE == clk}] {connect_bd_net [get_bd_pins ps7_0/FCLK_CLK0] $p}
 foreach p [get_bd_pins -of_objects [get_bd_cells $cell] -filter {TYPE == rst}] {connect_bd_net [get_bd_pins reset_100m/peripheral_aresetn] $p}
}
foreach pin {assist_core/aclk display_vdma/s_axi_lite_aclk display_vdma/m_axi_mm2s_aclk display_vdma/m_axis_mm2s_aclk hdmi_out/clk_100M hdmi_out/clk_142M} {connect_bd_net [get_bd_pins ps7_0/FCLK_CLK0] [get_bd_pins $pin]}
foreach pin {assist_core/aresetn display_vdma/axi_resetn hdmi_out/periph_resetn_clk100M hdmi_out/periph_resetn_clk142M} {connect_bd_net [get_bd_pins reset_100m/peripheral_aresetn] [get_bd_pins $pin]}
set irq [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconcat:2.1 irq_concat]
set_property -dict [list CONFIG.NUM_PORTS 2 CONFIG.IN1_WIDTH 15] $irq
set zero [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 irq_zero]
set_property -dict [list CONFIG.CONST_WIDTH 15 CONFIG.CONST_VAL 0] $zero
connect_bd_net [get_bd_pins display_vdma/mm2s_introut] [get_bd_pins irq_concat/In0]
connect_bd_net [get_bd_pins irq_zero/dout] [get_bd_pins irq_concat/In1]
connect_bd_net [get_bd_pins irq_concat/dout] [get_bd_pins ps7_0/IRQ_F2P]
foreach pin {cam_pclk cam_vsync cam_href cam_data buttons joy_n cam_scl cam_sda sensor_scl sensor_sda cam_resetn cam_pwdn} {
 set before [get_bd_ports]
 make_bd_pins_external [get_bd_pins assist_core/$pin]
 foreach p [get_bd_ports] {if {[lsearch -exact $before $p]<0} {set_property name $pin $p}}
}
make_bd_intf_pins_external [get_bd_intf_pins hdmi_out/TMDS_out]
set_property name hdmi_out [get_bd_intf_ports TMDS_out_0]
make_bd_pins_external [get_bd_pins hdmi_out/hdmi_out_hpd]
set_property name hdmi_out_hpd [get_bd_ports hdmi_out_hpd_0]
assign_bd_address
validate_bd_design
save_bd_design
generate_target all [get_files visual_aid.bd]
make_wrapper -files [get_files visual_aid.bd] -top
add_files [file join $project_dir visual_aid_v3.srcs sources_1 bd visual_aid hdl visual_aid_wrapper.v]
set_property top visual_aid_wrapper [current_fileset]
add_files -fileset constrs_1 [file join $root vivado pins.xdc]
add_files -fileset constrs_1 [file join $root vivado cdc.xdc]
set_property PROCESSING_ORDER LATE [get_files */cdc.xdc]
set_property USED_IN_SYNTHESIS false [get_files */cdc.xdc]
update_compile_order -fileset sources_1
write_bd_tcl -force [file join $root reports generated_system.tcl]
puts "PASS: independent system block design validated"
close_project
