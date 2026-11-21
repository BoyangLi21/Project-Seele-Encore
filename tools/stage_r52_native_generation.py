"""Small seed-identical native generation fixture; never copies a whole world.

Existing R52 FULL chunks remain authoritative. A later explicit merge may take
only the measured non-FULL targets from this fixture, never its play state.
"""
import json,zipfile,hashlib,shutil,os,ast
from pathlib import Path
from r52_spatial_plan import BASE
from query_blocks import chunk_statuses

WORLD=BASE/'WORLD_R52';HOST=BASE/'native_generation/server';FIXTURE=HOST/'R52_GENERATION_ONLY'
ARCHIVE=Path('D:/eva/delivery/Project_SEELE_Encore_R51_20261009_Server.zip')
GAME=Path('D:/eva/artifacts/r51_nonmap_release/native_r51/game')
CACHE=Path('D:/eva/.Codex/server-pack-cache/runtime-r25')


def sha(raw):return hashlib.sha256(raw).hexdigest()


def main():
    assert not HOST.exists(),'Keep an existing native fixture; never restage over it'
    generation=json.loads((BASE/'bank3_outlet_v3/NATIVE_GENERATION_REQUIRED.json').read_text('utf8'))
    requested={ast.literal_eval(k)for k in generation['missing']}
    requested|={(x,z)for x in range(-112,-97)for z in range(85,96)}
    statuses=chunk_statuses(WORLD,'projectseele:geofront',requested);targets={k:v for k,v in statuses.items()if v!='full'}
    context={(x+dx,z+dz)for x,z in targets for dx in range(-2,3)for dz in range(-2,3)}
    regions={(x//32,z//32)for x,z in context};HOST.mkdir(parents=True);FIXTURE.mkdir()
    linked=0;copied=0;members={}
    with zipfile.ZipFile(ARCHIVE)as archive:
        for entry in archive.infolist():
            if not entry.filename.startswith(('libraries/','mods/','config/','projectseele-local-maps/'))or entry.is_dir():continue
            if entry.filename=='mods/projectseele-0.1.0-all.jar':continue
            raw=archive.read(entry);target=HOST/entry.filename;target.parent.mkdir(parents=True,exist_ok=True)
            source=(CACHE/entry.filename)if entry.filename.startswith('libraries/')else GAME/entry.filename
            if entry.filename.startswith(('libraries/','mods/'))and source.is_file()and sha(source.read_bytes())==sha(raw):
                os.link(source,target);linked+=len(raw)
            else:target.write_bytes(raw);copied+=len(raw)
            members[entry.filename]=sha(raw)
    mod=GAME/'mods/projectseele-0.1.0-all.jar';raw=mod.read_bytes()
    assert sha(raw)=='9a176b2bbbe88ef0ea333d6a2c4b9d57d54a21440ef6b0ceda7d8c66985cf983'
    os.link(mod,HOST/'mods'/mod.name);members['mods/'+mod.name]=sha(raw);linked+=len(raw)
    # Reuse the owner's existing accepted EULA; archive acceptance stays false.
    eula=Path('D:/eva/run/eula.txt');assert 'eula=true'in eula.read_text('utf8');shutil.copy2(eula,HOST/'eula.txt')
    (HOST/'server.properties').write_text('server-ip=127.0.0.1\nserver-port=25578\nonline-mode=false\nview-distance=2\nsimulation-distance=2\nlevel-name=R52_GENERATION_ONLY\nmax-tick-time=180000\nallow-flight=true\nenable-rcon=false\nenable-query=false\nspawn-protection=0\n','utf8')
    (HOST/'generation_jvm_args.txt').write_text('-Xms1G\n-Xmx6G\n-XX:+UseG1GC\n-XX:ActiveProcessorCount=4\n-Dfile.encoding=UTF-8\n','utf8')
    shutil.copy2(WORLD/'level.dat',FIXTURE/'level.dat')
    shutil.copytree(WORLD/'datapacks',FIXTURE/'datapacks')
    for name in ('.projectseele_s20_rebuild.json','.projectseele_spatial_preview_read_only.json'):
        shutil.copy2(WORLD/name,FIXTURE/name)
    (FIXTURE/'.projectseele_s22_migration_frozen.json').write_text('{"reason":"Root native chunk generation fixture only"}','utf8')
    claim=Path('dimensions/projectseele/geofront/data/projectseele_nerv_routes_r52.dat');(FIXTURE/claim).parent.mkdir(parents=True);shutil.copy2(WORLD/claim,FIXTURE/claim)
    source_files={};region_dir=Path('dimensions/projectseele/geofront/region');(FIXTURE/region_dir).mkdir()
    for rx,rz in sorted(regions):
        rel=region_dir/f'r.{rx}.{rz}.mca';source=WORLD/rel
        if source.is_file():shutil.copy2(source,FIXTURE/rel);source_files[str(rel).replace('\\','/')]=sha(source.read_bytes())
    receipt=dict(world_written=False,fixture=str(FIXTURE),host=str(HOST),source_world=str(WORLD),mod_sha256=members['mods/'+mod.name],
                 protected_progress='No original entity/player/MTR/SavedData state is copied or merged',targets=[dict(x=x,z=z,status=s)for(x,z),s in sorted(targets.items())],
                 region_source_sha256=source_files,runtime_members=members,linked_immutable_bytes=linked,copied_runtime_bytes=copied,
                 source_level_sha256=sha((WORLD/'level.dat').read_bytes()))
    (BASE/'native_generation/STAGED.json').write_text(json.dumps(receipt,indent=2),'utf8')
    print(json.dumps({k:v for k,v in receipt.items()if k not in ('targets','runtime_members','region_source_sha256')})+' targets='+str(len(targets))+' regions='+str(len(source_files)),flush=True)


if __name__=='__main__':main()
