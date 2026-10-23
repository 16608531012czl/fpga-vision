# Inspect the implemented bidirectional sensor pads without rebuilding hardware.
set root [file normalize [file join [file dirname [info script]] ..]]
open_checkpoint [file join $root build verified_routed.dcp]
set out [open [file join $root reports sensor_routed_pads.txt] w]
foreach name {sensor_scl sensor_sda} {
 set port [get_ports $name]
 set cells [get_cells -of_objects [get_pins -leaf -of_objects [get_nets -of_objects $port]]]
 puts $out "PORT $name PIN=[get_property PACKAGE_PIN $port] PULLUP=[get_property PULLUP $port] IOSTANDARD=[get_property IOSTANDARD $port]"
 foreach cell $cells {
  set type [get_property REF_NAME $cell]
  puts $out "BUFFER $cell TYPE=$type LOC=[get_property LOC $cell]"
  foreach pin [get_pins -of_objects $cell] {
   set direction [get_property DIRECTION $pin]
   set net [get_nets -of_objects $pin]
   puts $out " PIN $pin DIR=$direction NET=$net"
   if {$direction == "IN"} {
    puts $out "  SOURCES [all_fanin -flat -startpoints_only -to $pin]"
   }
   if {$direction == "OUT"} {
    puts $out "  SINKS [all_fanout -flat -endpoints_only -from $pin]"
   }
  }
 }
}
close $out
close_design
puts "PASS: implemented sensor pad directions inspected"
