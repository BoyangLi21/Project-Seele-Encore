"""Build measured lower public ring links without changing rooms or devices."""
import argparse,json
from collections import Counter
import numpy as np
from scipy.ndimage import binary_dilation,label
import regional_voxels as vox
from r52_spatial_plan import BASE
from plan_pyramid_ring_links_r52 import LINKS
from survey_r52_original_complex import measure
from prepare_terminal_move_r52 import runs
from query_blocks import iter_block_entities


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');ap.add_argument('--upper',action='store_true');args=ap.parse_args()
    out=BASE/'pyramid_ring_links';world=BASE/'WORLD_R52'
    stage='upper_public_ring_closures'if args.upper else'lower_public_ring_closures'
    assert not list((out/stage).glob('applied_*')),'Do not overwrite an already installed patch receipt'
    lo,hi=((-5,-487,260),(82,-453,314))if args.upper else((-36,-556,240),(95,-509,292))
    before,names=measure(lo,hi)
    for s in ('minecraft:air','projectseele:nerv_floor_panel','projectseele:nerv_wall_panel','projectseele:clear_glass','projectseele:nerv_strip_light[lit=true]'):
        if s not in names:names.append(s)
    ids={s:i for i,s in enumerate(names)};after=before.copy();records=[]
    empty=np.array([s in ('minecraft:air','minecraft:void_air','minecraft:cave_air') for s in names])
    aperture_allowed={'minecraft:air','minecraft:void_air','minecraft:cave_air','minecraft:deepslate_bricks','minecraft:polished_deepslate',
                      'projectseele:nerv_structural_panel','projectseele:nerv_wall_panel','projectseele:clear_glass','projectseele:nerv_ceiling_light[hanging=false,lit=true]',
                      'projectseele:nerv_wall_datum','minecraft:gray_concrete','minecraft:light_gray_concrete'}
    for y in ((-485,-457)if args.upper else(-554,-541,-527,-513)):
        nodes=LINKS[y];mask=np.zeros(before.shape[1:],bool)
        for (x,z),(X,Z) in zip(nodes,nodes[1:]):
            mask[min(z,Z)-1-lo[2]:max(z,Z)+2-lo[2],min(x,X)-1-lo[0]:max(x,X)+2-lo[0]]=True
        yi=y-lo[1];new=mask&empty[before[yi-1]];height=2 if y==-485 else 3
        observed={names[int(v)]for v in np.unique(before[yi:yi+height,mask])}
        assert observed<=aperture_allowed,(y,observed-aperture_allowed)
        # A three-cell aperture is deliberately cut only through the measured
        # blind-end wall/window. Rooms, furnishings, stairs and controls are not
        # admitted by this whitelist. The original walking belts stay intact.
        after[yi:yi+height,mask]=ids['minecraft:air']
        after[yi-1,new]=ids['projectseele:nerv_floor_panel']
        boundary=binary_dilation(new)&~mask
        old_walk=~empty[before[yi-1]]&empty[before[yi]]&empty[before[yi+1]]
        boundary&=~old_walk
        wall_count=0
        for zi,xi in zip(*np.nonzero(boundary)):
            # Existing architecture supplies its own wall. Only formerly
            # empty adjacent space receives a matching windowed enclosure.
            if not empty[before[yi:yi+3,zi,xi]].all():continue
            if empty[before[yi-1,zi,xi]]:after[yi-1,zi,xi]=ids['projectseele:nerv_floor_panel']
            for dy in (0,2):after[yi+dy,zi,xi]=ids['projectseele:nerv_wall_panel']
            after[yi+1,zi,xi]=ids['projectseele:clear_glass'];wall_count+=1
        roof=binary_dilation(new)
        for zi,xi in zip(*np.nonzero(roof)):
            if empty[before[yi+3,zi,xi]]:
                after[yi+3,zi,xi]=ids['projectseele:nerv_strip_light[lit=true]'if mask[zi,xi]and(xi+zi)%12==0 else'projectseele:nerv_wall_panel']
        assert np.all(after[yi:yi+height,mask]==ids['minecraft:air'])
        assert not empty[after[yi-1,mask]].any()
        records.append(dict(y=y,path=nodes,clear_width=3,clear_height=height,new_floor_cells=int(new.sum()),new_glazed_side_cells=wall_count,
                            removed_blind_end_material=Counter(names[int(v)]for v in before[yi:yi+height,mask].ravel()if not empty[int(v)])))
    tags=dict(iter_block_entities(world,'projectseele:geofront',lo,hi))
    for (x,y,z),tag in tags.items():assert before[y-lo[1],z-lo[2],x-lo[0]]==after[y-lo[1],z-lo[2],x-lo[0]],('Original device touched',(x,y,z))
    vox.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront';p=vox.Painter(vertical_bounds=(-960,320))
    count=runs(p,lo,before,after,names,'R52_original_public_gallery_ring_closure')
    p.meta.update(root_author=True,links=records,original_devices_preserved=len(tags),playable=False)
    plan=p.save_plan(stage)
    report=dict(world_written=False,changed_cells=count,links=records,original_devices_preserved=len(tags),
                pending=['native whole ring path traversal','upper floor ring and private suite access','navigation regeneration'])
    (plan/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
    np.savez_compressed(plan/'BEFORE_AFTER.npz',origin=lo,palette=names,before=before,after=after)
    print(json.dumps(report),flush=True)
    if args.apply:
        assert not list(plan.glob('applied_*')),'Never replay an installed ring patch'
        receipt=p.apply(stage)
        actual,pal=measure(lo,hi);assert np.array_equal(np.asarray([ids[s]for s in pal],np.uint16)[actual],after)
        assert {p:t.snbt()for p,t in iter_block_entities(world,'projectseele:geofront',lo,hi)}=={p:t.snbt()for p,t in tags.items()}
        report.update(world_written=True,receipt=receipt,exact_readback=True)
        (plan/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')


if __name__=='__main__':main()
