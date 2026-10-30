`timescale 1ns/1ps
module tb_canvas;
 parameter WIDTH=64,HEIGHT=48;
 localparam N=WIDTH*HEIGHT;
 reg clk=0;always #5 clk=~clk;
 reg resetn=0,enable=1,start=0,s_valid=0;reg [27:0] s_data=0;wire s_ready;
 reg [31:0] destination=4096,view_cfg=0,roi_cfg=0;
 reg offset_roi=0;
 wire busy,done,error;wire [31:0] errors,awaddr;wire [63:0] wdata;wire [7:0] wstrb;
 wire canvas_ready,stats_ready,stats_done;reg [5:0] read_index=0;
 wire [23:0] read_sum;wire [15:0] sample_count;wire [31:0] published_id;reg [31:0] capture_id=0;
 wire [7:0] awlen;wire [2:0] awsize,awprot;wire [1:0] awburst;wire [3:0] awcache;
 wire awlock,awvalid,wlast,wvalid,bready;
 reg awready=0,wready=0,bvalid=0;reg [1:0] bresp=0;reg inject_error=0;
 reg [31:0] source_address=32'h100000;reg source_done=0;
 wire [31:0] araddr;wire [7:0] arlen;wire [2:0] arsize,arprot;wire [1:0] arburst;wire [3:0] arcache;
 wire arlock,arvalid,rready;reg arready=0,rvalid=0,rlast=0;reg [63:0] rdata=0;reg [1:0] rresp=0;
 reg have_ar=0,inject_read_error=0;reg [31:0] read_address;integer rbeat=0,rbeats=0,source_pixel;
 assign s_ready=canvas_ready&&stats_ready;
 canvas_writer #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) dut(.s_valid(s_valid&&stats_ready),.s_ready(canvas_ready),.*);
 frame_tiles #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) tiles(.clk(clk),.resetn(resetn),.enable(enable),.start(start),
 .capture_ok(done&&!error),.roi_cfg(roi_cfg),.view_cfg(view_cfg),.capture_id(capture_id),
 .s_valid(s_valid&&canvas_ready),.s_ready(stats_ready),.s_data(s_data),.read_index(read_index),
 .read_sum(read_sum),.sample_count(sample_count),.published_id(published_id),.done(stats_done));
 always @(posedge clk)if(resetn&&s_valid&&s_ready&&s_data[27])capture_id<=capture_id+1;
 reg [31:0] memory[0:N+31];reg [31:0] rng=32'habc14532,address=0;reg have_aw=0;
 integer beat=0,delay_b=0,writes=0;reg held_aw=0,held_w=0;reg [31:0] saved_aw;reg [72:0] saved_w;
 always @(negedge clk)begin
  rng<={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
  awready=!have_aw&&!bvalid&&delay_b==0&&rng[1];wready=have_aw&&rng[3:0]!=0;
  arready=!have_ar&&rng[2];
  if(!rvalid||rready)begin
   rvalid=have_ar&&rng[2:0]!=0;
   source_pixel=(read_address-source_address)/4+rbeat*2;
   rdata={8'd0,pixel((source_pixel+1)%WIDTH,(source_pixel+1)/WIDTH),8'd0,pixel(source_pixel%WIDTH,source_pixel/WIDTH)};
   rlast=rbeat==rbeats-1;rresp=inject_read_error?2:0;
  end
 end
 always @(posedge clk)begin
  if(!resetn)begin have_ar<=0;rbeat<=0;end
  else begin
   if(arvalid&&arready)begin
    if(!source_done||araddr<source_address||araddr+(arlen+1)*8>source_address+N*4||
       araddr[2:0]!=0||arsize!=3||arburst!=1||arlen>15||araddr[11:0]+(arlen+1)*8>4096)$fatal(1,"Canvas invalid source read");
    have_ar<=1;read_address<=araddr;rbeat<=0;rbeats<=arlen+1;
   end
   if(rvalid&&rready)begin rbeat<=rbeat+1;if(rlast)have_ar<=0;end
  end
 end
 always @(posedge clk)begin
  if(!resetn)begin have_aw<=0;bvalid<=0;delay_b<=0;held_aw<=0;held_w<=0;writes<=0;end
  else begin
   if(held_aw&&(!awvalid||awaddr!==saved_aw))$fatal(1,"Canvas AW changed under stall/stop");
   if(held_w&&(!wvalid||{wlast,wstrb,wdata}!==saved_w))$fatal(1,"Canvas W changed under stall/stop");
   held_aw<=awvalid&&!awready;saved_aw<=awaddr;
   held_w<=wvalid&&!wready;saved_w<={wlast,wstrb,wdata};
   if(awvalid&&awready)begin
    if(awlen!=15||awsize!=3||awburst!=1||awaddr[6:0]!=0||awaddr[11:0]>3968)$fatal(1,"Canvas bad AXI geometry");
    if(awaddr<4096||awaddr+128>4096+N*4)$fatal(1,"Canvas out-of-bounds write");
    address<=awaddr;have_aw<=1;beat<=0;
   end
   if(wvalid&&wready)begin
    if(wlast!==(beat==15)||wstrb!=255)$fatal(1,"Canvas burst framing");
    memory[16+(address-4096)/4+beat*2]<=wdata[31:0];
    memory[17+(address-4096)/4+beat*2]<=wdata[63:32];writes<=writes+1;beat<=beat+1;
    if(wlast)begin have_aw<=0;delay_b<=3+rng[5:4];bresp<=inject_error?2:0;end
   end
   if(delay_b!=0)begin delay_b<=delay_b-1;if(delay_b==1)bvalid<=1;end
   if(bvalid&&bready)bvalid<=0;
  end
 end
 function [23:0] pixel(input integer xx,input integer yy);
 begin pixel={8'((xx*7+yy*11)%256),8'((xx*3+yy*17)%256),8'((xx*13+yy*5)%256)};end endfunction
 task send(input [27:0] value);
 begin
  @(negedge clk);s_data=value;s_valid=1;
  @(posedge clk);while(!s_ready)@(posedge clk);
  @(negedge clk);s_valid=0;
 end endtask
 task frame;
 integer xx,yy;reg [27:0] value;
 begin
  for(yy=0;yy<HEIGHT;yy=yy+1)for(xx=0;xx<WIDTH;xx=xx+1)begin
   value={4'b0,pixel(xx,yy)};value[24]=(xx==0&&yy==0);value[25]=(xx==WIDTH-1);send(value);
  end
  send(28'hc000000);
  source_done=1;
 end endtask
 task arm(input integer zoom,input integer split);
 integer rx,ry;
 begin
  rx=((WIDTH-(WIDTH>>zoom))/2)&~1;ry=((HEIGHT-(HEIGHT>>zoom))/2)&~1;
  if(offset_roi&&zoom!=0)begin rx=2;ry=2;end
  view_cfg=128|(zoom<<1)|split;roi_cfg=rx|(ry<<16);source_done=0;
  @(negedge clk);start=1;@(negedge clk);start=0;
 end endtask
 task verify_frame(input integer zoom,input integer split);
 integer xx,yy,rx,ry,up,px,py,x0,y0,c,sum,j;reg [23:0] expected,p0,p1,p2,p3;
 begin
  rx=((WIDTH-(WIDTH>>zoom))/2)&~1;ry=((HEIGHT-(HEIGHT>>zoom))/2)&~1;
  if(offset_roi&&zoom!=0)begin rx=2;ry=2;end
  up=split?(zoom==2?1:0):zoom;
  for(yy=0;yy<HEIGHT;yy=yy+1)for(xx=0;xx<WIDTH;xx=xx+1)begin
   expected=0;
   if(!split||(yy>=HEIGHT/4&&yy<HEIGHT*3/4))begin
    px=split?(xx%(WIDTH/2)):xx;py=split?yy-HEIGHT/4:yy;
    if(split&&zoom==0)begin
     x0=rx+px*2;y0=ry+py*2;p0=pixel(x0,y0);p1=pixel(x0+1,y0);p2=pixel(x0,y0+1);p3=pixel(x0+1,y0+1);
     for(c=0;c<3;c=c+1)begin sum=p0[c*8+:8]+p1[c*8+:8]+p2[c*8+:8]+p3[c*8+:8]+2;expected[c*8+:8]=sum>>2;end
    end else expected=pixel(rx+(px>>up),ry+(py>>up));
   end
   if(memory[16+yy*WIDTH+xx]!=={8'b0,expected})$fatal(1,"Canvas mismatch z%0d split%0d x%0d y%0d got%h expected%h",zoom,split,xx,yy,memory[16+yy*WIDTH+xx],expected);
  end
  for(j=0;j<16;j=j+1)if(memory[j]!==32'hfeedface||memory[N+16+j]!==32'hfeedface)$fatal(1,"Canvas guard corrupt");
 end endtask
 task verify_tiles(input integer zoom);
 integer tx,ty,xx,yy,rx,ry,tw,th,total;reg [23:0] p;
 begin
  rx=((WIDTH-(WIDTH>>zoom))/2)&~1;ry=((HEIGHT-(HEIGHT>>zoom))/2)&~1;
  if(offset_roi&&zoom!=0)begin rx=2;ry=2;end
  tw=(WIDTH/8)>>zoom;th=(HEIGHT/6)>>zoom;
  wait(stats_done);repeat(3)@(negedge clk);
  if(published_id!=capture_id||sample_count!=tw*th)$fatal(1,"Tile publication/frame association");
  for(ty=0;ty<6;ty=ty+1)for(tx=0;tx<8;tx=tx+1)begin
   total=0;
   for(yy=ry+ty*th;yy<ry+(ty+1)*th;yy=yy+1)for(xx=rx+tx*tw;xx<rx+(tx+1)*tw;xx=xx+1)begin
    p=pixel(xx,yy);total=total+((77*p[23:16]+150*p[15:8]+29*p[7:0])>>8);
   end
   read_index=ty*8+tx;repeat(3)@(negedge clk);
   if(read_sum!==total)$fatal(1,"Tile %0d zoom%0d got%0d expected%0d",read_index,zoom,read_sum,total);
  end
 end endtask
 integer zoom,split,j;
 initial begin
  repeat(5)@(negedge clk);resetn=1;
  for(zoom=0;zoom<3;zoom=zoom+1)for(split=0;split<2;split=split+1)begin
   for(j=0;j<N+32;j=j+1)memory[j]=(j<16||j>=N+16)?32'hfeedface:0;
   arm(zoom,split);frame();wait(done||error);
   if(error||busy)$fatal(1,"Canvas good frame rejected");
   verify_frame(zoom,split);
   verify_tiles(zoom);
  end
  offset_roi=1;
  for(zoom=1;zoom<3;zoom=zoom+1)for(split=0;split<2;split=split+1)begin
   for(j=0;j<N+32;j=j+1)memory[j]=(j<16||j>=N+16)?32'hfeedface:0;
   arm(zoom,split);frame();wait(done||error);if(error)$fatal(1,"Panned ROI rejected");
   verify_frame(zoom,split);verify_tiles(zoom);
  end
  offset_roi=0;
  arm(0,1);inject_error=1;frame();wait(!busy);
  if(done||!error)$fatal(1,"Canvas AXI error published");inject_error=0;
  arm(1,0);inject_read_error=1;frame();wait(!busy);
  if(done||!error)$fatal(1,"Canvas AXI read error published");inject_read_error=0;
  arm(0,1);
  fork
   frame();
   begin wait(wvalid);@(negedge clk);enable=0;@(negedge clk);enable=1;end
  join
  wait(!busy);if(done||!error)$fatal(1,"Canvas stop published partial frame");
  arm(1,0);
  fork
   frame();
   begin wait(rvalid&&rready);@(negedge clk);enable=0;@(negedge clk);enable=1;end
  join
  wait(!busy);if(done||!error)$fatal(1,"Canvas read stop status done%0d error%0d state%0d abort%0d",done,error,dut.state,dut.aborting);
  $display("PASS canvas 6 ROI/scaling layouts AXI stalls error abort guards %0dx%0d",WIDTH,HEIGHT);$finish;
 end
 initial begin #2000000000;$fatal(1,"Canvas timeout state%0d source_row%0d read_index%0d",dut.state,dut.source_row,dut.read_index);end
endmodule
