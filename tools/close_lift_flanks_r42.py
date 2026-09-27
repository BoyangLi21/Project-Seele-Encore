"""Seal a measured side bypass of the upper hangar lift's closed landing door."""
from pathlib import Path
import argparse
import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities,AIR

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R42_REVIEW';OUT=ROOT/'artifacts/rebuild_r42/lift_vestibules'


def main(apply=False):
    w=MeasuredWorld(WORLD);w.box((88,-373,-59),(98,-363,-48));w.load()
    tags=dict(iter_block_entities(WORLD,v.DIM,(88,-373,-59),(98,-363,-48)))
    v.WORLD=WORLD;v.OUT=OUT;p=v.Painter()
    # Native five-wide car: x91..95,z-54..-50. The closed outer door is
    # z-56. The one-cell vestibule at z-55 needs its own fixed side cheeks.
    for x in (90,96):
        for y in (-369,-368,-367):
            q=(x,y,-55);before=w.block(q)
            assert q not in tags and before in AIR,(q,before,'Do not replace hardware or authored work')
            p.match((*q,*q),before,'projectseele:clear_glass','r42/upper_gallery/fixed_vestibule_cheek')
    for x in range(90,97):
        q=(x,-366,-55);before=w.block(q)
        assert q not in tags and before in AIR|{'projectseele:nerv_structural_panel','projectseele:nerv_shaft_panel'},(q,before)
        if before in AIR:p.match((*q,*q),before,'projectseele:nerv_structural_panel','r42/upper_gallery/vestibule_header')
    for x in (92,93,94):
        q=(x,-370,-58);before=w.block(q)
        assert q not in tags and before=='minecraft:smooth_quartz_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]',(q,before)
    p.meta.update(car_prism=[91,-371,-54,95,-366,-50],outer_door_z=-56,vestibule_z=-55,
                  finding='A public gallery edge at x90 could enter behind the closed door at z-56 through the missing z-55 side cheeks',
                  evidence='global_envelopes/runtime_interface_delta.json and current full-height measured slices',
                  protected=['All native controllers and door cells','Moving cage prism','Existing supported sill at y=-371','Existing three-wide north-facing quartz stairs'],
                  tests=['Closed-door lateral entry from gallery must be blocked','Pause on sill with car present must retain floor','Enter and exit via the intended north aperture with normal 0.6-block step height'],
                  walk_nodes=[dict(id='r42/upper_gallery/stepped_threshold',path=[[93.5,-370,-56.5],[93.5,-369.5,-57.25],[93.5,-369,-59.5]])])
    p.save_plan('upper_gallery_interlock_envelope')
    if apply:
        from release_combat_r36 import guard
        guard();p.apply('upper_gallery_interlock_envelope')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');main(ap.parse_args().apply)
