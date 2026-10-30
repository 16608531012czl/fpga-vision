"""Reproducible synthetic scene replay; never connects to a board.

Run with the project's desktop NumPy environment. Results validate software
decisions, not real-camera image quality or PYNQ processing speed.
"""
from pathlib import Path
import json
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'runtime'))
from visual_aid.auto_quality import AutoQuality
from visual_aid.controls import State
from visual_aid.image import AdaptivePolicy
from visual_aid.remote_control import snapshot


def main():
    scenarios=[('dark_clean',50,0,False,10), ('dark_noisy',50,12,False,10),
               ('uneven_page',70,0,True,120), ('bright_page',200,0,False,800),
               ('missing_light_sensor',50,8,False,None)]
    rows=[];timings=[]
    for name,mean,sigma,uneven,lux in scenarios:
        rng=np.random.RandomState(42)
        gray=np.full((180,320),float(mean))
        if uneven:gray+=np.linspace(-40,100,320)[None,:]
        if sigma:gray+=rng.normal(0,sigma,gray.shape)
        frame=np.repeat(np.clip(gray,0,255).astype(np.uint8)[:,:,None],3,axis=2)
        state=State('detail');quality=AutoQuality();tone=AdaptivePolicy('stable')
        trace=[]
        for i in range(50):
            start=time.perf_counter()
            quality.update(state,frame,(0,0,320,180),i*.5,lux)
            tone.update(frame,i*.5,lux)
            timings.append((time.perf_counter()-start)*1000)
            trace.append({'t':i*.5,'state':snapshot(state),'tone':tone.status(),
                          'effective_lut_at_60':int(quality.tone_lut(state,tone.lut)[60])})
        rows.append({'scene':name,'synthetic':True,'final':trace[-1],'trace':trace})
    out=ROOT/'delivery/auto_quality';out.mkdir(parents=True,exist_ok=True)
    result={'board_connected':False,'scope':'synthetic software replay only',
            'host_policy_ms_median':float(np.median(timings)),
            'host_policy_ms_p95':float(np.percentile(timings,95)),
            'timing_excludes':'DMA cache invalidation, FPGA, camera and HDMI',
            'scenarios':rows}
    (out/'synthetic_replay.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    lines=['# AUTO 离线合成场景验证','',
           '这些结果来自固定随机种子的合成图像，仅验证策略行为；不是实板测量或画质验收。','',
           '| 场景 | 降噪 | 锐化 | 噪点门限 | 局部补偿 | 提亮保留比例 | 灰度 60 映射为 |',
           '|---|---:|---:|---:|---|---:|---:|']
    for row in rows:
        final=row['final'];s=final['state']
        lines.append('| {} | {} | {} | {} | {} | {:.3f} | {} |'.format(row['scene'],s['denoise'],s['sharpness'],s['noise'],bool(s['local_tone']),s['auto_quality']['tone_strength'],final['effective_lut_at_60']))
    lines+=['','Gamma 目标由原有明暗策略产生，亮度补偿保持 0，避免重复提亮。',
            '完整参数变化、图像统计和目标值见 synthetic_replay.json。',
            '上板后必须补测缓存失效开销、帧率、HDMI 画质、实物噪声和光照切换。']
    (out/'REPLAY_zh.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))


if __name__=='__main__':main()
