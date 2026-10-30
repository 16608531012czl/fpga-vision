/* Exact 2x bilinear BGRX reduction (four-pixel average with rounding).
 * Cortex-A9 NEON accelerates the common side-by-side 720p comparison view.
 * No capture writes, allocations, threads, cache operations or DMA ownership. */
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#if defined(__ARM_NEON)
#include <arm_neon.h>
#endif
/* AXI-Lite device mapping, caller has checked LUT-not-pending and owns it.
 * Volatile stores retain every indexed write to the single streaming port. */
int load_gamma(volatile uint32_t *regs, const uint8_t *lut) {
    if (!regs || !lut) return -1;
    for (unsigned i=0; i<256; ++i) regs[0x44/4]=i|((uint32_t)lut[i]<<8);
    __sync_synchronize();
    regs[0x48/4]=1;
    __sync_synchronize();
    return 0;
}
int half_bgrx(const uint8_t *src, int src_stride, uint8_t *dst,
              uint8_t *second, int dst_stride, int width, int height) {
    if (!src || !dst || width <= 0 || height <= 0 || width > 4096 ||
        height > 4096 || src_stride < width*8 || dst_stride < width*4) return -1;
    for (int y=0; y<height; ++y) {
        const uint8_t *a=src+(ptrdiff_t)(2*y)*src_stride, *b=a+src_stride;
        uint8_t *out=dst+(ptrdiff_t)y*dst_stride;
        uint8_t *copy=second ? second+(ptrdiff_t)y*dst_stride : NULL;
        int x=0;
#if defined(__ARM_NEON)
        for (; x+4<=width; x+=4) {
            uint32x4x2_t va=vld2q_u32((const uint32_t *)(a+x*8));
            uint32x4x2_t vb=vld2q_u32((const uint32_t *)(b+x*8));
            uint8x16_t p=vreinterpretq_u8_u32(va.val[0]), q=vreinterpretq_u8_u32(va.val[1]);
            uint8x16_t r=vreinterpretq_u8_u32(vb.val[0]), s=vreinterpretq_u8_u32(vb.val[1]);
            uint16x8_t lo=vaddl_u8(vget_low_u8(p),vget_low_u8(q));
            uint16x8_t hi=vaddl_u8(vget_high_u8(p),vget_high_u8(q));
            lo=vaddw_u8(vaddw_u8(lo,vget_low_u8(r)),vget_low_u8(s));
            hi=vaddw_u8(vaddw_u8(hi,vget_high_u8(r)),vget_high_u8(s));
            uint8x16_t pixels=vcombine_u8(vrshrn_n_u16(lo,2),vrshrn_n_u16(hi,2));
            vst1q_u8(out+x*4,pixels);
            if(copy)vst1q_u8(copy+x*4,pixels);
        }
#endif
        for (; x<width; ++x) for(int c=0;c<4;++c) {
            uint8_t pixel=(a[x*8+c]+a[x*8+4+c]+b[x*8+c]+b[x*8+4+c]+2)>>2;
            out[x*4+c]=pixel;if(copy)copy[x*4+c]=pixel;
        }
    }
    return 0;
}

static int luma(const uint8_t *p) { return (29*p[0]+150*p[1]+77*p[2])>>8; }
static int absolute(int v) { return v<0 ? -v : v; }
static uint8_t clipped(int v) { return v<0 ? 0 : v>255 ? 255 : v; }
#if defined(__ARM_NEON)
static int16x8_t luma8(uint8x8x4_t p) {
    uint16x8_t y=vmull_u8(p.val[0],vdup_n_u8(29));
    y=vmlal_u8(y,p.val[1],vdup_n_u8(150));y=vmlal_u8(y,p.val[2],vdup_n_u8(77));
    return vreinterpretq_s16_u16(vshrq_n_u16(y,8));
}
static int16x8_t chroma8(uint8x8x4_t p,int c) {
    return vreinterpretq_s16_u16(vsubl_u8(p.val[c],p.val[1]));
}
static int16x8_t green8(int16x8_t yy,int16x8_t cb,int16x8_t cr) {
    int32x4_t lo=vshlq_n_s32(vmovl_s16(vget_low_s16(yy)),8);
    int32x4_t hi=vshlq_n_s32(vmovl_s16(vget_high_s16(yy)),8);
    lo=vmlsl_n_s16(lo,vget_low_s16(cb),29);lo=vmlsl_n_s16(lo,vget_low_s16(cr),77);
    hi=vmlsl_n_s16(hi,vget_high_s16(cb),29);hi=vmlsl_n_s16(hi,vget_high_s16(cr),77);
    return vcombine_s16(vshrn_n_s32(vaddq_s32(lo,vdupq_n_s32(128)),8),
                       vshrn_n_s32(vaddq_s32(hi,vdupq_n_s32(128)),8));
}
#endif

