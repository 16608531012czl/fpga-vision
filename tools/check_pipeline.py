"""Pixel-exact combined color NR -> reading -> local map -> OSD bypass test."""
from pathlib import Path
import json,hashlib,sys
import numpy as np
from verify import run
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'software'))
from visual_aid.local import spatial_chroma
from visual_aid.image import reference_enhance

def main():
 work=ROOT/'build/pipeline';work.mkdir(exist_ok=True)
 rng=np.random.RandomState(427);width,height,frames=64,48,6
 configs=[4|8|16|(6<<17),4|16|(6<<17),1|8|16|(4<<17),3|8|(8<<8),4,0]
 qualities=[0x111,0x111,0x11,0x51,0x11,0x111]
 inputs=[];outputs=[]
 pack=lambda rgb:(rgb[:,:,0].astype(int)<<16|rgb[:,:,1].astype(int)<<8|rgb[:,:,2]).ravel()
 for cfg,q in zip(configs,qualities):
  rgb=np.clip(60+rng.randint(-10,11,(height,width,3)),0,255).astype(np.uint8)
  rgb[:,35:39]=[180,40,30];rgb[20:23]=[8,8,8]
  clean=spatial_chroma(rgb,cfg,q)
  expected=reference_enhance(clean[:,:,::-1],cfg,np.arange(256,dtype=np.uint8),q)[:,:,::-1]
  inputs.extend(pack(rgb));outputs.extend(pack(expected))
 for name,values in [('input',inputs),('expected',outputs),('cfg',configs),('quality',qualities)]:
  (work/(name+'.mem')).write_text(''.join('%x\n'%int(v) for v in values))
 bench='''`timescale 1ns/1ps
module tb_pipeline;
reg clk=0;always #5 clk=~clk;reg rst=0;
reg [23:0] input_mem[0:18431],expected[0:18431];reg [31:0] configs[0:5],qualities[0:5];
reg [23:0] din=0;reg valid=0,user=0,last=0;wire ready;
reg [31:0] cfg=0,q=0;wire [23:0] cd,ed,od;wire cv,cr,cu,cl,ev,er,eu,el,ov,ou,ol;
wire [31:0] cc,cq,count;wire pending,bank,gp,tp;
reg [31:0] rng=32'hbac19014;reg output_ready=0;
always @(negedge clk)begin rng<={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};output_ready=rst&&rng[2:0]>1;end
chroma_filter #(.WIDTH(64)) cf(clk,rst,din,valid,ready,user,last,cfg,q,cd,cv,cr,cu,cl,cc,cq);
reading_enhance #(.WIDTH(64)) en(clk,rst,cd,cv,cr,cu,cl,ed,ev,er,eu,el,cc,1'b0,8'd0,8'd0,1'b0,pending,bank,count,cq,1'b0,1'b0,6'd0,10'd256,gp);
status_overlay #(.WIDTH(64)) osd(clk,rst,ed,ev,er,eu,el,od,ov,output_ready,ou,ol,1'b0,1'b0,1'b0,9'd0,8'd0,tp);
integer got=0,n;reg held=0;reg [25:0] previous;
always @(posedge clk)if(rst)begin
 if(held&&{ou,ol,od}!==previous)$fatal(1,"Combined output changed under stall");held=ov&&!output_ready;previous={ou,ol,od};
 if(ov&&output_ready)begin
  if(od!==expected[got]||ou!==(got%3072==0)||ol!==(got%64==63))$fatal(1,"Combined mismatch %0d got %h expected %h",got,od,expected[got]);got=got+1;
 end
end
initial begin
 $readmemh("input.mem",input_mem);$readmemh("expected.mem",expected);$readmemh("cfg.mem",configs);$readmemh("quality.mem",qualities);
 repeat(5)@(negedge clk);rst=1;
 for(n=0;n<18432;n=n+1)begin
  @(negedge clk);din=input_mem[n];valid=1;user=n%3072==0;last=n%64==63;
  if(user)begin cfg=configs[n/3072];q=qualities[n/3072];end
  else begin cfg=32'hffffffff;q=32'hffffffff;end
  @(posedge clk);while(!ready)@(posedge clk);
 end
 @(negedge clk);valid=0;user=0;last=0;wait(got==18432);repeat(10)@(posedge clk);
 if(count!=6)$fatal(1,"Combined count mismatch");$display("PASS pipeline combined NR reading mapping color OSD AXIS stalls config tags");$finish;
end
initial begin #2000000;$fatal(1,"Pipeline timeout");end
endmodule
'''
 path=work/'tb_pipeline.sv';path.write_text(bench)
 rtl=sorted((ROOT/'rtl').glob('*.sv'));hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in rtl}
 bins=Path(r'C:\Users\CHENZHELONG\Desktop\diansai\Vivado\2018.3\bin')
 run('pipeline_compile',[bins/'xvlog.bat','-sv']+rtl+[path],work)
 run('pipeline_elab',[bins/'xelab.bat','tb_pipeline','-s','pipeline_snapshot'],work)
 run('pipeline',[bins/'xsim.bat','pipeline_snapshot','-tclbatch',ROOT/'sim/run.tcl'],work,'PASS pipeline')
 assert hashes=={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in rtl}
 (ROOT/'reports/pipeline_stream.json').write_text(json.dumps({'passed':True,'pixels':18432,'sha256':hashes},indent=2))

if __name__=='__main__':main()
