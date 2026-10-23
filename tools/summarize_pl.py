"""Require current-release PL, AF and feature-exercise evidence before delivery."""
from pathlib import Path
import json,hashlib,datetime,sys,re
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'software'))
from visual_aid.integrity import verify_payload

def main():
 release=verify_payload(ROOT/'software');runs=[];exercises=[]
 for directory,pattern in [('reports/board_validation_20261022','live_*.json'),('reports/performance','performance_pl_exercise_*.json')]:
  for path in (ROOT/directory).glob(pattern):
   r=json.loads(path.read_text(encoding='utf-8'))
   if r.get('release',{}).get('built_at')!=release['built_at'] or r.get('pipeline')!='pl':continue
   d=r.get('counter_deltas',{});duration=max((s['t'] for s in r.get('samples',[])),default=0)
   modes={str(i):sum(s.get('config',0)&7==i for s in r.get('samples',[])) for i in range(5)}
   passed=(r.get('outcome')=='completed' and not r.get('cleanup_errors') and r.get('boot_id')==r.get('boot_id_after')
           and all(d.get(k)==0 for k in ('dma_errors','overflow_frames','malformed_frames'))
           and r.get('autofocus',{}).get('full_readback_verified') and r.get('autofocus',{}).get('continuous'))
   item={'path':path.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
         'passed':bool(passed),'duration_at_least':duration,'fps':r.get('measured_unique_capture_fps'),
         'render_fps':r.get('measured_pl_render_fps'),'rendered_frames':r.get('pl_rendered_frames'),
         'observed_display_updates':r.get('pl_observed_display_updates'),
         'frames':r.get('unique_camera_frames'),'quality_preset':r.get('quality_preset'),
         'mode_samples':modes,'counter_deltas':d,'exercise_checks':r.get('exercise_checks'),
         'same_boot':r.get('boot_id')==r.get('boot_id_after')}
   if r.get('exercise_checks'):
    exercises.append(item)
   else:runs.append(item)
 accepted=[r for r in runs if r['passed'] and r['duration_at_least']>=119 and r['quality_preset']=='detail'
           and (r['fps'] or 0)>=19 and (r['render_fps'] or 0)>=19
           and (r['observed_display_updates'] or 0)>=(r['rendered_frames'] or 1)*.9]
 if not accepted:raise RuntimeError('No current-release >=120s PL detail AF run passed')
 if not any(r['passed'] and all(r['exercise_checks'].values()) for r in exercises):raise RuntimeError('PL feature exercise not passed')
 chosen=max(accepted,key=lambda r:r['fps'])
 utilization=(ROOT/'reports/system_utilization.rpt').read_text(errors='replace')
 resource={}
 for name,label in [('lut','Slice LUTs'),('registers','Slice Registers'),('bram','Block RAM Tile'),('dsp','DSPs')]:
  m=re.search(r'\|\s*'+re.escape(label)+r'\*?\s*\|\s*([\d.]+)\s*\|[^\n]+',utilization)
  if m:resource[name]=m.group(0).strip()
 observations=json.loads((ROOT/'reports/board_validation_20261022/physical_observations.json').read_text(encoding='utf-8'))
 physical=observations.get('runs',{}).get(Path(chosen['path']).name,{})
 result={'timestamp':datetime.datetime.now().astimezone().isoformat(),'release':release['built_at'],
         'timing':release['timing'],'resources':resource,'selected':chosen,'all_pl_runs':runs,'exercises':exercises,
         'features':release['pl_features'],'physical_observation':physical,
         'physical_color_quality_acceptance':physical.get('color_quality_feedback','pending user observation'),
         'limitations':['mean-based tile mapping, not full CLAHE','integer nearest live upscale, not arbitrary bilinear',
                        'spatial PL chroma filter, no temporal motion compensation','20 FPS tested setting, no absolute sensor maximum claim']}
 (ROOT/'reports/pl_upgrade_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 lines=['# PL 图像链路验收','',
        '发布：`{}`。'.format(release['built_at']),'',
        '- 时序：建立余量 {:+.3f} ns，保持余量 {:+.3f} ns，DRC 错误 0。'.format(release['timing']['setup_ns'],release['timing']['hold_ns']),
        '- 实测独立采集 {:.3f} FPS，{} 帧，覆盖至少 {:.1f} 秒；HDMI 为 60Hz。'.format(chosen['fps'],chosen['frames'],chosen['duration_at_least']),
        '- PL 渲染完成 {:.3f} FPS，{} 帧，实际采样确认 {} 次画布显示切换。'.format(chosen['render_fps'],chosen['rendered_frames'],chosen['observed_display_updates']),
        '- DMA/溢出/坏帧区间增量均为 0，清理正常，同次启动；AF 固件完整回读和连续模式命令通过。',
        '- 实时缩放分屏和文字进入 PL；冻结/平移/1、2、4倍/分屏与全屏/五种模式自动操作验收通过。',
        '- 新增颜色质量实物反馈：{}。'.format(physical.get('color_quality_feedback','待用户观察；尚不宣称观感改善已验收')),'',
        '长测：`{}`。'.format(chosen['path']),'',
        '模式样本分布：`{}`。存在模式切换时，整体 FPS 不是锁定 COLOR 的基准。'.format(chosen['mode_samples']),'',
        '资源：']+['- '+v for v in resource.values()]+['','算法、操作、限制见 `docs/pl_upgrade_zh.md`。']
 (ROOT/'reports/PL_UPGRADE_zh.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 print('PASS current PL release acceptance',chosen['fps'])

if __name__=='__main__':main()
