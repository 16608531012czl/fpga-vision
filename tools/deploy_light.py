"""Deploy the verified Arduino sensor variant to its own board directory."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import shlex
import socket
import warnings
import zipfile

warnings.filterwarnings('ignore')
import paramiko

ROOT = Path(__file__).resolve().parents[1]
NAME = 'visual_aid_v4_camera_detail_20261028'
REMOTE = '/home/xilinx/jupyter_notebooks/' + NAME


def main():
    manifest = json.loads((ROOT/'software/board/build_manifest.json').read_text())
    archive = ROOT/'delivery'/(NAME+'_board.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for path, expected in manifest['payload_sha256'].items():
            content = (ROOT/'software'/path).read_bytes()
            assert hashlib.sha256(content).hexdigest() == expected, path
            z.writestr(NAME+'/'+path, content)
        z.write(ROOT/'software/board/build_manifest.json', NAME+'/board/build_manifest.json')
        z.write(ROOT/'README_zh.md', NAME+'/README_board_zh.md')
        z.write(ROOT/'docs/pins.json', NAME+'/docs/pins.json')
        for path in ('system_timing_values.json', 'arduino_io.rpt', 'arduino_variant_lineage.json', 'software_tests.json'):
            z.write(ROOT/'reports'/path, NAME+'/host_validation/'+path)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for path, expected in manifest['payload_sha256'].items():
            assert hashlib.sha256(z.read(NAME+'/'+path)).hexdigest() == expected
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(digest+'  '+archive.name+'\n')
    password = os.environ.get('FPGA_BOARD_PASSWORD', 'xilinx')
    client = paramiko.SSHClient(); client.load_system_host_keys()
    connection = socket.socket(); connection.settimeout(10)
    connection.bind(('192.168.2.1', 0)); connection.connect(('192.168.2.99', 22))
    client.connect('192.168.2.99', username='xilinx', password=password, sock=connection,
                   look_for_keys=False, allow_agent=False, timeout=10, banner_timeout=10, auth_timeout=10)
    remote_archive = '/tmp/'+archive.name
    try:
        with client.open_sftp() as sftp:
            sftp.put(str(archive), remote_archive)
        script = r'''
from pathlib import Path, PurePosixPath
import zipfile,hashlib,sys
archive,root,name,expected=sys.argv[1:]
assert hashlib.sha256(Path(archive).read_bytes()).hexdigest()==expected
target=Path(root)
if target.exists():raise RuntimeError('Variant target already exists; do not overwrite a deployment')
target.mkdir()
with zipfile.ZipFile(archive) as z:
 for item in z.infolist():
  path=PurePosixPath(item.filename)
  assert path.parts[0]==name and '..' not in path.parts and not path.is_absolute()
  dst=target.joinpath(*path.parts[1:])
  dst.parent.mkdir(parents=True,exist_ok=True)
  if not item.is_dir():dst.write_bytes(z.read(item.filename))
print('VERIFIED_DEPLOYMENT '+str(target))
'''
        command = '/usr/bin/python3 -c ' + shlex.quote(script) + ' ' + ' '.join(
            shlex.quote(s) for s in (remote_archive, REMOTE, NAME, digest))
        _, out, err = client.exec_command(command, timeout=30)
        output = out.read().decode(); errors = err.read().decode(); code = out.channel.recv_exit_status()
        print(output, end=''); assert code == 0, errors
        inp, out, err = client.exec_command('cd '+shlex.quote(REMOTE)+' && sudo -S -p "" /usr/bin/python3 preflight.py', timeout=30)
        inp.write(password+'\n'); inp.flush(); inp.close()
        result = json.loads(out.read().decode()); errors = err.read().decode(); code = out.channel.recv_exit_status()
        result.update(archive_sha256=digest, remote=REMOTE, stderr=errors, exit_code=code)
        (ROOT/'reports/board_deployment.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result,indent=2)); assert code == 0 and result['outcome']=='passed'
    finally:
        client.close()


if __name__ == '__main__':
    main()
