"""Board acceptance across live/frozen ROI, split/full and all display modes."""
from pathlib import Path
import time,json
import run_board as app
from visual_aid.controls import Controls

events=[(5,'zoom'),(10,'zoom'),(15,'split'),(25,'freeze'),(28,'right'),(30,'up'),
        (32,'zoom'),(35,'split'),(40,'freeze'),(45,'mode'),(50,'mode'),(55,'mode'),
        (60,'mode'),(65,'mode')]
class Exercise(Controls):
    def __init__(self):super().__init__();self.started=None;self.next=0
    def poll(self,bits,now):
        if self.started is None:self.started=now
        if self.next<len(events) and now-self.started>=events[self.next][0]:
            event=events[self.next][1];self.next+=1;return [event]
        return []
app.Controls=Exercise
base=Path(__file__).resolve().parent
report=base/'logs'/('performance_pl_exercise_'+time.strftime('%Y%m%d_%H%M%S')+'.json')
args=app.parse_args(['--pipeline','pl','--stage','live','--mode','color','--camera-fps','20',
                     '--quality-preset','detail','--no-sensors','--af','continuous','--seconds','90',
                     '--io-confirmed','--report',str(report)])
code=app.run(args)
r=json.loads(report.read_text());samples=r.get('samples',[])
checks={'completed':code==0 and r.get('outcome')=='completed',
        'no_capture_errors':all(r.get('counter_deltas',{}).get(k)==0 for k in ('dma_errors','overflow_frames','malformed_frames')),
        'all_five_modes':set(s['config']&7 for s in samples)==set(range(5)),
        'all_zooms':set(s['zoom'] for s in samples)=={1,2,4},
        'freeze_and_live':set(s['frozen'] for s in samples)=={False,True},
        'split_and_full':set(bool(s['config']&8) for s in samples)=={False,True},
        'display_slot_routed':bool(samples) and sum(s['scanout']['active']==s['scanout']['hardware_slot'] for s in samples)>=len(samples)*.9,
        'clean_shutdown':not r.get('cleanup_errors')}
r['exercise_checks']=checks;report.write_text(json.dumps(r,indent=2))
print('PL_EXERCISE '+json.dumps(checks),flush=True)
raise SystemExit(0 if all(checks.values()) else 1)
