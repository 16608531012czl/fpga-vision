set root [file normalize [file join [file dirname [info script]] ..]]
if {[version -short] ne "2018.3"} {error "Vivado 2018.3 required"}
open_project [file join $root build system visual_aid_v3.xpr]
if {![llength [get_files -quiet */cdc.xdc]]} {
 add_files -fileset constrs_1 [file join $root vivado cdc.xdc]
}
set_property PROCESSING_ORDER LATE [get_files */cdc.xdc]
set_property USED_IN_SYNTHESIS false [get_files */cdc.xdc]
open_bd_design [get_files visual_aid.bd]
foreach source [glob [file join $root rtl *.sv]] {if {![llength [get_files -quiet $source]]} {add_files $source}}
update_compile_order -fileset sources_1
# Vivado 2018.3 requires the generated IP object, not a BD cell/path.
set module_ip [get_ips -all *assist_core*]
if {[llength $module_ip] != 1} {error "Expected exactly one assist_core module IP"}
update_module_reference $module_ip
if {![llength [get_bd_nets -of_objects [get_bd_pins assist_core/display_slot]]]} {
 connect_bd_net [get_bd_pins display_vdma/mm2s_frame_ptr_out] [get_bd_pins assist_core/display_slot]
}
set_property CONFIG.NUM_SI 3 [get_bd_cells memory_bus]
if {![llength [get_bd_intf_nets -of_objects [get_bd_intf_pins assist_core/m_canvas]]]} {
 connect_bd_intf_net [get_bd_intf_pins assist_core/m_canvas] [get_bd_intf_pins memory_bus/S02_AXI]
}
foreach p [get_bd_pins -of_objects [get_bd_cells memory_bus] -filter {TYPE == clk}] {
 if {![llength [get_bd_nets -of_objects $p]]} {connect_bd_net [get_bd_pins ps7_0/FCLK_CLK0] $p}
}
foreach p [get_bd_pins -of_objects [get_bd_cells memory_bus] -filter {TYPE == rst}] {
 if {![llength [get_bd_nets -of_objects $p]]} {connect_bd_net [get_bd_pins reset_100m/peripheral_aresetn] $p}
}
if {![llength [get_bd_addr_segs -quiet assist_core/m_canvas/SEG_ps7_0_HP0_DDR_LOWOCM]]} {
 create_bd_addr_seg -range 0x20000000 -offset 0x00000000 [get_bd_addr_spaces assist_core/m_canvas] [get_bd_addr_segs ps7_0/S_AXI_HP0/HP0_DDR_LOWOCM] SEG_ps7_0_HP0_DDR_LOWOCM
}
validate_bd_design
save_bd_design
generate_target all [get_files visual_aid.bd]
write_bd_tcl -force [file join $root reports generated_system.tcl]
puts "PASS: existing independent block design validated"
close_project
