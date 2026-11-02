"""Merge explicitly absent/unfinished lake chunks from the isolated native bake.

Never replaces an existing FULL chunk, actor region, player or progress file.
The original region bytes are retained before replacing only selected slots.
"""
import argparse,copy,json,shutil,zipfile
from pathlib import Path
from collections import defaultdict,Counter
from transplant_s22_authority import read_region,parse_chunk,build_region
from apply_s20_approved_semantic_repairs import atomic_replace,chunk_blob
from install_r53_carrier_trays import stopped_world
from query_blocks import chunk_statuses
from map_pipeline.launch_protection import load as launch_protection
from map_pipeline.install.invariants import require_nbt_equal
import nbtlib

DIM=Path('dimensions/projectseele/geofront')
GENERATED_FIELDS={'sections','Status','Heightmaps','structures','PostProcessing','CarvingMasks',
    'Lights','isLightOn','starlight.light_version','blending_data','below_zero_retrogen','UpgradeData',
    'LastUpdate','InhabitedTime','block_entities','entities','block_ticks','fluid_ticks'}
PERSISTENT_FIELDS=('block_entities','entities','block_ticks','fluid_ticks','ToBeTicked','LiquidsToBeTicked')


def region_rows(path):
    if not path.exists() or path.stat().st_size==0:return bytes(4096),[None]*1024
    return read_region(path)


def prepare_slot(original,current,generated,coordinate,actual_time):
    if original!=current:raise ValueError(f'Target payload changed since capture: {coordinate}')
    old=parse_chunk(current) if current is not None else None
    status='missing' if old is None else str(old.get('Status','')).removeprefix('minecraft:')
    if status=='full':raise ValueError(f'Already FULL; preserve actual chunk {coordinate}')
    if old is not None and any(old.get(key) for key in PERSISTENT_FIELDS):
        raise ValueError(f'Original objects/ticks require explicit migration: {coordinate}')
    if generated is None:raise ValueError(f'Native bake did not save {coordinate}')
    tag=parse_chunk(generated)
    if str(tag.get('Status','')).removeprefix('minecraft:')!='full' or (int(tag['xPos']),int(tag['zPos']))!=coordinate:
        raise ValueError(f'Invalid generated native chunk {coordinate}')
    if any(tag.get(key) for key in PERSISTENT_FIELDS):
        raise ValueError(f'Generated objects/ticks require explicit migration: {coordinate}')
    if old is not None:
        require_nbt_equal({k:v for k,v in old.items() if k not in GENERATED_FIELDS},
                          {k:v for k,v in tag.items() if k not in GENERATED_FIELDS},str(coordinate))
    tag['LastUpdate']=nbtlib.Long(actual_time)
    tag['InhabitedTime']=copy.deepcopy(old.get('InhabitedTime',nbtlib.Long(0))) if old is not None else nbtlib.Long(0)
    # All tick lists were explicitly checked empty. No cache time or remaining
    # tick delays are imported into the actual world's timeline.
    return chunk_blob(tag),status


