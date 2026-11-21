"""Join the actual R28 airport road to its later north/south street.

Root finite component repair: preserve the street at81, grade both existing
approaches, retain the east terminal underpass, move complete edge rails onto
supported curbs, and blend only natural roadside soil. No railway edits.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import argparse, json, math, msvcrt
from collections import Counter
import numpy as np
import regional_voxels as vox
from query_blocks import read_box, iter_block_entities, AIR
from r52_spatial_plan import BASE
from extend_world_depth_r52 import acquire_world_lock
from prepare_continuous_upright_civil_r52 import cuboids

OUT=BASE/'final_map_audit/airport_road_intersection'
WORLD=BASE/'WORLD_R52';STAGE='full_width_at_grade_connection'
LO=(343,64,89);HI=(462,90,121)
NATURAL={'minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]'}
PAVING={'minecraft:black_concrete','minecraft:white_concrete','minecraft:gray_concrete','minecraft:smooth_stone',
        'minecraft:blackstone_slab[type=bottom,waterlogged=false]','minecraft:smooth_stone_slab[type=bottom,waterlogged=false]',
        'projectseele:road_asphalt_slab[type=bottom,waterlogged=false]','projectseele:road_marking_slab[type=bottom,waterlogged=false]'}

def feet(x):
    if x<=383:return round((79.5+(x-345)*1.5/38)*2)/2
    if x<=395:return 81.
    if x<=454:return round((81.-(x-395)*8./59)*2)/2
    return 73.

def plan():
    OUT.mkdir(parents=True,exist_ok=True);assert not (OUT/'CANDIDATE.npz').exists()
    cells=read_box(WORLD,'projectseele:geofront',LO,HI);devices=list(iter_block_entities(WORLD,'projectseele:geofront',LO,HI));assert not devices,devices
    before=dict(cells);changes={};rails=[];retained={}
    def put(q,state):
        assert q in cells,q;current=cells[q]
        allowed=current in AIR or current in NATURAL or current in PAVING or current.startswith('projectseele:nerv_edge_rail[')
        assert allowed or current==state, ('Foreign component would be edited',q,current,state)
        cells[q]=state
    for q,state in before.items():
        x,y,z=q
        if 345<=x<=460 and 96<=z<=113 and state.startswith('projectseele:nerv_edge_rail['):
            rails.append((q,state));put(q,'minecraft:air')
    for x in range(345,461):
        f=feet(x);floor=math.floor(f-.001);half=f%1>.1
        for z in range(97,113):
            # The original underpass at73 is an independent complete public
            # component. Its floor and load-bearing panels stay verbatim.
            if x>=458 and z<=100:
                assert f==73.;retained[x,z]=f;continue
            carriage=abs(z+.5-105)<5.5
            state=('projectseele:road_asphalt_slab[type=bottom,waterlogged=false]' if carriage else 'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]') if half else ('minecraft:black_concrete' if carriage else 'minecraft:smooth_stone')
            if 386<=x<=392:
                assert f==81 and before[x,80,z] in PAVING,(x,z,before[x,80,z])
                state=before[x,80,z]
            for y in range(64,floor):
                if cells[x,y,z] in AIR or cells[x,y,z] in NATURAL or cells[x,y,z] in PAVING:put((x,y,z),'minecraft:stone')
                else:raise AssertionError(('Undeclared load-bearing component',x,y,z,cells[x,y,z]))
            put((x,floor,z),state)
            for y in range(floor+1,math.ceil(f+6)):put((x,y,z),'minecraft:air')
        # Natural banks only: keep the crossing street, terminal and every
        # existing authored roadside object out of terrain grading.
        for z in list(range(90,97))+list(range(113,120)):
            column=[(y,cells[x,y,z]) for y in range(64,91) if cells[x,y,z] not in AIR]
            if not column or any(s not in NATURAL for y,s in column):continue
            oldtop=column[-1][0];distance=97-z if z<97 else z-112
            top=max(oldtop,math.floor(f-.001-distance/2))
            if top==oldtop:continue
            for y in range(oldtop,top):put((x,y,z),'minecraft:dirt')
            put((x,top,z),'minecraft:grass_block[snowy=false]')
    for q,state in rails:
        x,y,z=q;f=feet(x);new_y=math.ceil(f)
        # An outer curb supports a fence even beside a half-height sidewalk.
        for Y in range(min(y-1,new_y-1),new_y):put((x,Y,z),'minecraft:smooth_stone')
        put((x,new_y,z),state)
    for x in range(345,461):
        for z in range(97,113):
            if (x,z) in retained:continue
            f=feet(x);floor=math.floor(f-.001)
            assert cells[x,floor,z] in PAVING
            assert all(cells[x,y,z] in AIR for y in range(floor+1,math.ceil(f+6))), (x,z,'headroom')
        if x<460:assert abs(feet(x+1)-feet(x))<=.5
    names=sorted(set(before.values())|set(cells.values()));ids={s:i for i,s in enumerate(names)}
    shape=(HI[1]-LO[1]+1,HI[2]-LO[2]+1,HI[0]-LO[0]+1)
    a=np.empty(shape,np.uint16);b=np.empty(shape,np.uint16)
    for q,state in before.items():
        x,y,z=q;j=y-LO[1],z-LO[2],x-LO[0];a[j]=ids[state];b[j]=ids[cells[q]]
    np.savez_compressed(OUT/'CANDIDATE.npz',before=a,after=b,palette=names,lo=LO)
    report=dict(world_written=False,changed_cells=int((a!=b).sum()),source_component='tools/build_airport_station_r28.py: airport_road_walk and graded road',
        existing_cross_street_x=[386,392],cross_street_feet_y=81,graded_existing_road_x=[345,460],full_width_z=[97,112],
        retained_original_underpass_columns=len(retained),moved_edge_rail_blocks=len(rails),rail_moves=[dict(before=q,after=[q[0],math.ceil(feet(q[0])),q[2]],state=s) for q,s in rails],
        actual_block_entities=0,maximum_adjacent_road_step_m=.5,required_clearance_m=6,rail_database_unchanged=True,native_walk_passed=False)
    (OUT/'CANDIDATE.json').write_text(json.dumps(report,indent=2),'utf8')
    import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
    xs=np.arange(LO[0],HI[0]+1)
    def top(field,z):return [max(y for y in range(64,91) if field[x,y,z] not in AIR) for x in xs]
    fig,ax=plt.subplots(figsize=(13,4));ax.plot(xs,top(before,105),label='actual current road surface block');ax.step(xs,top(cells,105),where='mid',label='proposed connected surface block');ax.set(xlabel='World X / Z105',ylabel='World Y');ax.axvspan(386,392,color='gray',alpha=.15);ax.legend();ax.grid(alpha=.25);fig.tight_layout();fig.savefig(OUT/'BEFORE_AFTER_SECTION.png',dpi=130);plt.close(fig)
    print(json.dumps(report),flush=True)

def apply():
    assert not list((OUT/STAGE).glob('applied_*'))
    a=np.load(OUT/'CANDIDATE.npz');p=vox.Painter(vertical_bounds=(-960,320));names=list(map(str,a['palette']))
    count=cuboids(p,LO,a['before'],a['after'],names,'R52_airport_existing_road_intersection');report=json.loads((OUT/'CANDIDATE.json').read_text());assert count==report['changed_cells']
    vox.WORLD=WORLD;vox.OUT=OUT;vox.DIM='projectseele:geofront';p.meta.update(root_author=True,existing_cross_street_and_underpass_preserved=True)
    lock=acquire_world_lock()
    try:report.update(receipt=p.apply(STAGE,session_lock=lock),world_written=True)
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
    (OUT/STAGE/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');args=p.parse_args();apply() if args.apply else plan()
