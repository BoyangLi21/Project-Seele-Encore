"""Extend the current construction from -960 to -1344 without shifting old data.

Each exact current region is backed up and journalled before mutation. The
original release archive is not used as an inverse for a later edited world.
"""
from pathlib import Path
import argparse
import hashlib
import json
import msvcrt
import os
import time
import copy
import nbtlib
import extend_world_depth_r52 as depth
from transplant_s22_authority import read_region,parse_chunk,build_region
from apply_s20_approved_semantic_repairs import atomic_replace,chunk_blob

OLD_MIN,NEW_MIN,MAX_Y=-960,-1344,320


def sha(raw):return hashlib.sha256(raw).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True);ap.add_argument('--apply',action='store_true');ap.add_argument('--rollback-interrupted',action='store_true');a=ap.parse_args()
    base=a.base.resolve();world=base/'WORLD';depth.WORLD=world
    assert world.parent==base and not world.is_symlink() and not world.is_junction()
    out=base/'deeper_foundation_1344';out.mkdir(exist_ok=True);journal=out/'REGION_JOURNAL.jsonl'
    pack=world/'datapacks/tv_world_preview/data/projectseele/dimension_type/geofront.json'
    if a.rollback_interrupted:
        assert not a.apply and not (out/'APPLIED.json').exists()
        rows=[json.loads(s) for s in journal.read_text('utf8').splitlines()]
        lock=depth.acquire_world_lock()
        try:
            for row in reversed(rows):
                path=world/row['path'];before=(out/'before'/row['path']).read_bytes()
                assert path.resolve().is_relative_to(world.resolve()) and sha(before)==row['before_sha256']
                assert sha(path.read_bytes()) in (row['before_sha256'],row['after_sha256'])
                atomic_replace(path,before)
            if (out/'dimension_type_before.json').exists():atomic_replace(pack,(out/'dimension_type_before.json').read_bytes())
            journal.rename(out/f'ROLLED_BACK_{time.time_ns()}.jsonl')
        finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
        return
    paths=sorted((world/depth.REGION).glob('r.*.mca'));assert paths
    checked={}
    for path in paths:
        if not path.stat().st_size:continue
        for blob in read_region(path)[1]:
            if blob is None:continue
            root=parse_chunk(blob);key=(str(root.get('Status')),bool(root.get('block_entities')),bool(root.get('Heightmaps')))
            if key in checked:continue
            result=depth.verify_fixture(root,OLD_MIN,NEW_MIN,MAX_Y)
            # Exercise the exact serialized result used by the writer too.
            decoded=parse_chunk(chunk_blob(result));assert decoded.snbt()==result.snbt()
            checked[key]=True
            if len(checked)>=8:break
        if len(checked)>=8:break
    (out/'FIXTURE_CHECK.json').write_text(json.dumps(dict(old_min=OLD_MIN,new_min=NEW_MIN,max_y=MAX_Y,fixture_kinds=[list(k) for k in checked],original_sections_and_biomes_exact=True,unrelated_typed_nbt_exact=True,heightmap_offset=384,old_bits=11,new_bits=11),indent=2),'utf8')
    print('Detached actual deep extension fixtures passed',len(checked),flush=True)
    if not a.apply:return
    assert not (out/'APPLIED.json').exists() and not journal.exists(),'Inspect prior transaction, do not replay'
    original_pack=pack.read_bytes();old=json.loads(original_pack);assert (old['min_y'],old['height'])==(-960,1280)
    proposed=dict(old,min_y=NEW_MIN,height=MAX_Y-NEW_MIN,logical_height=MAX_Y-NEW_MIN)
    raw_pack=(json.dumps(proposed,indent=2)+'\n').encode('utf8');(out/'dimension_type_before.json').write_bytes(original_pack)
    lock=depth.acquire_world_lock();touched=[];total=0;start=time.monotonic()
    try:
        with journal.open('x',encoding='utf8') as log:
            for path in paths:
                assert not path.is_symlink() and not path.is_junction()
                before=path.read_bytes()
                if not before:continue
                stamps,blobs=read_region(path);count=0
                for i,blob in enumerate(blobs):
                    if blob is None:continue
                    blobs[i]=chunk_blob(depth.extend_chunk(parse_chunk(blob),OLD_MIN,NEW_MIN,MAX_Y));count+=1
                if not count:continue
                after=build_region(stamps,blobs);relative=path.relative_to(world).as_posix();backup=out/'before'/relative
                backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(before);assert sha(backup.read_bytes())==sha(before)
                row=dict(path=relative,before_sha256=sha(before),after_sha256=sha(after),chunks=count)
                log.write(json.dumps(row)+'\n');log.flush();os.fsync(log.fileno());touched.append(row)
                assert path.read_bytes()==before;atomic_replace(path,after);assert sha(path.read_bytes())==row['after_sha256']
                total+=count
                if len(touched)%10==0:print('Extended current regions',len(touched),'chunks',total,flush=True)
        assert pack.read_bytes()==original_pack;atomic_replace(pack,raw_pack);assert pack.read_bytes()==raw_pack
        (out/'APPLIED.json').write_text(json.dumps(dict(world=str(world),world_written=True,new_min_y=NEW_MIN,height=MAX_Y-NEW_MIN,chunks=total,regions=touched,original_absolute_sections_preserved=True,entities_players_mtr_saved_data_not_written=True,dimension_pack_sha256=sha(raw_pack),native_load_pending=True,elapsed_seconds=time.monotonic()-start),indent=2),'utf8')
    except BaseException:
        atomic_replace(pack,original_pack)
        for row in reversed(touched):atomic_replace(world/row['path'],(out/'before'/row['path']).read_bytes())
        (out/'ROLLED_BACK.json').write_text('{"reason":"transaction failure"}','utf8')
        raise
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
    print('Current construction depth extended',total,'chunks; no facility relocated by this stage',flush=True)


if __name__=='__main__':main()
