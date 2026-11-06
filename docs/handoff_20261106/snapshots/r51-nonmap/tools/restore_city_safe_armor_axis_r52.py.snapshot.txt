"""Restore the original city-safe roof aperture after checking moving cargo ownership.

Only the exact recent column delta is reversed. Other edits in its same region
file stay in place; the actual relocated Lilith remains the terminal target.
"""
import copy,gzip,json,msvcrt
import nbtlib
import numpy as np
import regional_voxels as vox
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure
from query_blocks import iter_block_entities
from prepare_terminal_move_r52 import runs
from extend_world_depth_r52 import acquire_world_lock
from apply_s20_approved_semantic_repairs import atomic_replace

def main():
    world=BASE/'WORLD_R52';source=BASE/'armor_column_alignment/complete_owned_column_z_minus7';out=BASE/'armor_column_alignment';stage='restore_original_city_safe_aperture'
    assert not list((out/stage).glob('applied_*'));assert json.loads((source/'PLAN.json').read_text())['world_written']
    lo=(26,20,344);hi=(40,84,360);a,names=measure(lo,hi)
    with gzip.open(source/'ops.json.gz','rt',encoding='utf8')as f:ops=json.load(f)
    for op in ops:
        assert op['mode']=='exact'and len(op['extra'])==1
        if op['extra'][0]not in names:names.append(op['extra'][0])
    ids={s:i for i,s in enumerate(names)};b=a.copy()
    for op in reversed(ops):
        x,y,z,X,Y,Z=op['box'];sl=np.s_[y-lo[1]:Y-lo[1]+1,z-lo[2]:Z-lo[2]+1,x-lo[0]:X-lo[0]+1]
        assert np.all(b[sl]==ids[op['state']]),op['box'];b[sl]=ids[op['extra'][0]]
    tags=dict(iter_block_entities(world,'projectseele:geofront',lo,hi));assert set(tags)=={(37,81,344)}
    barrel=copy.deepcopy(tags[(37,81,344)]);barrel['z']=nbtlib.Int(345)
    vox.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront';p=vox.Painter(vertical_bounds=(-960,320));n=runs(p,lo,a,b,names,'R52_restore_original_city_safe_armour_projection')
    p.block_entities[37,81,345]=barrel;p.meta.update(root_author=True,reason='Original raised tower centre [30,80,340] owns the rejected new aperture cells; preserve the entire city moving component')
    folder=p.save_plan(stage)
    meta=json.loads((source/'before_metadata.json').read_text('utf8'));assert meta['surface']==[30.5,80,355.5]
    meta['terminal_pos']=[30.5,-880,348.5];meta['r52_preserved_city_safe_roof_aperture']=True
    encoded=(json.dumps(meta,ensure_ascii=False,indent=2)+'\n').encode('utf8');lock=acquire_world_lock()
    try:
        receipt=p.apply(stage,session_lock=lock);actual,pal=measure(lo,hi);assert np.array_equal(np.asarray([ids[s]for s in pal])[actual],b)
        actual_tags=dict(iter_block_entities(world,vox.DIM,lo,hi));assert set(actual_tags)=={(37,81,345)}and actual_tags[37,81,345].snbt()==barrel.snbt()
        atomic_replace(world/'nerv_armor_column_r50.json',encoded);assert(world/'nerv_armor_column_r50.json').read_bytes()==encoded
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
    report=dict(world_written=True,changed_cells=n,exact_delta_reversed=True,other_region_components_untouched=True,original_barrel_and_city_owned_floor_restored=True,surface=[30.5,80,355.5],actual_lilith=[30.5,-880,348.5],roof_only_breach_opens_geofront=True,application=receipt,native_acceptance=False)
    (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)

if __name__=='__main__':main()
