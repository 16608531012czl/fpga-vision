set root [file normalize [file join [file dirname [info script]] ..]]
open_checkpoint [file join $root build system visual_aid_v3.runs impl_1 visual_aid_wrapper_placed.dcp]
report_timing -max_paths 20 -nworst 2 -file [file join $root reports pl_placed_paths.rpt]
puts "PASS: placed timing paths inspected"
close_design
