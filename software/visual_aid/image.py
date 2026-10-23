"""Host model and board ROI composition. No PYNQ dependency."""
import numpy as np
import cv2
from .fastcompose import half_resize


def gray8(bgr):
    x = bgr.astype(np.uint32)
    return ((77*x[:, :, 2]+150*x[:, :, 1]+29*x[:, :, 0]) >> 8).astype(np.uint8)


def trailing_mean(gray, size):
    """Integer causal square mean; unavailable border values are zero."""
    out = np.zeros(gray.shape, dtype=np.int32)
    if min(gray.shape) < size:
        return out
    integral = np.pad(gray.astype(np.int64), ((1, 0), (1, 0)), mode='constant').cumsum(0).cumsum(1)
    sums = integral[size:, size:]-integral[:-size, size:]-integral[size:, :-size]+integral[:-size, :-size]
    out[size-1:, size-1:] = sums // (size*size)
    return out


def trailing_edges(gray):
    """Sobel/Laplacian on a 3x3 window ending at each output coordinate."""
    h, w = gray.shape
    p = np.pad(gray.astype(np.int32), ((2, 0), (2, 0)), mode='constant')
    a,b,c,d,e,f,g,h0,i = [p[y:y+h, x:x+w] for y in range(3) for x in range(3)]
    gradient = (np.abs(c+2*f+i-a-2*d-g)+np.abs(g+2*h0+i-a-2*b-c)) >> 3
    lap = 4*e-b-h0-d-f
    gradient[:2] = 0;gradient[:, :2] = 0
    lap[:2] = 0;lap[:, :2] = 0
    return gradient, lap


def reconstruct_color(bgr,source_y,target_y,quality=0):
    chroma=bgr.astype(np.int32)-source_y[:,:,None]
    if not quality&1:
        return np.clip(target_y[:,:,None]+chroma,0,255).astype(np.uint8)
    limit=min(16,(quality>>1)&31)
    boost=np.where(source_y<16,min(4,limit),limit)
    gain=32+np.minimum(np.maximum(target_y-source_y,0)>>2,boost)
    candidate=target_y[:,:,None]+((chroma*gain[:,:,None])>>5)
    # Use exact pre-shift bounds, matching the hardware's common-gain test.
    fits=np.all((chroma*gain[:,:,None]>=-target_y[:,:,None]*32)&
                (chroma*gain[:,:,None]<=(255-target_y[:,:,None])*32),axis=2)
    one=target_y[:,:,None]+chroma
    half=target_y[:,:,None]+(chroma>>1)
    one_ok=np.all((one>=0)&(one<=255),axis=2)
    half_ok=np.all((half>=0)&(half<=255),axis=2)
    result=np.where(fits[:,:,None],candidate,np.where(one_ok[:,:,None],one,
                    np.where(half_ok[:,:,None],half,target_y[:,:,None])))
    return np.clip(result,0,255).astype(np.uint8)


