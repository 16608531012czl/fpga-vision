"""Run real Vivado XSim; exit status alone is never accepted as a pass."""
from pathlib import Path
import argparse, subprocess, sys, os, json, hashlib, time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from generate_vectors import generate


def run(label, args, cwd, marker=None):
    log = ROOT/'reports'/(label+'.log')
    # Batch file uses its own call chain. subprocess list2cmdline quotes Windows paths.
    # Xilinx .bat wrappers split unquoted NAME=VALUE tokens at '='.
    command = ' '.join('"'+str(a).replace('\\', '/')+'"' for a in args)
    t = time.time()
    with log.open('w', encoding='utf-8') as out:
        result = subprocess.run(command, cwd=str(cwd), stdout=out, stderr=subprocess.STDOUT, shell=True)
    txt = log.read_text(encoding='utf-8', errors='replace')
    if result.returncode or 'FATAL' in txt or 'ERROR:' in txt or (marker and marker not in txt):
        print(txt[-7000:]);raise RuntimeError('{} failed; {}'.format(label, log))
    print(label, 'PASS', round(time.time()-t, 2), 's', flush=True)


def main():
    ap = argparse.ArgumentParser();ap.add_argument('--full', action='store_true')
    ap.add_argument('--vivado', default=r'C:\Users\CHENZHELONG\Desktop\diansai\Vivado\2018.3')
    ap.add_argument('--only', choices=['reading','capture','registers','gamma','fifo','abort','encoder','canvas','kernels'])
    a = ap.parse_args();binpath=Path(a.vivado)/'bin'
    work=ROOT/'build'/('sim_full' if a.full else 'sim_quick');work.mkdir(parents=True,exist_ok=True)
    all_rtl=sorted((ROOT/'rtl').glob('*.sv'))
    compiled_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in all_rtl+list((ROOT/'sim').glob('*.sv'))}
    run('compile_'+work.name,[binpath/'xvlog.bat','-sv']+all_rtl+list((ROOT/'sim').glob('tb_*.sv')),work)
    tests=['reading','capture','registers','gamma','fifo','abort','encoder','canvas','kernels'] if a.only is None else [a.only]
    for test in tests:
        generics=[]
        if test=='reading':
            frames=generate(work,1280 if a.full else 32,720 if a.full else 24,a.full)
            generics=['-generic_top','WIDTH={}'.format(1280 if a.full else 32),'-generic_top','HEIGHT={}'.format(720 if a.full else 24),'-generic_top','FRAMES={}'.format(frames)]
        if test=='kernels':
            from generate_kernels import generate as generate_kernels
            generate_kernels(work)
        if test=='capture' and a.full:generics=['-generic_top','WIDTH=1280','-generic_top','HEIGHT=720']
        if test=='canvas' and a.full:generics=['-generic_top','WIDTH=1280','-generic_top','HEIGHT=720']
        snap=test+'_snapshot';label=test+('_full' if a.full else '_quick')
        run(label+'_elab',[binpath/'xelab.bat','tb_'+test,'-s',snap,'--debug','typical']+generics,work)
        run(label,[binpath/'xsim.bat',snap,'-tclbatch',ROOT/'sim/run.tcl'],work,'PASS '+test)
    stamp={'passed_tests':tests,'full_resolution':a.full,'sha256':{},'timestamp':time.strftime('%Y-%m-%dT%H:%M:%S')}
    for path,digest in compiled_hashes.items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=digest:
            raise RuntimeError('Source changed during verification; rerun: '+path)
    for folder in ['rtl','sim','software','tests','tools']:
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:stamp['sha256'][p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    (ROOT/'reports'/('xsim_full.json' if a.full else 'xsim_quick.json')).write_text(json.dumps(stamp,indent=2),encoding='utf-8')


if __name__=='__main__':main()

