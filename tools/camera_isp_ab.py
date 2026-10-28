"""Run a reversible same-scene ISP sharpness comparison using the focus probe."""
import camera_focus_probe as probe

old = """ wait_scene('near');scene_run('near',True)
 wait_scene('far');scene_run('far',False)
 result['outcome']='completed'"""
new = """ # Keep continuous AF active and freeze AEC/AGC only for this
 # paired comparison. Record AF state on each sample; the lens may move.
 # The finally block restores every changed register.
 # Let the user frame the scene after the long AF upload, then capture
 # the whole A/B sequence within approximately 15 seconds.
 wait_scene('near')
 stream_for(3)
 result['steps'].append({'operation':'continuous_focus','lens_may_move':True})
 exposure_regs=(0x3500,0x3501,0x3502,0x350a,0x350b)
 exposure_before={hex(r):cam.read(r) for r in exposure_regs}
 control_before=cam.read(0x3503)
 cam.write(0x3503,control_before|3)
 assert cam.read(0x3503)==(control_before|3)
 result['locked_exposure_before']=exposure_before
 result['exposure_control_original']=control_before
 print('AB_START '+json.dumps({'baseline_5302':baseline[0x5302],'candidate_5302':32,'exposure':exposure_before}),flush=True)
 for label,value in (('baseline_1',baseline[0x5302]),('detail_1',32),('baseline_2',baseline[0x5302]),('detail_2',32)):
  cam.write(0x5302,value)
  assert cam.read(0x5302)==value
  stream_for(2)
  capture(label)
  stream_for(.4)
 result['locked_exposure_after']={hex(r):cam.read(r) for r in exposure_regs}
 result['exposure_unchanged']=(result['locked_exposure_before']==result['locked_exposure_after'])
 cam.write(0x3503,control_before)
 assert cam.read(0x3503)==control_before
 result['outcome']='completed'"""
assert old in probe.BOARD_CODE
probe.BOARD_CODE=probe.BOARD_CODE.replace(old,new)
probe.BOARD_CODE=probe.BOARD_CODE.replace(
    "baseline={reg:cam.read(reg) for reg in (0x5000,0x5001,0x5308,0x5302,0x530b)}",
    "baseline={reg:cam.read(reg) for reg in (0x3503,0x5000,0x5001,0x5308,0x5302,0x530b)}")

if __name__=='__main__':
    raise SystemExit(probe.main())
