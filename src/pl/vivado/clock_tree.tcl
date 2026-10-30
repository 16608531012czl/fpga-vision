# The routed IP checkpoint still carries its old scoped clock override.
# Re-derive only that clock from its real MMCM ancestor, preserving full
# serial timing analysis. The MMCM and BUFR /5 clocks are checked below.
set reverse_clock [get_clocks -filter {NAME =~ *rgb2dvi*/SerialClk}]
if {[llength $reverse_clock]>1} {error "Unexpected HDMI clock overrides"}
if {[llength $reverse_clock]} {
 set serial_name [get_property NAME $reverse_clock]
 set serial_target [get_pins $serial_name]
 set mmcm_out [get_pins -of_objects [get_cells -hier -filter {REF_NAME == MMCME2_ADV}] -filter {REF_PIN_NAME == CLKOUT0}]
 if {[llength $serial_target]!=1 || [llength $mmcm_out]!=1} {error "Expected real MMCM-to-SerialClk path"}
 create_generated_clock -name $serial_name -source $mmcm_out -divide_by 1 $serial_target
}
# Confirm both HDMI clocks still exist with the correct divide relationship.
set serial_pins [get_pins -of_objects [get_cells -hier -filter {REF_NAME == BUFIO}] -filter {REF_PIN_NAME == O}]
set pixel_pins [get_pins -of_objects [get_cells -hier -filter {REF_NAME == BUFR}] -filter {REF_PIN_NAME == O}]
set serial_clock [get_clocks -of_objects $serial_pins]
set pixel_clock [get_clocks -of_objects $pixel_pins]
if {[llength $serial_clock]!=1 || [llength $pixel_clock]!=1} {error "Missing/ambiguous HDMI clocks"}
if {abs([get_property PERIOD $pixel_clock]-5.0*[get_property PERIOD $serial_clock])>0.001} {error "HDMI clock ratio must remain 5:1"}
