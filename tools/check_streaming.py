"""Exercise back-to-back pixels with randomized stalls, independently of camera FPS."""
from pathlib import Path
import hashlib
import json
import sys
from generate_vectors import generate
from verify import run

ROOT=Path(__file__).resolve().parents[1]


def main():
    work=ROOT/'build/continuous_stream';work.mkdir(exist_ok=True)
    bench=(ROOT/'sim/tb_reading.sv').read_text()
    bench=bench.replace('module tb_reading;','module tb_reading_continuous;')
    bench=bench.replace('    @(negedge clk);vin=0;uin=0;lin=0;','')
    bench=bench.replace('    if(j%17==0)repeat(2)@(negedge clk);','')
    bench=bench.replace('  wait(got==N);','  @(negedge clk);vin=0;uin=0;lin=0;\n  wait(got==N);')
    path=work/'tb_reading_continuous.sv';path.write_text(bench)
    count=generate(work,32,24)
    rtl=sorted((ROOT/'rtl').glob('*.sv'))
    hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in rtl}
    binpath=Path(r'C:\Users\CHENZHELONG\Desktop\diansai\Vivado\2018.3\bin')
    run('continuous_compile',[binpath/'xvlog.bat','-sv']+rtl+[path],work)
    run('continuous_elab',[binpath/'xelab.bat','tb_reading_continuous','-s','continuous_snapshot',
                           '-generic_top','FRAMES='+str(count)],work)
    run('continuous_stream',[binpath/'xsim.bat','continuous_snapshot','-tclbatch',ROOT/'sim/run.tcl'],
        work,'PASS reading')
    current={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in rtl}
    if hashes!=current:raise RuntimeError('RTL changed during streaming check')
    record={'passed':True,'source':'real XSim, continuous source and random output stalls',
            'pixel_count':32*24*count,'sha256':hashes,'board_fps_measured':False}
    (ROOT/'reports/continuous_stream.json').write_text(json.dumps(record,indent=2))
    print('PASS continuous stream',record['pixel_count'],'pixels')


if __name__=='__main__':main()
