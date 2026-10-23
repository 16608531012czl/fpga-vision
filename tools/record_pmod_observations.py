"""Record the specific physical feedback and invalidated boot-race evidence."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'reports/board_validation_20261022/physical_observations.json'
record=json.loads(path.read_text(encoding='utf-8'))
record.setdefault('runs',{})['live_20261022_172658.json']={
    'display_observed':True,'rotation_changed_parameters':True,
    'user_statement':'画面正常，旋钮能调参数',
    'limit':'60-second no-AF diagnostic; rotation events captured, no short/long press event captured'}
record.setdefault('invalid_runs',{})['sensors_20261022_171948.json']={
    'reason':'boot_leds.service loaded base.bin after the custom overlay; final counters refer to a different address map',
    'evidence':'health_20261022_172208.json kernel log',
    'ignore_counter_deltas':True}
for action in [
    'User confirmed PMOD B empty and sensor SCL/SDA disconnected before pad test',
    'User powered off, connected sensor SCL to PMOD B physical pin 3 and SDA to physical pin 4, then powered on',
    'User confirmed the GY-302 header is soldered',
    'EC11 wiring remains S1 AR8, S2 AR9, KEY AR10']:
    actions=record.setdefault('wiring_actions',[])
    if action not in actions:
        actions.append(action)
path.write_text(json.dumps(record,indent=2,ensure_ascii=False),encoding='utf-8')
print('Recorded PMOD B observations; invalid boot-race data retained separately')
