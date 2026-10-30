"""Portable Windows/Vivado 2018.3 entry; generated work never modifies src/."""
from pathlib import Path
import argparse, subprocess, sys, shutil, json, os, re
ROOT=Path(__file__).resolve().parents[1]
def run(argv,cwd,log,marker=None):
    log.parent.mkdir(parents=True,exist_ok=True)
    if str(argv[0]).endswith('vivado.bat'):
        def value(flag):return str(argv[argv.index(flag)+1])
        command=['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(ROOT/'build/invoke_vivado.ps1'),
                 '-Executable',str(argv[0]),'-ScriptFile',value('-source'),'-LogFile',value('-log'),'-JournalFile',value('-journal'),
                 '-OutputFile',str(log),'-WorkingDirectory',str(Path(cwd).parent)]
        p=subprocess.run(command,cwd=str(Path(cwd).parent),env=dict(os.environ))
    else:
        with log.open('w',encoding='utf-8') as out:
            p=subprocess.run([str(x) for x in argv],cwd=str(cwd),stdout=out,stderr=subprocess.STDOUT,env=dict(os.environ,PYTHONUTF8='1'))
    s=log.read_text(encoding='utf-8',errors='replace')
    if p.returncode or 'ERROR:' in s or 'FATAL:' in s or (marker and marker not in s):
        print(s[-5000:]);raise RuntimeError('Failed: '+str(log))
    print('PASS '+log.name,flush=True)
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('phase',choices=['host','quick','full','project','implement','all'])
    ap.add_argument('--vivado',default=os.environ.get('VIVADO_ROOT'))
    ap.add_argument('--work',type=Path,default=ROOT/'build/work')
    a=ap.parse_args();work=a.work.resolve();out=ROOT/'build/results'
    if a.phase in ['host','all']:
        run([sys.executable,'-m','unittest','discover','-s',ROOT/'src/ps/tests','-v'],ROOT,out/'host_tests.txt','OK')
        run([sys.executable,ROOT/'src/ps/runtime/preflight.py','--host'],ROOT,out/'preflight_host.json','"outcome": "passed"')
    if a.phase=='host':return
    if not a.vivado:ap.error('--vivado or VIVADO_ROOT is required for FPGA steps')
    viv=Path(a.vivado).resolve();exe=viv/'bin/vivado.bat'
    if not exe.is_file():ap.error('vivado.bat not found')
    if work==ROOT/'src/pl' or ROOT/'src/pl' in work.parents:ap.error('Use a separate generated work directory')
    if not work.exists():shutil.copytree(ROOT/'src/pl',work)
    (work/'reports').mkdir(exist_ok=True)
    if a.phase in ['quick','full','all']:
        args=[sys.executable,work/'tools/verify.py','--vivado',viv]
        if a.phase in ['full','all']:args+=['--full']
        run(args,work,out/('xsim_'+('full' if '--full' in args else 'quick')+'.txt'))
    if a.phase in ['project','all']:
        source=work/'vivado/create_system.tcl'
        run([exe,'-mode','batch','-source',source,'-log',out/'create_system.log','-journal',out/'create_system.jou'],work,out/'create_system_stdout.txt','PASS: independent system block design validated')
    if a.phase in ['implement','all']:
        stamp=work/'reports/xsim_full.json'
        if not stamp.exists():raise RuntimeError('Full-resolution XSim must pass first')
        import hashlib
        hashes=json.loads(stamp.read_text())['sha256']
        for p in (work/'rtl').glob('*.sv'):
            if hashes.get(p.relative_to(work).as_posix())!=hashlib.sha256(p.read_bytes()).hexdigest():raise RuntimeError('RTL changed after full simulation')
        source=work/'vivado/implement_system.tcl'
        run([exe,'-mode','batch','-source',source,'-log',out/'implement.log','-journal',out/'implement.jou'],work,out/'implement_stdout.txt','PASS')
        run([sys.executable,ROOT/'skill/check_timing.py',work/'reports/system_timing_values.json'],ROOT,out/'timing_gate.json','"passed": true')
if __name__=='__main__':main()
