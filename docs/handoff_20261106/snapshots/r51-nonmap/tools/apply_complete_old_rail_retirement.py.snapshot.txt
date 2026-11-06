"""Retire reviewed original formations from exact producer before states."""
from pathlib import Path
from collections import defaultdict
import argparse,gzip,hashlib,json,msvcrt
import numpy as np
import regional_voxels as vox
import extend_world_depth_r52 as extension
from query_blocks import iter_selected_sections,iter_block_entities

DIM='projectseele:geofront'


def verify(world,rows,key):
    groups=defaultdict(list);selected=defaultdict(set)
    for r in rows:
        x,y,z=r['pos'];groups[x//16,z//16,y//16].append(r);selected[x//16,z//16].add(y//16)
    found=set()
    for cx,cz,sy,palette,indices in iter_selected_sections(world,DIM,selected):
        section=(cx,cz,sy);found.add(section)
        for r in groups[section]:
            x,y,z=r['pos'];assert palette[int(indices[((y&15)<<8)|((z&15)<<4)|(x&15)])]==r[key],('Retirement readback mismatch',r['pos'],key)
    assert found==set(groups)
    points={tuple(r['pos']) for r in rows};lo=tuple(min(p[k] for p in points) for k in range(3));hi=tuple(max(p[k] for p in points) for k in range(3))
    assert not any(p in points for p,t in iter_block_entities(world,DIM,lo,hi,selected_chunks=set(selected)))


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--apply',action='store_true');a=p.parse_args()
    base=a.base.resolve();world=base/'WORLD';out=base/'old_HQ_rail_retirement';stage='complete_original_11_and_predecessor_formations'
    assert not(out/'APPLIED.json').exists()
    report=json.loads((a.candidate/'REPORT.json').read_text('utf8'));source=a.candidate/'EXACT_CHANGES.jsonl.gz'
    assert hashlib.sha256(source.read_bytes()).hexdigest()==report['exact_changes_sha256']
    assert report['changes']==42727 and report['original_complete_shared_station_and_R28_protection_cells']==1350
    with gzip.open(source,'rt',encoding='utf8') as f:rows=[json.loads(s) for s in f]
    assert len(rows)==len({tuple(r['pos']) for r in rows})==42727
    assert all(r['after'] in ('minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]') and r['before_nbt'] is None and r['after_nbt'] is None for r in rows)
    verify(world,rows,'before')
    vox.WORLD=extension.WORLD=world;vox.OUT=out;vox.DIM=DIM;painter=vox.Painter(vertical_bounds=(-1344,320))
    for r in rows:painter.exact((*r['pos'],*r['pos']),r['before'],r['after'],r['owner'])
    painter.meta.update(root_author=True,exact_original_producer_restoration=True,source_candidate=str(a.candidate),
        protected_original_station_and_walkway_cells=1350,original_traffic_metadata_unchanged=True,playable=False)
    folder=painter.save_plan(stage)
    if not a.apply:return
    assert not list(folder.glob('applied_*'));lock=extension.acquire_world_lock()
    try:
        receipt=painter.apply(stage,session_lock=lock);verify(world,rows,'after')
        (out/'APPLIED.json').write_text(json.dumps(dict(world_written=True,receipt=receipt,exact_original_bed_cells=41952,
            whole_previously_broken_tree_fragments_retired=775,protected_other_facility_cells=1350,
            complete_before_after_readback=True,source_changes_sha256=report['exact_changes_sha256'],
            mtr_entities_player_progress_written=False),indent=2),'utf8')
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
