"""Measured floor seams and edge rails, retaining full corridor/stair width."""
from pathlib import Path
from collections import defaultdict
import argparse,json
import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/spatial_repair_r41';WORLD=ROOT/'run/saves/SEELE_FIELD_R41_REVIEW'


def main(apply=False):
    rows=json.loads((ART/'native_spatial/first_results.json').read_text('utf8'))
    edges=[r['candidate'] for r in rows if r['status']=='floor_gap'];w=MeasuredWorld(WORLD)
    for r in edges:w.around(r['pos'],3)
    for y in (-434,-420,-406,-392,-378,-364):w.box((66,y-1,358),(72,y+2,364))
    for centre in (-12,30,72):w.box((centre-21,-397,-226),(centre+21,-389,-213))
    w.box((88,-445,-56),(116,-437,-42));w.box((357,70,30),(392,84,48));w.load()
    v.WORLD=WORLD;v.OUT=ART/'edge_repairs';p=v.Painter();changes={};rails=defaultdict(set);held=[]
    def state(q):return changes.get(tuple(q),(w.block(q),''))[0]
    def put(q,after,why,allowed):
        q=tuple(q);before=w.block(q)
        if before==after:return
        assert before is not None and before.partition('[')[0] in allowed,(q,before,why)
        changes[q]=(after,why)
    # These depressions are wholly inside measured wall lines. Restore their
    # floors instead of putting fences around a strip of missing paving.
    for z in range(-47,-42):put((90,-443,z),'projectseele:nerv_floor_panel','lower_lift_foyer/floor_to_existing_west_wall',AIR)
    for x in (113,114):
        for z in range(-54,-49):put((x,-443,z),'projectseele:nerv_floor_panel','station_west_foyer/floor_to_existing_glazing',AIR|{'minecraft:smooth_stone'})
    filled_edges={(91,-442,z) for z in (-47,-46)}|{(115,-442,z) for z in range(-54,-49)}|{(113,-442,-49),(114,-442,-49)}
    directions={(1,0,0):'east',(-1,0,0):'west',(0,0,1):'south',(0,0,-1):'north'}
    def rail(q,normal,why):
        q=tuple(q);before=state(q)
        if before not in AIR and not before.startswith('minecraft:light['):
            if before.startswith('projectseele:nerv_edge_rail['):
                rails[q].update(k for k in ('north','east','south','west') if k+'=true' in before)
            else:held.append(dict(pos=q,reason='Occupied guard cell; preserve fixture or existing wall',state=before,source=why));return
        rails[q].add(directions[tuple(normal)])
    for r in edges:
        if tuple(r['pos']) in filled_edges:continue
        rail(r['pos'],r['normal'],'native_confirmed_edge')
    # The same well has six layers, including layers absent from the old graph.
    for y in (-434,-420,-406,-392,-378,-364):
        for z in (361,362):
            for x,normal in [(67,(1,0,0)),(71,(-1,0,0))]:
                if state((x,y-1,z)) not in AIR:rail((x,y,z),normal,'complete_repeated_stairwell_sides')
    # Mirror the moving bridge's complete boundary, including its capsule well.
    # Runtime updates remove/recreate these rails together with the panels.
    for centre in (-12,30,72):
        for x in range(centre-19,centre+20):
            for z in range(-224,-215):
                q=x,-394,z
                if state((x,-395,z)) in AIR:continue
                for dx,dz in [(1,0),(-1,0),(0,1),(0,-1)]:
                    if state((x+dx,-395,z+dz)) in AIR:rail(q,(dx,0,dz),'complete_retractable_boarding_deck')
    for q,sides in rails.items():
        after='projectseele:nerv_edge_rail['+','.join(k+'='+str(k in sides).lower() for k in ('east','north','south','west'))+']'
        put(q,after,'supported_edge_guard',AIR|{'minecraft:light','projectseele:nerv_edge_rail'})
    # R21's access-road headroom cut through the terminal facade west of its
    # actual doorway. The new approach follows its outside pavement to the door.
    for x in range(364,379):
        for y in range(73,77):
            after='projectseele:clear_glass' if 370<=x<=377 and y>=74 else 'projectseele:nerv_structural_panel'
            put((x,y,38),after,'airport/restore_facade_below_road_cut',AIR)
    tags={}
    for cx,cz in {(q[0]//16,q[2]//16) for q in changes}:
        ys=[q[1] for q in changes if q[0]//16==cx and q[2]//16==cz]
        tags.update(iter_block_entities(WORLD,v.DIM,(cx*16,min(ys),cz*16),(cx*16+15,max(ys),cz*16+15)))
    assert not set(tags).intersection(changes),'Proposed rail/floor intersects an original block entity'
    for q,(after,why) in sorted(changes.items()):p.match((*q,*q),w.block(q),after,'r41/'+why)
    p.meta.update(native_failed_edges=len(edges),edge_rail_cells=len(rails),held=held,
                  preserved=['Native lift sweeps','Full stair widths and travel directions','Main command hall layout','Moving bridge panel ownership'],
                  airport_access_path=[[325.5,81,35.5],[385.5,73,35.5],[385.5,73,40.5]])
    p.save_plan('public_edges_and_terminal_facade')
    if apply:
        p.apply('public_edges_and_terminal_facade')
        file=WORLD/'regional_states.json';states=set(json.loads(file.read_text('utf8')));states.update(after for after,_ in changes.values());file.write_text(json.dumps(sorted(states)),'utf8')
    (ART/'edge_repairs/contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),'utf8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');main(p.parse_args().apply)
