"""Bounded scene-based quality controller. NumPy 1.13 / Python 3.6 compatible.

Nine contiguous patches preserve pixel adjacency for noise/edge estimates.
These are scene heuristics, not calibrated noise or optical quality measurements.
"""
import math
import numpy as np


def scene_metrics(frame, bounds, lux=None):
    x, y, w, h = bounds
    if frame is None or not isinstance(frame, np.ndarray) or frame.ndim != 3:
        return None
    if w < 8 or h < 8 or x < 0 or y < 0 or x+w > frame.shape[1] or y+h > frame.shape[0]:
        return None
    size = min(24, w, h)
    patches = []
    for fy in (0.15, 0.5, 0.85):
        for fx in (0.15, 0.5, 0.85):
            px = x+min(w-size, max(0, int(fx*w)-size//2))
            py = y+min(h-size, max(0, int(fy*h)-size//2))
            p = frame[py:py+size, px:px+size, :3].astype(np.float32)
            patches.append((29*p[:, :, 0]+150*p[:, :, 1]+77*p[:, :, 2])/256.)
    a = np.asarray(patches)
    c = a[:, 1:-1, 1:-1]
    gx = np.abs(a[:, 1:-1, 2:]-a[:, 1:-1, :-2])/2.
    gy = np.abs(a[:, 2:, 1:-1]-a[:, :-2, 1:-1])/2.
    gradient = gx+gy
    residual = c-(a[:, 1:-1, :-2]+a[:, 1:-1, 2:]+a[:, :-2, 1:-1]+a[:, 2:, 1:-1])/4.
    # Lowest-gradient half suppresses text boundaries; exclude clipped pixels.
    mask = (gradient <= np.percentile(gradient, 50)) & (c > 8) & (c < 247)
    r = residual[mask]
    noise = float(np.median(np.abs(r-np.median(r)))*1.4826/1.118) if r.size >= 64 else None
    illumination = None
    if isinstance(lux, (int, float)) and math.isfinite(lux) and lux >= 0:
        illumination = float(lux)
    return {'mean':float(a.mean()), 'dark_fraction':float(np.mean(a < 64)),
            'highlight_fraction':float(np.mean(a >= 224)),
            'contrast_range':float(np.percentile(a,90)-np.percentile(a,10)),
            'noise_sigma':noise, 'edge_fraction':float(np.mean(gradient > max(16., 3*(noise or 0)))),
            'unevenness':float(np.std(a.mean(axis=(1, 2)))), 'lux':illumination,
            'sample_pixels':int(a.size), 'scope':'9 raw ROI patches; heuristic estimates'}


class AutoQuality:
    INTERVAL = .5

    def __init__(self):
        self.last = -1e9
        self.key = None
        self.filtered = None
        self.local = None

    def due(self, state, now):
        if not state.automatic:
            self.filtered = None
            self.last = -1e9
            state.auto_status = {'status':'manual', 'reason':'参数由用户控制'}
            return False
        if state.frozen:
            state.auto_status = dict(state.auto_status, status='paused', reason='冻结画面，暂停自动调参')
            return False
        return now-self.last >= self.INTERVAL

    @staticmethod
    def tone_lut(state, lut):
        # Blend toward identity in noisy scenes instead of magnifying noise
        # with the full low-light curve. Both curves preserve highlights.
        strength = state.auto_status.get('tone_strength', 1.) if state.automatic else 1.
        return np.rint(np.arange(256)*(1-strength)+np.asarray(lut)*strength).astype(np.uint8)

    def update(self, state, frame, bounds, now, lux=None):
        if not self.due(state, now):
            return False
        self.last = now
        metrics = scene_metrics(frame, bounds, lux)
        if metrics is None:
            state.auto_status = {'status':'waiting', 'reason':'等待有效画面统计'}
            return False
        key = (tuple(bounds), state.mode)
        if key != self.key or self.filtered is None:
            self.filtered = dict(metrics)
            self.key = key
            self.local = bool(state.local_tone)
        else:
            for name in ('mean','dark_fraction','highlight_fraction','noise_sigma','edge_fraction','unevenness','contrast_range'):
                value = metrics[name]
                previous = self.filtered[name]
                self.filtered[name] = value if value is None or previous is None else .75*previous+.25*value
            self.filtered['lux'] = metrics['lux']
        m = self.filtered
        sigma = m['noise_sigma']
        noise = sigma if sigma is not None else 0.
        dark = m['mean'] < 90
        # Unknown noise never triggers aggressive denoising or sharpening.
        denoise = min(7, max(0, int(round((noise-1.)*.65)))) if sigma is not None else 0
        sharp = 1 if sigma is None or noise > 8 else (2 if noise > 4 or m['edge_fraction'] > .25 else (5 if m['contrast_range'] < 45 else 4))
        if m['edge_fraction'] < .005:
            sharp = min(sharp, 2)
        if m['unevenness'] > 28 and noise < 7 and m['highlight_fraction'] < .2:
            self.local = True
        elif m['unevenness'] < 18 or noise > 10 or m['highlight_fraction'] > .3:
            self.local = False
        # Conservative, bounded heuristics; let noisy/clipped scenes bypass
        # additional contrast. Do not switch the user's display/diagnostic mode.
        contrast = 0 if sigma is None or noise > 7 or m['highlight_fraction'] > .20 else (2 if m['contrast_range'] < 45 else (1 if m['contrast_range'] < 100 else 0))
        color = 4 if noise > 8 or m['highlight_fraction'] > .2 else (10 if dark else 6)
        binary_c = min(20, max(4, int(round(5+noise*.8+m['contrast_range']*.035))))
        if not hasattr(self, 'window31'): self.window31 = bool(state.window31)
        if m['unevenness'] > 24: self.window31 = True
        elif m['unevenness'] < 14: self.window31 = False
        targets = {'brightness':0, 'denoise':denoise, 'sharpness':sharp,
                   'noise':min(8, max(1, int(round(noise*.6)))), 'algorithm':3,
                   'contrast':contrast, 'local_tone':bool(self.local),
                   'color':color, 'binary_c':binary_c, 'window31':bool(self.window31)}
        # Existing adaptive LUT handles lift, avoiding a second gamma boost.
        # Integer controls change at most one step per second; no startup jump.
        if not hasattr(self, 'last_step') or now-self.last_step >= 1.:
            for name in ('brightness','denoise','sharpness','noise','contrast','color','binary_c'):
                value = getattr(state, name)
                setattr(state, name, value+max(-1, min(1, targets[name]-value)))
            state.algorithm = 3
            state.local_tone = targets['local_tone']
            state.window31 = targets['window31']
            self.last_step = now
        reason = '暗场提亮' if dark else '正常明暗'
        reason += '；抑制噪声' if noise > 4 else '；保留细节'
        if self.local: reason += '；补偿局部明暗'
        if m['lux'] is None: reason += '；照度缺失，使用图像判断'
        state.auto_status = {'status':'active', 'reason':reason, 'metrics':dict(m),
                             'targets':targets, 'updated_monotonic':now,
                             'tone_strength':max(.55, 1.-max(0., noise-4.)*.04),
                             'tone_control':'adaptive LUT using image brightness and valid lux'}
        return True
