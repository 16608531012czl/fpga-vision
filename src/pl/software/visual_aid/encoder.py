"""Consume hardware EC11 counters; Python polling never decodes A/B edges."""
def record_event(report, event, value):
    """Qualify each physical function separately; a key press cannot prove rotation."""
    observed = report.setdefault('encoder_functions_observed', {
        'positive_rotation': False, 'negative_rotation': False,
        'short_press': False, 'long_press': False})
    if event == 'rotate' and value:
        observed['positive_rotation' if value > 0 else 'negative_rotation'] = True
    elif event in ('short', 'long') and value:
        observed[event+'_press'] = True
    report['encoder_connected_verified'] = all(observed.values())


class Encoder:
    def __init__(self, reverse=False):
        self.previous = None
        self.reverse = reverse

    def snapshot(self, mmio):
        return {'position': int(mmio.read(0x50)), 'short': int(mmio.read(0x58)),
                'long': int(mmio.read(0x5c)), 'invalid': int(mmio.read(0x60)),
                'status': int(mmio.read(0x54))}

    def poll(self, mmio):
        current = self.snapshot(mmio)
        events = []
        if self.previous is not None:
            delta = ((current['position']-self.previous['position']+(1 << 31)) & 0xffffffff)-(1 << 31)
            if delta:
                events.append(('rotate', max(-100, min(100, -delta if self.reverse else delta))))
            for name in ('short', 'long'):
                count = (current[name]-self.previous[name]) & 0xffffffff
                if count:
                    events.append((name, min(count, 16)))
        self.previous = current
        return events, current
