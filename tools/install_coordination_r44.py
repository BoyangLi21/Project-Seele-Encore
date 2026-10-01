"""Measured annex equipment for the original dossier; the accepted command room is untouched."""
from pathlib import Path
import argparse,copy,json
import nbtlib
import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
OUT=ROOT/'artifacts/rebuild_r44/city_coordination/equipment'

def main(apply=False):
    if apply:
        from release_combat_r36 import guard
        guard()
    OUT.mkdir(parents=True,exist_ok=True);w=MeasuredWorld(WORLD);w.box((34,-408,388),(42,-402,395));w.load()
    tags=dict(iter_block_entities(WORLD,v.DIM,(34,-408,388),(42,-402,395)))
    v.WORLD=WORLD;v.OUT=OUT;p=v.Painter()
    for x in range(36,41):
        for z in (391,392):
            assert w.block((x,-407,z))=='projectseele:nerv_floor_panel',(x,z,'floor')
            assert w.block((x,-406,z))=='minecraft:air' and w.block((x,-405,z))=='minecraft:air',(x,z,'clearance')
    cells={
        (36,-405,393):'projectseele:nerv_grid_switch[face=wall,facing=north,powered=true]',
        (40,-405,393):'projectseele:nerv_grid_switch[face=wall,facing=north,powered=true]',
        (38,-405,393):'minecraft:stone_button[face=wall,facing=north,powered=false]',
        (38,-404,393):'projectseele:nerv_direction_panel[facing=north,wayfinding=true]',
        (36,-404,393):'projectseele:nerv_circuit_indicator[facing=north,lit=true]',
        (40,-404,393):'projectseele:nerv_circuit_indicator[facing=north,lit=true]',
    }
    for q,state in cells.items():
        assert w.block(q)=='minecraft:air' and q not in tags,('Equipment conflict',q,w.block(q))
        assert w.block((q[0],q[1],394))=='projectseele:nerv_wall_panel',('No back wall',q)
        p.match((*q,*q),w.block(q),state,'r44/city_coordination/annex_equipment')
    q=(38,-404,393)
    p.block_entities[q]=nbtlib.Compound(dict(id=nbtlib.String('projectseele:station_departure_board'),x=nbtlib.Int(q[0]),y=nbtlib.Int(q[1]),z=nbtlib.Int(q[2]),
        Station=nbtlib.String('電力管制'),Route=nbtlib.String('NERV · 通信管制室'),Row0=nbtlib.String('左：备用馈线　右：应急馈线'),Row1=nbtlib.String('中：隔离／复测　远山值班'),Row2=nbtlib.String('复测前请确认应急馈线'),Wayfinding=nbtlib.Byte(1)))
    p.meta.update(scope='r04/pyramid/407/21 communications annex, real personnel operation and two independent levers',
                  source='TV5–6 grid mobilisation concept; original dossier, engineer and two-feed test are clearly project-original',
                  occupied_public_floor=False,validation='Native operator navigation, switch cycle, decisions, cancel and save/reload pending')
    p.save_plan('coordination_annex')
    config=dict(version=1,dimension=v.DIM,reserve=[36,-405,393],emergency=[40,-405,393],test=[38,-405,393],operator_approach=[38,-406,392],
                visit=[-1076,119,570],passenger_access_certified=False)
    (OUT/'city_coordination_r44.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),'utf8')
    roster_path=WORLD/'nerv_staff_r15.json';roster=json.loads(roster_path.read_text('utf8'))
    liaison=dict(id='grid_liaison_r44',name='远山真纪',role='technician',skin='technician',feet=[38,-406,391],yaw=0,room='communications_annex')
    assert not any(r['id']==liaison['id'] for r in roster['stations']),'Already commissioned'
    roster['stations'].append(liaison)
    (OUT/'roster_before.json').write_bytes(roster_path.read_bytes());(OUT/'roster_after.json').write_text(json.dumps(roster,ensure_ascii=False,indent=2),'utf8')
    if apply:
        p.apply('coordination_annex');roster_path.write_bytes((OUT/'roster_after.json').read_bytes());(WORLD/'city_coordination_r44.json').write_bytes((OUT/'city_coordination_r44.json').read_bytes())
    print('Measured equipment plan:',len(cells),'cells, one independent NPC role; onsite transit remains locked pending native certification',flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--apply',action='store_true');main(a.parse_args().apply)
