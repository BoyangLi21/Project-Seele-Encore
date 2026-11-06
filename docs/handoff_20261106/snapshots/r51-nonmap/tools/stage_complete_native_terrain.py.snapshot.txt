"""Stage one seed-identical native terrain fixture for explicit design areas.

Only absent/incomplete target chunks may later be merged. Existing complete
chunks and all player/entity/MTR progress remain owned by the construction.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import zipfile
import numpy as np
from query_blocks import chunk_statuses
from build_continuous_upright_directory_r52 import sample


def sha(raw):return hashlib.sha256(raw).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True)
    ap.add_argument('--archive',type=Path,required=True);ap.add_argument('--jar',type=Path,required=True)
    a=ap.parse_args();base=a.base.resolve();world=base/'WORLD'
    out=base/'native_generation';host=out/'server';fixture=host/'CURRENT_TERRAIN_ONLY'
    assert not host.exists();host.mkdir(parents=True);fixture.mkdir()
    requested=set();domains={}
    def box(name,lo,hi):
        points={(x,z) for x in range(lo[0]//16,hi[0]//16+1) for z in range(lo[1]//16,hi[1]//16+1)}
        requested.update(points);domains[name]=dict(bounds=[lo,hi],chunks=len(points))
    box('hakone_and_yashima_ridge',(-1570,-1780),(-930,-1160))
    box('separate_natural_lake',(-1420,380),(-860,820))
    box('remote_air_transport_shaft',(-1220,-820),(-1020,-600))
    directory=json.loads((base/'complete_routes/GROUND_CONTINUOUS_DESIGN.json').read_text('utf8'))
    for leg in directory['legs']:
        if '/exit3/' not in leg['id'] or leg['id'].endswith('/reverse'):continue
        for segment in leg['centre_curve']['segments']:
            p=np.asarray(segment['controls']);points=sample(p,max(3,int(np.linalg.norm(np.ptp(p,axis=0)))+1))
            for q in points:
                low=np.floor((q[[0,2]]-40)/16).astype(int);high=np.floor((q[[0,2]]+40)/16).astype(int)
                requested.update((x,z) for x in range(low[0],high[0]+1) for z in range(low[1],high[1]+1))
    status=chunk_statuses(world,'projectseele:geofront',requested)
    targets={k:v for k,v in status.items() if v!='full'}
    assert targets
    context={(x+dx,z+dz) for x,z in targets for dx in range(-2,3) for dz in range(-2,3)}
    regions={(x//32,z//32) for x,z in context}
    members={}
    with zipfile.ZipFile(a.archive) as archive:
        for entry in archive.infolist():
            if entry.is_dir() or not entry.filename.startswith(('libraries/','mods/','config/','projectseele-local-maps/')):continue
            if entry.filename=='mods/projectseele-0.1.0-all.jar':continue
            relative=Path(entry.filename)
            assert not relative.is_absolute() and '..' not in relative.parts
            target=host/relative;target.parent.mkdir(parents=True,exist_ok=True)
            raw=archive.read(entry);target.write_bytes(raw);members[entry.filename]=sha(raw)
    jar=a.jar.read_bytes();(host/'mods/projectseele-0.1.0-all.jar').write_bytes(jar)
    members['mods/projectseele-0.1.0-all.jar']=sha(jar)
    eula=Path('D:/eva/run/eula.txt');assert 'eula=true' in eula.read_text('utf8');shutil.copy2(eula,host/'eula.txt')
    (host/'server.properties').write_text('server-ip=127.0.0.1\nserver-port=25578\nonline-mode=false\nview-distance=2\nsimulation-distance=2\nlevel-name=CURRENT_TERRAIN_ONLY\nmax-tick-time=180000\nallow-flight=true\nenable-rcon=false\nenable-query=false\nspawn-protection=0\n','utf8')
    (host/'generation_jvm_args.txt').write_text('-Xms1G\n-Xmx6G\n-XX:+UseG1GC\n-XX:ActiveProcessorCount=4\n-Dfile.encoding=UTF-8\n','utf8')
    shutil.copy2(world/'level.dat',fixture/'level.dat');shutil.copytree(world/'datapacks',fixture/'datapacks')
    for name in ('.projectseele_s20_rebuild.json','.projectseele_spatial_preview_read_only.json'):
        if (world/name).exists():shutil.copy2(world/name,fixture/name)
    (fixture/'.projectseele_s22_migration_frozen.json').write_text('{"reason":"Native missing terrain only; no facility generation"}','utf8')
    (fixture/'r52').mkdir();(fixture/'r52/travel.json').write_text('{"installed":false,"reason":"terrain-only fixture; migrated facility generators retired"}','utf8')
    rel=Path('dimensions/projectseele/geofront/region');(fixture/rel).mkdir(parents=True)
    source_files={}
    for rx,rz in sorted(regions):
        path=rel/f'r.{rx}.{rz}.mca';source=world/path
        if source.is_file():
            shutil.copy2(source,fixture/path);source_files[path.as_posix()]=sha(source.read_bytes())
    receipt=dict(world_written=False,fixture=str(fixture),host=str(host),source_world=str(world),
        mod_sha256=sha(jar),domains=domains,targets=[dict(x=int(x),z=int(z),status=s) for (x,z),s in sorted(targets.items())],
        region_source_sha256=source_files,runtime_members=members,source_level_sha256=sha((world/'level.dat').read_bytes()),
        protected_progress='No original entity/player/MTR/SavedData copied or merged',generation_only=True)
    (out/'STAGED.json').write_text(json.dumps(receipt,indent=2),'utf8')
    print(json.dumps(dict(target_chunks=len(targets),existing_full_retained=len(status)-len(targets),context_regions=len(source_files),fixture=str(fixture))),flush=True)


if __name__=='__main__':main()
