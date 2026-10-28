from pathlib import Path
import html
import json
import os
import signal
import subprocess
import threading
import time
import ipywidgets as widgets
from IPython.display import display, HTML
from IPython import get_ipython

ROOT = Path('/home/xilinx/jupyter_notebooks/visual_aid_v4_camera_detail_20261028')
STATE = ROOT/'logs/jupyter_control_state.json'
GUARD = ROOT/'jupyter_gui_guard.py'

try:
    _fpga_panel_stop.set()
except (NameError, AttributeError):
    pass
_fpga_panel_stop = threading.Event()

title = widgets.HTML('<h2>FPGA 视觉辅助 · 一键控制</h2>'
                     '<p>选择画质后点击启动；画面显示在 HDMI 显示器上。</p>')
mode = widgets.ToggleButtons(options=[('清晰模式', 'detail'), ('标准模式', 'baseline')],
                             value='detail', description='画质：')
start = widgets.Button(description='启动画面（持续）', button_style='success', icon='play',
                       layout=widgets.Layout(width='170px'))
duration = widgets.IntText(value=120, description='运行秒数：',
                           layout=widgets.Layout(width='220px'))
test = widgets.Button(description='按设定时长运行', button_style='info', icon='clock-o',
                      layout=widgets.Layout(width='170px'))
stop = widgets.Button(description='停止', button_style='danger', icon='stop')
refresh_button = widgets.Button(description='刷新状态', icon='refresh')
status = widgets.HTML()
detail = widgets.HTML()
notice = widgets.HTML('<p>运行秒数从实时画面开始后计算，初始化约 1 分钟另计。'
                      '例如 300 秒为 5 分钟、600 秒为 10 分钟。随时可点击停止。<br>'
                      '改秒数影响下一次启动；运行中请先停止再设置。'
                      '停止按钮会先请求程序正常清理；'
                      '关闭网页不会自动停止正在运行的画面。</p>')
_pending = [None]
_message = ['']


def _read_state():
    try:
        return json.loads(STATE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def _start_ticks(pid):
    text = Path('/proc/{}/stat'.format(pid)).read_text()
    return int(text[text.rfind(')')+2:].split()[19])


def _valid_guard(state):
    try:
        pid = int(state['guard_pid'])
        if state['boot_id'] != Path('/proc/sys/kernel/random/boot_id').read_text().strip():
            return False
        if _start_ticks(pid) != int(state['guard_start_ticks']):
            return False
        argv = Path('/proc/{}/cmdline'.format(pid)).read_bytes().split(b'\0')
        return str(GUARD).encode() in argv
    except (KeyError, ValueError, OSError):
        return False


def _tail(path):
    try:
        with open(path, 'rb') as f:
            f.seek(0, 2); f.seek(max(0, f.tell()-65536))
            return f.read().decode('utf-8', errors='replace').splitlines()
    except OSError:
        return []


def _live_info(state):
    lines = _tail(state.get('log', ''))
    for line in reversed(lines):
        try: record = json.loads(line)
        except ValueError: continue
        if 'rolling_unique_capture_fps' in record:
            sensor = record.get('sensors', {})
            lux = sensor.get('lux')
            return '采集：{:.1f} FPS　光照：{} lux'.format(
                record['rolling_unique_capture_fps'], '--' if lux is None else round(lux, 1))
    for line in reversed(lines):
        if line.startswith('AF firmware '):
            return '自动对焦初始化：'+line[len('AF firmware '):]
    return '正在启动，请等待摄像头初始化。'


def _refresh():
    state = _read_state()
    running = state.get('phase') in ('starting', 'running', 'stopping') and _valid_guard(state)
    if _pending[0] is not None and _pending[0].poll() is None and not running:
        running = True
    phase = state.get('phase', '')
    labels = {'starting':'正在启动', 'running':'运行中', 'stopping':'正在安全停止',
              'stopped':'已停止', 'completed':'测试已完成', 'error':'未能运行'}
    if running:
        label=labels.get(phase,'正在启动')
    elif phase in ('starting','running','stopping'):
        label='上次运行已退出，请刷新或重新启动'
    else:
        label=labels.get(phase,'未启动')
    start.disabled = test.disabled = running
    stop.disabled = not running
    mode.disabled = running
    duration.disabled = running
    temp = state.get('temperature_c')
    status.value = '<p><b>状态：{}</b>　板温：{} °C</p>'.format(
        html.escape(label), '--' if temp is None else html.escape(str(temp)))
    parts=[]
    if running:parts.append(_live_info(state))
    if state.get('report_outcome'):parts.append('报告结果：'+str(state['report_outcome']))
    if state.get('reason') and state['reason']!='user_stop':parts.append('原因：'+str(state['reason']))
    if _message[0]:parts.append(_message[0])
    detail.value='<p>{}</p>'.format('<br>'.join(html.escape(x) for x in parts))


def _start(seconds):
    _message[0]=''
    state=_read_state()
    if _valid_guard(state) or (_pending[0] is not None and _pending[0].poll() is None):
        _message[0]='已有控制进程运行，未重复启动。';_refresh();return
    if os.geteuid()!=0:
        _message[0]='当前 Jupyter 内核不是 root，无法加载硬件；请检查 Jupyter 内核运行用户。';_refresh();return
    if not GUARD.is_file():
        _message[0]='控制程序不存在，请检查项目目录。';_refresh();return
    _pending[0]=subprocess.Popen(['/usr/bin/python3','-u',str(GUARD),'--isp',mode.value,
                                  '--seconds',str(seconds)],cwd=str(ROOT),
                                 stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    _message[0]='启动请求已发送。'
    _refresh()


def _stop():
    _message[0]=''
    state=_read_state()
    if _valid_guard(state):
        os.kill(int(state['guard_pid']),signal.SIGINT)
        _message[0]='停止请求已发送，正在等待清理。'
    elif _pending[0] is not None and _pending[0].poll() is None:
        _pending[0].send_signal(signal.SIGINT)
        _message[0]='启动中的控制进程已收到停止请求。'
    else:_message[0]='当前没有本页面启动的程序。'
    _refresh()


def _start_timed():
    seconds = int(duration.value)
    if seconds <= 0:
        _message[0]='请输入大于 0 的整数秒数；持续运行请点击绿色启动按钮。'
        _refresh()
        return
    _start(seconds)


start.on_click(lambda button:_start(0))
test.on_click(lambda button:_start_timed())
stop.on_click(lambda button:_stop())
refresh_button.on_click(lambda button:_refresh())
display(title, mode, widgets.HBox([duration,test]),
        widgets.HBox([start,stop,refresh_button]), status, detail, notice)
_refresh()


def _monitor():
    while not _fpga_panel_stop.wait(2):
        try:get_ipython().kernel.io_loop.add_callback(_refresh)
        except Exception:return

threading.Thread(target=_monitor, name='fpga-panel-monitor', daemon=True).start()
