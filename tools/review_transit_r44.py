"""Real MTR route, door, boarding and exit coverage; station paths remain separate obligations."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys,time
from freeze_native_r44 import freeze
from release_combat_r36 import guard

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r44'
WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
CASES=ART/'facility_transit_r44/native_transit_cases/cases.json'
STATION_WALKS=ART/'facility_transit_r44/station_walk_cases_v3/station_walk_cases.json'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--start',type=int,default=0);ap.add_argument('--end',type=int,default=38)
    ap.add_argument('--timeout',type=int,default=7200);args=ap.parse_args();guard();assert 0<=args.start<args.end<=38
    out=ART/'transit_lifecycle'/time.strftime('%Y%m%d_%H%M%S');out.mkdir(parents=True)
    snapshot=out/'cases.json';shutil.copy2(CASES,snapshot);denominator=json.loads(snapshot.read_text('utf8'))
    assert len(denominator['cases'])==38
    station_snapshot=out/'station_walk_cases.json';shutil.copy2(STATION_WALKS,station_snapshot)
    station_walks=json.loads(station_snapshot.read_text('utf8'))
    assert len(station_walks)==501 and len({row['id'] for row in station_walks})==501
    spec=json.loads((ROOT/'.Codex/client-r42-interiors-photos.json').read_text('utf8'))
    command=[s for s in spec['command'] if not s.startswith('-Dprojectseele.')]
    command[1:1]=['-Dprojectseele.regionalBuild=r44-transit-all','-Dprojectseele.r44TransitCases='+snapshot.resolve().as_posix(),
        f'-Dprojectseele.r44TransitStart={args.start}',f'-Dprojectseele.r44TransitEnd={args.end}']
    command[command.index('--quickPlaySingleplayer')+1]=WORLD.name;spec['command']=command;spec=freeze(spec,out)
    launch=out/'launch.json';launch.write_text(json.dumps(spec),'utf8')
    cfg=ROOT/'run/config/oculus.properties';previous=cfg.read_bytes();began=time.time()
    cfg.write_text(previous.decode('utf8').replace('enableShaders=true','enableShaders=false'),'utf8')
    try:
        with (out/'native.log').open('w',encoding='utf8') as log:
            child=subprocess.Popen([sys.executable,'-X','utf8','tools/launch_rendered_client_r17.py','--prepared-file',str(launch)],
                cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            try:code=child.wait(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                # Stop only the launched child tree, never another Java session.
                subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],capture_output=True);raise
        path=WORLD/'r44_transit_review.json';assert code==0 and path.stat().st_mtime>=began
        data=json.loads(path.read_text());shutil.copy2(path,out/'result.json')
        scope=dict(start=args.start,end=args.end,world=str(WORLD),train_interfaces=34,air_interfaces=4,
            independent_station_paths=len(station_walks),station_paths_source=str(STATION_WALKS),
            station_paths_sha256=hashlib.sha256(station_snapshot.read_bytes()).hexdigest(),
            expected_cases=[r['id'] for r in denominator['cases'][args.start:args.end]],actual_cases=[r['id'] for r in data['cases']],
            mode='Real current MTR route/platform stop and doors, natural vehicle attach, destination disembark and supported exit path',
            not_verified=['501 independent whole-station path obligations, including actual north/south technical-centre cabinet journeys','All station art','Same-JVM and cold reload'])
        (out/'scope.json').write_text(json.dumps(scope,indent=2),'utf8')
        print('Actual MTR interface passages:',len(data['cases']),'error:',data['error'],out,flush=True)
        assert not data['error'],data['error'];assert scope['actual_cases']==scope['expected_cases']
        assert all(r['native_interface_pass'] and r['actual_exit_path'] for r in data['cases'])
        if args.start==0 and args.end==38:assert data['full_native_interface_run_pass']
    finally:cfg.write_bytes(previous)


if __name__=='__main__':main()
