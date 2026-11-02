"""Read-only verification of imported measurements; Python standard library only."""
from pathlib import Path
import hashlib
import json
import math
import statistics

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'board/results/measurements_20261102'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def equal(a, b):
    assert math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9), (a, b)


def main():
    sources = load(Path(__file__).with_name('source_hashes.json'))
    for name, expected in sources['files'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    assert hashlib.sha256((ROOT / 'report/design_report.pdf').read_bytes()).hexdigest() == sources['report_sha256']
    summary = load(Path(__file__).with_name('summary.json'))
    fast = load(BASE / 'short_ab/results.json')
    boundaries = load(BASE / 'short_ab/boundaries.json')
    telemetry = [json.loads(line) for line in (BASE / 'short_ab/telemetry.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    for i, row in enumerate(fast['ab']):
        a, b = boundaries['ab_%d_start' % i], boundaries['ab_%d_end' % i]
        duration = b['monotonic'] - a['monotonic']
        equal(duration, row['seconds'])
        assert row['pair'] == i // 2 + 1 and row['automatic'] == bool(i % 2)
        assert duration >= 19.8
        for field in ['capture', 'render']:
            count = b[field + '_count'] - a[field + '_count']
            assert count == row[field + '_frames']
            equal(count / duration, row[field + '_fps'])
        equal(100 * (b['cpu_seconds'] - a['cpu_seconds']) / duration, row['cpu_one_core_percent'])
        samples = [x for x in telemetry if a['monotonic'] <= x['monotonic'] <= b['monotonic']]
        assert samples
        assert all(x['state']['automatic'] == bool(i % 2) and not x['state']['frozen'] for x in samples)
        for counter in ['dma_errors', 'overflow_frames', 'malformed_frames']:
            assert (b['counters'][counter] - a['counters'][counter]) & 0xffffffff == row['error_deltas'][counter] == 0
    for enabled, key in [(False, 'off'), (True, 'on')]:
        rows = [x for x in fast['ab'] if x['automatic'] == enabled]
        assert len(rows) == 3
        for metric in ['capture_fps', 'render_fps', 'cpu_one_core_percent']:
            mean = statistics.mean(x[metric] for x in rows)
            equal(mean, fast['ab_means'][key][metric])
            equal(mean, summary['short_ab'][key][metric])
    for metric in ['capture_fps', 'render_fps']:
        equal(100 * (fast['ab_means']['on'][metric] / fast['ab_means']['off'][metric] - 1),
              fast['ab_change_percent'][metric])
    run = load(BASE / 'continuous/board_run.json')
    continuous = load(BASE / 'continuous/ten_minute_stability.json')
    assert continuous == summary['continuous_run']
    assert run['outcome'] == continuous['outcome'] == 'completed'
    assert run['cleanup_errors'] == continuous['cleanup_errors'] == []
    assert run['boot_id'] == run['boot_id_after']
    assert run['unique_camera_frames'] == continuous['capture_frames']
    assert run['pl_rendered_frames'] == continuous['render_frames']
    # A full-run observation includes N frames but N-1 inter-frame intervals.
    equal((continuous['capture_frames'] - 1) / continuous['capture_observation_span_s'], continuous['capture_fps'])
    equal((continuous['render_frames'] - 1) / continuous['render_observation_span_s'], continuous['render_fps'])
    equal(run['measured_unique_capture_fps'], continuous['capture_fps'])
    equal(run['measured_pl_render_fps'], continuous['render_fps'])
    assert run['counter_deltas'] == continuous['counter_deltas']
    for counter in ['dma_errors', 'overflow_frames', 'malformed_frames']:
        assert continuous['counter_deltas'][counter] == 0
    for key, name in [('bit_sha256', 'visual_aid_v3.bit'), ('hwh_sha256', 'visual_aid_v3.hwh')]:
        assert hashlib.sha256((ROOT / 'src/ps/runtime/board' / name).read_bytes()).hexdigest() == summary['source_version'][key]
    for group, values in summary['quality'].items():
        images = fast['quality'][group]['images']
        assert len(images) == values['n_images'] == 3
        for output, metric in [('mean_laplacian_variance', 'laplacian_variance'),
                               ('mean_tenengrad', 'tenengrad'),
                               ('mean_contrast_range', 'p90_minus_p10')]:
            equal(statistics.mean(x['metrics'][metric] for x in images), values[output])
        for image in images:
            assert (Path(__file__).parent / 'images' / image['file']).is_file()
    print(json.dumps({'passed': True, 'ab_pairs': 3, 'ab_sample_seconds': 'about 20',
                      'continuous_capture_span_s': continuous['capture_observation_span_s'],
                      'source_hashes_checked': len(sources['files']),
                      'board_connected': False, 'new_measurement_performed': False}, indent=2))


if __name__ == '__main__':
    main()
