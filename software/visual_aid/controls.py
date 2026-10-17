"""Debounced controls, no encoder/external function keys/PWM output."""


class State:
    def __init__(self):
        self.mode = 1
        self.zoom = 1
        self.center = [0.5, 0.5]
        self.frozen = False
        self.split = True
        self.automatic = True

    def config(self):
        return self.mode | (8 if self.split else 0) | 16 | 32 | (2 << 6) | (8 << 8)

    def apply(self, key):
        if key == 'mode':
            self.mode = (self.mode+1) % 5
        elif key == 'freeze':
            self.frozen = not self.frozen
        elif key == 'split':
            self.split = not self.split
        elif key == 'auto':
            self.automatic = not self.automatic
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
