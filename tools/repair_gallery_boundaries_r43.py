"""Complete measured, named gallery boundaries, preserving device openings.

The R41 rewriter omitted native moving walks from its floor vocabulary after
removing their old rails. This rebuilds the whole two-sided Dogma boundary, not
just the six reported ranges. Air never establishes the facility's purpose.
"""
from pathlib import Path
from collections import defaultdict
import argparse,json
import regional_voxels as v
from query_blocks import AIR,iter_block_entities
from measure_world_r40 import MeasuredWorld,properties
from facility_surfaces_r43 import gallery_bearing

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/repair_r43';SOURCE=ART/'source_world_backup';WORLD=ROOT/'run/saves/SEELE_FIELD_R43_REVIEW'
SIDES={(1,0):'east',(-1,0):'west',(0,1):'south',(0,-1):'north'}

def main(apply=False):
    if apply:
        from release_combat_r36 import guard
        guard()
    out=ART/'gallery_boundaries';out.mkdir(exist_ok=True);w=MeasuredWorld(SOURCE)
    w.box((-37,-571,266),(97,-562,403));w.box((86,-445,-48),(101,-436,-36));w.load()
    rails=defaultdict(set);members=[];held=[]
    def mark(q,side,why):
        old=w.block(q)
        if old.startswith('projectseele:nerv_edge_rail['):rails[q].update(k for k,x in properties(old).items() if x=='true')
        elif old not in AIR:
            held.append(dict(position=q,before=old,reason=why));return
        rails[q].add(side);members.append(dict(position=q,side=side,source=why))
    for x in range(-35,96):
        for z in range(268,401):
            if not gallery_bearing(w.get(x,-567,z)):continue
            if w.get(x,-566,z) not in AIR and not w.get(x,-566,z).startswith('projectseele:nerv_edge_rail['):continue
            for (dx,dz),side in SIDES.items():
                if w.get(x+dx,-567,z+dz) in AIR and w.get(x+dx,-566,z+dz) in AIR:
                    mark((x,-566,z),side,'Dogma named gallery bearing boundary')
    # The south edge ends one cell before the measured station-foyer jamb.
    # It leads into an actual lower void, not a lift/plug/rail operating port.
    assert w.get(90,-443,-43)=='projectseele:nerv_floor_panel' and w.get(90,-443,-42) in AIR
    mark((90,-442,-43),'south','Hangar station foyer south corner')
    changes={}
    for q,sides in rails.items():
        state='projectseele:nerv_edge_rail['+','.join(k+'='+str(k in sides).lower() for k in ('east','north','south','west'))+']'
        if state!=w.block(q):changes[q]=state
    tags=dict(iter_block_entities(SOURCE,v.DIM,(-37,-571,266),(97,-562,403)))
    tags.update(iter_block_entities(SOURCE,v.DIM,(86,-445,-48),(101,-436,-36)))
    assert not set(changes)&set(tags),'Full block-entity NBT must not be removed'
    v.WORLD=WORLD;v.OUT=out;p=v.Painter()
    for q,state in sorted(changes.items()):p.match((*q,*q),w.block(q),state,'r43/measured_gallery_boundary')
    p.meta.update(source=str(SOURCE),bounds=[[-35,-567,268],[95,-565,400]],cells=len(changes),held=held,
        first_error='R41 removed old rails but excluded mtr:escalator_step from gallery_floor',
        generator_fixed='repair_dogma_and_new_edges_r41.py uses facility_surfaces_r43.gallery_bearing',
        device_exclusions=['All EVA plug boarding ports','All lift thresholds/cage swept volumes','Lilith, cross and LCL lake'],
        status='PLAN: static and native/visual/lifecycle checks required')
    p.save_plan('complete_bearing_edges');(out/'members.json').write_text(json.dumps(members,ensure_ascii=False,indent=2),'utf8')
    if apply:
        p.apply('complete_bearing_edges')
        file=WORLD/'regional_states.json';states=set(json.loads(file.read_text('utf8')));states.update(changes.values());file.write_text(json.dumps(sorted(states)),'utf8')
    print('Named boundary cells changed',len(changes),'held',len(held),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');main(p.parse_args().apply)
