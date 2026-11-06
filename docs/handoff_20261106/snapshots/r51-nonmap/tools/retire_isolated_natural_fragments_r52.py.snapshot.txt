"""Root-owned finite cleanup of six-air-face natural fragments.

Only measured natural context is eligible. Authored stonework/concrete and
unmeasured context remain intact. Each write checks the current block, six
neighbors and nearby block entities; no terrain or component flood clearing.
"""
import argparse, json, msvcrt
from collections import Counter
import regional_voxels as vox
from r52_spatial_plan import BASE
from query_blocks import read_box, iter_block_entities, AIR
from extend_world_depth_r52 import acquire_world_lock

OUT = BASE / 'final_map_audit/floating_context'
STAGE = 'remaining_measured_natural_singletons'
STEPS = ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1))
SOIL = {'minecraft:stone', 'minecraft:dirt', 'minecraft:grass_block', 'minecraft:gravel',
        'minecraft:sand', 'minecraft:clay', 'minecraft:coarse_dirt', 'minecraft:deepslate',
        'minecraft:podzol', 'minecraft:tuff', 'minecraft:bedrock', 'minecraft:water',
        'minecraft:lava', 'minecraft:grass', 'minecraft:fern'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    assert not list((OUT/STAGE).glob('applied_*')), 'Do not replay cleanup'
    source=json.loads((OUT/'REMAINING_ACTUAL_CONTEXT.json').read_text('utf8'))
    world=BASE/'WORLD_R52';p=vox.Painter(vertical_bounds=(-960,320));rows=[]
    for row in source:
        q=tuple(row['pos']);lo=tuple(v-4 for v in q);hi=tuple(v+4 for v in q)
        cells=read_box(world,'projectseele:geofront',lo,hi)
        assert len(cells)==729, ('Incomplete measured context', q, len(cells))
        current=cells[q]
        foreign=sorted({s for s in cells.values() if s not in AIR and s.split('[')[0] not in SOIL})
        if foreign:
            rows.append(dict(position=q,status='AUTHORED_CONTEXT_PRESERVED',foreign=foreign));continue
        assert current.split('[')[0] in SOIL and current not in AIR, (q,current)
        assert all(cells[tuple(a+b for a,b in zip(q,d))] in AIR for d in STEPS), q
        assert not list(iter_block_entities(world,'projectseele:geofront',lo,hi)), q
        p.exact((*q,*q),current,'minecraft:air','R52_verified_suspended_natural_fragment')
        rows.append(dict(position=q,status='REMOVE_ISOLATED_NATURAL_CELL',before=current))
    count=sum(r['status']=='REMOVE_ISOLATED_NATURAL_CELL' for r in rows)
    assert count==42, count
    vox.WORLD=world;vox.OUT=OUT;vox.DIM='projectseele:geofront'
    p.meta.update(root_author=True,source='REMAINING_ACTUAL_CONTEXT.json',only_six_air_faces=True,
                  natural_context_radius=4,authored_components_preserved=True)
    stage=p.save_plan(STAGE);report=dict(world_written=False,rows=rows,counts=dict(Counter(r['status'] for r in rows)))
    if args.apply:
        lock=acquire_world_lock()
        try:report.update(receipt=p.apply(STAGE,session_lock=lock),world_written=True)
        finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
    (stage/'PLAN.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(world_written=report['world_written'],counts=report['counts'])),flush=True)

if __name__=='__main__':main()
