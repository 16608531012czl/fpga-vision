set root [file normalize [file join [file dirname [info script]] ..]]
if {[version -short] ne "2018.3"} {error "Vivado 2018.3 required"}
create_project visual_aid_v3_sim [file join $root build gui_sim] -part xc7z020clg400-1 -force
add_files [glob [file join $root rtl *.sv]]
set_property top visual_aid_core [current_fileset]
add_files -fileset sim_1 [glob [file join $root sim tb_*.sv]]
add_files -fileset sim_1 [glob [file join $root build sim_quick *.mem]]
set_property top tb_reading [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
set_property target_language Verilog [current_project]
update_compile_order -fileset sources_1
update_compile_order -fileset sim_1
puts "PASS: simulation project created"
if {[llength $argv] && [lindex $argv 0] eq "run"} {
 launch_simulation
 close_sim
 puts "PASS: GUI simulation launched"
}
close_project
