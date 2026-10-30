`timescale 1ns/1ps
// AXI-Lite AW and W are latched independently. Responses persist under stalls.
module assist_regs(
 input wire aclk,aresetn,
 input wire [7:0] s_axi_awaddr,input wire [2:0] s_axi_awprot,
 input wire s_axi_awvalid,output wire s_axi_awready,
 input wire [31:0] s_axi_wdata,input wire [3:0] s_axi_wstrb,
 input wire s_axi_wvalid,output wire s_axi_wready,
 output reg [1:0] s_axi_bresp=0,output reg s_axi_bvalid=0,input wire s_axi_bready,
 input wire [7:0] s_axi_araddr,input wire [2:0] s_axi_arprot,
 input wire s_axi_arvalid,output wire s_axi_arready,
 output reg [31:0] s_axi_rdata=0,output reg [1:0] s_axi_rresp=0,
 output reg s_axi_rvalid=0,input wire s_axi_rready,
 output reg capture_enable=0,capture_start=0,output reg [31:0] destination=0,cfg_word=32'h000008d1,
 output reg [5:0] gpio_out=6'h2f,input wire [3:0] gpio_in,
 input wire [31:0] cap_status,frame_id,dma_errors,camera_frames,overflows,malformed,display_frames,
 input wire [8:0] buttons,input wire lut_pending,lut_bank,
 input wire [31:0] encoder_position,encoder_short,encoder_long,encoder_invalid,
 input wire [2:0] encoder_status,
 input wire [31:0] capture_diagnostic,
 output reg lut_we=0,lut_commit=0,output reg [7:0] lut_index=0,lut_data=0,
 output reg [31:0] quality_word=32'h11,
 output reg [31:0] canvas_destination=0,view_cfg=0,roi_cfg=0,input wire [31:0] canvas_status,
 output reg [5:0] tile_read_index=0,input wire [23:0] tile_sum,
 input wire [15:0] tile_count,input wire [31:0] tile_frame_id,
 output reg text_we=0,text_commit=0,text_enable=0,output reg [8:0] text_index=0,
 output reg [7:0] text_data=32,input wire text_pending,
 input wire [5:0] display_slot,output wire [31:0] display_cfg_word,
 output reg gain_we=0,gain_commit=0,output reg [5:0] gain_index=0,
 output reg [9:0] gain_value=256,input wire gain_pending,
 output reg [31:0] canvas_source=0,output reg canvas_start=0);
 reg [31:0] slot_cfg[0:3];reg [1:0] slot_index=0;integer slot;
 assign display_cfg_word=view_cfg[7]?slot_cfg[display_slot[1:0]]:cfg_word;
 reg aw_full=0,w_full=0;reg [7:0] address;reg [31:0] data;reg [3:0] strobe;
 assign s_axi_awready=!aw_full&&!s_axi_bvalid;
 assign s_axi_wready=!w_full&&!s_axi_bvalid;
 assign s_axi_arready=!s_axi_rvalid;
 function [31:0] merge(input [31:0] old,input [31:0] val,input [3:0] mask);
 integer i;begin for(i=0;i<4;i=i+1)merge[i*8+:8]=mask[i]?val[i*8+:8]:old[i*8+:8];end endfunction
 wire [31:0] gpio_merged=merge({26'd0,gpio_out},data,strobe);
 always @(posedge aclk)begin
  if(!aresetn)begin
   aw_full<=0;w_full<=0;s_axi_bvalid<=0;s_axi_rvalid<=0;s_axi_bresp<=0;s_axi_rresp<=0;s_axi_rdata<=0;
   capture_enable<=0;capture_start<=0;destination<=0;cfg_word<=32'h000008d1;gpio_out<=6'h2f;lut_we<=0;lut_commit<=0;lut_index<=0;lut_data<=0;
   quality_word<=32'h11;canvas_source<=0;canvas_start<=0;
   canvas_destination<=0;view_cfg<=0;roi_cfg<=0;
   tile_read_index<=0;
   text_we<=0;text_commit<=0;text_enable<=0;text_index<=0;text_data<=32;slot_index<=0;
   for(slot=0;slot<4;slot=slot+1)slot_cfg[slot]<=32'h000008d1;
   gain_we<=0;gain_commit<=0;gain_index<=0;gain_value<=256;
  end else begin
   capture_start<=0;canvas_start<=0;lut_we<=0;lut_commit<=0;text_we<=0;text_commit<=0;gain_we<=0;gain_commit<=0;
   if(s_axi_awvalid&&s_axi_awready)begin aw_full<=1;address<=s_axi_awaddr;end
   if(s_axi_wvalid&&s_axi_wready)begin w_full<=1;data<=s_axi_wdata;strobe<=s_axi_wstrb;end
   if(s_axi_bvalid&&s_axi_bready)s_axi_bvalid<=0;
   if(aw_full&&w_full&&!s_axi_bvalid)begin
    aw_full<=0;w_full<=0;s_axi_bvalid<=1;s_axi_bresp<=0;
    case(address)
     8'h04:if(strobe[0])capture_enable<=data[0];
     8'h10:destination<=merge(destination,data,strobe);
     8'h14:if(strobe[0])capture_start<=data[0];
     8'h30:cfg_word<=merge(cfg_word,data,strobe);
     8'h3c:gpio_out<=gpio_merged[5:0];
     8'h44:if(strobe[0]&&strobe[1]&&!lut_pending)begin lut_index<=data[7:0];lut_data<=data[15:8];lut_we<=1;end
     8'h48:if(strobe[0]&&data[0]&&!lut_pending)lut_commit<=1;
     8'h78:quality_word<=merge(quality_word,data,strobe);
     8'h68:canvas_destination<=merge(canvas_destination,data,strobe);
     8'h6c:roi_cfg<=merge(roi_cfg,data,strobe);
     8'h70:view_cfg<=merge(view_cfg,data,strobe);
     8'h80:if(strobe[0])tile_read_index<=data[5:0];
     8'ha0:if(strobe[0]&&strobe[1]&&strobe[2]&&!text_pending)begin text_we<=1;text_index<=data[8:0];text_data<=data[23:16];end
     8'ha4:if(strobe[0]&&data[0]&&!text_pending)text_commit<=1;
     8'ha8:if(strobe[0])text_enable<=data[0];
     8'hb0:if(strobe[0])slot_index<=data[1:0];
     8'hb4:slot_cfg[slot_index]<=merge(slot_cfg[slot_index],data,strobe);
     8'h90:if(strobe[0]&&strobe[1]&&strobe[2]&&!gain_pending)begin gain_index<=data[5:0];gain_value<=data[17:8];gain_we<=1;end
     8'h94:if(strobe[0]&&data[0]&&!gain_pending)gain_commit<=1;
     8'hc0:canvas_source<=merge(canvas_source,data,strobe);
     8'hc4:if(strobe[0])canvas_start<=data[0];
     default:s_axi_bresp<=2'b10;
    endcase
   end
   if(s_axi_rvalid&&s_axi_rready)s_axi_rvalid<=0;
   if(s_axi_arvalid&&s_axi_arready)begin
    s_axi_rvalid<=1;s_axi_rresp<=0;
    case(s_axi_araddr)
     8'h00:s_axi_rdata<=32'h56410400;
     8'h04:s_axi_rdata<={31'd0,capture_enable};
     8'h08:s_axi_rdata<=1280;
     8'h0c:s_axi_rdata<=720;
     8'h10:s_axi_rdata<=destination;
     8'h18:s_axi_rdata<=cap_status;
     8'h1c:s_axi_rdata<=frame_id;
     8'h20:s_axi_rdata<=dma_errors;
     8'h24:s_axi_rdata<=camera_frames;
     8'h28:s_axi_rdata<=overflows;
     8'h2c:s_axi_rdata<=malformed;
     8'h30:s_axi_rdata<=cfg_word;
     8'h34:s_axi_rdata<=display_frames;
     8'h38:s_axi_rdata<={23'd0,buttons};
     8'h3c:s_axi_rdata<={26'd0,gpio_out};
     8'h40:s_axi_rdata<={28'd0,gpio_in};
     8'h4c:s_axi_rdata<={30'd0,lut_bank,lut_pending};
     8'h50:s_axi_rdata<=encoder_position;
     8'h54:s_axi_rdata<={29'd0,encoder_status};
     8'h58:s_axi_rdata<=encoder_short;
     8'h5c:s_axi_rdata<=encoder_long;
     8'h60:s_axi_rdata<=encoder_invalid;
     8'h64:s_axi_rdata<=capture_diagnostic;
     8'h78:s_axi_rdata<=quality_word;
     8'h68:s_axi_rdata<=canvas_destination;
     8'h6c:s_axi_rdata<=roi_cfg;
     8'h70:s_axi_rdata<=view_cfg;
     8'h74:s_axi_rdata<=canvas_status;
     8'h7c:s_axi_rdata<=32'h504c0002;
     8'h80:s_axi_rdata<={26'd0,tile_read_index};
     8'h84:s_axi_rdata<={8'd0,tile_sum};
     8'h88:s_axi_rdata<={16'd0,tile_count};
     8'h8c:s_axi_rdata<=tile_frame_id;
     8'ha8:s_axi_rdata<={31'd0,text_enable};
     8'hac:s_axi_rdata<={31'd0,text_pending};
     8'hb0:s_axi_rdata<={30'd0,slot_index};
     8'hb4:s_axi_rdata<=slot_cfg[slot_index];
     8'hb8:s_axi_rdata<={26'd0,display_slot};
     8'h98:s_axi_rdata<=32'hff;
     8'hc0:s_axi_rdata<=canvas_source;
     8'h9c:s_axi_rdata<={31'd0,gain_pending};
     default:begin s_axi_rdata<=0;s_axi_rresp<=2'b10;end
    endcase
   end
  end
 end
endmodule
