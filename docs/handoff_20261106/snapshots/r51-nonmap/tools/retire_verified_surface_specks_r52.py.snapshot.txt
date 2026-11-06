"""Remove five reviewed unsupported natural surface cells, with exact inverse.

Other singleton observations, carved stone decorations, cave features, and
unmeasured chunk edges are deliberately not generic demolition targets.
"""
import argparse,json,msvcrt
import regional_voxels as vox
from r52_spatial_plan import BASE
from query_blocks import read_box,iter_block_entities,AIR
from extend_world_depth_r52 import acquire_world_lock

TARGETS=((803,77,280),(806,101,281),(123,79,-17),(799,83,279),(7113,132,-6480))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    world=BASE/'WORLD_R52';out=BASE/'final_map_audit/floating_context';p=vox.Painter(vertical_bounds=(-960,320))
    source=json.loads((out/'CONTEXT.json').read_text('utf8'));contexts={tuple(r['pos']):r for r in source}
    scan=json.loads((out.parent/'ISOLATED_TERRAIN_REVIEW.json').read_text('utf8'))
    expected={tuple(r['pos']):r['state'] for r in scan['exposed_fragments']}
    steps=((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1))
    for q in TARGETS:
        assert contexts[q]['status']=='REVIEW' and not contexts[q]['foreign_materials']
        lo=tuple(v-1 for v in q);hi=tuple(v+1 for v in q);cells=read_box(world,'projectseele:geofront',lo,hi)
        assert expected[q] in ('minecraft:stone','minecraft:grass_block[snowy=false]')
        assert cells[q]==expected[q]
        assert all(cells.get(tuple(a+b for a,b in zip(q,d))) in AIR for d in steps)
        assert not list(iter_block_entities(world,'projectseele:geofront',lo,hi))
        p.exact((*q,*q),expected[q],'minecraft:air','R52_reviewed_natural_surface_singleton')
    vox.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront'
    p.meta.update(root_author=True,context_image='EXPOSED_CANDIDATES.png',targets=TARGETS,
        cave_and_authored_stone_candidates_preserved=True)
    stage=p.save_plan('five_verified_natural_surface_specks')
    report=dict(world_written=False,cells=5,targets=TARGETS,original_structures_and_nbt_unchanged=True)
    if args.apply:
        assert not list(stage.glob('applied_*')),'Do not replay'
        lock=acquire_world_lock()
        try:report.update(world_written=True,receipt=p.apply('five_verified_natural_surface_specks',session_lock=lock))
        finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
    (stage/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)


if __name__=='__main__':main()
