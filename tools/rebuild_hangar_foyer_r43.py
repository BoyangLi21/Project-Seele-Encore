"""Replace the obsolete dogleg partition with one closed lift/station foyer.

The north lift threshold, call button, shaft, rail platforms and their swept
volumes remain outside this component edit. Existing lower decking is covered
at the current hall's floor level; its south perimeter gains a supported wall.
"""
from pathlib import Path
import argparse,json
import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/repair_r43';WORLD=ROOT/'run/saves/SEELE_FIELD_R43_REVIEW'

def main(apply=False):
    if apply:
        from release_combat_r36 import guard
        guard()
    out=ART/'hangar_foyer';out.mkdir(exist_ok=True)
    assert not list(out.glob('continuous_foyer/applied_*/receipt.json')),'Revise the component instead of reapplying it'
    w=MeasuredWorld(WORLD);w.box((88,-446,-49),(106,-436,-32));w.load();changes={}
    tags=dict(iter_block_entities(WORLD,v.DIM,(88,-446,-49),(106,-436,-32)))
    def put(q,state,reason,allowed):
        before=w.block(q);assert before is not None,(q,'unmeasured');assert q not in tags,(q,'preserve complete NBT')
        if before==state:return
        assert before.partition('[')[0] in allowed,(q,before,reason)
        if q in changes:assert changes[q][0]==state,(q,'conflicting component operations')
        changes[q]=(state,reason)
    panels={'projectseele:nerv_wall_panel','projectseele:clear_glass','projectseele:nerv_edge_rail'}
    retired={(91,z) for z in range(-45,-41)}|{(92,-42)}|{(x,-43) for x in range(93,98)}|{(97,z) for z in range(-42,-34)}
    retired.add((90,-43))
    for x,z in retired:
        for y in range(-442,-437):
            if (w.get(x,y,z) or '').partition('[')[0] in panels:
                put((x,y,z),'minecraft:air','retire complete dogleg glazed partition',panels)
    for x in range(90,98):
        for z in range(-43,-33):
            put((x,-443,z),'projectseele:nerv_floor_panel','continuous foyer finished floor',AIR|{'projectseele:nerv_floor_panel'})
            if w.get(x,-444,z) in AIR:
                put((x,-444,z),'projectseele:nerv_structural_panel','deck bearing tied to existing perimeter',AIR)
    for x in range(90,98):
        for z in range(-47,-33):
            # A single continuous ceiling replaces the retired partition caps,
            # including its two rows north of the previously sunken deck.
            q=(x,-438,z);changes.pop(q,None)
            put(q,'projectseele:nerv_wall_panel','continuous enclosed foyer ceiling',AIR|panels)
    for x in range(90,98):
        for y in range(-442,-438):
            state='projectseele:nerv_wall_panel' if y==-442 else 'projectseele:clear_glass'
            put((x,y,-34),state,'closed south perimeter joined to station envelope',AIR|panels)
    # These physical interfaces are explicit negative edit masks.
    preserved=[(90,-441,-47)]+[(x,y,z) for x in range(90,97) for y in range(-444,-437) for z in range(-52,-47)]
    assert not set(preserved)&set(changes),'Lift/call interface entered edit mask'
    v.WORLD=WORLD;v.OUT=out;p=v.Painter()
    for q,(after,why) in sorted(changes.items()):p.match((*q,*q),w.block(q),after,'r43/hangar_foyer/'+why)
    p.meta.update(component='EVA hangar station / west hall / lift foyer',retired_component='Interior dogleg glazed wall and its full header',
        intended_flow='North native lift doors -> continuous supported foyer -> east existing station hall',
        new_footprint=[[90,-444,-45],[97,-438,-34]],negative_edit_mask=preserved,
        reference='JR official station threshold/foyer continuity, contemporary functional reference; original NERV industrial finish, not a claimed TV 1:1 set',
        cells=len(changes),validation='Pending complete port traversal, sign regeneration, visual and restart checks')
    p.save_plan('continuous_foyer')
    if apply:p.apply('continuous_foyer')
    print('Whole foyer component cells',len(changes),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');main(p.parse_args().apply)
