// Render a completed raw DDR frame; scaling cannot backpressure DVP capture.
module canvas_writer #(parameter WIDTH=1280,HEIGHT=720)(
 input wire clk,resetn,enable,start,input wire [31:0] destination,view_cfg,roi_cfg,
 input wire [27:0] s_data,input wire s_valid,output wire s_ready,
 output reg busy=0,done=0,error=0,output reg [31:0] errors=0,
 output reg [31:0] awaddr=0,output wire [7:0] awlen,output wire [2:0] awsize,
 output wire [1:0] awburst,output wire [3:0] awcache,output wire [2:0] awprot,
 output wire awlock,output wire awvalid,input wire awready,
 output wire [63:0] wdata,output wire [7:0] wstrb,output wire wlast,wvalid,input wire wready,
 input wire [1:0] bresp,input wire bvalid,output wire bready,
 input wire [31:0] source_address,input wire source_done,
 output reg [31:0] araddr=0,output wire [7:0] arlen,output wire [2:0] arsize,
 output wire [1:0] arburst,output wire [3:0] arcache,output wire [2:0] arprot,
 output wire arlock,output wire arvalid,input wire arready,
 input wire [63:0] rdata,input wire [1:0] rresp,input wire rlast,rvalid,output wire rready);
 localparam IDLE=0,WAIT_SOURCE=1,OFFSET=2,BASE=3,READ_INIT=4,READ_ADDR=5,READ_DATA=6,DRAIN=7,
            ADDRESS=8,PREFETCH=9,DATA=10,RESPONSE=11;
 reg [3:0] state=IDLE;
 reg [31:0] source_base=0,row_offset=0,row_source=0,row_canvas=0;
 reg [15:0] rx=0,ry=0,rw=WIDTH,rh=HEIGHT,source_row=0,outx=0,read_index=0;
 reg [13:0] read_remaining=0,remaining=0;reg [4:0] read_beat=0;reg [3:0] beat=0;
 reg [1:0] up=0;reg split=1,down=1,aborting=0,read_bad=0;reg [1:0] drain=0;
 (* ram_style="block" *) reg [63:0] line_pixels[0:WIDTH/2-1];
 (* ram_style="block" *) reg [26:0] pair_row[0:WIDTH/2-1];
 reg [26:0] old_pair,pair_hold;reg avg_valid=0;reg [15:0] avg_index;
 reg [63:0] read_pair;reg read_half;
 wire [26:0] pair_sum={({1'b0,rdata[23:16]}+{1'b0,rdata[55:48]}),
                        ({1'b0,rdata[15:8]}+{1'b0,rdata[47:40]}),
                        ({1'b0,rdata[7:0]}+{1'b0,rdata[39:32]})};
 wire [9:0] ar={1'b0,old_pair[26:18]}+{1'b0,pair_hold[26:18]}+10'd2;
 wire [9:0] ag={1'b0,old_pair[17:9]}+{1'b0,pair_hold[17:9]}+10'd2;
 wire [9:0] ab={1'b0,old_pair[8:0]}+{1'b0,pair_hold[8:0]}+10'd2;
 wire r_accept=rvalid&&rready;
 wire normal_write=r_accept&&!down&&!aborting&&enable;
 wire line_write=normal_write||avg_valid;
 wire [15:0] write_index=avg_valid?avg_index>>1:read_index;
 wire [31:0] average_pixel={8'd0,ar[9:2],ag[9:2],ab[9:2]};
 wire [63:0] write_data=avg_valid?{average_pixel,average_pixel}:rdata;
 wire low_write=normal_write||(avg_valid&&!avg_index[0]);
 wire high_write=normal_write||(avg_valid&&avg_index[0]);
 wire [15:0] pane_x=(split&&outx>=WIDTH/2)?outx-WIDTH/2:outx;
 wire [15:0] next_x=(outx==WIDTH-2)?0:outx+2;
 wire [15:0] next_pane_x=(split&&next_x>=WIDTH/2)?next_x-WIDTH/2:next_x;
 wire [15:0] fetch_x=(state==PREFETCH?pane_x:next_pane_x)>>up;
 always @(posedge clk)begin
  if(line_write)begin
   if(low_write)line_pixels[write_index][31:0]<=write_data[31:0];
   if(high_write)line_pixels[write_index][63:32]<=write_data[63:32];
  end
  if(state==PREFETCH||(state==DATA&&wready&&beat!=15))begin
   read_pair<=line_pixels[fetch_x>>1];read_half<=fetch_x[0];
  end
  if(r_accept&&down)begin
   if(!source_row[0])pair_row[read_index]<=pair_sum;
   else begin old_pair<=pair_row[read_index];pair_hold<=pair_sum;avg_index<=read_index;end
  end
 end
 // Reads may start at any even ROI x. Limit bursts to a row and 4-KiB page.
 wire [9:0] page_beats=10'd512-{1'b0,araddr[11:3]};
 wire [4:0] limit_page=page_beats>=16?5'd16:page_beats[4:0];
 wire [4:0] read_length=read_remaining>=limit_page?limit_page:read_remaining[4:0];
 assign arlen=read_length-1;assign arsize=3;assign arburst=1;assign arcache=3;assign arprot=0;assign arlock=0;
 assign arvalid=state==READ_ADDR;assign rready=state==READ_DATA;
 assign s_ready=enable;
 assign awlen=15;assign awsize=3;assign awburst=1;assign awcache=3;assign awprot=0;assign awlock=0;
 assign awvalid=state==ADDRESS;assign wvalid=state==DATA;
 assign wdata=up==0?read_pair:read_half?{2{read_pair[63:32]}}:{2{read_pair[31:0]}};
 assign wstrb=255;assign wlast=beat==15;assign bready=state==RESPONSE;
 wire [1:0] requested_zoom=view_cfg[2:1];
 wire [15:0] requested_w=WIDTH>>requested_zoom,requested_h=HEIGHT>>requested_zoom;
 wire [15:0] requested_x={5'b0,roi_cfg[10:0]},requested_y={6'b0,roi_cfg[25:16]};
 wire outstanding=state==READ_ADDR||state==READ_DATA||state==ADDRESS||state==PREFETCH||state==DATA||state==RESPONSE;
 always @(posedge clk)begin
  if(!resetn)begin
   state<=IDLE;busy<=0;done<=0;error<=0;errors<=0;avg_valid<=0;aborting<=0;read_bad<=0;
   awaddr<=0;araddr<=0;outx<=0;source_row<=0;
  end else begin
   avg_valid<=r_accept&&down&&source_row[0]&&!aborting&&enable;
   if(!enable&&outstanding)aborting<=1;
   if(!enable&&!outstanding)begin state<=IDLE;busy<=0;done<=0;avg_valid<=0;aborting<=0;end
   else case(state)
    IDLE:if(start)begin
     done<=0;error<=0;aborting<=0;read_bad<=0;source_row<=0;
     if(destination[6:0]!=0||source_address[2:0]!=0||requested_zoom==3||
        requested_x+requested_w>WIDTH||requested_y+requested_h>HEIGHT||requested_x[0]||requested_y[0])begin error<=1;errors<=errors+1;end
     else begin
      busy<=1;state<=WAIT_SOURCE;rx<=requested_x;ry<=requested_y;rw<=requested_w;rh<=requested_h;
      source_base<=source_address;split<=view_cfg[0];down<=view_cfg[0]&&requested_zoom==0;
      up<=view_cfg[0]?(requested_zoom==2?1:0):requested_zoom;
      row_canvas<=destination+(view_cfg[0]?(HEIGHT/4)*WIDTH*4:0);
     end
    end
    WAIT_SOURCE:if(source_done)state<=OFFSET;
    OFFSET:begin row_offset<=ry*WIDTH*4;state<=BASE;end
    BASE:begin row_source<=source_base+row_offset+(rx<<2);state<=READ_INIT;end
    READ_INIT:begin araddr<=row_source;read_remaining<=rw>>1;read_index<=0;read_beat<=0;read_bad<=0;state<=READ_ADDR;end
    READ_ADDR:if(arready)begin read_beat<=0;state<=READ_DATA;end
    READ_DATA:if(rvalid)begin
     read_index<=read_index+1;read_beat<=read_beat+1;
     if(rresp!=0||rlast!=(read_beat==read_length-1))read_bad<=1;
     if(rlast||read_beat==read_length-1)begin
      if(aborting||!enable||read_bad||rresp!=0||rlast!=(read_beat==read_length-1))begin state<=IDLE;busy<=0;error<=1;errors<=errors+1;end
      else if(read_remaining==read_length)begin
       if(down&&!source_row[0])begin source_row<=source_row+1;row_source<=row_source+WIDTH*4;state<=READ_INIT;end
       else begin drain<=2;state<=DRAIN;end
      end else begin
       read_remaining<=read_remaining-read_length;araddr<=araddr+(read_length<<3);state<=READ_ADDR;
      end
     end
    end
    DRAIN:if(drain!=0)drain<=drain-1;else begin state<=ADDRESS;outx<=0;remaining<=(WIDTH/2)<<up;awaddr<=row_canvas;end
    ADDRESS:if(awready)begin state<=PREFETCH;beat<=0;end
    PREFETCH:state<=DATA;
    DATA:if(wready)begin outx<=next_x;beat<=beat+1;if(beat==15)state<=RESPONSE;end
    RESPONSE:if(bvalid)begin
     if(aborting||!enable||bresp!=0)begin state<=IDLE;busy<=0;done<=0;error<=1;errors<=errors+1;end
     else if(remaining==16)begin
      if(source_row==rh-1)begin busy<=0;done<=1;state<=IDLE;end
      else begin
       source_row<=source_row+1;row_source<=row_source+WIDTH*4;
       row_canvas<=row_canvas+(WIDTH*4<<up);state<=READ_INIT;
      end
     end else begin remaining<=remaining-16;awaddr<=awaddr+128;state<=ADDRESS;end
    end
    default:state<=IDLE;
   endcase
  end
 end
endmodule
