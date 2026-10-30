`timescale 1ns/1ps
module tb_kernels;
reg clk=0;always #5 clk=~clk;
reg rst=0;integer cycle=0;always @(negedge clk)cycle=cycle+1;
reg [5:0] pointer_gray=0;wire [5:0] pointer_slot;integer p;
display_slot_decode pointer_test(pointer_gray,pointer_slot);
initial begin
 for(p=0;p<8;p=p+1)begin
  case(p)0:pointer_gray=0;1:pointer_gray=6;2:pointer_gray=1;3:pointer_gray=7;
   4:pointer_gray=3;5:pointer_gray=5;6:pointer_gray=2;7:pointer_gray=4;endcase
  #1;if(pointer_slot!=p/2)$fatal(1,"VDMA Gray pointer decoding failed");
 end
 pointer_gray=32;#1;if(pointer_slot!=63)$fatal(1,"Unknown VDMA pointer accepted");
end
reg [23:0] ci[0:18431],ce[0:18431];reg [63:0] cc[0:5];
reg [23:0] cd=0;reg cv=0,cu=0,cl=0;wire cr,co,ou,ol;wire [23:0] od;wire [31:0] oc,oq;
reg [31:0] cfg=0,q=0;wire ready=cycle%13>3;
chroma_filter #(.WIDTH(64)) cf(clk,rst,cd,cv,cr,cu,cl,cfg,q,od,co,ready,ou,ol,oc,oq);
integer cg=0,cj,cfm;reg cdone=0;
always @(posedge clk)if(co&&ready)begin
 if(od!==ce[cg]||ou!==(cg%3072==0)||ol!==(cg%64==63)||{oq,oc}!==cc[cg/3072])$fatal(1,"Chroma mismatch %0d got %h expected %h",cg,od,ce[cg]);
 cg=cg+1;
end
initial begin
 $readmemh("chroma_in.mem",ci);$readmemh("chroma_out.mem",ce);$readmemh("chroma_cfg.mem",cc);
 wait(rst);
 for(cj=0;cj<18432;cj=cj+1)begin
  @(negedge clk);cd=ci[cj];cv=1;cu=cj%3072==0;cl=cj%64==63;{q,cfg}=cc[cj/3072];
  @(posedge clk);while(!cr)@(posedge clk);
  @(negedge clk);cv=0;cu=0;cl=0;cfg=0;q=0;
  if(cj%7==0)repeat(2)@(negedge clk);
 end
 wait(cg==18432);cdone=1;
end
reg [112:0] ti[0:2399];reg [7:0] te[0:2399];reg [9:0] gains[0:47];
reg [112:0] td=0;reg tv=0,tu=0,gw=0,gc=0;reg [5:0] gi=0;reg [9:0] gv=256;
wire tr,to,gp;wire [7:0] ty;wire [31:0] tc;
local_tone_map #(.CONTEXT(32)) tm(clk,rst,td[39:32],td[47:40],td[15:0],td[31:16],td[79:48],td[111:80],td[112],32'hcafe1234,tv,tr,tu,ty,tc,to,ready,gw,gc,gi,gv,gp);
integer tg=0,tj;reg tdone=0;
always @(posedge clk)if(to&&ready)begin
 if(ty!==te[tg]||tc!==32'hcafe1234)$fatal(1,"Tone mismatch %0d got %d expected %d",tg,ty,te[tg]);tg=tg+1;
end
initial begin
 $readmemh("tone_in.mem",ti);$readmemh("tone_out.mem",te);$readmemh("gains.mem",gains);
 wait(rst);
 for(tj=0;tj<48;tj=tj+1)begin @(negedge clk);gw=1;gi=tj;gv=gains[tj];end
 @(negedge clk);gw=0;gc=1;@(negedge clk);gc=0;
 repeat(3)@(negedge clk);if(!gp)$fatal(1,"Tone premature commit");
 gw=1;gi=0;gv=0;@(negedge clk);gw=0;
 for(tj=0;tj<2400;tj=tj+1)begin
  @(negedge clk);td=ti[tj];tv=1;tu=tj==0;
  @(posedge clk);while(!tr)@(posedge clk);
  @(negedge clk);tv=0;tu=0;if(tj%7==0)repeat(2)@(negedge clk);
 end
 wait(tg==2400);tdone=1;
end
reg [23:0] se[0:6143];reg sv=0,su=0,sl=0,sw=0,sc=0,sena=1;reg [8:0] si=0;reg [7:0] sd=65;
wire sr,so,sp,sou,sol;wire [23:0] sod;
status_overlay #(.WIDTH(64)) osd(clk,rst,24'h123456,sv,sr,su,sl,sod,so,ready,sou,sol,sw,sc,sena,si,sd,sp);
integer sg=0,sj,sf;reg sdone=0;
always @(posedge clk)if(so&&ready)begin
 if(sod!==se[sg]||sou!==(sg%2048==0)||sol!==(sg%64==63))$fatal(1,"Text mismatch %0d got %h expected %h",sg,sod,se[sg]);sg=sg+1;
end
initial begin
 $readmemh("text_out.mem",se);wait(rst);
 for(sf=0;sf<3;sf=sf+1)begin
  for(sj=0;sj<384;sj=sj+1)begin @(negedge clk);sw=1;si=sj;sd=sf==0?65:66;end
  @(negedge clk);sw=0;sc=1;sena=sf<2;@(negedge clk);sc=0;
  repeat(3)@(negedge clk);if(!sp)$fatal(1,"Text premature commit");
  sw=1;si=0;sd=90;@(negedge clk);sw=0;
  for(sj=0;sj<2048;sj=sj+1)begin
   @(negedge clk);sv=1;su=sj==0;sl=sj%64==63;
   @(posedge clk);while(!sr)@(posedge clk);
   @(negedge clk);sv=0;su=0;sl=0;
  end
  wait(sg==(sf+1)*2048);wait(!sp);
 end
 sdone=1;
end
initial begin repeat(5)@(negedge clk);rst=1;wait(cdone&&tdone&&sdone);$display("PASS kernels chroma-edges raw-bypass local-bilinear bounds text-SOF guards stalls");$finish;end
initial begin #2000000;$fatal(1,"Kernels timeout");end
endmodule
