"""One new GeoFront aircraft plan; --apply reserved for Root after civil receipt.

Reuse the established exact entity-region codec/locks. No original aircraft,
inventory, EVA identity, SavedData or crew progress may be rewritten.
"""
from pathlib import Path
import argparse,copy,hashlib,json,time
import nbtlib
import prepare_yashima_supply_entities_r50 as shared
from transplant_s22_authority import atomic_replace,read_region,parse_chunk
from query_blocks import read_box,chunk_statuses,iter_block_entities,AIR

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/rebuild_r50/underground_airport'
MARKER='r50_underground_aircraft_receipt.json'

def geometry(world):
    lo=(-510,-476,-328);hi=(-370,-429,-210)
    chunks={(x,z)for x in range(lo[0]//16,hi[0]//16+1)for z in range(lo[2]//16,hi[2]//16+1)}
    assert set(chunk_statuses(world,shared.DIM,chunks).values())=={'full'}
    states=read_box(world,shared.DIM,lo,hi);tags=dict(iter_block_entities(world,shared.DIM,lo,hi))
    bad_floor=[p for p,s in states.items()if p[1]==-476 and s not in {'minecraft:gray_concrete','minecraft:smooth_stone'}]
    obstructions=[(p,s)for p,s in states.items()if p[1]>-476 and s not in AIR]
    return not bad_floor and not obstructions and not tags,dict(bounds=[lo,hi],bad_floor_count=len(bad_floor),
        obstruction_count=len(obstructions),block_entities=len(tags),gear_root=-464,wheel_min_y=-475,floor_top=-475,
        collision_shape='Actual fixed-yaw body139x114; full space above native contact floor, not entity8x8 proxy')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True)
    ap.add_argument('--metadata',type=Path,default=BASE/'flight_geometry_candidate.json')
    ap.add_argument('--receipt',type=Path);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--apply',action='store_true',help='Root only, one-time actor commission')
    args=ap.parse_args();world=args.world.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    assert world in [p.resolve()for p in shared.ALLOWED] and not out.is_relative_to(world)
    meta=json.loads(args.metadata.read_text('utf8'));uid=meta['aircraft_uuid'];assert meta['airport_stand']==[-440,-464,-270]
    tag=nbtlib.parse_nbt(Path(meta['aircraft_nbt_candidate']).read_text('utf8'))
    assert shared.canonical_uuid(tag)==uid and str(tag['id'])=='projectseele:un_transport' and int(tag['NervAircraft'])==1
    assert [float(v)for v in tag['Pos']]==meta['airport_stand'] and int(tag['Cargo'])==0
    assert 'seele_un_airlift'not in [str(v)for v in tag.get('Tags',[])]
    shared.RACKS=[uid]
    with shared.locked_world(world):
        receipt=shared.receipt(args.receipt,world);found,total,regions=shared.inspect_entities(world)
        good,evidence=geometry(world);blockers=[]
        if receipt is None:blockers.append('Requires this world actual verified airport civil-install receipt')
        if not good:blockers.append('Actual full apron/body/gear geometry has not yet been installed')
        if found:blockers.append('New fixed UUID already exists; never clone or reset it')
        if (world/MARKER).exists():blockers.append('One-time actor receipt already installed')
        committed=copy.deepcopy(tag)
        if receipt is not None:committed['ForgeData']=nbtlib.Compound({'TvUndergroundAircraftInstallReceiptR50':nbtlib.String(receipt['sha256'])})
        outputs={};reports=[]
        if not blockers:outputs,reports=shared.compose(world,{0:dict(position=meta['airport_stand'])},{0:committed},regions)
        plan=dict(schema=50,world=str(world),aircraft_uuid=uid,after_nbt=committed.snbt(),entities_before=total,
            new_entities=1,original_full_entity_NBT_preserved=True,item_inventory_written=False,original_actor_progress_reset=False,
            metadata_sha256=shared.sha(args.metadata),civil_receipt=None if receipt is None else receipt['file'],
            civil_receipt_digest=None if receipt is None else receipt['sha256'],geometry=evidence,
            region_operations=reports,blockers=blockers,apply_ready=not blockers,world_written=False,native_verified=False)
        shared.durable_json(out/'plan.json',plan)
        if not args.apply:
            print(json.dumps(dict(plan=str(out/'plan.json'),apply_ready=not blockers,blockers=blockers,world_written=False)));return
        if blockers:raise RuntimeError('; '.join(blockers))
        assert shared.sha(args.metadata)==plan['metadata_sha256'] and shared.sha(args.receipt)==receipt['sha256']
        backup=out/'entity_region_before';backup.mkdir(exist_ok=False)
        for path,(before,after)in outputs.items():
            if before is not None:
                assert path.read_bytes()==before
                target=backup/path.relative_to(world);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(before)
            path.parent.mkdir(parents=True,exist_ok=True);atomic_replace(path,after)
            stamps,blobs=read_region(path)
            actual=[e for blob in blobs if blob is not None for e in parse_chunk(blob).get('Entities',[])if shared.canonical_uuid(e)==uid]
            assert len(actual)==1 and actual[0]==committed
        done=dict(plan,world_written=True,installed_at_unix=int(time.time()),backup=str(backup),
            inverse_guard='Restore archive only before runtime flights/progress; never overwrite later world actors')
        shared.durable_json(out/'receipt.json',done);shared.durable_json(world/MARKER,done)
        print(json.dumps(dict(receipt=str(out/'receipt.json'),new_aircraft=1,world=str(world))))

if __name__=='__main__':main()
