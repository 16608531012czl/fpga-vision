"""Bounded tile policy and integer reference kernels for the PL path."""
import numpy as np


def spatial_chroma(rgb,cfg,quality):
    image=np.asarray(rgb,dtype=np.int32);out=image.copy();h,w,_=image.shape
    strength=min(10,(cfg>>17)&15)
    if not (quality&256 and cfg&16 and cfg&7==4 and not cfg&65536 and strength):return out.astype(np.uint8)
    yy=(image[:,:,0]*77+image[:,:,1]*150+image[:,:,2]*29)>>8
    for y in range(2,h):
        for x in range(2,w):
            if cfg&8 and x<w//2+2:continue
            mean=image[y-2:y+1,x-2:x+1].sum(axis=(0,1))//9
            my=int((mean*np.array([77,150,29])).sum())>>8
            diff=mean-my-image[y,x]+yy[y,x]
            if abs(int(yy[y,x])-my)<=strength*3 and abs(diff[0]-diff[1])<=strength*6+8 and abs(diff[2]-diff[1])<=strength*6+8:
                out[y,x]=np.clip(image[y,x]+((diff*strength)>>4),0,255)
    return out.astype(np.uint8)


def mapped_luma(source,target,x,y,cfg,quality,gains,width=1280,height=720,bypass=False):
    split=bool(cfg&8)
    if not quality&128 or bypass or (cfg&7) not in (1,2,4) or source<24 or target>=224:return target
    if split and not height//4<=y<height*3//4:return target
    px=x%(width//2) if split else x;py=y-height//4 if split else y
    nx=max(0,min(7*256,px*256//(width//16 if split else width//8)-128))
    ny=max(0,min(5*256,py*256//(height//12 if split else height//6)-128))
    ix,fx=divmod(nx,256);iy,fy=divmod(ny,256);jx=min(7,ix+1);jy=min(5,iy+1)
    g=np.clip(np.asarray(gains,dtype=int).reshape(6,8),192,384)
    gain=((g[iy,ix]*(256-fx)+g[iy,jx]*fx)*(256-fy)+(g[jy,ix]*(256-fx)+g[jy,jx]*fx)*fy)>>16
    correction=max(-24,min(24,target*(int(gain)-256)>>8))
    weight=min(max(0,min(32,source-24)),max(0,min(32,224-target)))
    return max(0,min(255,target+((correction*weight)>>5)))


class TilePolicy:
    def __init__(self):
        self.gains=np.full((6,8),256.0);self.key=None

    def update(self,means,key,enabled=True):
        means=np.asarray(means,dtype=float).reshape(6,8)
        # Small contrast around the ROI average; dark noise and highlights
        # receive no additional local lift. Spatial smoothing prevents seams.
        target=float(means.mean())
        gains=np.clip((target+32)/(means+32),.75,1.5)*256 if enabled else np.full((6,8),256.)
        padded=np.pad(gains,1,mode='edge')
        smooth=sum(padded[j:j+6,i:i+8] for j in range(3) for i in range(3))/9
        # Start a new view at unity. Bound each subsequent change to 2/256
        # gain units, so parameter updates cannot cause a local brightness jump.
        self.gains=np.full((6,8),256.) if key!=self.key else self.gains+np.clip((smooth-self.gains)*.15,-2.,2.)
        self.key=key
        return np.rint(self.gains).astype(np.uint16)