def preflight(a):
    directory=a.list.parent
    plan=json.loads((directory/'plan.json').read_text('utf8'))
    proof=json.loads((directory/'native-preflight.json').read_text('utf8'))
    progress=json.loads((directory/'progress.json').read_text('utf8'))
    isolation=json.loads((directory/'input-isolation.json').read_text('utf8'))
    stop=json.loads((directory/'normal-stop.json').read_text('utf8'))
    requested=json.loads(a.list.read_text('utf8'))
    if not requested or requested!=plan['chunks'] or len(set(map(tuple,requested)))!=len(requested):
        raise ValueError('Exact finite reviewed chunk list required')
    for path,key in ((a.world,'actual_world'),(a.source,'cache_world')):
        if path.resolve()!=Path(plan[key]).resolve():raise ValueError('Save path differs from plan')
    if not progress.get('generated') or progress.get('completed')!=len(requested) or progress.get('total')!=len(requested):
        raise ValueError('Native generation incomplete')
    if (directory/'error.txt').exists():raise ValueError('Native generation error requires review')
    if not all(proof.get(k) is True for k in ('cache_only','seed_matches','terrain_matches')):
        raise ValueError('Native preflight failed')
    if proof['world_uuid']!=plan['world_uuid'] or proof['requested_chunks']!=len(requested) or int(proof['seed'])!=int(plan['seed']):
        raise ValueError('Native proof differs from plan')
    if proof['generator']!='com.projectseele.world.GeoFrontBoundedChunkGenerator' or Path(proof['cache_world']).resolve()!=a.source.resolve():
        raise ValueError('Native generator/save mismatch')
    if Path(proof['recipe_directory']).resolve()!=(a.source/DIM/'data/city_rigid_generation_r45').resolve():
        raise ValueError('Native recipe binding mismatch')
    if not isolation.get('cache_only') or not isolation.get('entity_ticks_paused') or isolation.get('entities_removed_or_reset'):
        raise ValueError('Cache input isolation missing')
    if stop['state']!='ORDINARY_CONSOLE_STOP_SUBMITTED' or stop['pid']!=proof['pid'] or Path(stop['actual_server_world']).resolve()!=a.source.resolve():
        raise ValueError('Matching ordinary cache stop receipt required')
    data=nbtlib.load(a.world/'level.dat')['Data']
    for root in (a.source,directory/'actual-before'):
        require_nbt_equal(data['WorldGenSettings'],nbtlib.load(root/'level.dat')['Data']['WorldGenSettings'])
    if int(data['WorldGenSettings']['seed'])!=int(plan['seed']):raise ValueError('Actual seed changed')
    primary=('GeoFrontBoundedChunkGenerator','GeoFrontHeightR52','TvWorldPreviewTerrain','TvAuthoredTerrainR44',
        'FacilitySchemaV2','CityRigidGenerationR45','CityRigidTopologyR45','CityLowriseAddonR48',
        'RegionalEcologyBiomeSourceR44','NativeGeofrontVegetationR44','NativeEcologyFeatureProtectionR44',
        'S24CoordinateTransform','FacilityWorldPolicy')
    with zipfile.ZipFile(a.world.parent.parent/'mods/projectseele-0.1.0-all.jar') as actual,zipfile.ZipFile(a.source.parent/'mods/projectseele-0.1.0-all.jar') as cache:
        names=[n for n in actual.namelist() if n.endswith('.class') and any(n=='com/projectseele/world/'+v+'.class' or n.startswith('com/projectseele/world/'+v+'$') for v in primary)]
        for name in names:
            if actual.read(name)!=cache.read(name):raise ValueError('Native generation class changed: '+name)
        for name in ('hakone_surface.bin.gz','hakone_surface_blend.bin.gz'):
            expected=(directory/'terrain-inputs'/name).read_bytes()
            for archive in (actual,cache):
                if archive.read('data/projectseele/worldgen/'+name)!=expected:raise ValueError('Terrain input changed: '+name)
    for cx,cz in requested:
        for group in ('chunks','surface'):
            rel=DIM/'data/city_rigid_generation_r45'/group/f'{cx}_{cz}.dat'
            old=directory/'actual-before'/rel;expected=old.read_bytes() if old.exists() else None
            for root in (a.world,a.source):
                f=root/rel
                if (f.read_bytes() if f.exists() else None)!=expected:raise ValueError('Future recipe changed: '+str(rel))
    return plan,int(data['Time'])


