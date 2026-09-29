"""Run all native managed lift landings with real client entry and exit movement."""
from pathlib import Path
import argparse,json,shutil,subprocess,sys,time
from release_combat_r36 import guard

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/repair_r43';WORLD=ROOT/'run/saves/SEELE_FIELD_R43_REVIEW'

def main():
    p=argparse.ArgumentParser();p.add_argument('--start',type=int,default=0);p.add_argument('--end',type=int,default=25);p.add_argument('--cold-attempt',type=int);a=p.parse_args();guard()
    world=WORLD
    if a.cold_attempt is not None:
        assert a.cold_attempt>0
        world=ROOT/f'run/saves/SEELE_R43_LIFT_COLD_REVIEW_V{a.cold_attempt}'
        assert not world.exists(),'Cold-start evidence requires a fresh frozen-source copy'
        shutil.copytree(ART/'source_world_backup',world)
        (world/'session.lock').write_bytes(bytes([0xe2,0x98,0x83]))
        import nbtlib
        level=nbtlib.load(world/'level.dat');level['Data']['LevelName']=nbtlib.String('R43 Lift Cold Review TEST '+str(a.cold_attempt));level.save()
    assert world.is_dir();out=ART/'lift_lifecycle'/time.strftime('%Y%m%d_%H%M%S');out.mkdir(parents=True)
    spec=json.loads((ROOT/'.Codex/client-r42-lifts.json').read_text('utf8'))
    prefixes=('-Dprojectseele.regionalBuild=','-Dprojectseele.r40LiftStart=','-Dprojectseele.r40LiftEnd=','-Dprojectseele.r41LiftEnd=','-Dprojectseele.r41LiftNoDiagnostics=')
    spec['command']=[x for x in spec['command'] if not x.startswith(prefixes)]
    spec['command'][1:1]=['-Dprojectseele.regionalBuild=r43-lifts','-Dprojectseele.r43LiftCallTrace=true',f'-Dprojectseele.r40LiftStart={a.start}',f'-Dprojectseele.r41LiftEnd={a.end}',
        f'-Dprojectseele.liftFrameFile={(out/"lift_frames.csv").resolve().as_posix()}']
    spec['command'][spec['command'].index('--quickPlaySingleplayer')+1]=world.name
    launch=out/'launch.json';launch.write_text(json.dumps(spec),'utf8')
    cfg=ROOT/'run/config/oculus.properties';previous=cfg.read_bytes();began=time.time()
    cfg.write_text(previous.decode('utf8').replace('enableShaders=true','enableShaders=false'),'utf8')
    try:
        with (out/'native.log').open('w',encoding='utf8') as stream:
            subprocess.run([sys.executable,'tools/launch_rendered_client_r17.py','--prepared-file',str(launch)],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,check=True)
        result=world/'r20_lift_review.json';assert result.stat().st_mtime>=began
        data=json.loads(result.read_text('utf8'));(out/'result.json').write_bytes(result.read_bytes())
        (out/'scope.json').write_text(json.dumps(dict(start=a.start,end=a.end,world=str(world),cold_source_copy=a.cold_attempt is not None,
            interaction='Real client movement through entry/exit; external call uses native handler; not a mouse-targeting UI test',
            acceptance='Trip passes are functional movement only; restart, all device states and visual quality tracked separately'),indent=2),'utf8')
        (ART/'lift_lifecycle/latest.json').write_text(json.dumps(dict(folder=str(out),error=data['error'],completed=len(data['trips'])),indent=2),'utf8')
        print('Completed native passages',len(data['trips']),'error',data['error'],out,flush=True)
        assert not data['error'],data['error'];assert len(data['trips'])==a.end-a.start
        assert all(t['actual_client_entry'] and t['actual_client_exit'] for t in data['trips'])
    finally:cfg.write_bytes(previous)

if __name__=='__main__':main()
