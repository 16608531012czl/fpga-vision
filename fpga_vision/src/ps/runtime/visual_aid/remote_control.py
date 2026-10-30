"""File mailbox: only the capture loop may mutate State. Python 3.6."""
import json
import os
import time
from pathlib import Path
from .controls import AUTO_PARAMETERS

LIMITS = {'brightness':(-10,10), 'sharpness':(0,10), 'denoise':(0,10),
          'contrast':(0,3), 'algorithm':(0,3), 'noise':(0,10), 'color':(0,16),
          'binary_c':(0,32), 'mode':(0,4)}
FLAGS = ('edge_view','local_tone','window31','frozen','split','automatic')


def snapshot(state):
    out = state.snapshot()
    out.update({k:getattr(state,k) for k in ('mode','zoom','frozen','split','automatic')})
    out['center'] = list(state.center)
    out['auto_quality'] = dict(state.auto_status)
    return out


def apply_command(state, command):
    if not isinstance(command, dict): raise ValueError('Expected command object')
    op = command.get('op')
    if op == 'set':
        values = command.get('values')
        if not isinstance(values, dict) or not values: raise ValueError('Empty parameters')
        for key, value in values.items():
            if key in FLAGS:
                if type(value) is not bool: raise ValueError('Expected boolean: '+key)
            elif key == 'zoom':
                if type(value) is not int or value not in (1,2,4): raise ValueError('Invalid zoom')
            elif key in LIMITS:
                low, high = LIMITS[key]
                if type(value) is not int or not low <= value <= high: raise ValueError('Out of range: '+key)
            else: raise ValueError('Unknown parameter: '+key)
        managed = any(key in AUTO_PARAMETERS for key in values)
        if managed and values.get('automatic') is True:
            raise ValueError('AUTO 与手动画质参数不能同时设置，请切换 MANUAL')
        if managed: state.set_automatic(False)
        if 'automatic' in values: state.set_automatic(values['automatic'])
        for key, value in values.items():
            if key != 'automatic': setattr(state,key,value)
        margin = .5/state.zoom
        state.center = [min(1-margin,max(margin,v)) for v in state.center]
    elif op == 'move':
        direction = command.get('direction')
        if direction not in ('up','down','left','right'): raise ValueError('Invalid direction')
        state.apply(direction)
    elif op == 'reset':
        state.set_automatic(False)
        state.reset_parameters()
    else: raise ValueError('Unknown operation')
    return snapshot(state)


def save(path, data):
    path = Path(path)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data), encoding='utf-8')
    os.replace(str(tmp),str(path))


class Mailbox:
    def __init__(self):
        directory = os.environ.get('VISION_CONTROL_DIR')
        self.root = Path(directory) if directory else None
        self.session = os.environ.get('VISION_CONTROL_SESSION','')
        self.last = 0

    def poll(self, state):
        if self.root is None: return
        for path in sorted(self.root.glob('command_*.json'))[:8]:
            try:
                request = json.loads(path.read_text(encoding='utf-8'))
                if request.get('session') != self.session or time.time() > request.get('expires',0):
                    raise ValueError('Expired command or old session')
                result = {'ok':True,'state':apply_command(state,request['command'])}
            except Exception as exc: result = {'ok':False,'error':str(exc)}
            save(self.root/path.name.replace('command_','result_'),result)
            path.unlink()

    def publish(self, state, fps, readings, counters):
        if self.root is None or time.monotonic()-self.last < .25: return
        self.last = time.monotonic()
        if callable(counters): counters = counters()
        save(self.root/'live.json', {'session':self.session,'updated':time.time(),
             'state':snapshot(state),'fps':fps,'lux':readings.get('lux'),'counters':counters})
