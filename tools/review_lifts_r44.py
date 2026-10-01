"""All measured R44 lift sources: real client calls, cabin selection, ride and exit."""
from pathlib import Path
import argparse,json,shutil,subprocess,sys,time
from release_combat_r36 import guard
from freeze_native_r44 import freeze

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r44'
WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
INTERFACES=ART/'facility_transit_r44/measured_interfaces_v3/lifts.json'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--start',type=int,default=0);ap.add_argument('--end',type=int,default=25)
    ap.add_argument('--cold-attempt',type=int);args=ap.parse_args();guard()
    assert 0<=args.start<args.end<=25
    world=WORLD
    if args.cold_attempt is not None:
        assert args.cold_attempt>0
        # A cold reopen is a new JVM loading the saved existing devices, not
        # another entire world clone. Immutable attempt evidence is separate.
        assert (world/'level.dat').is_file(),'Existing construction save required'
    suffix='' if args.cold_attempt is None else f'_cold_{args.cold_attempt}'
    output=ART/'lift_lifecycle'/(time.strftime('%Y%m%d_%H%M%S')+suffix);output.mkdir(parents=True)
    snapshot=output/'interfaces.json';shutil.copy2(INTERFACES,snapshot)
    spec=json.loads((ROOT/'.Codex/client-r42-lifts.json').read_text('utf8'))
    prefixes=('-Dprojectseele.regionalBuild=','-Dprojectseele.r40LiftStart=','-Dprojectseele.r40LiftEnd=',
        '-Dprojectseele.r41LiftEnd=','-Dprojectseele.r41LiftNoDiagnostics=','-Dprojectseele.r44LiftInterfaces=')
    spec['command']=[s for s in spec['command'] if not s.startswith(prefixes)]
    spec['command'][1:1]=['-Dprojectseele.regionalBuild=r44-lifts','-Dprojectseele.r43LiftCallTrace=true',
        f'-Dprojectseele.r40LiftStart={args.start}',f'-Dprojectseele.r41LiftEnd={args.end}',
        '-Dprojectseele.r44LiftInterfaces='+snapshot.resolve().as_posix(),
        '-Dprojectseele.liftFrameFile='+(output/'lift_frames.csv').resolve().as_posix()]
    spec['command'][spec['command'].index('--quickPlaySingleplayer')+1]=world.name
    spec=freeze(spec,output);launch=output/'launch.json';launch.write_text(json.dumps(spec),'utf8')
    cfg=ROOT/'run/config/oculus.properties';previous=cfg.read_bytes();began=time.time()
    cfg.write_text(previous.decode('utf8').replace('enableShaders=true','enableShaders=false'),'utf8')
    try:
        with (output/'native.log').open('w',encoding='utf8') as log:
            subprocess.run([sys.executable,'-X','utf8','tools/launch_rendered_client_r17.py','--prepared-file',str(launch)],
                cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
        path=world/'r44_lift_review.json';assert path.stat().st_mtime>=began
        data=json.loads(path.read_text());shutil.copy2(path,output/'result.json')
        scope=dict(start=args.start,end=args.end,world=str(world),cold_process=args.cold_attempt is not None,
            new_jvm_process=True,cold_attempt=args.cold_attempt,same_saved_world=True,world_copy_created=False,
            denominator=dict(unique_source_stops=24,trips=25),current_trips=len(data['trips']),
            actual_source_stops=data['completed_source_stops'],full_run=args.start==0 and args.end==25,
            interaction='Actual client OUTLINE sightline and useItemOn for exterior button and official cabin display; actual entry and exit movement',
            not_verified=['Artistic acceptance','Same-JVM reload','Other lift door states beyond recorded trip'])
        (output/'scope.json').write_text(json.dumps(scope,indent=2),'utf8')
        print('R44 actual client trips:',len(data['trips']),'unique sources:',data['completed_source_stops'],'error:',data['error'],output,flush=True)
        assert not data['error'],data['error'];assert len(data['trips'])==args.end-args.start
        assert all(t['actual_client_entry'] and t['actual_client_exit'] and t['actual_client_call_click'] and t['actual_client_car_selection'] and t['grounded_exit'] for t in data['trips'])
        if scope['full_run']:assert data['full_current_run_pass'] and data['completed_source_stops']==24
    finally:cfg.write_bytes(previous)


if __name__=='__main__':main()