/* Chroma only: spatial filtering guided by luminance and color distance,
 * followed by motion-gated temporal blending. Preserve the current Y, so
 * black text edges are not blurred and moving objects retain current luma.
 * Scratch/history are caller-owned contiguous BGRX, never DMA input buffers.
 * Run before OSD and PL enhancement, on the enhanced pane only. */
int clean_chroma(uint8_t *pane, int stride, uint8_t *scratch, uint8_t *history,
                 int width, int height, int strength, int history_valid) {
    if (!pane || !scratch || !history || width<=0 || height<=0 || width>4096 ||
        height>4096 || stride<width*4 || strength<0 || strength>10) return -1;
    if (!strength) return 0;
    for (int y=0;y<height;++y)
        memcpy(scratch+(ptrdiff_t)y*width*4,pane+(ptrdiff_t)y*stride,width*4);
    for (int y=0;y<height;++y) {
      int x=0;
#if defined(__ARM_NEON)
      /* Eight pixels per iteration. Clamp the horizontal neighbor at each
       * vector boundary using vext, without crossing a row or guard region. */
      for(;x+8<=width;x+=8) {
        const uint8_t *p=scratch+(y*width+x)*4;
        uint8_t *out=pane+(ptrdiff_t)y*stride+x*4,*old=history+(y*width+x)*4;
        uint8x8x4_t center=vld4_u8(p),left,right;
        uint8x8x4_t up=vld4_u8(scratch+((y>0?y-1:y)*width+x)*4);
        uint8x8x4_t down=vld4_u8(scratch+((y+1<height?y+1:y)*width+x)*4);
        if(x)left=vld4_u8(p-4);
        else for(int c=0;c<4;++c)left.val[c]=vext_u8(vdup_n_u8(p[c]),center.val[c],7);
        if(x+8<width)right=vld4_u8(p+4);
        else for(int c=0;c<4;++c)right.val[c]=vext_u8(center.val[c],vdup_n_u8(p[28+c]),1);
        int16x8_t yy=luma8(center),cb=chroma8(center,0),cr=chroma8(center,2);
        int16x8_t amount=vshrq_n_s16(vmulq_n_s16(vsubq_s16(vdupq_n_s16(160),yy),strength),6);
        amount=vbslq_s16(vcltq_s16(yy,vdupq_n_s16(96)),vdupq_n_s16(strength),amount);
        amount=vmaxq_s16(vdupq_n_s16(0),vminq_s16(vdupq_n_s16(8),amount));
        int16x8_t sb=vshlq_n_s16(cb,2),sr=vshlq_n_s16(cr,2);
        uint8x8x4_t neighbors[4]={up,down,left,right};
        for(int k=0;k<4;++k) {
            int16x8_t qb=chroma8(neighbors[k],0),qr=chroma8(neighbors[k],2);
            uint16x8_t accept=vcleq_s16(vabsq_s16(vsubq_s16(luma8(neighbors[k]),yy)),vdupq_n_s16(10+strength));
            accept=vandq_u16(accept,vcleq_s16(vabsq_s16(vsubq_s16(qb,cb)),vdupq_n_s16(24+strength*4)));
            accept=vandq_u16(accept,vcleq_s16(vabsq_s16(vsubq_s16(qr,cr)),vdupq_n_s16(24+strength*4)));
            sb=vaddq_s16(sb,vbslq_s16(accept,qb,cb));sr=vaddq_s16(sr,vbslq_s16(accept,qr,cr));
        }
        int16x8_t nb=vaddq_s16(cb,vshrq_n_s16(vmulq_s16(vsubq_s16(vshrq_n_s16(vaddq_s16(sb,vdupq_n_s16(4)),3),cb),amount),3));
        int16x8_t nr=vaddq_s16(cr,vshrq_n_s16(vmulq_s16(vsubq_s16(vshrq_n_s16(vaddq_s16(sr,vdupq_n_s16(4)),3),cr),amount),3));
        if(history_valid) {
            uint8x8x4_t previous=vld4_u8(old);
            int16x8_t ob=chroma8(previous,0),orr=chroma8(previous,2);
            uint16x8_t accept=vcleq_s16(vabsq_s16(vsubq_s16(luma8(previous),yy)),vdupq_n_s16(6+strength));
            accept=vandq_u16(accept,vcleq_s16(vabsq_s16(vsubq_s16(ob,cb)),vdupq_n_s16(16+strength*2)));
            accept=vandq_u16(accept,vcleq_s16(vabsq_s16(vsubq_s16(orr,cr)),vdupq_n_s16(16+strength*2)));
            int16x8_t weight=vbslq_s16(accept,amount,vdupq_n_s16(0));
            nb=vshrq_n_s16(vaddq_s16(vaddq_s16(vmulq_s16(nb,vsubq_s16(vdupq_n_s16(16),weight)),vmulq_s16(ob,weight)),vdupq_n_s16(8)),4);
            nr=vshrq_n_s16(vaddq_s16(vaddq_s16(vmulq_s16(nr,vsubq_s16(vdupq_n_s16(16),weight)),vmulq_s16(orr,weight)),vdupq_n_s16(8)),4);
        }
        int16x8_t green=green8(yy,nb,nr);
        uint8x8x4_t result=center;
        uint8x8_t active=vmovn_u16(vcgtq_s16(amount,vdupq_n_s16(0)));
        result.val[0]=vbsl_u8(active,vqmovun_s16(vaddq_s16(green,nb)),center.val[0]);
        result.val[1]=vbsl_u8(active,vqmovun_s16(green),center.val[1]);
        result.val[2]=vbsl_u8(active,vqmovun_s16(vaddq_s16(green,nr)),center.val[2]);
        vst4_u8(out,result);vst4_u8(old,result);
      }
#endif
      for (;x<width;++x) {
        int pos=(y*width+x)*4;
        const uint8_t *p=scratch+pos;
        uint8_t *out=pane+(ptrdiff_t)y*stride+x*4, *old=history+pos;
        int yy=luma(p), cb=(int)p[0]-p[1], cr=(int)p[2]-p[1];
        /* Taper the filter on bright pixels; leave highlights untouched. */
        int amount=yy<96 ? strength : yy<160 ? (strength*(160-yy))>>6 : 0;
        if(amount>8) amount=8;
        int sb=cb*4,sr=cr*4;
        const uint8_t *neighbors[4]={scratch+((y>0?y-1:y)*width+x)*4,
            scratch+((y+1<height?y+1:y)*width+x)*4,
            scratch+(y*width+(x>0?x-1:x))*4,
            scratch+(y*width+(x+1<width?x+1:x))*4};
        for(int k=0;k<4;++k) {
            const uint8_t *q=neighbors[k];
            int qb=(int)q[0]-q[1],qr=(int)q[2]-q[1];
            int accept=absolute(luma(q)-yy)<=10+strength &&
                       absolute(qb-cb)<=24+strength*4 && absolute(qr-cr)<=24+strength*4;
            sb+=accept?qb:cb;sr+=accept?qr:cr;
        }
        int nb=cb+((((sb+4)>>3)-cb)*amount>>3);
        int nr=cr+((((sr+4)>>3)-cr)*amount>>3);
        if(history_valid && amount && absolute(luma(old)-yy)<=6+strength &&
            absolute(((int)old[0]-old[1])-cb)<=16+strength*2 &&
            absolute(((int)old[2]-old[1])-cr)<=16+strength*2) {
            int weight=amount>8?8:amount;
            nb=(nb*(16-weight)+((int)old[0]-old[1])*weight+8)>>4;
            nr=(nr*(16-weight)+((int)old[2]-old[1])*weight+8)>>4;
        }
        /* floor division by 256 gives the closest BGR triplet to the same Y. */
        int green=(256*yy-29*nb-77*nr+128)>>8;
        if(!amount) { out[0]=p[0];out[1]=p[1];out[2]=p[2]; }
        else { out[0]=clipped(green+nb);out[1]=clipped(green);out[2]=clipped(green+nr); }
        memcpy(old,out,4);
      }
    }
    return 0;
}

