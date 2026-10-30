import ast
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import HTTPServer

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'))
from visual_aid.controls import State
from visual_aid.remote_control import apply_command, snapshot, Mailbox, save
from control_server import Controller, handler


class StateTests(unittest.TestCase):
    def setUp(self): self.state=State('detail')
    def test_atomic_validation(self):
        before=snapshot(self.state)
        with self.assertRaises(ValueError):apply_command(self.state,{'op':'set','values':{'brightness':4,'sharpness':999}})
        self.assertEqual(before,snapshot(self.state))
    def test_all_bounds(self):
        from visual_aid.remote_control import LIMITS
        for key,(lo,hi) in LIMITS.items():
            for v in (lo,hi):apply_command(self.state,{'op':'set','values':{key:v}});self.assertEqual(getattr(self.state,key),v)
            for v in (lo-1,hi+1,True,1.5,'2'):
                with self.assertRaises(ValueError):apply_command(self.state,{'op':'set','values':{key:v}})
    def test_boolean_strictness(self):
        with self.assertRaises(ValueError):apply_command(self.state,{'op':'set','values':{'frozen':1}})
    def test_zoom_move_clamp(self):
        apply_command(self.state,{'op':'set','values':{'zoom':4}})
        for _ in range(100):apply_command(self.state,{'op':'move','direction':'left'})
        self.assertEqual(self.state.center[0],.125)
        apply_command(self.state,{'op':'set','values':{'zoom':1}})
        self.assertEqual(self.state.center,[.5,.5])
    def test_hardware_and_remote_share_state(self):
        apply_command(self.state,{'op':'set','values':{'brightness':5,'mode':4}})
        self.state.encoder('rotate',1);self.state.apply('mode')
        self.assertEqual(snapshot(self.state)['brightness'],6)
        self.assertEqual(snapshot(self.state)['mode'],0)
    def test_reset_preserves_view(self):
        apply_command(self.state,{'op':'set','values':{'zoom':4,'frozen':True,'brightness':8}})
        apply_command(self.state,{'op':'reset'})
        self.assertEqual(self.state.brightness,0);self.assertTrue(self.state.frozen);self.assertEqual(self.state.zoom,4)
    def test_invalid_commands(self):
        for c in (None,[],{}, {'op':'move','direction':'wrong'}, {'op':'set','values':{'mmio':4}}, {'op':'set','values':{}}, {'op':'set','values':{'zoom':3}}):
            with self.assertRaises(ValueError): apply_command(self.state,c)


class MailboxTests(unittest.TestCase):
    def test_ack_expiration_and_session(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,{'VISION_CONTROL_DIR':directory,'VISION_CONTROL_SESSION':'current'}):
            box=Mailbox();state=State('detail');root=Path(directory)
            for name,session,expires in [('a','current',time.time()+3),('b','old',time.time()+3),('c','current',0)]:
                save(root/('command_'+name+'.json'),{'session':session,'expires':expires,'command':{'op':'set','values':{'brightness':7}}})
            box.poll(state)
            self.assertEqual(state.brightness,7)
            self.assertTrue(json.loads((root/'result_a.json').read_text())['ok'])
            for name in ('b','c'):self.assertFalse(json.loads((root/('result_'+name+'.json')).read_text())['ok'])
            self.assertFalse(list(root.glob('command_*.json')))
            box.publish(state,19.9,{'lux':12},{'dma_errors':0})
            live=json.loads((root/'live.json').read_text());self.assertEqual(live['session'],'current');self.assertEqual(live['state']['brightness'],7)
    def test_disabled_without_env(self):
        with patch.dict(os.environ,{},clear=True):
            box=Mailbox();box.poll(State());box.publish(State(),0,{},{});self.assertIsNone(box.root)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.control=Controller(True)
        self.server=HTTPServer(('127.0.0.1',0),handler(self.control,'test-token'))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url='http://127.0.0.1:'+str(self.server.server_port)
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join()
    def request(self,path,data=None,token='test-token',origin=None):
        headers={'X-Control-Token':token,'Content-Type':'application/json'}
        if origin:headers['Origin']=origin
        req=Request(self.url+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
        with urlopen(req,timeout=4) as res:return json.loads(res.read())
    def test_lifecycle(self):
        self.assertFalse(self.request('/api/status')['ready'])
        self.assertTrue(self.request('/api/start',{'seconds':0})['ready'])
        with self.assertRaises(HTTPError):self.request('/api/start',{})
        data=self.request('/api/command',{'op':'set','values':{'brightness':3,'frozen':True}})
        self.assertEqual(data['state']['brightness'],3);self.assertTrue(data['state']['frozen'])
        self.assertIsNone(data['fps']);self.assertIsNone(data['temperature_c'])
        self.assertEqual(self.request('/api/stop',{})['phase'],'stopped')
        with self.assertRaises(HTTPError):self.request('/api/command',{'op':'reset'})
    def test_timer(self):
        self.control.start({'seconds':1});self.control.started-=2
        self.assertEqual(self.request('/api/status')['phase'],'completed')
    def test_auth_origin_and_traversal(self):
        for path,data,token,origin in [('/api/status',None,'bad',None),('/api/start',{},'test-token','http://other.invalid'),('/../control_server.py',None,'test-token',None)]:
            with self.assertRaises(HTTPError):self.request(path,data,token,origin)
    def test_duration_validation(self):
        for value in (-1,86401,True,1.2,'2'):
            with self.assertRaises(HTTPError):self.request('/api/start',{'seconds':value})
    def test_assets(self):
        for path in ('/','/app.js','/style.css'):
            with urlopen(self.url+path) as res:self.assertEqual(res.status,200)


class CompatibilityTests(unittest.TestCase):
    def test_python36_syntax(self):
        for path in (ROOT/'runtime').rglob('*.py'):
            ast.parse(path.read_text(encoding='utf-8-sig'),feature_version=(3,6))


class BoardBridgeTests(unittest.TestCase):
    def test_board_command_ack_and_stale_state(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,{'VISION_CONTROL_DIR':directory,'VISION_CONTROL_SESSION':'test'}):
            root=Path(directory);(root/'logs').mkdir()
            save(root/'logs/jupyter_control_state.json',{'guard_pid':123,'phase':'running','temperature_c':45})
            controller=Controller(False);controller.session='test';controller.mail=root
            controller.child=Mock(pid=123);controller.child.poll.return_value=None
            state=State('detail');box=Mailbox();box.publish(state,20,{'lux':100},{'dma_errors':0})
            done=threading.Event()
            def loop():
                while not done.is_set():box.poll(state);time.sleep(.005)
            thread=threading.Thread(target=loop);thread.start()
            try:
                with patch('control_server.ROOT',root):
                    self.assertTrue(controller.status()['ready'])
                    result=controller.command({'op':'set','values':{'brightness':4,'frozen':True}})
                    self.assertEqual(result['state']['brightness'],4);self.assertTrue(state.frozen)
                    live=json.loads((root/'live.json').read_text());live['updated']-=10;save(root/'live.json',live)
                    self.assertFalse(controller.status()['ready'])
                    with self.assertRaises(ValueError):controller.command({'op':'reset'})
            finally:done.set();thread.join()
    def test_disabled_mailbox_does_not_read_registers(self):
        from unittest.mock import Mock
        with patch.dict(os.environ,{},clear=True):
            read=Mock();Mailbox().publish(State(),20,{},read);read.assert_not_called()


if __name__=='__main__':unittest.main(verbosity=2)
