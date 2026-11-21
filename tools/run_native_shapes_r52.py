"""One small legal R45 registry-only fixture, using immutable candidate6.

No construction-world blocks, actors, gameplay or walking results are imported.
"""
import argparse,hashlib,json,os,shutil,subprocess,time
from pathlib import Path
import nbtlib
from r52_spatial_plan import BASE


def sha(path):
    with Path(path).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--resume-staging',action='store_true');options=parser.parse_args()
    root=Path(__file__).resolve().parents[1];out=BASE/'native_collision_shapes_candidate6';host=out/'server';world=host/'SEELE_FIELD_R45_REVIEW'
    assert not(out/'RUNNING.json').exists()and not(out/'RUN_RESULT.json').exists(),'Preserve a native run'
    assert not out.exists()or options.resume_staging,'Preserve the attempted staging; inspect before retrying'
    original=BASE/'native_generation/server';jar=root/'artifacts/r52_unified_candidate6/projectseele-0.1.0-all.jar'
    expected='3e84e0f6cfe0544535002f52fc004d457742846cc8cd36d320ad824aae4d7146';assert sha(jar)==expected
    host.mkdir(parents=True,exist_ok=True);world.mkdir(exist_ok=True);links=0
    for folder in ('libraries','mods','config','projectseele-local-maps'):
        for source in(original/folder).rglob('*'):
            if not source.is_file():continue
            rel=source.relative_to(original);target=host/rel;target.parent.mkdir(parents=True,exist_ok=True)
            if rel.as_posix()=='mods/projectseele-0.1.0-all.jar':
                if target.exists():assert sha(target)==expected
                else:shutil.copyfile(jar,target)
            elif target.exists():assert sha(target)==sha(source)
            elif folder in('libraries','mods'):os.link(source,target);links+=1
            else:shutil.copyfile(source,target)
    eula=(original/'eula.txt').read_bytes();assert b'eula=true'in eula;(host/'eula.txt').write_bytes(eula)
    (host/'server.properties').write_text('server-ip=127.0.0.1\nserver-port=25579\nonline-mode=false\nview-distance=2\nsimulation-distance=2\nlevel-name=SEELE_FIELD_R45_REVIEW\nmax-tick-time=180000\nallow-flight=true\nenable-rcon=false\nenable-query=false\nspawn-protection=0\n','utf8')
    fixture=Path('D:/eva/artifacts/r51_nonmap_release/native_r51/game/saves/SEELE_FIRST_BATTLE_REVIEW_R10')
    level=nbtlib.load(fixture/'level.dat');level['Data'].pop('Player',None);level['Data'].pop('CustomBossEvents',None);level.save(world/'level.dat')
    if(fixture/'datapacks').exists():shutil.copytree(fixture/'datapacks',world/'datapacks',dirs_exist_ok=True)
    # Retired construction guards, but no player/entity/task/traffic state.
    for name in('.projectseele_s20_rebuild.json','.projectseele_spatial_preview_read_only.json'):
        source=BASE/'WORLD_R52'/name
        if source.is_file():shutil.copyfile(source,world/name)
    (world/'.projectseele_s22_migration_frozen.json').write_text('{"reason":"registry-only isolated native shape fixture"}','utf8')
    claim=Path('dimensions/projectseele/geofront/data/projectseele_nerv_routes_r52.dat');(world/claim).parent.mkdir(parents=True);shutil.copyfile(BASE/'WORLD_R52'/claim,world/claim)
    keys=json.loads((root/'.codex/r52_native_collision_export/native_collision_states_r52.json').read_text('utf8'))
    assert isinstance(keys,list)and len(keys)==2622
    (world/'regional_states.json').write_text(json.dumps(keys),'utf8');(world/'quality_walk_cases.json').write_text('[]','utf8')
    args=['-Xms512M','-Xmx3G','-XX:+UseG1GC','-XX:ActiveProcessorCount=4','-Dfile.encoding=UTF-8',
          '-Dprojectseele.regionalBuild=r44-collision','-Dprojectseele.nativeReviewWorld=SEELE_FIELD_R45_REVIEW']
    (host/'shape_args.txt').write_text('\n'.join(args)+'\n','utf8')
    command=['C:/Users/liboy/jdks/jdk-17.0.19+10/bin/java.exe','@shape_args.txt','@libraries/net/minecraftforge/forge/1.20.1-47.4.10/win_args.txt','nogui']
    start=time.monotonic()
    with(out/'server.log').open('wb')as log:
        child=subprocess.Popen(command,cwd=host,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000)
        (out/'RUNNING.json').write_text(json.dumps(dict(pid=child.pid,jar_sha256=expected,world=str(world),source_world_opened=False,walking_cases=0,immutable_links=links),indent=2),'utf8')
        print('Registry-only native server PID',child.pid,flush=True)
        try:code=child.wait(timeout=180)
        except subprocess.TimeoutExpired:
            child.stdin.write(b'stop\n');child.stdin.flush();code=child.wait(timeout=45)
    shape=world/'native_collision_shapes.json';valid=code==0 and shape.is_file()
    report=dict(exit_code=code,elapsed_seconds=time.monotonic()-start,jar_sha256=expected,native_shapes_exported=valid,world_blocks_imported=False,
                gameplay_or_traffic_imported=False,native_walks_verified=False,source_world_opened=False)
    if valid:
        actual=json.loads(shape.read_text('utf8'));assert set(keys)<=set(actual)
        report.update(shape_count=len(actual),shape_sha256=sha(shape),requested_keys=len(keys))
        shutil.copyfile(shape,out/'native_collision_shapes.json')
        traits=world/'native_state_traits_r44.json'
        if traits.exists():shutil.copyfile(traits,out/traits.name)
    assert sha(jar)==expected
    (out/'RUN_RESULT.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)
    assert valid,'Inspect native server log; no collision data accepted'


if __name__=='__main__':main()