/* Real-time path: ISP UV average handles spatial color noise. Use temporal
 * chroma only here to keep the ARM budget bounded, with the same motion gate. */
int load_parameters(volatile uint32_t *registers,const uint16_t *values,int text) {
    if(!registers || !values || (text!=0 && text!=1))return -1;
    int count=text?384:48;
    for(int i=0;i<count;++i) {
        if(values[i]>(text?127:384) || (!text && values[i]<192))return -1;
    }
    for(int i=0;i<count;++i) {
        registers[(text?0xa0:0x90)/4]=(uint32_t)i|((uint32_t)values[i]<<(text?16:8));
    }
    __sync_synchronize();
    registers[(text?0xa4:0x94)/4]=1;
    return 0;
}

int temporal_chroma(uint8_t *pane,int stride,uint8_t *history,int width,int height,
                    int strength,int history_valid) {
    if(!pane || !history || width<=0 || height<=0 || width>4096 || height>4096 ||
       stride<width*4 || strength<0 || strength>10)return -1;
    if(!strength)return 0;
    for(int y=0;y<height;++y) {
      uint8_t *row=pane+(ptrdiff_t)y*stride,*previous=history+(ptrdiff_t)y*width*4;
      if(!history_valid) {memcpy(previous,row,width*4);continue;}
      int x=0;
#if defined(__ARM_NEON)
      for(;x+8<=width;x+=8) {
        uint8x8x4_t p=vld4_u8(row+x*4),old=vld4_u8(previous+x*4),result=p;
        int16x8_t yy=luma8(p),cb=chroma8(p,0),cr=chroma8(p,2);
        int16x8_t ob=chroma8(old,0),orr=chroma8(old,2);
        int16x8_t amount=vshrq_n_s16(vmulq_n_s16(vsubq_s16(vdupq_n_s16(160),yy),strength),6);
        amount=vbslq_s16(vcltq_s16(yy,vdupq_n_s16(96)),vdupq_n_s16(strength),amount);
        amount=vmaxq_s16(vdupq_n_s16(0),vminq_s16(vdupq_n_s16(8),amount));
        uint16x8_t accept=vcleq_s16(vabsq_s16(vsubq_s16(luma8(old),yy)),vdupq_n_s16(6+strength));
        accept=vandq_u16(accept,vcleq_s16(vabsq_s16(vsubq_s16(ob,cb)),vdupq_n_s16(16+strength*2)));
        accept=vandq_u16(accept,vcleq_s16(vabsq_s16(vsubq_s16(orr,cr)),vdupq_n_s16(16+strength*2)));
        int16x8_t weight=vbslq_s16(accept,amount,vdupq_n_s16(0));
        int16x8_t nb=vshrq_n_s16(vaddq_s16(vaddq_s16(vmulq_s16(cb,vsubq_s16(vdupq_n_s16(16),weight)),vmulq_s16(ob,weight)),vdupq_n_s16(8)),4);
        int16x8_t nr=vshrq_n_s16(vaddq_s16(vaddq_s16(vmulq_s16(cr,vsubq_s16(vdupq_n_s16(16),weight)),vmulq_s16(orr,weight)),vdupq_n_s16(8)),4);
        int16x8_t green=green8(yy,nb,nr);
        uint8x8_t active=vmovn_u16(vcgtq_s16(weight,vdupq_n_s16(0)));
        result.val[0]=vbsl_u8(active,vqmovun_s16(vaddq_s16(green,nb)),p.val[0]);
        result.val[1]=vbsl_u8(active,vqmovun_s16(green),p.val[1]);
        result.val[2]=vbsl_u8(active,vqmovun_s16(vaddq_s16(green,nr)),p.val[2]);
        vst4_u8(row+x*4,result);vst4_u8(previous+x*4,result);
      }
#endif
      for(;x<width;++x) {
        uint8_t *p=row+x*4,*old=previous+x*4;
        int yy=luma(p),cb=(int)p[0]-p[1],cr=(int)p[2]-p[1];
        int amount=yy<96?strength:yy<160?(strength*(160-yy))>>6:0;
        if(amount>8)amount=8;
        if(amount && absolute(luma(old)-yy)<=6+strength &&
           absolute(((int)old[0]-old[1])-cb)<=16+strength*2 &&
           absolute(((int)old[2]-old[1])-cr)<=16+strength*2) {
          int nb=(cb*(16-amount)+((int)old[0]-old[1])*amount+8)>>4;
          int nr=(cr*(16-amount)+((int)old[2]-old[1])*amount+8)>>4;
          int green=(256*yy-29*nb-77*nr+128)>>8;
          p[0]=clipped(green+nb);p[1]=clipped(green);p[2]=clipped(green+nr);
        }
        memcpy(old,p,4);
      }
    }
    return 0;
}
