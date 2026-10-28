"""Local recovery of a stalled SSH service through the board's Jupyter API."""
import json
import os
import time
import uuid
import requests
import websocket

BASE='http://192.168.2.99:9090'


def main():
    session=requests.Session();session.trust_env=False
    response=session.get(BASE+'/login',timeout=10);response.raise_for_status()
    token=session.cookies.get('_xsrf')
    session.post(BASE+'/login',data={'_xsrf':token,'password':os.environ.get('FPGA_BOARD_PASSWORD','xilinx')},
                 headers={'Referer':BASE+'/login'},timeout=10).raise_for_status()
    session.get(BASE+'/api/status',timeout=10).raise_for_status()
    response=session.post(BASE+'/api/kernels',json={'name':'python3'},headers={'X-XSRFToken':token},timeout=15)
    response.raise_for_status();kernel=response.json()['id'];ws=None
    try:
        cookie='; '.join(k+'='+v for k,v in session.cookies.get_dict().items())
        ws=websocket.create_connection('ws://192.168.2.99:9090/api/kernels/'+kernel+'/channels',
                                      cookie=cookie,origin=BASE,timeout=20,http_proxy_host=None)
        message_id=uuid.uuid4().hex
        code=("import os,subprocess,json\n"
              "print('RECOVERY_UID',os.geteuid())\n"
              "print('UPTIME',open('/proc/uptime').read().strip())\n"
              "p=subprocess.run(['ps','-eo','pid,ppid,args'],stdout=subprocess.PIPE,universal_newlines=True)\n"
              "print('SSH_PROCESSES',[line for line in p.stdout.splitlines() if 'sshd' in line])\n"
              "if os.geteuid()==0:\n"
              " p=subprocess.run(['systemctl','restart','ssh'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)\n"
              " print('SSH_RESTART',p.returncode,p.stderr)\n"
              "else: print('SSH_RESTART_REQUIRES_ROOT')\n")
        ws.send(json.dumps({'header':{'msg_id':message_id,'username':'local-board-validation',
                'session':uuid.uuid4().hex,'msg_type':'execute_request','version':'5.3'},
                'parent_header':{},'metadata':{},'channel':'shell',
                'content':{'code':code,'silent':False,'store_history':False,
                           'user_expressions':{},'allow_stdin':False,'stop_on_error':True}}))
        deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            message=json.loads(ws.recv())
            if message.get('parent_header',{}).get('msg_id')!=message_id:continue
            kind=message['header']['msg_type'];content=message['content']
            if kind=='stream':print(content.get('text',''),end='',flush=True)
            if kind=='error':raise RuntimeError(content.get('ename','')+': '+content.get('evalue',''))
            if kind=='status' and content.get('execution_state')=='idle':return
        raise TimeoutError('Jupyter recovery did not finish')
    finally:
        if ws is not None:ws.close()
        session.delete(BASE+'/api/kernels/'+kernel,headers={'X-XSRFToken':token},timeout=10).raise_for_status()


if __name__=='__main__':main()
