"""Extend the retained surface lift to the translated original HQ landing.

The original upper car, street pavilion and controller remain in place.
Only the lower controller and its existing selector link change elevation.
"""
import argparse,copy,json,msvcrt
import nbtlib
import numpy as np
import regional_voxels as vox
from r52_spatial_plan import BASE,PYRAMID
from survey_r52_original_complex import measure
from query_blocks import iter_block_entities,read_box
from prepare_terminal_move_r52 import runs
from prepare_pyramid_move_r52 import encoded
from facility_frame_nbt_r52 import block_entity_in_frame
from extend_world_depth_r52 import acquire_world_lock
from apply_s20_approved_semantic_repairs import atomic_replace

WORLD=BASE/'WORLD_R52'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    world=WORLD;lo=(126,-537,269);hi=(134,-437,277)
    actual,palette=measure(lo,hi)
    source=np.load(BASE/'survey/headquarters_and_original_station.npz');o=source['origin'];sp=list(map(str,source['palette']))
    names=list(dict.fromkeys(palette+sp));ids={s:i for i,s in enumerate(names)}
    before=np.asarray([ids[s] for s in palette],np.uint16)[actual];after=before.copy()
    wall=ids['projectseele:nerv_structural_panel'];air=ids['minecraft:air']
    after[:]=wall
    # Nine-wide external shaft, original seven-wide native cage clearance.
    # The closed bottom slab is below the lowest car floor, never in its sweep.
    after[1:,1:-1,1:-1]=air
    for y in range(-443,-436):
        row=source['states'][y-o[1],269-o[2]:278-o[2],126-o[0]]
        after[y-93-lo[1],:,0]=np.asarray([ids[s] for s in sp],np.uint16)[row]
    # Existing lower landing is closed while the one original car is upstairs.
    assert np.all(after[-535-lo[1]:-532-lo[1],2:7,0]==ids['minecraft:gray_stained_glass'])
    old_controller=(130,-442,269);new_controller=(130,-535,269)
    current=dict(iter_block_entities(world,'projectseele:geofront',lo,hi))
    assert set(current)=={old_controller},('Unexpected shaft device',list(current))
    original=current[old_controller];assert str(original['id'])=='movingelevators:elevator_tile'
    references={old_controller:new_controller}
    controller=block_entity_in_frame(original,PYRAMID,reference_positions=references)
    after[new_controller[1]-lo[1],0,4]=ids['movingelevators:elevator_block[facing=south]']
    # The preserved upper selector links to the old lower controller. Update
    # this complete typed NBT rather than replace the existing car or controls.
    upper=dict(iter_block_entities(world,'projectseele:geofront',(126,74,269),(134,81,277)))
    button_pos=(130,76,270);button=copy.deepcopy(upper[button_pos])
    assert int(button['data']['controllerY'])==-442
    button['data']['controllerY']=nbtlib.Int(-535)
    # The already translated gallery and its original call button are the
    # actual personnel endpoint; no extra corridor or station is introduced.
    landing=read_box(world,'projectseele:geofront',(120,-536,270),(125,-530,276))
    for x in range(120,126):
        assert landing[x,-536,273]=='projectseele:nerv_floor_panel'
        assert all(landing[x,y,273]=='minecraft:air' for y in (-535,-534,-533))
    call=(125,-534,270)
    assert landing[call]=='minecraft:polished_blackstone_button[face=wall,facing=west,powered=false]',landing[call]
    caps_path=world/'dimensions/projectseele/geofront/data/capabilities.dat';caps=nbtlib.load(caps_path)
    group=caps['data']['movingelevators:elevator_groups']['130;269']['group']
    assert not bool(group['isMoving']) and list(map(int,group['floors']))==[-442,75]
    assert [bool(t['isCageAvailable']) for t in group['floorData']]==[False,True]
    group['floors']=nbtlib.IntArray([-535,75])
    vox.WORLD=world;vox.OUT=BASE/'public_lift_extension';vox.DIM='projectseele:geofront'
    p=vox.Painter(vertical_bounds=(-960,320));count=runs(p,lo,before,after,names,'R52_public_lift_lower_extension')
    p.block_entities[new_controller]=controller
    p.update_block_entity(button_pos,'movingelevators:button_block',upper[button_pos],button,'R52_preserve_car_relink_lower_controller')
    p.meta.update(root_author=True,original_upper_car_unchanged=True,original_lift_id='s20-surface-transit-v2',
                  actual_floors=[-535,75],original_lower_call=list(call),playable=False)
    folder=p.save_plan('retained_public_lift_lower_extension')
    report=dict(world_written=False,playable=False,changed_cells=count,controller_before=old_controller,
                controller_after=new_controller,original_car_at=[130,75,273],actual_floors=[-535,75],
                retained_upper_devices=len(upper),pending=['complete seven-lift manifest','native ride and door interlocks'])
    (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)
    if not args.apply:return
    assert not list(folder.glob('applied_*')),'Applied component must not be replayed'
    lock=acquire_world_lock();raw=caps_path.read_bytes();geometry=None
    try:
        (folder/'capabilities_before.dat').write_bytes(raw)
        geometry=p.apply('retained_public_lift_lower_extension',session_lock=lock)
        assert caps_path.read_bytes()==raw;atomic_replace(caps_path,encoded(caps))
        readback=dict(iter_block_entities(world,'projectseele:geofront',(126,-537,269),(134,81,277)))
        assert old_controller not in readback and new_controller in readback
        assert int(readback[button_pos]['data']['controllerY'])==-535
        for pos,tag in upper.items():
            if pos!=button_pos:assert readback[pos].snbt()==tag.snbt(),('Upper device changed',pos)
        final,_pal=measure(lo,hi)
        final=np.asarray([ids[s] for s in _pal],np.uint16)[final]
        assert np.array_equal(final,after),'Shaft readback differs from exact plan'
        report.update(world_written=True,receipt=geometry,whole_shaft_exact_readback=True)
        (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
    except BaseException:
        atomic_replace(caps_path,raw)
        if geometry is not None:
            app=list(folder.glob('applied_*'));assert len(app)==1
            for f in (app[0]/'before').glob('r.*.mca'):atomic_replace(world/'dimensions/projectseele/geofront/region'/f.name,f.read_bytes())
            (app[0]/'ROLLED_BACK.json').write_text('{"reason":"public lift metadata/readback failed"}','utf8')
        raise
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
