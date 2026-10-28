# Reuse the accepted V4 optimized netlist; change only sensor package pins.
set root [file normalize [file join [file dirname [info script]] ..]]
if {[version -short] ne "2018.3"} {error "Vivado 2018.3 required"}
set_param general.maxThreads 4
open_checkpoint [file join $root build source_optimized.dcp]
if {[get_property PACKAGE_PIN [get_ports sensor_scl]] ne "T11" || [get_property PACKAGE_PIN [get_ports sensor_sda]] ne "T10"} {
 error "Source checkpoint does not match the verified PMOD B release"
}
set_property PACKAGE_PIN P15 [get_ports sensor_scl]
set_property PACKAGE_PIN P16 [get_ports sensor_sda]
foreach pair {{sensor_scl P15} {sensor_sda P16}} {
 lassign $pair port pin
 if {[get_property PACKAGE_PIN [get_ports $port]] ne $pin} {error "Pin relocation failed"}
 puts "ARDUINO_SENSOR_PIN $port $pin"
}
source [file join $root vivado clock_tree.tcl]
place_design -directive Explore
phys_opt_design -directive Explore
route_design -directive Explore
report_io -file [file join $root reports arduino_io.rpt]
source [file join $root vivado finalize_system.tcl]
close_design
