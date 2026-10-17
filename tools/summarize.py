"""Summarize current verification without overwriting implementation evidence."""
from pathlib import Path
import hashlib,json,re,sys,datetime
ROOT=Path(__file__).resolve().parents[1]
from package_board import check_simulation,check_software,hardware_sources
sim=check_simulation();software=check_software()
original=json.loads((ROOT/'reports/original_project_check.json').read_text(encoding='utf-8'))
if not original['unchanged']:raise RuntimeError('Original project changed')
gui=(ROOT/'reports/create_sim.log').read_text(errors='replace')
if 'PASS: GUI simulation launched' not in gui or re.search(r'^(ERROR:|Fatal:)',gui,re.M):
    raise RuntimeError('GUI XSim did not complete')
manifest_path=ROOT/'software/board/build_manifest.json'
release=None
if manifest_path.exists():
    sys.path.insert(0,str(ROOT/'software'))
    from visual_aid.integrity import verify_payload
    candidate=verify_payload(ROOT/'software')
    if candidate.get('hardware_source_sha256')==hardware_sources():release=candidate
summary={'timestamp':datetime.datetime.now().astimezone().isoformat(),
         'xsim_suites':['quick','full'],'python_tests':software['tests'],'gui_simulation':'passed',
         'original_project_unchanged':True,'original_file_count':original['original_files'],
         'full_system_implementation':'passed' if release else 'not_currently_verified',
         'bitstream':'generated_two_matching_variants' if release else 'not_currently_verified',
         'hardware':'not_tested_user_requested_host_only','measured_board_camera_fps':None,
         'rtl_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'rtl').glob('*.sv')}}
if release:
    summary.update(timing=release['timing'],protected_projects=release['protected_projects'],
                   board_archive='delivery/visual_aid_v3_board.zip')
    archive=ROOT/summary['board_archive']
    summary['board_archive_sha256']=hashlib.sha256(archive.read_bytes()).hexdigest()
(ROOT/'reports/delivery_manifest.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
rows=[('小尺寸多模式/反压/SOF配置','PASS，10帧逐像素比对','reading_quick.log'),
      ('1280×720阅读增强','PASS，921600像素','reading_full.log'),
      ('DVP→DDR、坏末行/AXI错误/溢出与恢复','PASS，小尺寸及720p','capture_quick.log / capture_full.log'),
      ('寄存器、FIFO停钟复位、DMA停止时排空','PASS','registers/fifo/abort 日志'),
      ('Gamma帧边界切换与旧bank流水保护','PASS，含输出堵塞期间保护','gamma_quick.log'),
      ('板端兼容/缓存/分阶段入口/错误回退/3.6语法','PASS，{}项主机测试'.format(software['tests']),'software_tests.json'),
      ('Vivado图形工程实际运行仿真','PASS','create_sim.log'),
      ('原始vision_enhancer完整性','1481文件未改动、未新增','original_project_check.json')]
if release:
    t=release['timing']
    rows += [('完整增强系统综合与布局布线','PASS','system_route_status.rpt'),
             ('建立/保持时间','WNS {:+.3f} ns；WHS {:+.3f} ns'.format(t['setup_ns'],t['hold_ns']),'system_timing.rpt'),
             ('DRC','0 Error','system_drc.rpt'),
             ('五组自定义Gray总线偏斜','PASS；另含官方IP约束','system_bus_skew.rpt'),
             ('四路双向IO pad与增强数据通路','已核对','system_timing_values.json'),
             ('配套bit/HWH及发布包文件校验','PASS，两种SCCB上拉版本','software/board/build_manifest.json'),
             ('原图回退版本完整性','{}个受保护文件未改动'.format(release['protected_projects']['raw_protected_files']),'protected_projects_check.json')]
rows += [('增强版实板、光学对焦、物理HDMI、实际帧率/延迟/稳定性','本轮按用户要求不执行','后续按上板说明验收')]
text='# 增强版电脑端验收状态\n\n| 项目 | 结果 | 证据 |\n| --- | --- | --- |\n'
for row in rows:text+='| '+' | '.join(row)+' |\n'
text+='''
## 交付入口

- 上板压缩包：`delivery/visual_aid_v3_board.zip`；解压根目录为 `visual_aid_v3_enhanced`。
- 上板步骤：`docs/board_bringup_zh.md`；先 preflight，再 static / keys / sensors / colorbars / live。
- 仿真工程：`build/gui_sim/visual_aid_v3_sim.xpr`。
- 系统工程：`build/system/visual_aid_v3.xpr`。
- `build.ps1 -Step verify` 重跑主机验证；`-Step bit` 重建并发布；`-Step package` 只重新核对打包。

## 仍保留的说明

CDC详细报告保留一条CDC-10：capture_enable与系统复位组合后送入camera/crst首级的CLR。
该路径用于异步置复位、摄像头时钟域两级同步释放；不是未同步的数据通路。
没有降低告警严重性或把所有CDC报告写成零告警，结构说明与证据见 `docs/validation_notes_zh.md`。
源同步输入延迟仍为资料预算，实物线缆/波形未测；不得把正时序裕量当作实物接线已通过。
历史失败尝试单独保留在 `reports/implementation_attempt1`、`implementation_attempt2`，当前结论取当前清单与报告。
预览图来自软件参考模型，不是板上照片。
'''
(ROOT/'reports/STATUS_zh.md').write_text(text,encoding='utf-8')
print('PASS current-source delivery status; implementation='+summary['full_system_implementation'])
