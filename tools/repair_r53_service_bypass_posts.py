"""Preserve four active original pipe brackets after retiring the main shaft."""
from pathlib import Path
import argparse
import json
import regional_voxels as vox
from query_blocks import read_box,iter_block_entities


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--base',type=Path,required=True);ap.add_argument('--apply',action='store_true')
    args=ap.parse_args();b=args.base;w=b/'CANDIDATE';dim='projectseele:geofront';painter=vox.Painter(vertical_bounds=(-1344,320))
    vox.WORLD=w;vox.DIM=dim;vox.OUT=b/'service-bypass-posts';points=[]
    source=json.loads((b/'selected-assets/assets/projectseele/mesh/legacy_service_bypass_r52.json').read_text('utf8'))
    required={tuple([int(r['at'][0]),int(r['at'][1])-384,int(r['at'][2])]) for r in source['native_wall_faces']}
    assert required=={(x,y,z) for x in (6,12) for z,y in ((251,-1050),(255,-1051))}
    for x,top,z in sorted(required):
        lo=(x,top-6,z);hi=(x,top,z);now=read_box(w,dim,lo,hi);frozen=read_box(b/'WORLD',dim,lo,hi)
        assert now[x,top-4,z]=='projectseele:nerv_floor_panel'
        assert all(now[x,y,z]=='projectseele:nerv_structural_panel' for y in (top-5,top-6))
        assert not list(iter_block_entities(w,dim,lo,hi))
        for y in range(top-3,top+1):
            q=x,y,z;assert frozen[q]=='projectseele:nerv_structural_panel' and now[q]=='minecraft:air'
            painter.exact((*q,*q),now[q],frozen[q],'active_service_bypass_independent_floor_post');points.append(q)
    painter.meta.update(original_frozen_wall_faces_retained=True,continuous_floor_bearing=True,retired_lift_not_restored=True)
    folder=painter.save_plan('four_original_active_bracket_posts')
    assert not list(folder.glob('applied_*'))
    if args.apply:
        painter.apply('four_original_active_bracket_posts')
        for q in points:assert read_box(w,dim,q,q)[q]=='projectseele:nerv_structural_panel'
    (vox.OUT/'POSTS.json').write_text(json.dumps(dict(points=points,world_written=args.apply),indent=2),'utf8')
    print('Four active bracket posts, 16 original cells, floor connection read back')


if __name__=='__main__':main()
