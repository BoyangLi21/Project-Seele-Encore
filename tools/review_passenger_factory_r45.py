"""Root-only sequential actual factory review; preserve failed evidence."""
from pathlib import Path
import argparse,json,subprocess,sys,time,uuid
import nbtlib
from release_combat_r36 import guard
from freeze_native_r44 import freeze

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True);p.add_argument('--variant',type=int,choices=range(3),required=True);a=p.parse_args();guard()
    plan=json.loads(a.plan.read_text('utf8'));row=next(r for r in plan['runs']if r['variant']==a.variant)
    out=a.plan.parent/f'variant_{a.variant}_native';out.mkdir(exist_ok=False)
    spec=freeze(json.loads(Path(row['launch']).read_text('utf8')),out);path=out/'launch.json';path.write_text(json.dumps(spec,indent=2),'utf8')
    started=time.time()
    with(out/'native.log').open('w',encoding='utf8')as log:
        r=subprocess.run([sys.executable,'tools/launch_rendered_client_r17.py','--prepared-file',str(path)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    assert r.returncode==0,('Client failed',r.returncode)
    folder=ROOT/'run/saves/SEELE_FIELD_R45_REVIEW/Review'
    reports=list(folder.glob(f'r44_passenger_factory_{a.variant}.json'));assert len(reports)==1 and reports[0].stat().st_mtime>=started,'Missing fresh original-fleet result'
    samples=json.loads(reports[0].read_text('utf8'));(out/'actual_samples.json').write_bytes(reports[0].read_bytes())
    assert isinstance(samples,list)and samples,'Empty success-only cycle report'
    # Samples are periodic; the last sample can precede the final PARKED tick.
    # The success file is written only after the guarded final real exit.
    # Independently check the actual saved endpoint after the process stopped.
    fleet=nbtlib.load(ROOT/'run/saves/SEELE_FIELD_R45_REVIEW/data/projectseele_eva_fleet.dat')['data']['Fleet']
    unit=next(x for x in fleet if int(x['Variant'])==a.variant)
    identity=lambda tag:str(uuid.UUID(hex=''.join(f'{int(x)&0xffffffff:08x}'for x in tag)))
    assert str(unit['Phase'])=='PARKED'and identity(unit['Canonical'])==row['eva_uuid']and identity(unit['EntryPlug'])==row['plug_uuid'],'Saved physical endpoint or original identity differs'
    trace=Path(row['callback_trace']);assert trace.is_file()and trace.stat().st_mtime>=started,'Missing fresh actual passenger callback stream'
    result=dict(passed=True,variant=a.variant,eva_uuid=row['eva_uuid'],plug_uuid=row['plug_uuid'],samples=len(samples),
                phases=list(dict.fromkeys(r['phase']for r in samples)),callback_trace=str(trace),visual_passed=False,
                basis='Fresh success-only report written after real final exit; each original identity and physical phase guarded in FactoryR20Review')
    (out/'result.json').write_text(json.dumps(result,indent=2),'utf8');print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
