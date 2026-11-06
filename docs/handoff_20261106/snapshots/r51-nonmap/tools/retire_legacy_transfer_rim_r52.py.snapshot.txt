"""Retire the measured obsolete upper rim while retaining laboratory and lift access."""
import argparse,gzip,json,msvcrt
import numpy as np
import regional_voxels as vox
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure
from query_blocks import iter_block_entities
from prepare_continuous_upright_civil_r52 import cuboids
from extend_world_depth_r52 import acquire_world_lock


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    out=BASE/'final_map_audit/old_transfer_rim';stage='retired_exposed_rim_retained_lab_and_surface_columns'
    assert not list((out/stage).glob('applied_*')), 'Never replay'
    lo=(-56,-485,-151);hi=(111,-345,15)
    before,names=measure(lo,hi)
    for s in ('minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]','projectseele:nerv_shaft_panel'):
        if s not in names:names.append(s)
    ids={s:i for i,s in enumerate(names)};after=before.copy()
    yy,zz,xx=np.ogrid[lo[1]:hi[1]+1,lo[2]:hi[2]+1,lo[0]:hi[0]+1]
    west=(xx>=-55)&(xx<=-41)&(zz>=-150)&(zz<=14)
    north=(xx>=-40)&(xx<=110)&(zz>=-5)&(zz<=14)
    # The obsolete high retaining lip is lowered to the retained laboratory
    # landscape. Its earth slope meets the measured surrounding ground.
    west_top=-481+np.minimum(14,xx+55)
    north_top=-467-np.floor(np.maximum(0,zz+5)*8/19).astype(int)
    top=np.where(west,np.minimum(west_top,north_top),north_top)
    rim=np.broadcast_to(west|north,before.shape)
    own=np.isin(before,[i for i,s in enumerate(names)if s in ('minecraft:deepslate_bricks','minecraft:polished_deepslate')])
    edit=rim&own&(yy>=top-3)
    target=np.where(yy>top,ids['minecraft:air'],np.where(yy==top,ids['minecraft:grass_block[snowy=false]'],
                    np.where(yy>=top-3,ids['minecraft:dirt'],ids['minecraft:stone'])))
    after[edit]=np.broadcast_to(target,before.shape)[edit]
    # The old three emergency facade proxies no longer operate here. Their
    # exact original planes now form visible fixed skins of the retained
    # surface shafts, instead of invisible obsolete doors.
    facade=np.zeros(before.shape,bool)
    for cx in (-12,30,72):
        face=(xx>=cx-15)&(xx<=cx+15)&(yy>=-410)&(yy<=-346)&(zz>=-19)&(zz<=-17)
        facade |= np.broadcast_to(face,before.shape)
    assert np.all(before[facade]==ids['minecraft:barrier']), 'Old facade domain changed'
    after[facade]=ids['projectseele:nerv_shaft_panel']
    # No active gate claims the retired facade coordinates.
    for gate in json.loads((BASE/'runtime_directory/gates/ROOT_GATES.json').read_text())['gates']:
        cells=json.loads(gzip.decompress((BASE/'runtime_directory/gates'/gate['collision_steps']['cells_file']).read_bytes()))
        for row in cells[0]:
            x,y,z=row['position']
            if lo[0]<=x<=hi[0] and lo[1]<=y<=hi[1] and lo[2]<=z<=hi[2]:
                assert before[y-lo[1],z-lo[2],x-lo[0]]==after[y-lo[1],z-lo[2],x-lo[0]],('Active gate changed',gate['resource'],row)
    graph=np.load(BASE/'navigation_rebuild/combined/CURRENT_GRAPH.npz');nodes=graph['coords'][graph['kept']]
    for x,y,z in nodes:
        for fy in (y-1,y,y+1):
            if lo[0]<=x<=hi[0] and lo[1]<=fy<=hi[1] and lo[2]<=z<=hi[2]:
                assert before[fy-lo[1],z-lo[2],x-lo[0]]==after[fy-lo[1],z-lo[2],x-lo[0]],('Actual retained walking cell changed',x,fy,z)
    tags=dict(iter_block_entities(BASE/'WORLD_R52','projectseele:geofront',lo,hi))
    for x,y,z in tags:assert before[y-lo[1],z-lo[2],x-lo[0]]==after[y-lo[1],z-lo[2],x-lo[0]]
    vox.WORLD=BASE/'WORLD_R52';vox.OUT=out;vox.DIM='projectseele:geofront';paint=vox.Painter(vertical_bounds=(-960,320))
    n=cuboids(paint,lo,before,after,names,'R52_retire_old_transfer_rim_and_door_facade')
    paint.meta.update(root_author=True,retained_lab_and_east_upper_walk_unchanged=True,compact_lift_unchanged=True,
                      original_surface_columns_retained=True,native_art_review_pending=True)
    target_path=paint.save_plan(stage)
    report=dict(world_written=False,changed_cells=n,old_fixed_facade_cells=int(facade.sum()),retired_or_graded_rim_cells=int(edit.sum()),
        all_registered_walking_cells_preserved=True,active_gate_cells_preserved=True,protected_devices=len(tags),native_art_accepted=False)
    np.savez_compressed(target_path/'EXPECTED.npz',origin=lo,states=after,palette=names)
    if args.apply:
        lock=acquire_world_lock()
        try:report.update(world_written=True,receipt=paint.apply(stage,session_lock=lock))
        finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
    (target_path/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)


if __name__=='__main__':main()