def reference_enhance(bgr, cfg, lut=None, quality=0):
    """Bit-exact model of reading_enhance.sv, including seam/border policy."""
    if lut is None:
        lut = np.arange(256, dtype=np.uint8)
    g = gray8(bgr).astype(np.int32)
    h, w = g.shape
    window=31 if quality&64 and cfg&7==3 else 15
    m3, m15 = trailing_mean(g, 3), trailing_mean(g, window)
    y, x = np.indices(g.shape)
    if cfg & 8:
        half = w//2
        m3 = np.concatenate((trailing_mean(g[:, :half], 3), trailing_mean(g[:, half:], 3)), axis=1)
        m15 = np.concatenate((trailing_mean(g[:, :half], window), trailing_mean(g[:, half:], window)), axis=1)
        x = np.where(x >= half, x-half, x)
    ok3, ok15 = (x >= 2) & (y >= 2), (x >= window-1) & (y >= window-1)
    advanced = bool(cfg & (1 << 31))
    noise = (cfg >> 21) & 15
    denoise = ((cfg >> 17) & 15)*3 if advanced else 12
    base = np.where(ok3 & (np.abs(g-m3) <= denoise), m3, g) if cfg & 16 else g
    detail = np.where(ok15, base-m15, 0)
    sharp = np.where(ok3, g-m3, 0) if cfg & 32 else np.zeros_like(g)
    if advanced:
        if cfg & 8:
            left = trailing_edges(g[:, :w//2]);right = trailing_edges(g[:, w//2:])
            gradient = np.concatenate((left[0],right[0]),axis=1)
            lap = np.concatenate((left[1],right[1]),axis=1)
        else:
            gradient,lap = trailing_edges(g)
        method = (cfg >> 29) & 3
        delta = (lap >> 2) if method == 2 else g-m3
        scaled = (delta*((cfg >> 25) & 15)) >> 3
        if method == 3:
            scaled = np.where((gradient <= noise*4) | (np.abs(delta) <= noise*2), 0,
                              np.where((gradient < noise*4+24) | (gradient > 160), scaled >> 1, scaled))
            detail = np.where(gradient <= noise*4, 0, detail)
        sharp = np.where(ok3 & bool(cfg & 32) & (method != 0), np.clip(scaled,-24,24)*4, 0)
    enhanced = np.clip(np.asarray(lut, dtype=np.int32)[base]+((detail*((cfg >> 6) & 3)) >> 2)+(sharp >> 2), 0, 255)
    mode = cfg & 7
    if mode == 0 or mode > 4:
        result = bgr.copy()
    elif mode == 4:
        result = reconstruct_color(bgr,g,enhanced,quality)
    else:
        if mode == 1:
            z = enhanced
        elif mode == 2:
            z = 255-enhanced
        else:
            z = np.where(base < np.where(ok15, m15-((cfg >> 8) & 255), 128), 0, 255)
        result = np.repeat(z.astype(np.uint8)[:, :, None], 3, axis=2)
    if advanced and cfg & (1 << 16) and mode != 0:
        result = np.repeat(gradient.astype(np.uint8)[:, :, None], 3, axis=2)
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


def compose(frame, zoom=1, center=(0.5, 0.5), split=True, size=(1280, 720), out=None):
    """Duplicate the SAME source ROI into two panes before the PL filter.

    Aspect ratio is preserved with letterboxing. Freeze is applied to the full
    captured frame by the caller, so panning/zooming a frozen page still works.
    """
    roi, bounds = crop_roi(frame, zoom, center)
    w, h = size
    pane_w = w//2 if split else w
    ratio = min(pane_w/roi.shape[1], h/roi.shape[0])
    rw, rh = max(1, int(roi.shape[1]*ratio)), max(1, int(roi.shape[0]*ratio))
    if out is None:
        out = np.empty((h, w, frame.shape[2]), dtype=np.uint8)
    elif out.shape != (h,w,frame.shape[2]) or out.dtype != np.uint8 or not out.flags.writeable:
        raise ValueError('Composition output must be a writable uint8 canvas of matching shape')
    if np.may_share_memory(out, frame):
        raise ValueError('Composition output must not alias the capture buffer')
    ox, oy = (pane_w-rw)//2, (h-rh)//2
    # Compose directly into an owned HDMI buffer. Clear only letterbox regions;
    # OpenCV writes every active pixel, so a second full-frame copy is avoided.
    out[:oy].fill(0);out[oy+rh:].fill(0)
    out[oy:oy+rh,:ox].fill(0);out[oy:oy+rh,ox+rw:pane_w].fill(0)
    pane=out[oy:oy+rh,ox:ox+rw]
    second=out[oy:oy+rh,pane_w+ox:pane_w+ox+rw] if split else None
    native=half_resize(roi,pane,second)
    if native:
        if split:
            out[oy:oy+rh,pane_w:pane_w+ox].fill(0)
            out[oy:oy+rh,pane_w+ox+rw:].fill(0)
    elif roi.shape[:2] == (rh,rw):
        pane[:]=roi
    else:
        cv2.resize(roi,(rw,rh),dst=pane,interpolation=cv2.INTER_LINEAR)
    if split and not native:
        out[oy:oy+rh,pane_w:]=out[oy:oy+rh,:pane_w]
    return out, roi, bounds


class AdaptivePolicy:
    """Frame-level tone LUT; lowlight preserves highlights and caps near-black gain."""
    def __init__(self, profile='lowlight'):
        if profile not in ('lowlight', 'legacy', 'stable'):
            raise ValueError('Unknown tone profile: '+str(profile))
        self.profile = profile
        self.lut = np.arange(256, dtype=np.uint8)
        self._lut_float = self.lut.astype(float)
        self.mean = None
        self.level = None
        self.last = -1e9
        self._status = {'profile': profile, 'mean': None, 'target_gamma': 1.0,
                        'lut_mean_estimate': None}

    def status(self):
        """CPU statistics/estimate, not a measurement of the HDMI output."""
        return self._status.copy()

    def update(self, roi, now, lux=None):
        if now-self.last < 0.25:
            return None
        # Sample before conversion: avoid expanding an entire 720p frame into
        # temporary uint32 planes just to keep one sixteenth of the pixels.
        # At most about 160x90 samples: exposure/tone is a frame-level statistic,
        # while the full-resolution denoise and edge operators remain in PL.
        stride=max(1,int(np.ceil(max(roi.shape[1]/160.0,roi.shape[0]/90.0))))
        samples = gray8(roi[::stride, ::stride, :3])
        mean = float(samples.mean())
        # Reject invalid ambient readings rather than interpreting them as dark.
        lux = float(lux) if lux is not None and np.isfinite(lux) and lux >= 0 else None
        ambient = 0 if lux is None else float(np.clip((100-lux)/100, 0, 1))
        first = self.mean is None
        dt = 0.25 if first else max(0, now-self.last)
        alpha = 1-np.exp(-dt/(2.0 if self.profile=='stable' else 0.6))
        p60 = float(np.percentile(samples, 60))
        level = 0.5*mean+0.5*p60
        if self.profile == 'legacy':
            # Retain the previous policy exactly for same-scene comparisons.
            self.mean = mean if first else 0.8*self.mean+0.2*mean
            exponent = float(np.clip(1+(self.mean-120)/250-0.08*ambient, 0.55, 1.3))
            target = np.rint(255*(np.arange(256)/255.0)**exponent)
            new = np.rint(0.75*self.lut+0.25*target).astype(np.uint8)
        else:
            self.mean = mean if first else (1-alpha)*self.mean+alpha*mean
            if first:self.level=level
            elif self.profile!='stable' or abs(level-self.level)>3:
                self.level=(1-alpha)*self.level+alpha*level
            # Lux strengthens a genuinely dark scene, not an already bright page.
            darkness = float(np.clip((144-self.level)/112, 0, 1))
            exponent = float(np.clip(1-(0.74+0.12*ambient)*darkness, 0.35, 1.0))
            x = np.arange(256, dtype=float)
            # Anchor the curve at 224: values >=224 remain unchanged. Both
            # branches and the near-black cap are monotonic and preserve zero.
            target = np.where(x < 224, 224*(x/224.0)**exponent, x)
            target = np.minimum(target, (3 if self.profile=='stable' else 5)*x)
            if self.profile=='stable':
                # One luma level per update after startup. Small exposure
                # fluctuations cannot repeatedly change the complete curve.
                if first:self._lut_float=target
                else:self._lut_float+=np.clip(alpha*(target-self._lut_float),-1.,1.)
            else:self._lut_float = (1-alpha)*self._lut_float+alpha*target
            new = np.rint(self._lut_float).astype(np.uint8)
        self.last = now
        histogram = np.bincount(samples.ravel(), minlength=256)
        self._status = {'profile': self.profile, 'mean': mean, 'smoothed_mean': self.mean,
                        'p60': p60, 'dark_fraction': float(np.mean(samples < 64)),
                        'lux': lux, 'target_gamma': exponent,
                        'lut_mean_estimate': float(np.dot(histogram, new.astype(float))/samples.size),
                        'estimate_scope': 'sampled source ROI through CPU LUT only; not HDMI measurement'}
        if np.max(np.abs(new.astype(int)-self.lut.astype(int))) < 1:
            return None
        self.lut = new
        return new.copy()
