"""Plan two fixed surface supply entities; --apply is reserved for Root.

No item inventory, equipment SavedData, player, original entity or progress is
changed. Each allowed world needs its own real verified civil-install receipt.
The production commission creates the two conserved items on its first call.
"""
from __future__ import annotations
from pathlib import Path
from contextlib import contextmanager
import argparse,copy,hashlib,json,math,os,re,shutil,time,uuid
import nbtlib
from transplant_s22_authority import read_region,parse_chunk,chunk_blob,build_region,atomic_replace
from query_blocks import read_box,iter_block_entities,chunk_statuses,AIR

ROOT=Path(__file__).resolve().parents[1]
DIM='projectseele:geofront'
ALLOWED=[ROOT/'artifacts/rebuild_r49/construction/SEELE_R49_WORLD',
         ROOT/'artifacts/rebuild_r49/native_qa/worlds/SEELE_R49_QA']
RACKS=['e9fd32e9-b3a3-5dc6-8d9f-21ce267a848e','749cf141-0e2f-59ef-9e9b-d08346d5ea8d']
CARGO=['3ea20e4d-37bf-5c8c-90b6-26316d2b4911','58eab304-0fb0-5f44-b500-4fed8824db08']
MARKER='r50_yashima_supply_entities_receipt.json'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical_uuid(tag):
    if 'UUID'in tag:
        values=tag['UUID']
        if isinstance(values,nbtlib.String):return str(uuid.UUID(str(values)))
        return str(uuid.UUID(bytes=b''.join((int(v)&0xffffffff).to_bytes(4,'big')for v in values)))
    if 'UUIDMost'in tag and 'UUIDLeast'in tag:
        return str(uuid.UUID(int=((int(tag['UUIDMost'])&((1<<64)-1))<<64)|(int(tag['UUIDLeast'])&((1<<64)-1))))
    return None
def uuid_nbt(value):
    raw=uuid.UUID(value).bytes
    return nbtlib.IntArray([int.from_bytes(raw[n:n+4],'big',signed=True)for n in range(0,16,4)])
