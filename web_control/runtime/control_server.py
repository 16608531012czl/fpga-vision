"""Offline browser console; --simulate needs only Python stdlib. Python 3.6."""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from visual_aid.controls import State
from visual_aid.remote_control import apply_command, snapshot, save

ROOT = Path(__file__).resolve().parent


class Controller:
    def __init__(self, simulate=False):
        self.simulate = simulate
        self.state = State('detail'); self.state.mode = 4
        self.phase = 'stopped'; self.child = None; self.started = None
        self.seconds = 0; self.session = None; self.mail = None
        self.isp = 'detail'

    def status(self):
        if self.simulate:
            if self.phase == 'running' and self.seconds and time.monotonic()-self.started >= self.seconds:
                self.phase = 'completed'
            return {'simulation':True,'phase':self.phase,'ready':self.phase=='running',
                    'state':snapshot(self.state),'fps':None,'lux':None,'temperature_c':None,
                    'counters':{},'reason':None,'seconds':self.seconds,'isp':self.isp}
        guard = {}
        if self.child is not None:
            try: guard=json.loads((ROOT/'logs/jupyter_control_state.json').read_text(encoding='utf-8'))
            except (OSError, ValueError): pass
            if guard.get('guard_pid') != self.child.pid: guard={}
        alive = self.child is not None and self.child.poll() is None
        if self.child is not None and not alive and not guard:
            guard={'phase':'error','reason':'控制守护进程退出，可能已有其他项目运行。退出码：'+str(self.child.returncode)}
        phase = guard.get('phase','starting' if alive else 'stopped')
        if not alive and phase in ('starting','running','stopping'): phase='error'
        live = {}
        if self.mail:
            try: live=json.loads((self.mail/'live.json').read_text(encoding='utf-8'))
            except (OSError, ValueError): pass
        fresh = alive and live.get('session')==self.session and time.time()-live.get('updated',0)<3
        ready = fresh and phase=='running'
        if alive and phase=='running' and not fresh: phase='initializing'
        return {'simulation':False,'phase':phase,'ready':ready,'state':live.get('state'),
                'fps':live.get('fps') if fresh else None,'lux':live.get('lux') if fresh else None,
                'counters':live.get('counters',{}) if fresh else {},
                'temperature_c':guard.get('temperature_c'),'reason':guard.get('reason'),
                'cleanup_errors':guard.get('cleanup_errors',[]),
                'seconds':guard.get('seconds',self.seconds),'isp':guard.get('isp',self.isp)}

    def start(self, data):
        seconds=data.get('seconds',0); isp=data.get('isp','detail')
        if type(seconds) is not int or not 0<=seconds<=86400: raise ValueError('运行秒数需为 0～86400 的整数')
        if isp not in ('detail','baseline'): raise ValueError('Invalid camera mode')
        if (self.simulate and self.phase=='running') or (self.child and self.child.poll() is None):
            raise ValueError('程序已启动，请先停止')
        self.seconds=seconds; self.isp=isp; self.started=time.monotonic()
        if self.simulate:
            self.state=State('detail');self.state.mode=4;self.phase='running'
        else:
            if sys.platform != 'linux' or os.geteuid()!=0: raise ValueError('实板模式需要在 PYNQ 上用 sudo 启动')
            self.session=uuid.uuid4().hex
            self.mail=ROOT/'logs'/'control_sessions'/self.session
            self.mail.mkdir(parents=True)
            env=dict(os.environ,VISION_CONTROL_DIR=str(self.mail),VISION_CONTROL_SESSION=self.session)
            self.child=subprocess.Popen(['/usr/bin/python3',str(ROOT/'jupyter_gui_guard.py'),
                 '--isp',isp,'--seconds',str(seconds)],cwd=str(ROOT),env=env)
        return self.status()

    def stop(self):
        if self.simulate: self.phase='stopped'
        elif self.child is not None and self.child.poll() is None:
            self.child.send_signal(signal.SIGTERM)
        return self.status()

    def command(self, command):
        if not self.status()['ready']: raise ValueError('画面未就绪，暂不能调参')
        if self.simulate: apply_command(self.state,command); return self.status()
        # Validate before enqueueing, without modifying the actual board state.
        apply_command(State('detail'),command)
        name=uuid.uuid4().hex
        path=self.mail/('command_'+name+'.json'); result=self.mail/('result_'+name+'.json')
        save(path,{'session':self.session,'expires':time.time()+2,'command':command})
        until=time.monotonic()+2.5
        while time.monotonic()<until:
            if result.exists():
                data=json.loads(result.read_text(encoding='utf-8')); result.unlink()
                if not data['ok']: raise ValueError(data['error'])
                status=self.status();status['state']=data['state'];return status
            time.sleep(.02)
        raise ValueError('调参确认超时，请查看当前状态后再操作')


def handler(controller, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def respond(self, data, code=200, mime='application/json; charset=utf-8'):
            content=json.dumps(data,ensure_ascii=False).encode('utf-8') if isinstance(data,dict) else data
            self.send_response(code);self.send_header('Content-Type',mime)
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
        def authorized(self):
            return self.headers.get('X-Control-Token')==token
        def do_GET(self):
            path=urlsplit(self.path).path
            if path=='/api/status':
                if not self.authorized(): return self.respond({'error':'请输入控制口令'},403)
                return self.respond(controller.status())
            assets={'/':('index.html','text/html; charset=utf-8'),
                    '/app.js':('app.js','application/javascript; charset=utf-8'),
                    '/style.css':('style.css','text/css; charset=utf-8')}
            if path not in assets:return self.respond({'error':'Not found'},404)
            name,mime=assets[path]; self.respond((ROOT/'web'/name).read_bytes(),mime=mime)
        def do_POST(self):
            if not self.authorized(): return self.respond({'error':'请输入控制口令'},403)
            origin=self.headers.get('Origin')
            if origin and origin != 'http://'+self.headers.get('Host',''):
                return self.respond({'error':'不允许跨站控制'},403)
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=4096: raise ValueError('Invalid request length')
                data=json.loads(self.rfile.read(size).decode('utf-8'))
                if not isinstance(data,dict):raise ValueError('Expected object')
                path=urlsplit(self.path).path
                if path=='/api/start': result=controller.start(data)
                elif path=='/api/stop': result=controller.stop()
                elif path=='/api/command': result=controller.command(data)
                else:return self.respond({'error':'Not found'},404)
                self.respond(result)
            except (ValueError, TypeError, OSError) as exc:self.respond({'error':str(exc)},400)
    return Handler


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--simulate',action='store_true')
    parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8088)
    args=parser.parse_args()
    token=os.environ.get('VISION_WEB_TOKEN') or uuid.uuid4().hex[:16]
    control=Controller(args.simulate)
    server=HTTPServer((args.host,args.port),handler(control,token))
    def shutdown(signum,frame): raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM,shutdown)
    print('FPGA Vision | '+('SIMULATION' if args.simulate else 'BOARD'),flush=True)
    print('http://'+args.host+':'+str(args.port)+'/#token='+token,flush=True)
    print('Control token: '+token,flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        control.stop()
        if control.child is not None:
            try:control.child.wait(timeout=30)
            except subprocess.TimeoutExpired:print('Supervisor still stopping; check board logs.',flush=True)
        server.server_close()


if __name__=='__main__': main()
