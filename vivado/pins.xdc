# PYNQ-Z2 verified board mapping; camera IO compatibility must be confirmed physically.
set_property -dict {PACKAGE_PIN U18 IOSTANDARD LVCMOS33} [get_ports {cam_pclk}]
set_property -dict {PACKAGE_PIN Y7 IOSTANDARD LVCMOS33} [get_ports {cam_vsync}]
set_property -dict {PACKAGE_PIN W6 IOSTANDARD LVCMOS33} [get_ports {cam_href}]
set_property -dict {PACKAGE_PIN B20 IOSTANDARD LVCMOS33} [get_ports {cam_scl}]
set_property -dict {PACKAGE_PIN B19 IOSTANDARD LVCMOS33} [get_ports {cam_sda}]
set_property -dict {PACKAGE_PIN A20 IOSTANDARD LVCMOS33} [get_ports {cam_resetn}]
set_property -dict {PACKAGE_PIN Y9 IOSTANDARD LVCMOS33} [get_ports {cam_pwdn}]
# Original Arduino J3-10 SCL / J3-9 SDA; same connector wiring as V3.
set_property -dict {PACKAGE_PIN P15 IOSTANDARD LVCMOS33} [get_ports {sensor_scl}]
set_property -dict {PACKAGE_PIN P16 IOSTANDARD LVCMOS33} [get_ports {sensor_sda}]
set_property -dict {PACKAGE_PIN L16 IOSTANDARD TMDS_33} [get_ports {hdmi_out_clk_p}]
set_property -dict {PACKAGE_PIN L17 IOSTANDARD TMDS_33} [get_ports {hdmi_out_clk_n}]
set_property -dict {PACKAGE_PIN R19 IOSTANDARD LVCMOS33} [get_ports {hdmi_out_hpd[0]}]
set_property -dict {PACKAGE_PIN U7 IOSTANDARD LVCMOS33} [get_ports {cam_data[0]}]
set_property -dict {PACKAGE_PIN V7 IOSTANDARD LVCMOS33} [get_ports {cam_data[1]}]
set_property -dict {PACKAGE_PIN U8 IOSTANDARD LVCMOS33} [get_ports {cam_data[2]}]
set_property -dict {PACKAGE_PIN V8 IOSTANDARD LVCMOS33} [get_ports {cam_data[3]}]
set_property -dict {PACKAGE_PIN V10 IOSTANDARD LVCMOS33} [get_ports {cam_data[4]}]
set_property -dict {PACKAGE_PIN W10 IOSTANDARD LVCMOS33} [get_ports {cam_data[5]}]
set_property -dict {PACKAGE_PIN F19 IOSTANDARD LVCMOS33} [get_ports {cam_data[6]}]
set_property -dict {PACKAGE_PIN F20 IOSTANDARD LVCMOS33} [get_ports {cam_data[7]}]
set_property -dict {PACKAGE_PIN V13 IOSTANDARD LVCMOS33} [get_ports {joy_n[0]}]
set_property -dict {PACKAGE_PIN V15 IOSTANDARD LVCMOS33} [get_ports {joy_n[1]}]
set_property -dict {PACKAGE_PIN T15 IOSTANDARD LVCMOS33} [get_ports {joy_n[2]}]
# The supplied EC11 has a 10k series resistor on each A/B output and its own
# supply pull-up. An FPGA pull-up after that series resistor raises contact-low
# voltage. Rely on the module pull-ups; do not load these inputs internally.
set_property -dict {PACKAGE_PIN V17 IOSTANDARD LVCMOS33 PULLUP false} [get_ports enc_a]
set_property -dict {PACKAGE_PIN V18 IOSTANDARD LVCMOS33 PULLUP false} [get_ports enc_b]
set_property -dict {PACKAGE_PIN T16 IOSTANDARD LVCMOS33 PULLUP true} [get_ports enc_key_n]
set_property -dict {PACKAGE_PIN R16 IOSTANDARD LVCMOS33} [get_ports {joy_n[3]}]
set_property -dict {PACKAGE_PIN U17 IOSTANDARD LVCMOS33} [get_ports {joy_n[4]}]
set_property -dict {PACKAGE_PIN D19 IOSTANDARD LVCMOS33} [get_ports {buttons[0]}]
set_property -dict {PACKAGE_PIN D20 IOSTANDARD LVCMOS33} [get_ports {buttons[1]}]
set_property -dict {PACKAGE_PIN L20 IOSTANDARD LVCMOS33} [get_ports {buttons[2]}]
set_property -dict {PACKAGE_PIN L19 IOSTANDARD LVCMOS33} [get_ports {buttons[3]}]
set_property -dict {PACKAGE_PIN K17 IOSTANDARD TMDS_33} [get_ports {hdmi_out_data_p[0]}]
set_property -dict {PACKAGE_PIN K19 IOSTANDARD TMDS_33} [get_ports {hdmi_out_data_p[1]}]
set_property -dict {PACKAGE_PIN J18 IOSTANDARD TMDS_33} [get_ports {hdmi_out_data_p[2]}]
set_property -dict {PACKAGE_PIN K18 IOSTANDARD TMDS_33} [get_ports {hdmi_out_data_n[0]}]
set_property -dict {PACKAGE_PIN J19 IOSTANDARD TMDS_33} [get_ports {hdmi_out_data_n[1]}]
set_property -dict {PACKAGE_PIN H18 IOSTANDARD TMDS_33} [get_ports {hdmi_out_data_n[2]}]
# Initial 84MHz DVP timing budget from supplied 720p30 guide, not measured SI.
create_clock -name camera_pclk -period 11.904 [get_ports cam_pclk]
# 0x4740[5]=1 launches data on falling PCLK; IOB registers sample rising PCLK.
set_input_delay -clock camera_pclk -clock_fall -max 4.0 [get_ports {cam_data[*] cam_vsync cam_href}]
set_input_delay -clock camera_pclk -clock_fall -min 0.5 [get_ports {cam_data[*] cam_vsync cam_href}]
set_property PULLUP true [get_ports {joy_n[*] cam_scl cam_sda sensor_scl sensor_sda}]
# Match the user's previously accepted OV5640 raw-display hardware setup.
# A separately named external-pullup variant is also exported; never generalize
# this 3.3V control-IO confirmation to a different camera module.
set_property PULLUP true [get_ports {cam_scl cam_sda}]
set_clock_groups -asynchronous -group [get_clocks camera_pclk] -group [get_clocks -filter {NAME != camera_pclk}]
