# Implementation-only Gray bus skew bounds; pure XDC (no Tcl control flow).
set_bus_skew 10.0 -from [get_cells -hier -filter {NAME =~ */camera/fifo/wg_reg* || NAME =~ */camera/fifo/wb_reg*}] -to [get_cells -hier -filter {NAME =~ */camera/fifo/wg1_reg*}]
set_bus_skew 10.0 -from [get_cells -hier -filter {NAME =~ */camera/fifo/rg_reg* || NAME =~ */camera/fifo/rb_reg*}] -to [get_cells -hier -filter {NAME =~ */camera/fifo/rg1_reg*}]
set_bus_skew 10.0 -from [get_cells -hier -filter {NAME =~ */camera/fg_reg* || NAME =~ */camera/frames_p_reg*}] -to [get_cells -hier -filter {NAME =~ */camera/f1_reg*}]
set_bus_skew 10.0 -from [get_cells -hier -filter {NAME =~ */camera/og_reg* || NAME =~ */camera/overflow_p_reg*}] -to [get_cells -hier -filter {NAME =~ */camera/o1_reg*}]
set_bus_skew 10.0 -from [get_cells -hier -filter {NAME =~ */camera/mg_reg* || NAME =~ */camera/malformed_p_reg*}] -to [get_cells -hier -filter {NAME =~ */camera/m1_reg*}]
# Only asynchronous controls are excluded; DVP inputs remain timed.
set_false_path -from [get_ports {buttons[*] joy_n[*] cam_scl cam_sda sensor_scl sensor_sda}]
set_false_path -to [get_ports {cam_resetn cam_pwdn cam_scl cam_sda sensor_scl sensor_sda}]
