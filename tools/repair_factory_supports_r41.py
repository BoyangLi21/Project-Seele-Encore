"""Reconnect surveyed plant supports without reopening retired corridors."""
from pathlib import Path
import argparse,json
import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/spatial_repair_r41';WORLD=ROOT/'run/saves/SEELE_FIELD_R41_REVIEW'
GROUND={'minecraft:grass_block','minecraft:dirt','minecraft:stone','minecraft:deepslate','minecraft:deepslate_bricks','minecraft:gravel','minecraft:tuff'}


def main(apply=False):
    if apply:
        from release_combat_r36 import guard
        guard()
    w=MeasuredWorld(WORLD if apply else ART/'source_world_backup')
    boxes=[]
    for x in (-34,94):
        for z in (-192,-172,-152):boxes.append(((x-2,-500,z-2),(x+2,-465,z+3)))
    boxes.append(((111,-473,-84),(115,-384,-80)))
    for lo,hi in boxes:w.box(lo,hi)
    w.load();v.WORLD=WORLD;v.OUT=ART/'supports';p=v.Painter();changes={};piers=[]
    def put(q,new,why,allowed):
        old=w.block(q)
        if old==new:return
        assert old is not None and old.partition('[')[0] in allowed,(q,old,why)
        changes[tuple(q)]=(new,why)
    for x in (-34,94):
        for z in (-192,-172,-152):
            footing=[]
            for X in ([x-1,x] if x<0 else [x,x+1]):
                for Z in (z,z+1):
                    found=None
                    for y in range(-468,-501,-1):
                        old=w.get(X,y,Z)
                        if old in AIR:continue
                        assert old.partition('[')[0] in GROUND,(X,y,Z,old)
                        found=y;break
                    assert found is not None,(X,Z)
                    for y in range(found,-466):
                        put((X,y,Z),'projectseele:nerv_machine_panel' if y<=found+1 else 'projectseele:nerv_structural_panel','transfer_pier/measured_terrain_bearing',AIR|GROUND|{'projectseele:nerv_structural_panel'})
                    footing.append([X,found,Z])
            piers.append(dict(original=[x,-467,z],terrain_bearings=footing))
    # A broad historical retirement mask cut the old column below the gallery.
    # Restore its lower load path only. The occupied gallery remains clear.
    for y in range(-443,-436):put((112,y,-82),'projectseele:nerv_structural_panel','observer_support/lower_cut_reconnection',AIR)
    # Carry the upper segment around the active -394 corridor, through a beam
    # above its headroom and a pier outside the retained east wall (X113).
    for y in range(-468,-386):put((114,y,-82),'projectseele:nerv_structural_panel','observer_support/external_pier',AIR|GROUND|{'projectseele:nerv_structural_panel','projectseele:nerv_wall_panel','projectseele:nerv_floor_panel'})
    for x in range(112,115):
        for y in (-388,-387):put((x,y,-82),'projectseele:nerv_machine_edge','observer_support/above_corridor_transfer_beam',AIR|{'projectseele:nerv_structural_panel','projectseele:nerv_wall_panel','projectseele:nerv_floor_panel'})
    tags={}
    for lo,hi in boxes:tags.update(iter_block_entities(w.world,v.DIM,lo,hi))
    assert not set(tags)&set(changes),'Support plan intersects a device'
    for q,(after,why) in changes.items():p.match((*q,*q),w.block(q),after,'r41/'+why)
    p.meta.update(piers=piers,retained_gallery_clearance=[112,-394,-82,112,-389,-82],external_pier_x=114,
                  basis='Actual surveyed terrain, original R20 load-bearing support purpose, exact existing gallery envelope; no retired passage rebuilt')
    p.save_plan('terrain_bearings_and_observer_load_path')
    if apply:p.apply('terrain_bearings_and_observer_load_path')
    (ART/'supports/contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),'utf8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');main(p.parse_args().apply)
