set root [file normalize [file join [file dirname [info script]] ..]]
open_checkpoint [file join $root build verified_routed.dcp]
set out [open [file join $root reports encoder_routed_ports.txt] w]
foreach name {enc_a enc_b enc_key_n sensor_scl sensor_sda} {
 set p [get_ports $name]
 set ibuf [get_cells -of_objects [get_nets -of_objects $p] -filter {REF_NAME == IBUF}]
 set sinks [all_fanout -flat -endpoints_only -from $p]
 puts $out "$name PACKAGE_PIN=[get_property PACKAGE_PIN $p] PULLUP=[get_property PULLUP $p] IOSTANDARD=[get_property IOSTANDARD $p] IBUF=$ibuf SINKS=$sinks"
}
close $out
close_design
puts "PASS: encoder routed input ports inspected"