def durable_json(path,value):
    atomic_replace(Path(path),(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf8'))

@contextmanager
def locked_world(world):
    path=world/'session.lock'
    if not path.is_file():raise RuntimeError('Existing allowed world must have its actual session.lock')
    with path.open('r+b')as handle:
        if os.name=='nt':
            import msvcrt
            handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            try:yield
            finally:handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            try:yield
            finally:fcntl.flock(handle,fcntl.LOCK_UN)

def metadata_racks(path):
    document=json.loads(path.read_text('utf8'))
    if 'candidate'in document:site=document['candidate']
    elif 'sites'in document:site=document['sites']['ramiel']
    else:raise RuntimeError('Expected final ramiel_metadata_candidate or actual tv_encounter_sites document')
    rows=site['yashima_controls']['supply_racks'];assert len(rows)==2
    indexed={int(row['unit']):row for row in rows};assert set(indexed)=={0,1}
    for unit,row in indexed.items():
        assert str(uuid.UUID(row['uuid']))==RACKS[unit] and str(uuid.UUID(row['cargo_uuid']))==CARGO[unit]
        assert len(row['position'])==3 and all(math.isfinite(float(v))for v in row['position'])
        assert row.get('surface_READY_forever') is True, 'No underground mechanism may be inferred for these surface fixtures'
    return document,indexed

def ready_constant():
    source=(ROOT/'src/main/java/com/projectseele/entity/NervArmamentStationEntity.java').read_text('utf8')
    ready=int(re.search(r'public static final int READY\s*=\s*(\d+)',source)[1]);assert ready==3
    eva=(ROOT/'src/main/java/com/projectseele/entity/EvaUnit01Entity.java').read_text('utf8')
    assert int(re.search(r'public static final int WEAPON_CANNON\s*=\s*(\d+)',eva)[1])==2
    assert 'payload==2||payload==6||payload==7'in source
    return ready

def receipt(path,world):
    if path is None:return None
    document=json.loads(path.read_text('utf8'))
    assert document.get('dimension')==DIM, 'Civil receipt dimension mismatch'
    assert Path(document['world']).resolve()==world, 'Each world needs its own independently committed receipt'
    assert document.get('verified') is True, 'Only a real verified installation receipt authorizes first supply'
    return dict(file=str(path.resolve()),sha256=sha(path),document=document)

def entity_tag(unit,row,digest,ready):
    p=[float(v)for v in row['position']]
    return nbtlib.Compound({
        'id':nbtlib.String('projectseele:nerv_armament_station'),'UUID':uuid_nbt(RACKS[unit]),
        'Pos':nbtlib.List[nbtlib.Double](p),'Motion':nbtlib.List[nbtlib.Double]([0,0,0]),
        'Rotation':nbtlib.List[nbtlib.Float]([float(row.get('yaw',180 if unit==0 else 0)),0]),
        'FallDistance':nbtlib.Float(0),'Fire':nbtlib.Short(-1),'Air':nbtlib.Short(300),
        'OnGround':nbtlib.Byte(1),'Invulnerable':nbtlib.Byte(1),'PortalCooldown':nbtlib.Int(0),
        'NoGravity':nbtlib.Byte(1),'CanUpdate':nbtlib.Byte(1),
        'Tags':nbtlib.List[nbtlib.String](['seele_r50_surface_supply',f'seele_r50_supply_unit_{unit}']),
        'PayloadR47':nbtlib.Int(7 if unit==0 else 2),'StationState':nbtlib.Int(ready),
        'LiftProgress':nbtlib.Float(1),'HatchProgress':nbtlib.Float(1),'DoorProgress':nbtlib.Float(1),
        'Stocked':nbtlib.Byte(1),'PhaseTicks':nbtlib.Int(0),'DeployQueued':nbtlib.Byte(0),
        'ForgeData':nbtlib.Compound({'TvMissionRackUnitR45':nbtlib.Int(unit),
            'TvMissionSupplyReceiptR45':nbtlib.String(digest)})})

def entity_directories(world):
    paths=[world/'entities',world/'DIM-1/entities',world/'DIM1/entities']
    if (world/'dimensions').is_dir():paths.extend(p.parent/'entities'for p in(world/'dimensions').rglob('region'))
    return sorted({p.resolve()for p in paths if p.is_dir()})
def inspect_entities(world):
    found={};count=0;regions={}
    for folder in entity_directories(world):
        for path in sorted(folder.glob('r.*.*.mca')):
            if path.stat().st_size==0:continue
            stamps,blobs=read_region(path);regions[path]=(stamps,blobs)
            for slot,blob in enumerate(blobs):
                if blob is None:continue
                document=parse_chunk(blob)
                for tag in document.get('Entities',document.get('entities',[])):
                    count+=1;identifier=canonical_uuid(tag)
                    if identifier in RACKS:found[identifier]=dict(region=str(path),slot=slot,nbt=tag.snbt())
    return found,count,regions

def check_geometry(world,rows):
    evidence=[];ready=True
    for unit,row in sorted(rows.items()):
        x,y,z=map(float,row['position']);half=15.5 if unit==0 else 5.5
        lo=(math.floor(x-half),int(y)-1,math.floor(z-half));hi=(math.ceil(x+half)-1,int(y)+61,math.ceil(z+half)-1)
        selected={(cx,cz)for cx in range(lo[0]//16,hi[0]//16+1)for cz in range(lo[2]//16,hi[2]//16+1)}
        assert set(chunk_statuses(world,DIM,selected).values())=={'full'}
        states=read_box(world,DIM,lo,hi);tags=dict(iter_block_entities(world,DIM,lo,hi))
        bad_floor=[list(p)for p,s in states.items()if p[1]==int(y)-1 and s!='projectseele:nerv_floor_panel']
        obstructed=[dict(pos=list(p),state=s)for p,s in states.items()if p[1]>=int(y) and s not in AIR]
        ready &=not bad_floor and not obstructed and not tags
        evidence.append(dict(unit=unit,bounds=[lo,hi],full_floor=not bad_floor,
            complete61_high_air=not obstructed,block_entities_preserved=not tags,
            bad_floor_count=len(bad_floor),bad_floor_examples=bad_floor[:8],
            obstacle_count=len(obstructed),obstacle_examples=obstructed[:8]))
    return ready,evidence

def compose(world,rows,tags,regions):
    base=world/'dimensions/projectseele/geofront/entities';outputs={};reports=[]
    data_version=int(nbtlib.load(world/'level.dat')['Data']['DataVersion'])
    grouped={}
    for unit,row in rows.items():
        x,y,z=map(float,row['position']);cx,cz=math.floor(x)//16,math.floor(z)//16
        path=base/f'r.{cx//32}.{cz//32}.mca';slot=(cz%32)*32+cx%32
        grouped.setdefault(path,{}).setdefault(slot,[]).append((unit,cx,cz,tags[unit]))
    for path,slots in grouped.items():
        original=path.read_bytes()if path.exists()else None
        stamps,blobs=regions.get(path,(bytes(4096),[None]*1024));new=list(blobs);stamps=bytearray(stamps)
        for slot,entries in slots.items():
            document=copy.deepcopy(parse_chunk(blobs[slot]))if blobs[slot]is not None else nbtlib.File({'DataVersion':nbtlib.Int(data_version),'Position':nbtlib.IntArray([entries[0][1],entries[0][2]]),'Entities':nbtlib.List[nbtlib.Compound]([])})
            key='Entities'if 'Entities'in document else'entities';before=copy.deepcopy(document.get(key,nbtlib.List[nbtlib.Compound]([])))
            if key not in document:document[key]=nbtlib.List[nbtlib.Compound]([])
            for unit,cx,cz,tag in entries:document[key].append(copy.deepcopy(tag))
            new[slot]=chunk_blob(document);stamps[slot*4:slot*4+4]=int(time.time()).to_bytes(4,'big')
            reread=parse_chunk(new[slot]);assert reread[key][:len(before)]==before
            assert len(reread[key])==len(before)+len(entries)
        payload=build_region(bytes(stamps),new);outputs[path]=(original,payload)
        reports.append(dict(relative_target=path.relative_to(world).as_posix(),slots=sorted(slots),
            before_sha256=None if original is None else hashlib.sha256(original).hexdigest(),
            after_sha256=hashlib.sha256(payload).hexdigest(),old_entities_and_full_NBT_retained=True))
    return outputs,reports

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True)
    ap.add_argument('--metadata',type=Path,default=ROOT/'artifacts/rebuild_r50/yashima/ramiel_metadata_candidate.json')
    ap.add_argument('--receipt',type=Path);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--apply',action='store_true',help='Root only; commit the reviewed two new entity records')
    args=ap.parse_args();world=args.world.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    assert world in [p.resolve()for p in ALLOWED], 'Only construction and the existing R49_QA are authorized'
    assert (world/'level.dat').is_file() and not out.is_relative_to(world), 'Plans/backups must stay outside the world'
    document,rows=metadata_racks(args.metadata.resolve());ready=ready_constant()
    with locked_world(world):
        authorization=receipt(args.receipt,world);found,total,regions=inspect_entities(world)
        geometry_ready,geometry=check_geometry(world,rows)
        old_marker=(world/MARKER).exists();blockers=[]
        if authorization is None:blockers.append('A real verified civil receipt for this specific world is required')
        if found:blockers.append('Fixed supply UUID already exists; original full NBT and stock must not be reset')
        if old_marker:blockers.append('One-time installation receipt already exists; do not re-install or replenish')
        if not geometry_ready:blockers.append('Actual full supply footprint/61-high air must first match the applied civil')
        tags={}if authorization is None else{unit:entity_tag(unit,row,authorization['sha256'],ready)for unit,row in rows.items()}
        outputs={};reports=[]
        if tags and not found and not old_marker:outputs,reports=compose(world,rows,tags,regions)
        plan=dict(schema='projectseele.r50.two-supply-entity-plan.v1',world=str(world),dimension=DIM,
            metadata=str(args.metadata.resolve()),metadata_sha256=sha(args.metadata),
            civil_receipt=None if authorization is None else authorization['file'],
            civil_receipt_digest=None if authorization is None else authorization['sha256'],
            entities_before=total,new_entity_count=2,original_entities_and_full_NBT_retained=True,
            new_entities=[dict(unit=unit,uuid=RACKS[unit],expected_cargo_uuid=CARGO[unit],position=row['position'],payload=7 if unit==0 else 2,
                actual_READY_constant=ready,after_nbt=None if unit not in tags else tags[unit].snbt())for unit,row in sorted(rows.items())],
            duplicate_UUIDs=found,one_time_marker_already_present=old_marker,geometry=geometry,
            region_operations=reports,blockers=blockers,apply_ready=not blockers,
            item_inventory_generated_offline=False,equipment_SavedData_rewritten=False,
            player_or_original_actor_progress_rewritten=False,world_written=False,native_verified=False)
        durable_json(out/'plan.json',plan)
        for unit,tag in tags.items():(out/f'unit{unit}_new_entity.snbt').write_text(tag.snbt(),'utf8')
        if not args.apply:
            print(json.dumps(dict(plan=str(out/'plan.json'),apply_ready=not blockers,blockers=blockers,world_written=False),ensure_ascii=False));return
        if blockers:raise RuntimeError('Root application is blocked: '+'; '.join(blockers))
        assert authorization is not None and sha(args.receipt)==authorization['sha256'] and sha(args.metadata)==plan['metadata_sha256']
        backup=out/'entity_region_before';backup.mkdir(exist_ok=False)
        for path,(before,after)in outputs.items():
            if before is not None:
                assert path.read_bytes()==before, 'Entity region changed after locked preflight'
                destination=backup/path.relative_to(world);destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(before)
            path.parent.mkdir(parents=True,exist_ok=True);atomic_replace(path,after)
            stamps,blobs=read_region(path)
            actual={canonical_uuid(e):e for blob in blobs if blob is not None for e in parse_chunk(blob).get('Entities',[])}
            for unit,tag in tags.items():
                if RACKS[unit]in actual:assert actual[RACKS[unit]]==tag
        installed=dict(plan,world_written=True,installed_at_unix=int(time.time()),backup=str(backup),
            production_commission_required=True,commission_generates_only_first_declared_two_real_stacks=True,
            inverse_guard='Restore only before any runtime commission or actor progress; never overwrite later stock/progress')
        durable_json(out/'receipt.json',installed);durable_json(world/MARKER,installed)
        print(json.dumps(dict(receipt=str(out/'receipt.json'),world=str(world),new_entities=2,inventory_written=False),ensure_ascii=False))
if __name__=='__main__':main()
