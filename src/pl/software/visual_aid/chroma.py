"""Color-noise suppression before PL tone/sharpen, with current luminance retained."""
import numpy as np
from .fastcompose import clean_chroma,available


def luma(image):
    p=image.astype(np.int32)
    return (29*p[:,:,0]+150*p[:,:,1]+77*p[:,:,2])>>8


def reference_chroma(image, strength, previous=None):
    """Portable specification; native code is used for real-time board output."""
    if not 0<=strength<=10:raise ValueError('Chroma strength must be 0..10')
    if not strength:return image.copy()
    p=image.astype(np.int32);yy=luma(p)
    cb,cr=p[:,:,0]-p[:,:,1],p[:,:,2]-p[:,:,1]
    amount=np.minimum(8,np.where(yy<96,strength,np.where(yy<160,strength*(160-yy)>>6,0)))
    padded=np.pad(p,((1,1),(1,1),(0,0)),mode='edge')
    h,w=yy.shape;sb,sr=cb*4,cr*4
    for dy,dx in ((0,1),(2,1),(1,0),(1,2)):
        q=padded[dy:dy+h,dx:dx+w];qb,qr=q[:,:,0]-q[:,:,1],q[:,:,2]-q[:,:,1]
        accept=(np.abs(luma(q)-yy)<=10+strength)&(np.abs(qb-cb)<=24+strength*4)&(np.abs(qr-cr)<=24+strength*4)
        sb+=np.where(accept,qb,cb);sr+=np.where(accept,qr,cr)
    nb=cb+((((sb+4)>>3)-cb)*amount>>3)
    nr=cr+((((sr+4)>>3)-cr)*amount>>3)
    if previous is not None:
        old=previous.astype(np.int32);ob,orr=old[:,:,0]-old[:,:,1],old[:,:,2]-old[:,:,1]
        accept=(amount>0)&(np.abs(luma(old)-yy)<=6+strength)&(np.abs(ob-cb)<=16+strength*2)&(np.abs(orr-cr)<=16+strength*2)
        nb=np.where(accept,(nb*(16-amount)+ob*amount+8)>>4,nb)
        nr=np.where(accept,(nr*(16-amount)+orr*amount+8)>>4,nr)
    green=(256*yy-29*nb-77*nr+128)>>8
    result=image.copy()
    for c,values in enumerate((green+nb,green,green+nr)):
        result[:,:,c]=np.where(amount>0,np.clip(values,0,255),image[:,:,c])
    return result


class ChromaDenoiser:
    def __init__(self):
        self.scratch=self.history=None
        self.key=None
        self.last=None
        self.valid=False

    def reset(self):
        self.valid=False
        self.key=None

    def apply(self,pane,strength,key,now):
        if not strength:
            self.reset();return False
        if self.scratch is None or self.scratch.shape!=pane.shape:
            self.scratch=np.empty(pane.shape,np.uint8)
            self.history=np.empty(pane.shape,np.uint8)
            self.valid=False
        valid=self.valid and key==self.key and self.last is not None and 0<now-self.last<0.2
        if not clean_chroma(pane,self.scratch,self.history,strength,valid):
            pane[:]=reference_temporal(pane,strength,self.history if valid else None)
            self.history[:]=pane
        self.key,self.last,self.valid=key,now,True
        return available()


def reference_temporal(image,strength,previous=None):
    if not 0<=strength<=10:raise ValueError('Chroma strength must be 0..10')
    if not strength or previous is None:return image.copy()
    p=image.astype(np.int32);old=previous.astype(np.int32);yy=luma(p)
    cb,cr=p[:,:,0]-p[:,:,1],p[:,:,2]-p[:,:,1]
    ob,orr=old[:,:,0]-old[:,:,1],old[:,:,2]-old[:,:,1]
    amount=np.minimum(8,np.where(yy<96,strength,np.where(yy<160,strength*(160-yy)>>6,0)))
    accept=(np.abs(luma(old)-yy)<=6+strength)&(np.abs(ob-cb)<=16+strength*2)&(np.abs(orr-cr)<=16+strength*2)
    weight=np.where(accept,amount,0)
    nb=(cb*(16-weight)+ob*weight+8)>>4;nr=(cr*(16-weight)+orr*weight+8)>>4
    green=(256*yy-29*nb-77*nr+128)>>8
    result=image.copy()
    for c,values in enumerate((green+nb,green,green+nr)):
        result[:,:,c]=np.where(weight>0,np.clip(values,0,255),image[:,:,c])
    return result


def enhanced_pane(canvas,bounds,split):
    """Return only active pixels, excluding letterbox and the original pane."""
    h,w=canvas.shape[:2];pw=w//2 if split else w
    rw,rh=bounds[2:]
    scale=min(pw/rw,h/rh);dw,dh=max(1,int(rw*scale)),max(1,int(rh*scale))
    x=(pw-dw)//2+(pw if split else 0);y=(h-dh)//2
    return canvas[y:y+dh,x:x+dw]
