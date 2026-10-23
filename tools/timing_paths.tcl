set root [file normalize [file join [file dirname [info script]] ..]]
open_checkpoint [file join $root build verified_routed.dcp]
report_timing -delay_type max -max_paths 60 -nworst 2 -file [file join $root reports performance_paths.rpt]
set f [open [file join $root reports performance_paths.tsv] w]
puts $f "slack\tstart\tend\tlevels"
foreach p [get_timing_paths -delay_type max -max_paths 60 -nworst 2] {
 puts $f "[get_property SLACK $p]\t[get_property STARTPOINT_PIN $p]\t[get_property ENDPOINT_PIN $p]\t[get_property LOGIC_LEVELS $p]"
}
close $f
puts "PASS: performance path diagnosis"
