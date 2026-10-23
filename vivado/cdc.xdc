# Implementation-only Gray bus skew bounds; pure XDC (no Tcl control flow).
set_bus_skew 10.0 -from [get_cells -hier -filter {(NAME =~ */camera/fifo/wg_reg* || NAME =~ */camera/fifo/wb_reg*) && REF_NAME =~ FD*}] -to [get_cells -hier -filter {(NAME =~ */camera/fifo/wg1_reg*) && REF_NAME =~ FD*}]
set_bus_skew 10.0 -from [get_cells -hier -filter {(NAME =~ */camera/fifo/rg_reg* || NAME =~ */camera/fifo/rb_reg*) && REF_NAME =~ FD*}] -to [get_cells -hier -filter {(NAME =~ */camera/fifo/rg1_reg*) && REF_NAME =~ FD*}]
set_bus_skew 10.0 -from [get_cells -hier -filter {(NAME =~ */camera/fg_reg* || NAME =~ */camera/frames_p_reg*) && REF_NAME =~ FD*}] -to [get_cells -hier -filter {(NAME =~ */camera/f1_reg*) && REF_NAME =~ FD*}]
set_bus_skew 10.0 -from [get_cells -hier -filter {(NAME =~ */camera/og_reg* || NAME =~ */camera/overflow_p_reg*) && REF_NAME =~ FD*}] -to [get_cells -hier -filter {(NAME =~ */camera/o1_reg*) && REF_NAME =~ FD*}]
set_bus_skew 10.0 -from [get_cells -hier -filter {(NAME =~ */camera/mg_reg* || NAME =~ */camera/malformed_p_reg*) && REF_NAME =~ FD*}] -to [get_cells -hier -filter {(NAME =~ */camera/m1_reg*) && REF_NAME =~ FD*}]
# Only asynchronous controls are excluded; DVP inputs remain timed.
set_false_path -from [get_ports {enc_a enc_b enc_key_n}] -to [get_pins -of_objects [get_cells -hier -filter {NAME =~ */encoder/sync1_reg*}] -filter {REF_PIN_NAME == D}]
set_false_path -from [get_ports {buttons[*] joy_n[*] cam_scl cam_sda sensor_scl sensor_sda}]
set_false_path -to [get_ports {cam_resetn cam_pwdn cam_scl cam_sda sensor_scl sensor_sda}]