def merge(a):
    if a.out.exists():raise ValueError('Use a fresh reversible installation directory')
    if '/cache-server/'not in a.source.resolve().as_posix():raise ValueError('Expected the isolated authoring save')
    plan,actual_time=preflight(a)
    chosen=set(map(tuple,plan['chunks']))
    guard=launch_protection(a.world)
    if chosen.intersection(guard.by_chunk):raise ValueError('Native chunks intersect launch protection')
    groups=defaultdict(list)
    for x,z in chosen:groups[x//32,z//32].append((x,z))
    relative=DIM/'region';prepared=[];prior=Counter();protected_files={}
    a.out.mkdir(parents=True);(a.out/'before').mkdir();(a.out/'after').mkdir()
    for rx,rz in sorted(groups):
        name=f'r.{rx}.{rz}.mca';actual=a.world/relative/name
        existed=actual.exists()
        timestamps,rows=region_rows(actual)
        raw=actual.read_bytes() if existed else None
        if existed:shutil.copy2(actual,a.out/'before'/name)
        _,captured=region_rows(a.list.parent/'actual-before'/relative/name)
        _,source=read_region(a.source/relative/name)
        for kind in ('entities','poi'):
            f=a.world/DIM/kind/name
            protected_files[f]=f.read_bytes() if f.exists() else None
            _,records=region_rows(f)
            _,old_records=region_rows(a.list.parent/'actual-before'/DIM/kind/name)
            for cx,cz in groups[rx,rz]:
                slot=cz%32*32+cx%32
                if records[slot]!=old_records[slot]:raise ValueError(f'Original {kind} changed: {(cx,cz)}')
                if kind=='entities' and records[slot] is not None and parse_chunk(records[slot]).get('Entities'):
                    raise ValueError(f'Original modern actors require preservation: {(cx,cz)}')
        for cx,cz in groups[rx,rz]:
            slot=cz%32*32+cx%32;old=rows[slot]
            rows[slot],status=prepare_slot(captured[slot],old,source[slot],(cx,cz),actual_time)
            prior[status]+=1
        staging=a.out/'after'/name;atomic_replace(staging,build_region(timestamps,rows))
        prepared.append((actual,staging,existed,raw,timestamps,rows))
    journal=dict(status='prepared',chunks=len(chosen),actual_game_time=actual_time,
        before_statuses=dict(prior),regions=[p.name for p,*_ in prepared],
        originally_absent=[p.name for p,_,existed,*_ in prepared if not existed])
    (a.out/'installation.json').write_text(json.dumps(journal,indent=2),'utf8')
    written=[]
    try:
        for actual,staging,existed,raw,_,_ in prepared:
            if (actual.read_bytes() if actual.exists() else None)!=raw:raise ValueError('Region changed before installation: '+actual.name)
            actual.parent.mkdir(parents=True,exist_ok=True);atomic_replace(actual,staging.read_bytes());written.append((actual,existed))
        for actual,staging,_,_,timestamps,rows in prepared:
            if actual.read_bytes()!=staging.read_bytes():raise ValueError('Installed byte readback failed: '+actual.name)
            read_timestamps,read_rows=read_region(actual)
            if read_timestamps!=timestamps or read_rows!=rows:raise ValueError('Installed slot/timestamp readback failed: '+actual.name)
        for f,raw in protected_files.items():
            if (f.read_bytes() if f.exists() else None)!=raw:raise ValueError('Actor/POI store changed: '+str(f))
        statuses=chunk_statuses(a.world,'projectseele:geofront',chosen)
        if any(s!='full'for s in statuses.values()):raise ValueError('Generated chunk save incomplete')
    except BaseException:
        for actual,existed in reversed(written):
            if existed:atomic_replace(actual,(a.out/'before'/actual.name).read_bytes())
            else:actual.unlink(missing_ok=True)
        journal['status']='rolled_back'
        (a.out/'installation.json').write_text(json.dumps(journal,indent=2),'utf8')
        raise
    report=dict(status='installed',world=str(a.world),chunks=len(chosen),
        tiles=sorted({(x//4,z//4) for x,z in chosen}),
        before_statuses=dict(prior),existing_full_chunks_replaced=0,progress_files_written=[],
        actual_game_time=actual_time,cache_tick_lists_imported=0,actual_entity_and_poi_stores_unchanged=True,
        non_target_payloads_and_all_timestamps_preserved=True,exact_target_preconditions=True,
        launch_guard=guard.report,launch_guard_chunk_intersections=0,
        source=str(a.source),remaining='Author from the expanded current FULL source and refresh changed LOD')
    (a.out/'installation.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('world','source','list','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    with stopped_world(a.source),stopped_world(a.world):merge(a)
