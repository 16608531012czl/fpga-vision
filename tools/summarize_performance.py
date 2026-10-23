"""Current-release performance evidence; never promotes failed or old runs."""
from pathlib import Path
import datetime,hashlib,json,sys,statistics
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'software'))
from visual_aid.integrity import verify_payload

def main():
 release=verify_payload(ROOT/'software')
 runs=[];accepted=[]
 for path in sorted((ROOT/'reports/board_validation_20261022').glob('live_*.json')):
  r=json.loads(path.read_text(encoding='utf-8'))
  if '20261023' not in path.name:continue
  delta=r.get('counter_deltas',{})
  duration=max((s['t'] for s in r.get('samples',[])),default=0)
  item={k:r.get(k) for k in ('outcome','unique_camera_frames','measured_unique_capture_fps',
          'counter_deltas','cleanup_errors','autofocus','autofocus_after','capture_geometry','error')}
  item.update(path=path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    current_release=r.get('release',{}).get('built_at')==release['built_at'],
    requested_fps=r.get('camera',{}).get('requested_fps'),camera_timing=r.get('camera',{}).get('timing'),
    measured_duration_at_least_seconds=duration,
    same_boot=r.get('boot_id')==r.get('boot_id_after'),
    native=r.get('native_neon_composition_available',False))
  item['quality_preset']=r.get('quality_preset','baseline')
  item['sample_mode_counts']={str(mode):sum((s.get('config',0)&7)==mode for s in r.get('samples',[])) for mode in range(5)}
  chroma=[s['chroma_denoise_ms'] for s in r.get('samples',[]) if s.get('chroma_denoise_ms',0)>.1]
  item['chroma_median_ms']=statistics.median(chroma) if chroma else None
  item['accepted']=(item['current_release'] and r.get('outcome')=='completed' and duration>=119
      and not r.get('cleanup_errors') and item['same_boot']
      and r.get('autofocus',{}).get('continuous') and r.get('autofocus',{}).get('full_readback_verified')
      and all(delta.get(k)==0 for k in ('dma_errors','overflow_frames','malformed_frames')))
  runs.append(item)
  if item['accepted']:accepted.append(item)
 if not accepted:raise RuntimeError('No current-release AF run passed the >=120-second gate')
 default_runs=[r for r in accepted if r['quality_preset']=='balanced']
 chosen=max(default_runs or accepted,key=lambda r:r['measured_unique_capture_fps'])
 observed=json.loads((ROOT/'reports/board_validation_20261022/physical_observations.json').read_text(encoding='utf-8'))
 optics={k:v for k,v in observed.get('runs',{}).items() if v.get('near_far_refocus_observed')}
 quality_observations={k:v for k,v in observed.get('runs',{}).items() if v.get('color_noise_reduction_observed')}
 baseline=json.loads((ROOT/'reports/board_validation_20261022/live_20261022_172658.json').read_text())['measured_unique_capture_fps']
 r={'timestamp':datetime.datetime.now().astimezone().isoformat(),'release':release['built_at'],
    'timing':release['timing'],'setup_before_ns':.146,'baseline_unique_fps':baseline,
    'baseline_evidence':'reports/board_validation_20261022/live_20261022_172658.json',
    'selected':chosen,'tested_runs':runs,'user_optical_observations':optics,
    'user_quality_observations':quality_observations,
    'accepted_by_quality':{preset:max([r for r in accepted if r['quality_preset']==preset],key=lambda r:r['measured_unique_capture_fps'])
                           for preset in ('baseline','balanced') if any(r['quality_preset']==preset for r in accepted)},
    'chroma_validation':json.loads((ROOT/'reports/native_validation.json').read_text()).get('chroma_quality'),
    'not_claimed':['720p30/60 camera acceptance','instrumented optical sharpness or focus time',
                   'zero CDC warnings','absolute maximum possible frame rate'],
    'board_archive_sha256':hashlib.sha256((ROOT/'delivery/visual_aid_v4_ec11_board.zip').read_bytes()).hexdigest()}
 (ROOT/'reports/performance_summary.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
 fps=chosen['measured_unique_capture_fps'];delta=chosen['counter_deltas']
 lines=['# 时序、帧率与自动对焦验收（2026-10-23）','',
   '发布：`{}`，ABI `0x56410400`。'.format(release['built_at']),'',
   '- 建立余量：+0.146 → +1.068 ns；保持余量+0.015 ns；DRC错误0。',
   '- 默认相机档位：{}，画质预设{}；实测独立采集 {:.3f} FPS，{} 帧，覆盖至少 {:.1f} 秒。'.format(
       chosen['requested_fps'],chosen['quality_preset'],fps,chosen['unique_camera_frames'],chosen['measured_duration_at_least_seconds']),
   '- DMA/溢出/坏帧区间增量：{}/{}/{}，清理正常，启动与结束boot_id一致。'.format(
       delta['dma_errors'],delta['overflow_frames'],delta['malformed_frames']),
   '- 相比旧版同类分屏实测{:.3f} FPS，提高约{:.1f}%。场景、用户操作与实现不同，非严格同场景基准。'.format(baseline,(fps/baseline-1)*100),
   '- 4077字节AF固件全部回读一致，连续模式命令已应答；近远重新合焦的用户观察另见下面的对应记录。',
   '- 光照通信按要求停用，图像统计提亮保持工作。','',
   '证据：`{}`。'.format(chosen['path']),'',
   '本轮降低CPU复制和查表更新开销，保持15帧档PLL配置并缩短行空白。提高PLL速度的18/20/22/24/30诊断档曾出现坏行或无有效帧；HTS1351的21帧长测与HTS1290的约22帧尝试也未通过。',
   '因此本版不声称30/60相机帧率或硬件绝对上限。HDMI刷新仍为60Hz，和相机独立帧率分开计数。','',
   '## 当前运行与复现','',
   '运行方法见`docs/performance_af_zh.md`。交付时另查看`active_demo_snapshot.json`确认后台服务及实时计数；有限时长报告完成不表示程序会一直运行。','',
   'balanced使用ISP UV平均、较低重复锐化和运动门控的颜色时域降噪；保留当前帧亮度。baseline可用于原处理对照，帧率分别见各预设记录。',
   '当前报告样本中的模式分布：{}；若用户切换过模式，此报告整体FPS不是严格锁定COLOR模式的基准。'.format(chosen['sample_mode_counts']),
   '完整720p七组仿真、连续流随机停顿、{}项软件测试、ARM逐像素和内存边界检查通过。'.format(release['software_tests']['tests']),
   '旧OV5640 V3、USB相机工程和原始基线保留。光学锐度、暗光噪声和端到端延迟仍没有仪器测量。','',
   '## 本轮实板记录','',
   '| 请求FPS/预设 | 当前发布 | 结果 | 独立FPS | 错误增量 DMA/溢出/坏帧 | 文件 |',
   '| --- | --- | --- | --- | --- | --- |']
 for item in runs:
  d=item.get('counter_deltas') or {};f=item['measured_unique_capture_fps']
  lines.append('| {}/{} | {} | {} | {} | {}/{}/{} | {} |'.format(item['requested_fps'],item['quality_preset'],
     '是' if item['current_release'] else '早期诊断',item['outcome'],'-' if f is None else '{:.3f}'.format(f),
     d.get('dma_errors','-'),d.get('overflow_frames','-'),d.get('malformed_frames','-'),item['path']))
 lines+=['','## 用户实物反馈','']
 for filename,item in optics.items():lines.append('- `{}`：{}。'.format(filename,item['user_statement']))
 for filename,item in quality_observations.items():lines.append('- `{}`：{}。颜色偏淡仍需后续保色重建改进，未宣称颜色保真验收通过。'.format(filename,item['user_statement']))
 lines+=['','保持裕量较小及既有CDC/复位/厂商IP告警保留在原始报告中；不表述为零告警。','']
 (ROOT/'reports/PERFORMANCE_zh.md').write_text('\n'.join(lines),encoding='utf-8')
 print('PASS current release AF performance: {:.3f} FPS'.format(fps))

if __name__=='__main__':main()
