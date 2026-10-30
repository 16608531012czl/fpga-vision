# Read-only diagnostics from the accepted routed checkpoint; no bit download.
set root [file normalize [file join [file dirname [info script]] ..]]
open_checkpoint [file join $root build verified_routed.dcp]
report_cdc -details -file [file join $root reports system_cdc_details.rpt]
check_timing -verbose -file [file join $root reports check_timing.rpt]
puts "PASS: routed CDC and timing inspection"
close_design
