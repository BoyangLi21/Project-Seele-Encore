"""Merge only explicitly measured unfinished chunks from the native fixture."""
import argparse,json,hashlib,time,msvcrt
from pathlib import Path
from collections import defaultdict
from transplant_s22_authority import read_region,parse_chunk,build_region
from apply_s20_approved_semantic_repairs import atomic_replace
from extend_world_depth_r52 import acquire_world_lock
from r52_spatial_plan import BASE


def sha(raw):return hashlib.sha256(raw).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');ap.add_argument('--job-root',type=Path,default=BASE/'native_generation');args=ap.parse_args()
    out=args.job_root.resolve();assert out.is_relative_to((BASE/'native_generation').resolve())
    spec=json.loads((out/'STAGED.json').read_text('utf8'));run=json.loads((out/'RUN_RESULT.json').read_text('utf8'))
    assert run['passed'] and run['exit_code']==0 and run['full']==len(spec['targets'])
    assert not(out/'APPLIED.json').exists(),'Never replay a native chunk merge'
    world=Path(spec['source_world']).resolve();fixture=Path(spec['fixture']);group=defaultdict(list)
    assert world.parent==BASE.resolve() and world.name in ('WORLD','WORLD_R52'),'Explicit construction source required'
    for row in spec['targets']:group[row['x']//32,row['z']//32].append(row)
    prepared=[];rows=[]
    for(rx,rz),targets in sorted(group.items()):
        rel=f'dimensions/projectseele/geofront/region/r.{rx}.{rz}.mca';path=world/rel
        before=path.read_bytes()if path.is_file()else None
        if rel in spec['region_source_sha256']:assert before is not None and sha(before)==spec['region_source_sha256'][rel],('Source changed',rel)
        else:assert before is None,('New external region',rel)
        # A measured zero-byte placeholder owns no chunk slots. Its exact
        # empty preimage is still checked and backed up above/below; a
        # non-empty malformed region continues to fail the strict reader.
        stamps,blobs=read_region(path)if before else(bytes(4096),[None]*1024)
        old_stamps=bytes(stamps);stamps=bytearray(stamps);old_blobs=list(blobs);source_stamps,source_blobs=read_region(fixture/rel);touched=set();old_full=0
        for row in targets:
            x,z=row['x'],row['z'];index=(x%32)+(z%32)*32;old=blobs[index]
            assert row['status']!='full'
            if old is None:assert row['status']=='missing'
            else:assert str(parse_chunk(old)['Status']).removeprefix('minecraft:')==row['status']
            blob=source_blobs[index];assert blob is not None;tag=parse_chunk(blob)
            assert(int(tag['xPos']),int(tag['zPos']))==(x,z)and str(tag['Status']).removeprefix('minecraft:')=='full'
            assert int(tag['yPos'])==-60 and any(int(s['Y'])==-60 for s in tag['sections'])
            assert not any(str(be['id']).startswith(('projectseele:','mtr:'))for be in tag.get('block_entities',[])),('Unexpected automatic construction in generation target',(x,z))
            blobs[index]=blob;stamps[index*4:index*4+4]=source_stamps[index*4:index*4+4];touched.add(index)
        for i in range(1024):
            if i not in touched:
                assert old_stamps[i*4:i*4+4]==stamps[i*4:i*4+4]and old_blobs[i]==blobs[i]
                old_full+=old_blobs[i]is not None
        after=build_region(bytes(stamps),blobs);prepared.append((path,before,after,touched,old_stamps,old_blobs))
        rows.append(dict(file=rel,before_sha256=None if before is None else sha(before),after_sha256=sha(after),native_completed_chunks=len(touched),other_existing_chunks_preserved=old_full))
    report=dict(world_written=False,source_native_run=str(out/'RUN_RESULT.json'),native_chunks=len(spec['targets']),regions=rows,
                player_entities_mtr_saved_data_not_written=True,original_FULL_chunks_not_written=True)
    (out/'MERGE_PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)
    if not args.apply:return
    lock=acquire_world_lock();backup=out/'merge_before';backup.mkdir();written=[]
    try:
        for path,before,after,touched,old_stamps,old_blobs in prepared:
            assert(path.read_bytes()if path.is_file()else None)==before
            if before is not None:
                dest=backup/path.relative_to(world);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(before)
            path.parent.mkdir(parents=True,exist_ok=True);atomic_replace(path,after);written.append((path,before))
            stamps,blobs=read_region(path);assert sha(path.read_bytes())==sha(after)
            for i in range(1024):
                if i not in touched:assert old_stamps[i*4:i*4+4]==stamps[i*4:i*4+4]and old_blobs[i]==blobs[i]
                else:assert str(parse_chunk(blobs[i])['Status']).removeprefix('minecraft:')=='full'
        report.update(world_written=True,applied_at_unix=int(time.time()),exact_all_region_slots_readback=True)
        (out/'APPLIED.json').write_text(json.dumps(report,indent=2),'utf8')
    except BaseException:
        for path,before in reversed(written):
            if before is not None:atomic_replace(path,before)
            else:path.unlink()
        raise
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
