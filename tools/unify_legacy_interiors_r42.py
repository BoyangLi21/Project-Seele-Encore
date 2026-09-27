"""Replace imported mineral ornament with the established NERV metal palette.

Full cubes only: preserve geometry, command-room layout, furniture, buttons,
block entities and every measured native lift's horizontal capture footprint.
"""
from pathlib import Path
from collections import Counter
import argparse,json
import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R42_REVIEW'
OUT=ROOT/'artifacts/rebuild_r42/interior_palette'
AREAS=[('original_command_hall',(-25,-436,248),(85,-394,357)),
       ('upper_command_meeting',(0,-336,300),(60,-308,348)),
       ('hangar_observation',(-55,-398,-287),(125,-360,-18))]
PALETTE={'minecraft:chiseled_deepslate':'projectseele:nerv_structural_panel',
         'minecraft:reinforced_deepslate':'projectseele:nerv_structural_panel',
         'minecraft:deepslate[axis=y]':'projectseele:nerv_wall_panel',
         'minecraft:deepslate[axis=x]':'projectseele:nerv_wall_panel',
         'minecraft:deepslate[axis=z]':'projectseele:nerv_wall_panel'}


def main(apply=False):
    assert not list(OUT.glob('inherited_room_materials/applied_*/receipt.json')),'Material pass already applied'
    w=MeasuredWorld(WORLD);tags={}
    for _,lo,hi in AREAS:w.box(lo,hi);tags.update(iter_block_entities(WORLD,v.DIM,lo,hi))
    w.load();v.WORLD=WORLD;v.OUT=OUT;p=v.Painter();counts=Counter();hold=0
    controllers=[q for q,t in tags.items() if str(t.get('id','')).startswith('movingelevators:')]
    for name,lo,hi in AREAS:
        for x in range(lo[0],hi[0]+1):
            for z in range(lo[2],hi[2]+1):
                in_lift=any(abs(x-q[0])<=7 and abs(z-q[2])<=7 for q in controllers)
                for y in range(lo[1],hi[1]+1):
                    q=(x,y,z);old=w.block(q)
                    if old not in PALETTE:continue
                    if in_lift or q in tags:hold+=1;continue
                    p.match((*q,*q),old,PALETTE[old],'r42/material/'+name);counts[name]+=1
    p.meta.update(areas=AREAS,materials=PALETTE,counts=dict(counts),protected_lift_columns=controllers,held=hold,
                  intent='1995 TV industrial panels rather than carved deepslate motifs; existing full-cube walls remain in exactly the same positions',
                  preserved=['Original command-room layout','All controls and block entities','Lift capture columns','All stairs/slabs/doors','Room and corridor openings'])
    p.save_plan('inherited_room_materials');OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),'utf8');print(dict(counts),'held',hold)
    if apply:
        from release_combat_r36 import guard
        guard();p.apply('inherited_room_materials')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');main(ap.parse_args().apply)
