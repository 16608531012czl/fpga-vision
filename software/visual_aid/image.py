"""Host model and board ROI composition. No PYNQ dependency."""
import numpy as np
import cv2


def gray8(bgr):
    x = bgr.astype(np.uint32)
    return ((77*x[:, :, 2]+150*x[:, :, 1]+29*x[:, :, 0]) >> 8).astype(np.uint8)


def trailing_mean(gray, size):
    """Integer causal square mean; unavailable border values are zero."""
    out = np.zeros(gray.shape, dtype=np.int32)
    if min(gray.shape) < size:
        return out
    integral = np.pad(gray.astype(np.int64), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    sums = integral[size:, size:]-integral[:-size, size:]-integral[size:, :-size]+integral[:-size, :-size]
    out[size-1:, size-1:] = sums // (size*size)
    return out


def reference_enhance(bgr, cfg, lut=None):
    """Bit-exact model of reading_enhance.sv, including seam/border policy."""
    if lut is None:
        lut = np.arange(256, dtype=np.uint8)
    g = gray8(bgr).astype(np.int32)
    h, w = g.shape
    m3, m15 = trailing_mean(g, 3), trailing_mean(g, 15)
    y, x = np.indices(g.shape)
    if cfg & 8:
        half = w//2
        m3 = np.concatenate((trailing_mean(g[:, :half], 3), trailing_mean(g[:, half:], 3)), axis=1)
        m15 = np.concatenate((trailing_mean(g[:, :half], 15), trailing_mean(g[:, half:], 15)), axis=1)
        x = np.where(x >= half, x-half, x)
    ok3, ok15 = (x >= 2) & (y >= 2), (x >= 14) & (y >= 14)
    base = np.where(ok3 & (np.abs(g-m3) <= 12), m3, g) if cfg & 16 else g
    detail = np.where(ok15, base-m15, 0)
    sharp = np.where(ok3, g-m3, 0) if cfg & 32 else np.zeros_like(g)
    enhanced = np.clip(np.asarray(lut, dtype=np.int32)[base]+((detail*((cfg >> 6) & 3)) >> 2)+(sharp >> 2), 0, 255)
    mode = cfg & 7
    if mode == 0 or mode > 4:
        result = bgr.copy()
    elif mode == 4:
        result = np.clip(bgr.astype(np.int32)+(enhanced-g)[:, :, None], 0, 255).astype(np.uint8)
    else:
        if mode == 1:
            z = enhanced
        elif mode == 2:
            z = 255-enhanced
        else:
            z = np.where(base < np.where(ok15, m15-((cfg >> 8) & 255), 128), 0, 255)
        result = np.repeat(z.astype(np.uint8)[:, :, None], 3, axis=2)
    if cfg & 8:
        result[:, :w//2] = bgr[:, :w//2]
    return result


def crop_roi(frame, zoom=1, center=(0.5, 0.5)):
    if zoom not in (1, 2, 4):
        raise ValueError('zoom must be 1, 2 or 4')
    h, w = frame.shape[:2]
    rw, rh = max(1, w//zoom), max(1, h//zoom)
    cx, cy = center
    x = int(np.clip(round(cx*w-rw/2), 0, w-rw))
    y = int(np.clip(round(cy*h-rh/2), 0, h-rh))
    return frame[y:y+rh, x:x+rw], (x, y, rw, rh)


def compose(frame, zoom=1, center=(0.5, 0.5), split=True, size=(1280, 720)):
    """Duplicate the SAME source ROI into two panes before the PL filter.

    Aspect ratio is preserved with letterboxing. Freeze is applied to the full
    captured frame by the caller, so panning/zooming a frozen page still works.
    """
    roi, bounds = crop_roi(frame, zoom, center)
    w, h = size
    pane_w = w//2 if split else w
    ratio = min(pane_w/roi.shape[1], h/roi.shape[0])
    rw, rh = max(1, int(roi.shape[1]*ratio)), max(1, int(roi.shape[0]*ratio))
    resized = cv2.resize(roi, (rw, rh), interpolation=cv2.INTER_LINEAR)
    out = np.zeros((h, w, frame.shape[2]), dtype=np.uint8)
    ox, oy = (pane_w-rw)//2, (h-rh)//2
    out[oy:oy+rh, ox:ox+rw] = resized
    if split:
        out[oy:oy+rh, pane_w+ox:pane_w+ox+rw] = resized
    return out, roi, bounds


class AdaptivePolicy:
    """Scene brightness + optional measured lux, with slow temporal adaptation."""
    def __init__(self):
        self.lut = np.arange(256, dtype=np.uint8)
        self.mean = None
        self.last = -1e9

    def update(self, roi, now, lux=None):
        if now-self.last < 0.25:
            return None
        # Sample before conversion: avoid expanding an entire 720p frame into
        # temporary uint32 planes just to keep one sixteenth of the pixels.
        samples = gray8(roi[::4, ::4, :3])
        mean = float(samples.mean())
        self.mean = mean if self.mean is None else 0.8*self.mean+0.2*mean
        # Image brightness remains primary: low ambient lux alone must not
        # over-brighten a page already correctly exposed by the camera AEC.
        ambient = 0 if lux is None else float(np.clip((100-lux)/100, 0, 1))
        exponent = float(np.clip(1+(self.mean-120)/250-0.08*ambient, 0.55, 1.3))
        target = np.rint(255*(np.arange(256)/255.0)**exponent)
        new = np.rint(0.75*self.lut+0.25*target).astype(np.uint8)
        self.last = now
        if np.max(np.abs(new.astype(int)-self.lut.astype(int))) < 1:
            return None
        self.lut = new
        return new.copy()
