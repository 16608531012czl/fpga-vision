"""Reproducible algorithm comparison; synthetic model output, never board evidence."""
from pathlib import Path
import json
import sys
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'software'))
from visual_aid.controls import State
from visual_aid.image import AdaptivePolicy,gray8,reference_enhance


def main():
    out=ROOT/'reports/ec11_preview';out.mkdir(exist_ok=True)
    h,w=300,480
    y,x=np.indices((h,w));mono=(50+25*x/w).astype(np.uint8)
    image=np.repeat(mono[:,:,None],3,axis=2)
    for i,line in enumerate(('READING ASSISTANT','Edge guided sharpening','Fine strokes: 0123456789',
                              'Same source image in every panel.')):
        cv2.putText(image,line,(15,45+i*43),cv2.FONT_HERSHEY_SIMPLEX,0.55,(15,15,15),1,cv2.LINE_AA)
    rng=np.random.RandomState(22)
    image=np.clip(image.astype(int)+rng.randint(-3,4,image.shape),0,255).astype(np.uint8)
    image[230:280,20:120]=240;image[230:280,140:240]=10
    policy=AdaptivePolicy()
    for i in range(17):policy.update(image,i*0.25,10)
    s=State();s.mode=4;s.split=False;s.contrast=0
    panels=[('ORIGINAL',image)]
    for name,method in (('USM',1),('LAPLACIAN',2),('GUIDED',3)):
        s.algorithm=method
        panels.append((name,reference_enhance(image,s.config(),policy.lut)))
    s.edge_view=True
    panels.append(('SOBEL DIAGNOSTIC',reference_enhance(image,s.config(),policy.lut)))
    sheet=np.full((2*(h+60)+35,3*w,3),245,np.uint8)
    for i,(name,panel) in enumerate(panels):
        row,col=divmod(i,3);ox=col*w;oy=row*(h+60)
        cv2.putText(sheet,name,(ox+12,oy+28),cv2.FONT_HERSHEY_SIMPLEX,0.65,(30,30,30),2)
        sheet[oy+45:oy+45+h,ox:ox+w]=panel
    cv2.putText(sheet,'SYNTHETIC SOFTWARE REFERENCE - NOT A BOARD CAPTURE',(12,2*(h+60)+24),
                cv2.FONT_HERSHEY_SIMPLEX,0.65,(30,30,30),1)
    cv2.imwrite(str(out/'algorithms.png'),sheet)
    noise=np.repeat((100+rng.randint(-3,4,(128,192))).astype(np.uint8)[:,:,None],3,axis=2)
    s=State();s.mode=1;s.split=False;s.denoise=0;s.contrast=0;s.sharpness=8
    sigma={'original':float(noise[4:,4:,0].std())}
    for name,method in (('usm',1),('laplacian',2),('guided',3)):
        s.algorithm=method
        sigma[name]=float(reference_enhance(noise,s.config())[4:,4:,0].std())
    record={'source':'synthetic_reference','board_tested':False,'background_noise_sigma':sigma,
            'configuration':s.snapshot(),'note':'Equal brightness, no denoise/local contrast for noise comparison'}
    (out/'results.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
