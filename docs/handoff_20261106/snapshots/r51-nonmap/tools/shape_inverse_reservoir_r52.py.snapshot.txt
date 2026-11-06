"""Root art correction: slope the existing corner basin inward, without moving its banks."""
import argparse, json, msvcrt
import numpy as np
import regional_voxels as vox
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure
from prepare_continuous_upright_civil_r52 import cuboids
from extend_world_depth_r52 import acquire_world_lock
from query_blocks import iter_block_entities


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    out=BASE/'final_map_audit/inverse_reservoir';stage='existing_corner_basin_inverted_faces'
    assert not list((out/stage).glob('applied_*')), 'Already applied'
    lo=(-300,-509,211);hi=(-1,-474,509)
    before,names=measure(lo,hi)
    for state in ('minecraft:stone','minecraft:black_concrete','projectseele:nerv_strip_light[lit=true]'):
        if state not in names:names.append(state)
    ids={s:i for i,s in enumerate(names)};after=before.copy()
    yy,zz,xx=np.ogrid[lo[1]:hi[1]+1,lo[2]:hi[2]+1,lo[0]:hi[0]+1]
    u=xx+zz;v=xx-zz
    # Keep all eight previously verified waterline/corner relationships.
    # Only the below-water interior profile changes; the surrounding walk,
    # pyramid, roads, shoreline and separate natural lake are fixed.
    fraction=np.clip(np.minimum(np.minimum((u-25)/185,(395-u)/185),
                      np.minimum((v+620)/110,(-400-v)/110)),0,1)
    floor=-473-np.maximum(1,np.floor(36*fraction)).astype(int)
    water=np.isin(before,[i for i,s in enumerate(names) if s.split('[')[0]=='minecraft:water'])
    fill=water & (yy<=floor)
    after[fill]=ids['minecraft:stone']
    skin=fill & (yy>=floor-1)
    after[skin]=ids['minecraft:black_concrete']
    # Recessed, spaced lamps follow one contour instead of illuminating the
    # whole water surface. They remain backed by solid lining.
    lamps=fill & (yy==floor) & (fraction>=.30) & (fraction<=.315) & ((u+v)%8==0)
    after[lamps]=ids['projectseele:nerv_strip_light[lit=true]']
    assert np.all(water[before!=after]), 'Only existing basin water may be replaced'
    tags=dict(iter_block_entities(BASE/'WORLD_R52','projectseele:geofront',lo,hi))
    for (x,y,z) in tags:assert before[y-lo[1],z-lo[2],x-lo[0]]==after[y-lo[1],z-lo[2],x-lo[0]]
    vox.WORLD=BASE/'WORLD_R52';vox.OUT=out;vox.DIM='projectseele:geofront'
    painter=vox.Painter(vertical_bounds=(-960,320));n=cuboids(painter,lo,before,after,names,'R52_TV_inverse_reservoir_faces')
    painter.meta.update(root_author=True,shoreline_unchanged=True,pyramid_volume_unchanged=True,
        waterline=-473,lowest_floor=-509,original_reference='TV GeoFront exterior, inward sloping geometric reservoir',
        native_art_review_pending=True)
    folder=painter.save_plan(stage)
    report=dict(world_written=False,changed_cells=n,existing_water_only=True,lamps=int(lamps.sum()),
                protected_devices=len(tags),waterline_and_one_corner_relationship_unchanged=True,native_art_accepted=False)
    if args.apply:
        lock=acquire_world_lock()
        try:report.update(world_written=True,receipt=painter.apply(stage,session_lock=lock))
        finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
    (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
