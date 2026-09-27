"""Retire measured 7 m lamp posts inside the UN loading envelope; retain light."""
from pathlib import Path
import argparse
import regional_voxels as v
from measure_world_r40 import MeasuredWorld,ROOT
from query_blocks import iter_block_entities


def main(world,apply):
    world=world.resolve();assert world.parent==ROOT/'run/saves' and world.name in ('SEELE_FIELD_R40_REVIEW','SEELE_R32_AIR_REVIEW')
    v.WORLD=world;v.OUT=ROOT/'artifacts/world_combat_r40/apron_lights'/world.name
    p=v.Painter();w=MeasuredWorld(world)
    for cx in (6282,6442):w.box((cx-36,76,-6135),(cx+36,83,-6090))
    w.load();sites=[]
    for cx in (6282,6442):
        for x in range(cx-36,cx+37):
            for z in range(-6135,-6089):
                if w.get(x,83,z)=='projectseele:nerv_strip_light' and w.get(x,77,z)=='minecraft:light_gray_concrete' and all(w.get(x,y,z)=='projectseele:nerv_machine_edge' for y in range(78,83)):
                    sites.append((x,z))
    changed=0;measured_sites=[]
    for x,z in sites:
        assert w.get(x,76,z) in ('projectseele:nerv_floor_panel','minecraft:light_gray_concrete')
        if all(w.get(x,y,z)=='minecraft:air' for y in range(77,84)):continue
        measured_sites.append((x,z))
        tags=list(iter_block_entities(world,v.DIM,(x,77,z),(x,83,z)));assert not tags,tags
        for y in range(77,84):
            before=w.get(x,y,z);expected='minecraft:light_gray_concrete' if y==77 else 'projectseele:nerv_strip_light' if y==83 else 'projectseele:nerv_machine_edge'
            after='projectseele:nerv_ceiling_light[hanging=false,lit=true]' if y==77 else 'minecraft:air'
            if before==after:continue
            assert before==expected,(x,y,z,before,expected)
            p.match((x,y,z,x,y,z),before,after,'r40/un_apron/low_loading_lights');changed+=1
    p.meta.update(purpose='Measured UN01 foot convex hull intersected a prior apron lamp during pickup; convert only the existing matching pole to a low deck fixture',
                  preserved_floor_y=76,old_poles=[dict(x=x,z=z,y=[77,83]) for x,z in measured_sites])
    p.save_plan('loading_clearance')
    if apply:p.apply('loading_clearance')
    print(world,changed,flush=True)


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--world',type=Path,required=True);a.add_argument('--apply',action='store_true');args=a.parse_args();main(args.world,args.apply)
