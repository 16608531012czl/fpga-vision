set root [file normalize [file join [file dirname [info script]] ..]]
if {[version -short] ne "2018.3"} {error "Vivado 2018.3 required"}
open_project [file join $root build system visual_aid_v3.xpr]
if {![llength [get_files -quiet */cdc.xdc]]} {
 add_files -fileset constrs_1 [file join $root vivado cdc.xdc]
}
set_property PROCESSING_ORDER LATE [get_files */cdc.xdc]
set_property USED_IN_SYNTHESIS false [get_files */cdc.xdc]
open_bd_design [get_files visual_aid.bd]
update_compile_order -fileset sources_1
# Vivado 2018.3 requires the generated IP object, not a BD cell/path.
set module_ip [get_ips -all *assist_core*]
if {[llength $module_ip] != 1} {error "Expected exactly one assist_core module IP"}
update_module_reference $module_ip
validate_bd_design
save_bd_design
generate_target all [get_files visual_aid.bd]
write_bd_tcl -force [file join $root reports generated_system.tcl]
puts "PASS: existing independent block design validated"
close_project
