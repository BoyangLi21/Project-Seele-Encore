"""Upgrade the measured annex equipment without changing circuit identities or behaviour."""
from pathlib import Path
import argparse,copy,json
import nbtlib
import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
OUT=ROOT/'artifacts/rebuild_r44/city_coordination/industrial_controls'


def main(apply=False):
    if apply:
        from release_combat_r36 import guard
        guard()
    w=MeasuredWorld(WORLD);w.box((34,-407,390),(42,-403,395));w.load()
    tags=dict(iter_block_entities(WORLD,v.DIM,(34,-407,390),(42,-403,395)))
    v.WORLD=WORLD;v.OUT=OUT;p=v.Painter()
    for x in (36,40):
        for y,old,new in [(-405,'minecraft:lever','projectseele:nerv_grid_switch'),
                          (-404,'minecraft:redstone_lamp','projectseele:nerv_circuit_indicator')]:
            q=(x,y,393);state=w.block(q)
            assert state.split('[')[0]==old and q not in tags,('Existing control changed',q,state)
            assert w.block((x,y,394))=='projectseele:nerv_wall_panel',('Lost wall attachment',q)
            properties=state.split('[',1)[1]
            replacement=new+'['+('facing=north,' if y==-404 else '')+properties
            p.match((*q,*q),state,replacement,'r44/city_coordination/industrial_control')
    q=(38,-404,393);before=tags[q];after=copy.deepcopy(before)
    after['Station']=nbtlib.String('电力管制')
    after['Route']=nbtlib.String('NERV · 通信管制室')
    after['Row0']=nbtlib.String('左：备用馈线　右：应急馈线')
    after['Row1']=nbtlib.String('中：隔离／复测　远山值班')
    after['Row2']=nbtlib.String('复测前请确认应急馈线')
    p.update_block_entity(q,w.block(q),before,after,'r44/city_coordination/legible_panel')
    p.meta.update(scope='Existing original annex, four mounted controls and preserved full-NBT instruction board',
        function='Vanilla lever subclass retains actual use/redstone; wall indicators reflect neighbouring supply',
        reference='Original industrial interpretation; not claimed to reproduce an unseen TV control drawing',
        validated='Pending actual switch/NPC operation, restart and shader pictures')
    if apply:p.apply('industrial_controls')
    else:p.save_plan('industrial_controls')
    print('Measured control refinement: four blocks, one full-NBT board',flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');main(ap.parse_args().apply)
