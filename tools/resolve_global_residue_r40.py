"""Retire measured isolated soil; support the two remaining detached service fixtures."""
import argparse,json,gzip
from pathlib import Path
import regional_voxels as v
from measure_world_r40 import MeasuredWorld,WORLD,ROOT
from query_blocks import AIR
OUT=ROOT/'artifacts/world_combat_r40/residue_repairs'

def main(apply=False):
    v.WORLD=WORLD;v.OUT=OUT;p=v.Painter();scan=ROOT/'artifacts/world_combat_r40/global_components'
    with gzip.open(scan/'isolated_soil_points.json.gz','rt',encoding='utf8') as f:rows=json.load(f)
    w=MeasuredWorld()
    for r in rows:w.around(r['pos'],1)
    w.box((6244,76,-6133),(6244,83,-6133));w.box((28,-464,481),(30,-455,485));w.box((-375,-465,718),(-331,-459,741));w.load()
    for r in rows:
        q=tuple(r['pos']);old=w.block(q)
        if old!=r['state']:raise RuntimeError(('Residue changed since frozen global scan',q,old,r['state']))
        p.match((*q,*q),old,'minecraft:air','r40/global/isolated_soil')
    for y in (77,78,79):
        q=6244,y,-6133;assert w.block(q) in AIR
        p.match((*q,*q),w.block(q),'projectseele:nerv_machine_edge','r40/global/un_service_lamp_mast')
    # The map is three cells wide along Z. Its old rods were six cells apart
    # and did not meet the model; mount to its actual two upper corners.
    rods=[]
    for z in (482,484):
        for y in range(-462,-456):
            q=29,y,z;old=w.block(q)
            rod='minecraft:iron_bars[east=false,north=false,south=false,waterlogged=false,west=false]'
            if old!=rod and old not in AIR:raise RuntimeError(('Board suspension obstructed',q,old))
            if old!=rod:p.match((*q,*q),old,rod,'r40/global/hq_map_ceiling_hangers')
            rods.append(q)
        assert w.get(29,-456,z)=='minecraft:light_gray_concrete'
    # Native photos showed the new arrival strips as one-metre-thick blocks.
    # Keep their layout, replacing only those R40 lamp cells with thin fixtures.
    slim=[]
    for x in range(-375,-330):
        for z in range(718,742):
            q=x,-460,z
            if w.block(q)=='projectseele:nerv_strip_light':
                p.match((*q,*q),w.block(q),'projectseele:nerv_ceiling_light[hanging=true,lit=true]','r40/arrival/slim_fluorescent');slim.append(q)
    decisions=[]
    for r in json.loads((scan/'contact_classification.json').read_text())['groups']:
        if r['kind']!='isolated_structure':continue
        lo=tuple(r['lo']);states=set(r['states'])
        if lo in [(-110,-62,150),(139,-62,128),(120,-61,291),(144,-62,302)]:why='Preserve registered retractable skyscraper cargo/identity marker'
        elif lo==(19,-443,313):why='Preserve original command-room MAGI display and luminous glazing'
        elif lo in [(1407,84,362),(1407,84,502),(1427,74,370),(1427,74,510)]:why='Preserve harbour crane and suspended hook; support is modelled machinery'
        elif states=={'minecraft:structure_void'}:why='Preserve noncolliding construction receipt'
        elif lo==(6244,80,-6133):why='Restore missing mast to measured platform floor'
        elif lo==(29,-464,483):why='Fit ceiling hangers to the actual three-cell sign width'
        else:raise RuntimeError(('Unclassified structural component',r))
        decisions.append(dict(lo=r['lo'],hi=r['hi'],cells=r['cells'],decision=why))
    p.meta.update(global_scan_full_chunks=60261,removed_soil=len(rows),architectural_decisions=decisions,sign_rods=rods,slim_arrival_lights=slim,scope='Global frozen baseline scanned; every edit remeasured against current R40, no removal of model-supported machinery')
    p.save_plan('classified_global_repairs')
    if apply:p.apply('classified_global_repairs')
    (OUT/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),encoding='utf8');print('Global residue cells',len(rows),'slim lamps',len(slim),'changes',len(p.ops))
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--apply',action='store_true');main(a.parse_args().apply)
