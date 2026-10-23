"""Summarize this upgrade; qualify physical functions from recorded events."""
from pathlib import Path
import datetime
import hashlib
import json
import sys
from package_board import check_simulation, check_software, hardware_sources

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'software'))
from visual_aid.integrity import verify_payload
from visual_aid.encoder import record_event


def main():
    sim, software = check_simulation(), check_software()
    release = verify_payload(ROOT/'software')
    if release['hardware_source_sha256'] != hardware_sources():
        raise RuntimeError('Implementation is stale')
    board, observed = [], {}
    observations_path = ROOT/'reports/board_validation_20261022/physical_observations.json'
    observations = json.loads(observations_path.read_text(encoding='utf-8')) if observations_path.exists() else {}
    equivalence_path = ROOT/'reports/rebuild_equivalence.json'
    equivalence = json.loads(equivalence_path.read_text()) if equivalence_path.exists() else {}
    equivalent_verified = (equivalence.get('current_built_at') == release['built_at']
        and equivalence.get('hardware_sources_identical') and equivalence.get('runtime_payload_identical')
        and all(v.get('configuration_data_identical') for v in equivalence.get('variants', {}).values()))
    for path in sorted((ROOT/'reports/board_validation_20261022').glob('*.json')):
        result = json.loads(path.read_text(encoding='utf-8'))
        if 'stage' not in result:
            continue
        entry = {name: result.get(name) for name in (
            'stage', 'outcome', 'release', 'unique_camera_frames',
            'measured_unique_capture_fps', 'counter_deltas', 'cleanup_errors',
            'display_observed', 'autofocus', 'warnings', 'sensor_readings_observed')}
        entry['path'] = path.relative_to(ROOT).as_posix()
        entry['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        entry['release_matches_current'] = result.get('release', {}).get('built_at') == release['built_at']
        entry['configuration_and_runtime_equivalent_to_current'] = bool(equivalent_verified and
            result.get('release', {}).get('built_at') == equivalence.get('reference_built_at'))
        invalid = observations.get('invalid_runs', {}).get(path.name)
        if invalid:
            entry['outcome'] = 'invalid_overlay_replaced'
            entry['validation_invalid_reason'] = invalid['reason']
            entry['counter_deltas'] = None
            entry['measured_unique_capture_fps'] = None
            entry['sensor_readings_observed'] = None
        physical = observations.get('runs', {}).get(path.name, {})
        if 'display_observed' in physical:
            entry['display_observed'] = physical['display_observed']
            entry['display_observation_source'] = 'user feedback; physical_observations.json'
        local_observed = {}
        for event in result.get('events', []):
            if 'encoder_event' in event:
                record_event(local_observed, event['encoder_event'], event['value'])
                record_event(observed, event['encoder_event'], event['value'])
        entry['encoder_functions_observed'] = local_observed.get('encoder_functions_observed', {})
        board.append(entry)
    archive = ROOT/'delivery/visual_aid_v4_ec11_board.zip'
    summary = {
        'timestamp': datetime.datetime.now().astimezone().isoformat(),
        'project': 'visual_aid_v4_ec11', 'abi': hex(release['abi']),
        'sensor_wiring': release.get('sensor_wiring', {}),
        'simulation': sim, 'software_tests': software,
        'timing': release['timing'], 'protected_projects': release['protected_projects'],
        'board_archive': archive.relative_to(ROOT).as_posix(),
        'board_archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
        'board_runs': board,
        'encoder_functions_observed': observed.get('encoder_functions_observed', {}),
        'encoder_all_functions_verified': observed.get('encoder_connected_verified', False),
        'optical_quality_and_response_latency': 'not_measured',
    }
    (ROOT/'reports/delivery_manifest.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    text = '# EC11升级验收状态\n\n'
    current_light = [r for r in board if r['release_matches_current'] and
                     (r.get('sensor_readings_observed') or {}).get('lux')]
    text += '旋转、短按、长按、画面亮度调节和SH参数选择已有历史实测；各项是否对应当前硬件见下表。\n\n'
    if current_light:
        text += '当前发布已取得有效lux；遮挡响应及完整图像联动以用户反馈和对应实板记录为准。\n\n'
    else:
        text += '当前发布尚未取得有效lux，光照通信仍需验收；失败时按图像统计回退。\n\n'
    if release.get('sensor_wiring', {}).get('connector') == 'PMOD B':
        text += '当前光照接线为PMOD B物理第3脚SCL、第4脚SDA；EC11保持AR8/AR9/AR10。旧Arduino SCL/SDA接线不能用于本包。\n\n'
    recovery = [r for r in board if r['stage'] == 'bus-recovery']
    if recovery:
        text += ('本次修复I2C超时后SDA未释放的问题；故障路径实板检查已记录，但不代表光照通信恢复。'
                 '原SCL/SDA曾在信号线断开且释放后仍读低；KEY已恢复AR10。'
                 '此前另观察到用户未主动操作的系统重启，不能据此宣称长时间稳定，详见engineering_notes_zh.md。\n\n')
    text += '当前ABI `{}`；软件测试{}项通过；完整720p仿真及{}组模块检查通过。\n\n'.format(
        summary['abi'], software['tests'],len(sim['full']['tests']))
    text += '建立裕量{:+.3f}ns，保持裕量{:+.3f}ns；DRC错误{}。\n\n'.format(
        release['timing']['setup_ns'], release['timing']['hold_ns'], release['timing']['drc_errors'])
    text += '| 实板阶段 | 运行 | 独立采集FPS | 物理显示反馈 | 发布对应 | 证据 |\n| --- | --- | --- | --- | --- | --- |\n'
    for run in board:
        fps = run['measured_unique_capture_fps']
        match = '当前' if run['release_matches_current'] else ('配置与程序等价' if run['configuration_and_runtime_equivalent_to_current'] else '早期/诊断')
        text += '| {} | {} | {} | {} | {} | {} |\n'.format(
            run['stage'], run['outcome'], '-' if fps is None else '{:.3f}'.format(fps),
            '未确认' if run['display_observed'] is None else ('已确认' if run['display_observed'] else '未出图'), match, run['path'])
    text += '\n旋钮各功能实测：`{}`。\n\n'.format(json.dumps(summary['encoder_functions_observed'], ensure_ascii=False))
    text += ('首次启用内部上拉时AR9没有变化；按模块串联10k电阻修订、关闭内部上拉后，双向旋转、短按、长按均已记录，非法跳变增量0。\n'
             '旧日志中的encoder_connected_verified只代表出现任一事件；本汇总从事件重新核定，要求双向旋转和两种按压均被记录。\n\n'
             '报告中的release_matches_current区分当前发布和先前硬件；不能把先前实板运行直接记作当前发布通过。\n\n'
             '实际可读性、光晕、暗光噪点和端到端可见响应延迟仍需实物评估。\n'
             'CDC详细报告保留既有capture_enable复位路径CDC-10；不得表述为零CDC告警。\n\n'
             '入口：docs/upgrade_ec11_zh.md；独立发布目录visual_aid_v4_ec11；原V3保留，可退出后从原目录回退。\n')
    (ROOT/'reports/STATUS_zh.md').write_text(text, encoding='utf-8')
    print('PASS current upgrade summary; board runs={}'.format(len(board)))


if __name__ == '__main__':
    main()
