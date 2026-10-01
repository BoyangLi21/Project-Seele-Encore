"""Compose whole parcel grading with solved public datums and founded plinths.

No world writes. Every changed state is measured against the current authorized
construction world. Pending landscape edges remain explicit delivery blockers.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import math
import shutil
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR, iter_block_entities

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / 'run/saves/SEELE_FIELD_R44_REVIEW'
SOFT = {'minecraft:'+n for n in ['grass_block','dirt','coarse_dirt','rooted_dirt','stone','gravel','sand','clay','sandstone','mud','grass','tall_grass','fern','large_fern','dandelion','poppy']}
FLOOR = {'minecraft:smooth_stone', 'minecraft:smooth_stone_slab', 'minecraft:stone_bricks'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('plan',type=Path)
    parser.add_argument('datums',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--garden-datums',type=Path)
    a=parser.parse_args();assert not a.output.exists();a.output.mkdir(parents=True)
    district=json.loads((a.plan/'new_district.json').read_text('utf8'))
    parcels=json.loads((a.plan/'parcel_ground_plan.json').read_text('utf8'))
    components=json.loads((a.plan/'parcel_components.json').read_text('utf8'))
    datum=json.loads(a.datums.read_text('utf8'))
    columns={tuple(r['pos']):r for r in parcels['columns']}
    public={tuple(r['pos']):r['feet'] for r in datum['solved_columns']}
    source_rows=[json.loads(s) for s in gzip.open(a.plan/'forward.jsonl.gz','rt',encoding='utf8')]
    rows={tuple(r['pos']):r for r in source_rows}
    w=MeasuredWorld(WORLD)
    for r in source_rows:w.box(tuple(r['pos']),tuple(r['pos']))
    garden=json.loads(a.garden_datums.read_text('utf8')) if a.garden_datums else None
    if garden and 'whole_bounds' in garden:
        assert not garden['infeasible']
        import numpy as np
        heightfield=np.load(a.garden_datums.parent/'whole_landscape_heightfield.npz');ox,oz=heightfield['origin']
        for r in garden['solved_garden_columns']:
            q=tuple(r['pos'])
            if q in columns:continue
            before_ground=int(heightfield['before'][q[1]-oz,q[0]-ox])
            columns[q]=dict(pos=list(q),before_ground=before_ground,target_ground=r['feet']-1,feet=r['feet'],role='graded_garden_edge',owner='r44/kirisato/whole_natural_transition',changed_cells=0)
        parcels['columns']=list(columns.values())
    changes=datum['changed_public_columns']+(garden['changed_garden_columns'] if garden else [])
    for r in changes:
        x,z=r['pos'];lo=math.floor(min(r['before_feet'],r['proposed_feet']))-4;hi=math.ceil(max(r['before_feet'],r['proposed_feet']))+2
        w.box((x,lo,z),(x,hi,z))
    for b in district['buildings']:
        x,z,X,Z=b['bounds'];f=b['floor'];w.box((x-1,f-12,z-1),(X+1,f,Z+1))
    w.load()
    lo=tuple(min(q[k] for q in rows) for k in range(3));hi=tuple(max(q[k] for q in rows) for k in range(3))
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',lo,hi,selected_chunks=set(w.selected)))
    held=[];foundations=[];preserved_water=[]
    def get(q):return rows[q]['after'] if q in rows else w.block(q)
    def put(q,state,owner,reason):
        before=w.block(q)
        if before is None or q in tags:
            held.append(dict(pos=q,reason='Unknown cell or retained complete block entity',state=before));return
        if state==before:rows.pop(q,None)
        else:rows[q]=dict(pos=q,before=before,after=state,before_nbt=None,after_nbt=None,owner=owner,reason=reason)
    for r in changes:
        x,z=r['pos'];feet=r['proposed_feet'];target=math.ceil(feet)-1
        base=columns[x,z];paved=not base['role'].startswith('graded_') and base['role']!='public_court_lawn'
        for y in range(math.floor(min(r['before_feet'],feet))-4,math.ceil(max(r['before_feet'],feet))+2):
            q=(x,y,z);st=get(q);name=(st or '').split('[')[0]
            if name=='minecraft:water':
                preserved_water.append(dict(pos=q,state=st,scope='Complete actual water component, including a retained aquifer below dry soil. Soil grading may not replace this voxel.'));continue
            if name not in SOFT|FLOOR|AIR:
                held.append(dict(pos=q,reason='Whole public regrade meets retained authored component',state=st));continue
            if y>target:after='minecraft:air'
            elif y==target:after='minecraft:smooth_stone_slab[type=bottom,waterlogged=false]' if feet%1 else 'minecraft:smooth_stone' if paved else 'minecraft:grass_block[snowy=false]'
            elif y>=target-3:after='minecraft:dirt'
            else:after='minecraft:stone'
            put(q,after,r['owner']+'/complete_public_grade','Whole public datum and adjoining garden grade derived from fixed real streets and entrance ports; water-bearing columns remain excluded')
        base['target_ground']=target;base['feet']=feet;base['public_datum_regraded']=True
    for b in district['buildings']:
        x,z,X,Z=b['bounds'];f=b['floor'];perimeter=[]
        perimeter.extend(((xx,z),(xx,z-1)) for xx in range(x,X+1))
        perimeter.extend(((xx,Z),(xx,Z+1)) for xx in range(x,X+1))
        perimeter.extend(((x,zz),(x-1,zz)) for zz in range(z+1,Z))
        perimeter.extend(((X,zz),(X+1,zz)) for zz in range(z+1,Z))
        for (xx,zz),outside in perimeter:
            if outside not in public:continue
            feet=public[outside]
            if feet>=f+1:continue
            for yy in range(math.floor(feet)-1,f):
                q=(xx,yy,zz);st=get(q);name=(st or '').split('[')[0]
                if name not in SOFT|FLOOR|AIR:
                    held.append(dict(pos=q,reason='Exposed foundation meets retained structure',state=st,building=b['id']));continue
                put(q,'minecraft:stone_bricks',b['id']+'/founded_plinth','Complete load-bearing masonry below the unchanged building floor, founded one metre below adjacent new public grade')
                foundations.append(dict(pos=q,building=b['id'],adjacent_public_feet=feet))
    for r in components['full_court_columns']:r['native_feet']=public[tuple(r['pos'])]
    for name,inverse in [('forward',False),('inverse',True)]:
        with gzip.open(a.output/(name+'.jsonl.gz'),'wt',encoding='utf8') as stream:
            for q,row in sorted(rows.items()):
                r=dict(row)
                if inverse:r['before'],r['after']=row['after'],row['before'];r['before_nbt'],r['after_nbt']=row['after_nbt'],row['before_nbt']
                stream.write(json.dumps(r,ensure_ascii=False)+'\n')
    if garden and 'whole_bounds' in garden:
        coords=list(columns)
        district['bounds']=[min(q[0] for q in coords),max(q[0] for q in coords),min(q[1] for q in coords),max(q[1] for q in coords)]
        district['whole_landscape_source']=str(a.garden_datums.resolve())
    (a.output/'new_district.json').write_text(json.dumps(district,ensure_ascii=False,indent=2),'utf8')
    for name in ['road_authority.json','native_cases.json']:shutil.copy2(a.plan/name,a.output/name)
    if (a.plan/'complete_current_water_landscape.json').exists():shutil.copy2(a.plan/'complete_current_water_landscape.json',a.output/'complete_current_water_landscape.json')
    (a.output/'parcel_ground_plan.json').write_text(json.dumps(parcels,ensure_ascii=False,indent=2),'utf8')
    (a.output/'parcel_components.json').write_text(json.dumps(components,ensure_ascii=False,indent=2),'utf8')
    report=dict(source_plan=str(a.plan.resolve()),source_datums=str(a.datums.resolve()),source_datums_sha256=hashlib.sha256(a.datums.read_bytes()).hexdigest(),
                changed_cells=len(rows),regraded_public_columns=len(datum['changed_public_columns']),regraded_garden_columns=len(garden['changed_garden_columns']) if garden else 0,founded_plinth_cells=len({tuple(r['pos']) for r in foundations}),
                held=held,foundations=foundations,preserved_actual_water_cells=preserved_water,world_written=False,root_apply_ready=False,visual_passed=False,native_passed=False,
                pending='Whole garden/retaining/actual culvert edge design, street furniture/lighting, full source/runtime protections, complete static and native review')
    (a.output/'public_grade_composition.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('Private whole public grade patch',len(rows),'cells;',len(held),'held; foundations',report['founded_plinth_cells'],'NO WORLD WRITE',flush=True)


if __name__=='__main__':main()
