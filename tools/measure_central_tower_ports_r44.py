"""Measure all 93 generated-tower entrance cells and fixed roof anchor masks."""
from pathlib import Path
from collections import Counter
import json
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW';OUT=ROOT/'artifacts/rebuild_r44/central_towers'

def specs():
    private={(-120,-80),(120,-80),(120,80),(80,80),(80,40)}
    all_lots=[(x,z,False) for x in range(-160,161,40) for z in range(-160,161,40)
        if not(abs(x)<=40 and abs(z)<=40) and (x,z) not in {(0,-80),(80,0),(0,80)}|private]
    all_lots.extend((x,z,True) for x in range(-200,201,40) for z in range(-200,201,40) if max(abs(x),abs(z))==200 and x!=200)
    for x,z,outer in all_lots:
        h=(x//40*31+z//40*17)%97;height=20+h%4*7 if outer else 96+h%4*8 if h%11==0 else 44+h%6*6
        yield x+30,z+220,height,9 if outer or h%11 else 10

def main():
    OUT.mkdir(parents=True,exist_ok=True);w=MeasuredWorld(WORLD);lots=list(specs());assert len(lots)==93
    for x,z,height,half in lots:
        base=20-height-1;w.box((x-1,base+1,z+half),(x+1,base+3,z+half));w.box((x-half,21,z-half),(x+half,24,z+half))
    w.load();lo=(min(x-h for x,z,_,h in lots),21,min(z-h for x,z,_,h in lots));hi=(max(x+h for x,z,_,h in lots),24,max(z+h for x,z,_,h in lots))
    tags={q:t for q,t in iter_block_entities(WORLD,'projectseele:geofront',lo,hi,selected_chunks=set(w.selected))};records=[];states=Counter();failures=[];roof_nbt=[]
    for index,(x,z,height,half) in enumerate(lots):
        base=20-height-1;doors=[];anchors=[]
        for y in range(base+1,base+4):
            for xx in range(x-1,x+2):
                state=w.get(xx,y,z+half);doors.append(dict(pos=[xx,y,z+half],state=state));states[state]+=1
        for xx in (x-half,x+half):
            for zz in (z-half,z+half):
                for y in range(21,25):
                    q=(xx,y,zz);state=w.block(q);anchors.append(dict(pos=q,state=state,nbt=tags[q].snbt() if q in tags else None))
                    if state!='minecraft:iron_block' or q in tags:failures.append(dict(tower=index,pos=q,state=state,reason='Fixed negative-mask state differs from the known complete dome steel-column template'))
        for q,t in tags.items():
            if x-half<=q[0]<=x+half and z-half<=q[2]<=z+half and q[1] in (21,22):roof_nbt.append(dict(tower=index,pos=q,full_nbt=t.snbt()))
        records.append(dict(id=f'tokyo3_retractable/{index}',center=[x,80,z],height=height,half=half,entrance_cells=doors,fixed_dome_negative_mask=anchors))
    data=dict(towers=len(lots),entrance_cell_denominator=93*9,entrance_states=dict(states),fixed_anchor_denominator=93*16,
        fixed_anchor_failures=failures,roof_extension_block_entities=roof_nbt,roof_extension_layers=[21,22],objects=records,
        world_changed=False,native_travel_passed=False,all_user_rooftop_extent_beyond_two_layers='Not included; any extended construction requires a declared movement component rather than inferred air/geometry')
    (OUT/'measured_ports_and_roofs.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8');print({k:v if k not in ('fixed_anchor_failures','roof_extension_block_entities') else len(v) for k,v in data.items() if k!='objects'},flush=True)

if __name__=='__main__':main()
