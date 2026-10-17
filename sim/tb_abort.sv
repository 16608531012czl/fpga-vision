`timescale 1ns/1ps
// Stopping acquisition must preserve outstanding AXI transfers until B arrives.
module tb_abort;
 reg clk=0;always #5 clk=~clk;
 reg resetn=0,enable=0,start=0,valid=0;
 reg [27:0] packet=0;
 wire ready,busy,done,error;
 wire [31:0] frame_id,errors,awaddr,wdata;
 wire [7:0] awlen;wire [2:0] awsize,awprot;
 wire [1:0] awburst;wire [3:0] awcache,wstrb;
 wire awlock,awvalid,wlast,wvalid,bready;
 reg awready=0,wready=0,bvalid=0;
 integer aw_count=0,w_count=0,b_count=0,beat=0,scenario=0;
 reg held_aw=0,held_w=0;reg [31:0] saved_aw;reg [36:0] saved_w;
 frame_writer #(.WIDTH(16),.HEIGHT(1)) writer(
 .aclk(clk),.aresetn(resetn),.capture_enable(enable),.start(start),.destination(32'h2000),
 .s_data(packet),.s_valid(valid),.s_ready(ready),.busy(busy),.done(done),.error(error),
 .frame_id(frame_id),.error_count(errors),.m_axi_awaddr(awaddr),.m_axi_awlen(awlen),
 .m_axi_awsize(awsize),.m_axi_awburst(awburst),.m_axi_awcache(awcache),.m_axi_awprot(awprot),
 .m_axi_awlock(awlock),.m_axi_awvalid(awvalid),.m_axi_awready(awready),
 .m_axi_wdata(wdata),.m_axi_wstrb(wstrb),.m_axi_wlast(wlast),.m_axi_wvalid(wvalid),
 .m_axi_wready(wready),.m_axi_bresp(2'b00),.m_axi_bvalid(bvalid),.m_axi_bready(bready));
 always @(posedge clk)if(resetn)begin
  if(held_aw&&(!awvalid||awaddr!==saved_aw))$fatal(1,"Stop cancelled/changed stalled AW");
  if(held_w&&(!wvalid||{wlast,wstrb,wdata}!==saved_w))$fatal(1,"Stop cancelled/changed stalled W");
  held_aw<=awvalid&&!awready;saved_aw<=awaddr;
  held_w<=wvalid&&!wready;saved_w<={wlast,wstrb,wdata};
  if(awvalid&&awready)begin
   if(awaddr!=32'h2000||awlen!=15||awsize!=2||awburst!=1)$fatal(1,"Invalid burst");
   aw_count<=aw_count+1;beat<=0;
  end
  if(wvalid&&wready)begin
   if(wdata!==beat||wstrb!=15||wlast!==(beat==15))$fatal(1,"Incomplete/incorrect burst after stop");
   beat<=beat+1;w_count<=w_count+1;
  end
  if(bvalid&&bready)b_count<=b_count+1;
 end
 task arm;begin
  @(negedge clk);enable=1;start=1;@(negedge clk);start=0;
  if(!busy)$fatal(1,"No capture armed");
 end endtask
 task pixels(input integer count);
 integer i;begin
  for(i=0;i<count;i=i+1)begin
   @(negedge clk);packet={2'b00,(i==15),(i==0),24'(i)};valid=1;
   @(posedge clk);while(!ready)@(posedge clk);
  end
  @(negedge clk);valid=0;
 end endtask
 task wait_busy;begin
  repeat(8)begin @(negedge clk);if(!busy||done)$fatal(1,"Busy cleared before AXI quiesced scenario=%0d",scenario);end
 end endtask
 task address;begin
  wait(awvalid);@(negedge clk);awready=1;
  @(negedge clk);awready=0;
 end endtask
 task send_data;begin
  @(negedge clk);wready=1;
  @(posedge clk);while(!(wlast&&wvalid))@(posedge clk);
  @(negedge clk);wready=0;
 end endtask
 task response;begin
  wait(bready);@(negedge clk);bvalid=1;@(negedge clk);bvalid=0;
 end endtask
 task check_stopped;begin
  repeat(2)@(negedge clk);
  if(busy||done||awvalid||wvalid||frame_id!=0)$fatal(1,"Aborted frame was published/left active");
  if(w_count!=16*aw_count||b_count!=aw_count)$fatal(1,"Unfinished AXI transaction");
 end endtask
 initial begin
  repeat(5)@(negedge clk);resetn=1;
  // No outstanding request: stop while waiting for SOF or a partial burst.
  arm();@(negedge clk);enable=0;check_stopped();
  arm();pixels(5);enable=0;check_stopped();
  // VALID was already presented; it cannot be withdrawn even before READY.
  scenario=1;arm();pixels(16);enable=0;wait_busy();address();
  wait_busy();send_data();wait_busy();response();check_stopped();
  // Stop halfway through a stalled W channel, then briefly re-enable. The
  // pending stop is latched, so this frame still cannot complete as valid.
  scenario=2;arm();pixels(16);address();
  @(negedge clk);wready=1;repeat(7)@(negedge clk);wready=0;enable=0;
  wait_busy();enable=1;wait_busy();send_data();wait_busy();response();check_stopped();
  // All W beats accepted but B response is still outstanding.
  scenario=3;arm();pixels(16);address();send_data();enable=0;
  wait_busy();response();check_stopped();
  // Waiting for the camera end token owns no outstanding AXI request.
  scenario=4;arm();pixels(16);address();send_data();response();enable=0;check_stopped();
  // Recovery: a later complete frame still publishes exactly once.
  scenario=5;arm();pixels(16);address();send_data();response();
  @(negedge clk);packet={2'b11,26'd0};valid=1;
  @(negedge clk);valid=0;
  if(!done||busy||error||frame_id!=1)$fatal(1,"No recovery after drained stop");
  if(w_count!=16*aw_count||b_count!=aw_count)$fatal(1,"Recovery AXI accounting");
  $display("PASS abort AW/W/B stalls drained, partial frame rejected, recovery frame_id=%0d",frame_id);$finish;
 end
 initial begin #100000;$fatal(1,"Abort watchdog scenario=%0d state=%0d",scenario,writer.state);end
endmodule
