"""Align the commissioned shared car with its measured north landing.

The source car's quarter-turn retained an east aperture. Move this aperture
within the new shared car; preserve all original control NBT and the floor.
"""
import argparse,json
import regional_voxels as vox
from query_blocks import read_box,iter_block_entities
from r52_spatial_plan import BASE


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    world=BASE/'WORLD_R52';lo=(106,-555,405);hi=(110,-549,409)
    states=read_box(world,'projectseele:geofront',lo,hi);tags=dict(iter_block_entities(world,'projectseele:geofront',lo,hi))
    vox.WORLD=world;vox.OUT=BASE/'shared_lift_door_alignment';vox.DIM='projectseele:geofront'
    p=vox.Painter(vertical_bounds=(-960,320));changes=[]
    for y in range(-554,-551):
        panel='projectseele:tv_staff_lift_band_r45' if y==-553 else 'projectseele:tv_staff_lift_panel_r45'
        for x in range(107,110):
            pos=(x,y,405);assert states[pos]==panel and pos not in tags
            changes.append((pos,'minecraft:air'))
        for z in range(406,409):
            pos=(110,y,z);assert states[pos]=='minecraft:air' and pos not in tags
            changes.append((pos,panel))
    for pos,state in changes:p.exact((*pos,*pos),states[pos],state,'R52_shared_car_north_aperture')
    p.meta.update(root_author=True,actual_landing_side='north',native_car_at=[108,-554,407],
                  original_car_panel_and_controls_preserved=True,retired_source_aperture='east')
    folder=p.save_plan('shared_car_north_aperture_v2')
    report=dict(world_written=False,changed_cells=len(changes),playable=False,pending=['native all-stop door interlock and ride'])
    (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
    if args.apply:
        assert not list(folder.glob('applied_*'))
        receipt=p.apply('shared_car_north_aperture_v2')
        assert {q:t.snbt()for q,t in iter_block_entities(world,'projectseele:geofront',lo,hi)}=={q:t.snbt()for q,t in tags.items()}
        actual=read_box(world,'projectseele:geofront',lo,hi)
        assert all(actual[q]==s for q,s in changes)
        report.update(world_written=True,receipt=receipt,exact_control_nbt_preserved=True)
        (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps(report))


if __name__=='__main__':main()
