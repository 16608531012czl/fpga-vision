# Only the independent enhanced project is built/reset. No board programming.
set root [file normalize [file join [file dirname [info script]] ..]]
if {[version -short] ne "2018.3"} {error "Vivado 2018.3 required"}
open_project [file join $root build system visual_aid_v3.xpr]
open_bd_design [get_files visual_aid.bd]
update_compile_order -fileset sources_1
set module_ip [get_ips -all *assist_core*]
if {[llength $module_ip]!=1} {error "Expected one enhanced module reference"}
update_module_reference $module_ip
validate_bd_design
save_bd_design
generate_target all [get_files visual_aid.bd]
if {![llength [get_files -quiet */cdc.xdc]]} {add_files -fileset constrs_1 [file join $root vivado cdc.xdc]}
set_property PROCESSING_ORDER LATE [get_files */cdc.xdc]
set_property USED_IN_SYNTHESIS false [get_files */cdc.xdc]
# Disable the backwards SerialClk-from-PixelClk override. Preserve automatic
# clocks from the real axi_dynclk MMCM/BUFR; finalize checks the 5:1 ratio.
set reverse_clock_xdc [get_files -all -filter {NAME =~ *rgb2dvi_clocks.xdc}]
if {![llength $reverse_clock_xdc]} {error "Expected scoped HDMI clock constraints"}
set_property USED_IN_IMPLEMENTATION false $reverse_clock_xdc
set module_run [get_runs -quiet *assist_core*_synth_1]
if {[llength $module_run]} {reset_run $module_run}
reset_run synth_1
set_property strategy Flow_PerfOptimized_high [get_runs synth_1]
set_property strategy Performance_Explore [get_runs impl_1]
set_property STEPS.INIT_DESIGN.TCL.POST [file join $root vivado clock_tree.tcl] [get_runs impl_1]
launch_runs synth_1 -jobs 4
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "Enhanced synthesis failed"}
launch_runs impl_1 -to_step route_design -jobs 4
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {error "Enhanced routing failed"}
open_run impl_1
source [file join $root vivado finalize_system.tcl]
close_project
