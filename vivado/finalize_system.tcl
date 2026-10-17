source [file join $root vivado clock_tree.tcl]
report_clocks -file [file join $root reports system_clocks.rpt]
report_timing_summary -file [file join $root reports system_timing.rpt]
report_utilization -file [file join $root reports system_utilization.rpt]
report_drc -file [file join $root reports system_drc.rpt]
set gray_groups 0
foreach pattern {*/camera/fifo/wg1_reg* */camera/fifo/rg1_reg* */camera/f1_reg* */camera/o1_reg* */camera/m1_reg*} {
 set targets [get_cells -hier -filter "NAME =~ $pattern"]
 if {![llength $targets]} {error "Missing Gray synchronizer group: $pattern"}
 incr gray_groups
 puts "CDC_GRAY_TARGETS $pattern [llength $targets]"
}
report_bus_skew -file [file join $root reports system_bus_skew.rpt]
report_cdc -file [file join $root reports system_cdc.rpt]
report_route_status -file [file join $root reports system_route_status.rpt]
set setup [get_property SLACK [get_timing_paths -delay_type max -max_paths 1]]
set hold [get_property SLACK [get_timing_paths -delay_type min -max_paths 1]]
puts "ENHANCED_TIMING setup=$setup hold=$hold"
if {$setup < 0 || $hold < 0} {error "Enhanced timing failed; bitstream not published"}
if {[llength [get_drc_violations -filter {SEVERITY == Error}]]} {error "Enhanced DRC failed"}
# Check the enhanced datapath and all four bidirectional pad buffers.
if {![llength [get_cells -hier -filter {NAME =~ *enhancement*}]]} {error "Enhanced datapath missing"}
set iobufs [get_cells -hier -filter {REF_NAME == IOBUF}]
set pads_ok 0
foreach pad {cam_scl cam_sda sensor_scl sensor_sda} {
 set nets [get_nets -of_objects [get_ports $pad]]
 set pins [get_pins -leaf -of_objects $nets]
 set types [get_property REF_NAME [get_cells -of_objects $pins]]
 if {[lsearch -exact $types IOBUF]>=0 || ([lsearch -exact $types IBUF]>=0 && [lsearch -exact $types OBUFT]>=0)} {
  incr pads_ok
 } else {error "Missing bidirectional input/output buffers on $pad: $types"}
}
write_checkpoint -force [file join $root build verified_routed.dcp]
write_bitstream -force [file join $root build visual_aid_v3.bit]
# Stage artifacts only. Python publication checks current XSim, software tests,
# source fingerprints and bus-skew reports before placing files in software/board.
file copy -force [file join $root build system visual_aid_v3.srcs sources_1 bd visual_aid hw_handoff visual_aid.hwh] [file join $root build visual_aid_v3.hwh]
foreach pad {cam_scl cam_sda} {set_property PULLUP false [get_ports $pad]}
report_drc -file [file join $root reports external_pullup_drc.rpt]
if {[llength [get_drc_violations -filter {SEVERITY == Error}]]} {error "External-pullup variant DRC errors"}
write_bitstream -force [file join $root build visual_aid_v3_external_pullup.bit]
file copy -force [file join $root build visual_aid_v3.hwh] [file join $root build visual_aid_v3_external_pullup.hwh]
set status [open [file join $root reports system_timing_values.json] w]
puts $status "{\"setup_ns\":$setup,\"hold_ns\":$hold,\"drc_errors\":0,\"bidirectional_pads\":$pads_ok,\"enhancement_present\":true,\"gray_groups\":$gray_groups}"
close $status
puts "PASS: enhanced overlay timing, DRC and staged bit/HWH"
