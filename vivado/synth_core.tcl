set root [file normalize [file join [file dirname [info script]] ..]]
create_project -in_memory -part xc7z020clg400-1
read_verilog -sv [glob [file join $root rtl *.sv]]
synth_design -top visual_aid_core -part xc7z020clg400-1
report_utilization -file [file join $root reports core_utilization.rpt]
write_checkpoint -force [file join $root build core_synth.dcp]
puts "PASS: custom RTL synthesis"
