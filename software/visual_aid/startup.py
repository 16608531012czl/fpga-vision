"""Wait for PYNQ's boot LED service before replacing its base overlay."""
import subprocess
import time


def _boot_overlay_state():
    output=subprocess.check_output(
        ['systemctl','show','boot_leds.service','--property=LoadState',
         '--property=ActiveState','--property=Job','--no-pager'],
        universal_newlines=True,timeout=5)
    return dict(line.split('=',1) for line in output.splitlines() if '=' in line)


def wait_for_boot_overlay(timeout=90):
    """A queued or running boot job can still overwrite a custom bitstream."""
    deadline=time.monotonic()+timeout
    announced=False
    while True:
        state=_boot_overlay_state()
        if state.get('LoadState')=='not-found':
            return
        job=state.get('Job','').strip()
        busy=(job not in ('','0') or state.get('ActiveState') in ('activating','deactivating'))
        if not busy:
            return
        if time.monotonic()>=deadline:
            raise TimeoutError('PYNQ boot overlay is still starting; wait for boot LEDs to finish')
        if not announced:
            print('Waiting for PYNQ boot overlay to finish before loading this project.',flush=True)
            announced=True
        time.sleep(0.2)
