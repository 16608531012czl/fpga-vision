"""Independent vectors for chroma, tile interpolation and SOF text switching."""
from pathlib import Path
import sys,ast
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'software'))
from visual_aid.local import spatial_chroma,mapped_luma

def write(path,items):path.write_text(''.join('%x\n'%int(i) for i in items))

def generate(work):
    rng=np.random.RandomState(463);inputs=[];outputs=[];cfgs=[]
    for f in range(6):
        cfg=4|16|(6<<17)|(8 if f%2 else 0)
        if f==4:cfg=(cfg&~7)|1
        quality=0 if f==5 else 256
        image=np.clip(60+rng.randint(-10,11,(48,64,3)),0,255).astype(np.uint8)
        image[:,35:39]=[180,40,30];image[20:23]=[8,8,8]
        expected=spatial_chroma(image,cfg,quality)
        inputs.extend((image[:,:,0].astype(int)<<16|image[:,:,1].astype(int)<<8|image[:,:,2]).ravel())
        outputs.extend((expected[:,:,0].astype(int)<<16|expected[:,:,1].astype(int)<<8|expected[:,:,2]).ravel())
        cfgs.append((quality<<32)|cfg)
    write(work/'chroma_in.mem',inputs);write(work/'chroma_out.mem',outputs);write(work/'chroma_cfg.mem',cfgs)
    gains=rng.randint(192,385,48);write(work/'gains.mem',gains)
    vec=[];out=[]
    for i in range(2400):
        x=int(rng.randint(1280));y=int(rng.randint(720));src=int(rng.randint(256));target=int(rng.randint(256))
        cfg=[4,12,3,1][i//600];q=128;bypass=i%11==0
        vec.append(x|(y<<16)|(src<<32)|(target<<40)|(cfg<<48)|(q<<80)|(int(bypass)<<112))
        out.append(mapped_luma(src,target,x,y,cfg,q,gains,bypass=bypass))
    write(work/'tone_in.mem',vec);write(work/'tone_out.mem',out)
    font=ast.literal_eval(ast.parse((ROOT/'tools/generate_font.py').read_text()).body[2].value)
    values=[]
    for f in range(3):
        for y in range(32):
            for x in range(64):
                px=x-12;py=y-12;lit=False
                if f<2 and 0<=px<1024 and 0<=py<96:
                    col=(px%16)//2;row=(py%16)//2
                    if col<5 and row<7:lit=font['A' if f==0 else 'B'][row][col]=='1'
                values.append(0x00ff00 if lit else 0x123456)
    write(work/'text_out.mem',values)

