"""Merge only missing/proto native halo slots, extended to the current depth.

The one original seed-identical terrain fixture supplies no entity regions,
players, MTR, SavedData or existing FULL chunks. Existing region slots remain
byte-identical. This is for explicit already-authored finite construction bounds.
"""
from pathlib import Path
from collections import defaultdict,Counter
import argparse,ast,copy,hashlib,json,msvcrt
import nbtlib
from query_blocks import chunk_statuses
from transplant_s22_authority import read_region,parse_chunk,build_region,chunk_blob
from apply_s20_approved_semantic_repairs import atomic_replace
import extend_world_depth_r52 as depth


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--area',required=True)
    choice=p.add_mutually_exclusive_group(required=True)
    choice.add_argument('--xz-bounds',type=int,nargs=4)
    choice.add_argument('--chunks-file',type=Path,help='Explicit measured missing/proto chunk map')
    p.add_argument('--apply',action='store_true');a=p.parse_args()
    base=a.base.resolve();world=base/'WORLD';fixture=base/'native_generation/server/CURRENT_TERRAIN_ONLY'
    assert a.area.replace('_','').isalnum();out=base/'native_generation'/a.area;out.mkdir(exist_ok=True)
    assert not(out/'APPLIED.json').exists()
    original_run=json.loads((base/'native_generation/RUN_RESULT.json').read_text('utf8'))
    assert original_run['passed'] and original_run['exit_code']==0
    def seed(path):return int(nbtlib.load(path/'level.dat')['Data']['WorldGenSettings']['seed'])
    assert seed(world)==seed(fixture)
    if a.chunks_file:
        table=json.loads(a.chunks_file.read_text('utf8'))
        keys={tuple(ast.literal_eval(k)) for k in table}
        assert keys and len(keys)<=20000 and all(len(k)==2 and all(type(v) is int for v in k) for k in keys)
    else:
        x,z,X,Z=a.xz_bounds;assert x<=X and z<=Z and (X-x)*(Z-z)<200000
        keys={(i,j) for i in range(x//16,X//16+1) for j in range(z//16,Z//16+1)}
    statuses=chunk_statuses(world,'projectseele:geofront',keys);wanted={p:s for p,s in statuses.items() if s!='full'}
    assert wanted and set(chunk_statuses(fixture,'projectseele:geofront',wanted).values())=={'full'}
    groups=defaultdict(list)
    for pos,status in wanted.items():groups[pos[0]//32,pos[1]//32].append((pos,status))
    planned=[]
    for (rx,rz),targets in sorted(groups.items()):
        rel=Path(f'dimensions/projectseele/geofront/region/r.{rx}.{rz}.mca');path=world/rel
        raw=path.read_bytes() if path.exists() else None
        stamps,blobs=read_region(path) if raw else (bytes(4096),[None]*1024)
        fs,fb=read_region(fixture/rel);updated=list(blobs);new_stamps=bytearray(stamps);selected=[]
        for (cx,cz),status in targets:
            index=(cx&31)+(cz&31)*32
            if blobs[index] is None:assert status=='missing'
            else:
                previous=parse_chunk(blobs[index]);assert str(previous['Status']).removeprefix('minecraft:')==status
                assert not previous.get('block_entities',[]),'Existing proto device requires explicit preservation'
            tag=parse_chunk(fb[index]);original=copy.deepcopy(tag)
            assert int(tag['yPos'])==-60 and str(tag['Status']).removeprefix('minecraft:')=='full'
            assert not any(str(be['id']).startswith(('projectseele:','mtr:')) for be in tag.get('block_entities',[]))
            tag=depth.verify_fixture(original,old_min=-960,new_min=-1344,max_y=320)
            updated[index]=chunk_blob(tag);new_stamps[index*4:index*4+4]=fs[index*4:index*4+4];selected.append(index)
        untouched=set(range(1024))-set(selected)
        assert all(blobs[i]==updated[i] and stamps[i*4:i*4+4]==new_stamps[i*4:i*4+4] for i in untouched)
        planned.append((path,raw,build_region(bytes(new_stamps),updated),stamps,blobs,selected))
    report=dict(world_written=False,world=str(world),fixture=str(fixture),xz_bounds=a.xz_bounds,
        explicit_chunk_source=None if a.chunks_file is None else str(a.chunks_file.resolve()),
        explicit_chunk_source_sha256=None if a.chunks_file is None else hashlib.sha256(a.chunks_file.read_bytes()).hexdigest(),
        native_slots=len(wanted),original_status_counts=dict(Counter(wanted.values())),new_min_y=-1344,
        every_unselected_slot_and_stamp_preserved=True,entities_players_mtr_saveddata_written=False)
    (out/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)
    if not a.apply:return
    depth.WORLD=world;lock=depth.acquire_world_lock();written=[]
    try:
        for path,old,new,stamps,blobs,selected in planned:
            assert (path.read_bytes() if path.exists() else None)==old
            if old is not None:
                backup=out/'before'/path.relative_to(world);backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(old)
            path.parent.mkdir(parents=True,exist_ok=True);atomic_replace(path,new);written.append((path,old))
            s,b=read_region(path)
            assert path.read_bytes()==new
            for i in range(1024):
                if i not in selected:assert s[i*4:i*4+4]==stamps[i*4:i*4+4] and b[i]==blobs[i]
                else:assert int(parse_chunk(b[i])['yPos'])==-84
        report['world_written']=True;(out/'APPLIED.json').write_text(json.dumps(report,indent=2),'utf8')
        print('Exact native halo slots merged, existing FULL slots unchanged.',flush=True)
    except BaseException:
        for path,old in reversed(written):
            if old is None:path.unlink()
            else:atomic_replace(path,old)
        raise
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
