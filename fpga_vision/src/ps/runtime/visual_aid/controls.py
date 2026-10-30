"""Existing keys plus bounded EC11 parameter editing."""


AUTO_PARAMETERS = ('brightness','sharpness','denoise','contrast','algorithm','noise','local_tone','color','window31','binary_c')


class State:
    def __init__(self, quality='baseline'):
        if quality not in ('baseline','balanced','detail'):raise ValueError('Unknown image quality preset')
        self.quality=quality
        self.mode = 1
        self.zoom = 1
        self.center = [0.5, 0.5]
        self.frozen = False
        self.split = True
        self.automatic = True
        self.auto_status = {'status':'waiting', 'reason':'等待有效画面统计'}
        self.parameters = ('brightness','sharpness','denoise','contrast','algorithm','noise','edge_view',
                           'color','local_tone','window31','binary_c')
        self.selected = 0
        self.reset_parameters()

    def reset_parameters(self):
        self.brightness = 0
        self.sharpness = 4
        self.denoise = 4
        self.contrast = 1
        self.algorithm = 3
        self.noise = 4
        self.edge_view = False
        self.color=0;self.local_tone=0;self.window31=0;self.binary_c=8
        if self.quality=='balanced':
            self.sharpness=2
            self.denoise=6
            self.noise=6
            self.contrast=0
            self.color=8;self.local_tone=1;self.window31=1
        elif self.quality=='detail':
            # Weak text strokes must survive the luma mean gate. Keep the
            # accepted sensor ISP; use mild PL filtering and bounded edges.
            self.sharpness=4;self.denoise=0;self.noise=1;self.contrast=0
            self.color=8;self.local_tone=1;self.window31=1

    def encoder(self, event, value=1):
        if event == 'short':
            self.selected = (self.selected+value) % len(self.parameters)
        elif event == 'long':
            self.set_automatic(False)
            self.reset_parameters()
        elif event == 'rotate':
            name = self.parameters[self.selected]
            if name in AUTO_PARAMETERS: self.set_automatic(False)
            low, high = {'brightness':(-10,10),'sharpness':(0,10),'denoise':(0,10),
                         'contrast':(0,3),'algorithm':(0,3),'noise':(0,10),'edge_view':(0,1),
                         'color':(0,16),'local_tone':(0,1),'window31':(0,1),'binary_c':(0,32)}[name]
            setattr(self,name,min(high,max(low,getattr(self,name)+value)))

    def set_automatic(self, enabled):
        self.automatic = bool(enabled)
        self.auto_status = {'status':'waiting' if enabled else 'manual',
                            'reason':'等待有效画面统计' if enabled else '参数由用户控制'}

    def snapshot(self):
        return dict({name:getattr(self,name) for name in self.parameters},
                    selected=self.parameters[self.selected],edge_view=self.edge_view)

    def config(self):
        return (self.mode | (8 if self.split else 0) | (16 if self.denoise else 0) |
                (32 if self.sharpness and self.algorithm else 0) | (self.contrast << 6) | (self.binary_c << 8) |
                (1 << 31) | (self.algorithm << 29) | (self.sharpness << 25) |
                (self.noise << 21) | (self.denoise << 17) | (int(self.edge_view) << 16))

    def quality_config(self):
        return int(bool(self.color))|(self.color<<1)|(int(bool(self.window31))<<6)|\
               (int(bool(self.local_tone))<<7)|(int(bool(self.denoise) and self.quality in ('balanced','detail'))<<8)

    def apply(self, key):
        if key == 'mode':
            self.mode = (self.mode+1) % 5
        elif key == 'freeze':
            self.frozen = not self.frozen
        elif key == 'split':
            self.split = not self.split
        elif key == 'auto':
            self.set_automatic(not self.automatic)
        elif key == 'zoom':
            self.zoom = {1: 2, 2: 4, 4: 1}[self.zoom]
        elif key in ('up', 'down', 'left', 'right'):
            dx, dy = {'up': (0, -1), 'down': (0, 1), 'left': (-1, 0), 'right': (1, 0)}[key]
            step = 0.08/self.zoom
            margin = 0.5/self.zoom
            self.center[0] = min(1-margin, max(margin, self.center[0]+dx*step))
            self.center[1] = min(1-margin, max(margin, self.center[1]+dy*step))
        margin = 0.5/self.zoom
        self.center = [min(1-margin, max(margin, v)) for v in self.center]


class Controls:
    # Hardware presents all keys as active HIGH after normalizing the joystick.
    KEYS = ('mode', 'freeze', 'split', 'auto', 'up', 'down', 'left', 'right', 'zoom')

    def __init__(self, debounce=0.025):
        self.debounce = debounce
        self.candidate = [False]*9
        self.stable = [False]*9
        self.since = [0.0]*9
        self.repeat_at = [0.0]*9

    def poll(self, bits, now):
        events = []
        for i, key in enumerate(self.KEYS):
            pressed = bool(bits & (1 << i))
            if pressed != self.candidate[i]:
                self.candidate[i] = pressed
                self.since[i] = now
            if now-self.since[i] >= self.debounce and pressed != self.stable[i]:
                self.stable[i] = pressed
                if pressed:
                    events.append(key)
                    self.repeat_at[i] = now+0.35
            elif pressed and self.stable[i] and 4 <= i <= 7 and now >= self.repeat_at[i]:
                events.append(key)
                self.repeat_at[i] = now+0.09
        return events
