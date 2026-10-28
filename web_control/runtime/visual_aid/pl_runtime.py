"""Live PL composition with explicit raw/canvas/scanout ownership."""
import time
from collections import deque
import numpy as np
from .image import compose
from .local import TilePolicy
from .encoder import record_event
from .status_panel import StatusPanel
from .remote_control import Mailbox

MODES=('RAW','GRAY','INVERSE','BINARY','COLOR')


def run_pl(dev,state,controls,encoder,policy,sensors,args,report,start,af_label,brightness_lut):
    remote = Mailbox()
    tiles=TilePolicy();times=deque();frozen=None;frozen_id=None;frozen_view=None
    frozen_canvas=None;frozen_split=None;last_update=-1e9;last_text=-1e9
    panel=StatusPanel();last_text_signature=None;last_text_lines=None
    pending_lut=None;pending_gains=None;tone_key=None;first=last=None;fps=0.
    descriptor={};last_stats=None;last_stats_key=None
    report['pl_pipeline']={'cpu_live_frame_copy':False,'source':'PL renders completed DDR frame while next raw capture runs independently',
                           'scaler':'2x2 box downscale, integer nearest upscale',
                           'local_mapping':'8x6 bounded mean-based gains with bilinear interpolation',
                           'statistics':'source ROI tile averages, not a full pixel histogram',
                           'color_denoise':'gated spatial 3x3 in PL, no temporal history'}
    dev.set_view(state);dev.arm(0)
    while args.seconds==0 or time.monotonic()-start<args.seconds:
        begin=time.monotonic()
        index,frame_id,frame=dev.finish(rearm=True,invalidate=False)
        now=time.monotonic();first=now if first is None else first;last=now
        report['_capture_first']=first;report['_capture_last']=last
        report['unique_camera_frames']+=1;report['camera_capture_verified']=True
        times.append(now)
        while len(times)>2 and now-times[0]>1:times.popleft()
        fps=(len(times)-1)/(now-times[0]) if len(times)>1 else 0.
        completed=dev.views[index];descriptor[frame_id]=completed
        if len(descriptor)>12:descriptor.pop(next(iter(descriptor)))
        was_frozen=state.frozen
        remote.poll(state)
        events,encoder_raw=encoder.poll(dev.mmio)
        for event,value in events:
            state.encoder(event,value);record_event(report,event,value)
            report['events'].append({'t':now-start,'encoder_event':event,'value':value,'parameters':state.snapshot()})
        for key in controls.poll(dev.mmio.read(0x38),now):
            state.apply(key);report['events'].append({'t':now-start,'key':key})
        if state.frozen and not was_frozen:
            dev.render_live=False
            dev.scanout.pinned_raw=index;dev.buffers[index].invalidate()
            frozen=frame;frozen_id=frame_id;frozen_view=None
        if not state.frozen:
            dev.render_live=True
            frozen=None;frozen_id=None;frozen_view=None;dev.scanout.pinned_raw=None
        dev.set_view(state)
        if state.frozen:
            # Recompose only a changed frozen ROI. Camera continues in the
            # other raw slots, while the original full-resolution source stays pinned.
            if dev.view_request!=frozen_view:
                frozen_canvas=dev.free_canvas_slot();buffer=dev.canvases[frozen_canvas]
                buffer.flags.writeable=True
                try:
                    image=np.asarray(buffer).view(np.uint8).reshape(720,1280,4)
                    _,roi,bounds=compose(frozen,state.zoom,state.center,state.split,out=image)
                    buffer.flush()
                finally:buffer.flags.writeable=False
                dev.canvas_layout[frozen_canvas]=state.split
                frozen_view=dev.view_request;frozen_split=state.split
                # Frozen policy samples still refer to the pinned source.
                policy.update(roi,now,None)
            cfg=(state.config()&~8)|(8 if frozen_split else 0)
            dev.slot_config(frozen_canvas,cfg)
            dev.scanout.present(frozen_canvas)
            bounds=frozen_view[2]
        else:
            cfg=(state.config()&~8)|(8 if completed[3] else 0)
            dev.queue_render(index,frame_id,cfg,completed);bounds=completed[2]
        dev.mmio.write(0x78,state.quality_config())
        composed=time.monotonic()
        readings=sensors.snapshot() if sensors is not None else {'lux':None,'distance_mm':None}
        remote.publish(state, fps, readings, dev.counters)
        seen=report.setdefault('sensor_readings_observed',{'lux':False,'distance_mm':False})
        for name in seen:
            seen[name] |= readings[name] is not None
        if now-last_update>=.25:
            stats=dev.tile_statistics()
            if stats is not None and stats['frame_id'] in descriptor:
                source_view=descriptor[stats['frame_id']]
                key=source_view[:2]
                last_stats={'frame_id':stats['frame_id'],'mean':stats['mean'],'roi':source_view[2]}
                if not state.frozen:
                    sample=np.repeat(np.rint(stats['means']).astype(np.uint8)[:,:,None],3,axis=2)
                    policy.update(sample,now,readings['lux'])
                    pending_gains=tiles.update(stats['means'],key,bool(state.local_tone))
                    last_stats_key=key
            # Disable stale local gains when the displayed ROI is changing or frozen.
            if state.frozen or last_stats_key!=dev.view_request[:2]:pending_gains=np.full((6,8),256,np.uint16)
            last_update=now
        base=policy.lut if state.automatic else np.arange(256,dtype=np.uint8)
        next_key=(state.automatic,state.brightness,base.tobytes())
        if tone_key!=next_key:pending_lut=brightness_lut(base,state.brightness);tone_key=next_key
        if pending_lut is not None and dev.gamma(pending_lut):pending_lut=None
        if pending_gains is not None and dev.local_gains(pending_gains):pending_gains=None
        adapted=time.monotonic()
        # Display-only smoothing keeps input data and the automatic policy intact.
        panel.sample(now, fps, readings['lux'])
        signature=panel.signature(state)
        changed=signature!=last_text_signature
        if now-last_text>=.25 or (changed and now-last_text>=.10):
            lines=panel.lines(state, af_label)
            if lines==last_text_lines:
                last_text_signature=signature
                last_text=now
            elif dev.status_text(lines):
                last_text_signature=signature
                last_text_lines=lines
                last_text=now
        ended=time.monotonic()
        report['pl_rendered_frames']=dev.render_count
        report['pl_observed_display_updates']=dev.display_count
        report['measured_pl_render_fps']=((dev.render_count-1)/(dev.render_last-dev.render_first)
            if dev.render_count>1 and dev.render_last>dev.render_first else None)
        if report['unique_camera_frames']%15==0:
            active,desired=dev.scanout.status();hardware_slot=dev.mmio.read(0xb8)
            sample={'t':now-start,'capture_id':frame_id,'render_source_id':frozen_id if state.frozen else frame_id,
                    'roi':bounds,'zoom':state.zoom,'config':cfg,'quality_config':state.quality_config(),
                    'frozen':state.frozen,'automatic':state.automatic,'sensors':readings,'parameters':state.snapshot(),
                    'encoder':encoder_raw,'counters':dev.counters(),'tone':policy.status(),'tile_statistics':last_stats,
                    'rolling_unique_capture_fps':fps,'scanout':{'active':active,'desired':desired,'hardware_slot':hardware_slot},
                    'timing_ms':{'capture_wait':(now-begin)*1000,'compose':(composed-now)*1000,'policy':(adapted-composed)*1000,'display':(ended-adapted)*1000}}
            report['samples'].append(sample)
            import json
            print(json.dumps(sample),flush=True)
            if args.seconds==0 and len(report['samples'])>600:del report['samples'][:300]
    return first,last
