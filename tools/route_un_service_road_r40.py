"""An actual campus-road bypass around the new loading apron, at its old datum."""
from pathlib import Path
import argparse,json,math
import regional_voxels as v
from measure_world_r40 import MeasuredWorld,ROOT
from query_blocks import iter_block_entities

WORLD=ROOT/'run/saves/SEELE_FIELD_R40_REVIEW';OUT=ROOT/'artifacts/world_combat_r40/service_road'
PATH=[[6344.5,75,-6079.5],[6338.5,75,-6079.5],[6338.5,75,-5987.5],[6520.5,75,-5987.5],[6520.5,75,-6079.5],[6712.5,75,-6079.5]]
PAVING={'minecraft:black_concrete','minecraft:white_concrete','minecraft:light_gray_concrete','minecraft:gray_concrete','projectseele:nerv_floor_panel'}
GROUND={'minecraft:grass_block[snowy=false]','minecraft:dirt','minecraft:stone','minecraft:gravel'}


def main(apply=False):
    v.WORLD=WORLD;v.OUT=OUT;p=v.Painter();w=MeasuredWorld();mask=set();centres=set()
    for a,b in zip(PATH[:-1],PATH[1:-1]):
        n=round(max(abs(a[0]-b[0]),abs(a[2]-b[2])))
        for i in range(n+1):
            x=math.floor(a[0]+(b[0]-a[0])*i/max(1,n));z=math.floor(a[2]+(b[2]-a[2])*i/max(1,n));centres.add((x,z))
            mask.update((x+dx,z+dz) for dx in range(-3,4) for dz in range(-3,4))
    # Retire only obsolete paved stubs; the receiving deck/foundations are owned
    # by the apron, and the eastern main-road connection stays intact.
    retired={(x,z) for x in list(range(6349,6426))+list(range(6507,6517)) for z in range(-6086,-6073)}
    w.box((6330,69,-6087),(6525,85,-5984));w.load()
    tags=dict(iter_block_entities(WORLD,v.DIM,(6330,69,-6087),(6525,85,-5984)))
    changes={};held=[]
    for x,z in sorted(mask):
        floor=w.get(x,74,z)
        if floor not in PAVING|GROUND:held.append([x,74,z,floor]);continue
        for y in range(75,80):
            state=w.get(x,y,z)
            if '_wall_sign[' in state:continue
            if state not in GROUND|{'minecraft:air','minecraft:grass','minecraft:tall_grass[half=lower]','minecraft:tall_grass[half=upper]'}:
                held.append([x,y,z,state])
            elif state!='minecraft:air':changes[x,y,z]='minecraft:air'
        edge=any((x+dx,z+dz) not in mask for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)))
        stripe=(x,z) in centres and (x+z)%8<4
        changes[x,74,z]='minecraft:white_concrete' if edge or stripe else 'minecraft:black_concrete'
    for x,z in retired-mask:
        if w.get(x,74,z) in PAVING:
            if all(w.get(x,y,z)=='minecraft:air' for y in range(75,80)):changes[x,74,z]='minecraft:grass_block[snowy=false]'
            # Keep the existing footings of lights and signs. They remain
            # deliberate equipment bases alongside the new landscaped verge.
    conflicts=set(changes)&set(tags)
    (OUT).mkdir(parents=True,exist_ok=True);(OUT/'preflight.json').write_text(json.dumps(dict(held=held,block_entities=list(conflicts),route=PATH),ensure_ascii=False,indent=2),'utf8')
    if held or conflicts:raise RuntimeError(('Bypass needs a measured adjustment',held[:15],list(conflicts)))
    for q,after in sorted(changes.items()):
        before=w.block(q)
        if before!=after:p.match((*q,*q),before,after,'r40/un_apron/campus_service_bypass')
    p.meta.update(purpose='Old east-west campus road crossed the raised UN00 receiving deck. Route around its southern edge and the existing power building at the original Y75 walking datum',
                  width=7,route=PATH,original_endpoints=[[6344.5,75,-6079.5],[6712.5,75,-6079.5]],loading_zone_excluded=True)
    p.save_plan('campus_bypass')
    if apply:
        p.apply('campus_bypass');file=WORLD/'quality_walk_cases.json';rows=json.loads(file.read_text('utf8'))
        for row in rows:
            if row['id']=='r07/base/cross_-6080':row['path']=PATH
            if row['id']=='r07/base/cross_-6080/return':row['path']=PATH[::-1]
        file.write_text(json.dumps(rows,ensure_ascii=False),'utf8')
    print('Bypass planned',len(p.ops),flush=True)


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--apply',action='store_true');main(a.parse_args().apply)
