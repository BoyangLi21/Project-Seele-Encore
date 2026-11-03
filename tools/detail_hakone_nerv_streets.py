"""Finite civil details using installed native fixture models and full NBT."""
import json
from collections import defaultdict
import numpy as np
import nbtlib
from scipy.ndimage import distance_transform_edt
from hakone_earthworks import road_blocks
from prepare_hakone_city_cross import packed
from query_blocks import AIR
from plan_ashi_landscape_r54 import SOIL,PLANTS
from prepare_hakone_togendai_neighbourhood import PAVE

EMPTY=AIR|PLANTS|{'minecraft:light'}


def preservation_mask(candidate,spec):
    boxes=list(spec.get('protected_volumes',[]));columns=defaultdict(list)
    retained=candidate/'plan/retained-buildings.json'
    if retained.is_file():
        boxes.extend([b[0]-2,b[1]-3,b[2]-2,b[3]+2,b[4]+8,b[5]+2] for b in json.loads(retained.read_text('utf8')))
    curves=json.loads((candidate/'plan/native-curves.json').read_text('utf8'))
    with np.load(candidate/'plan/network.npz')as f:x,z,X,Z=map(int,f['bounds'])
    for kind,radius,below,above in [('ropeway',3,10,6)]+([('trains',8,30,7)]if spec.get('preserve_train_corridors',False)else[]):
        for row in curves.get(kind,[]):
            for px,py,pz in row['points']:
                px,py,pz=map(int,np.floor([px,py,pz]))
                if px<x-radius or px>X+radius or pz<z-radius or pz>Z+radius or py<-100 or py>310:continue
                for Q in range(px-radius,px+radius+1):
                    for R in range(pz-radius,pz+radius+1):columns[Q,R].append((py-below,py+above))
    def protected(pos):
        px,py,pz=pos
        return any(all(b[k]<=pos[k]<=b[k+3]for k in range(3))for b in boxes)or any(lo<=py<=hi for lo,hi in columns.get((px,pz),()))
    return protected


def decorate(e,d,spec,rows,out,details,outdoor,preserved):
    x,z,X,Z=map(int,d['bounds']);distance,nearest=distance_transform_edt(~d['walk'],return_indices=True)
    details.update(bridges=[],native_fixtures=[],entry_handrails=[],frontage_pads=[])
    def put(p,state,allow=EMPTY|SOIL|PAVE):
        if preserved(p):raise ValueError(('Detail intersects retained native volume',p))
        before=e.state(*p)
        if before==state:return
        if before.split('[')[0]not in allow:raise ValueError(('Unowned detail cell',p,before))
        if any(all(r['new_payload_bounds'][k]<=p[k]<=r['new_payload_bounds'][k+3]for k in range(3))for r in rows):
            outdoor.append(dict(kind='outside frontage pad',pos=list(p),before=before,after=state))
        e.put(*p,state)
    for name,lo,hi in [('west',-507,-455),('east',-290,-250)]:
        count=0;rail=0
        for pz in range(652,720):
            for px in range(lo,hi+1):
                j,i=pz-z,px-x
                if d['walk'][j,i]:
                    floor,_=road_blocks(d['grade2'][j,i]);floor=int(floor)
                    for y in (floor-2,floor-1):
                        if preserved((px,y,pz)):continue
                        put((px,y,pz),'minecraft:light_gray_concrete');count+=1
                elif .5<distance[j,i]<=1.45:
                    J,I=nearest[:,j,i];floor,_=road_blocks(d['grade2'][J,I]);floor=int(floor)
                    if any(preserved((px,y,pz))for y in (floor-1,floor,floor+1)):continue
                    put((px,floor-1,pz),'minecraft:light_gray_concrete');put((px,floor,pz),'minecraft:stone_bricks')
                    put((px,floor+1,pz),'minecraft:iron_bars[east=true,north=true,south=true,waterlogged=false,west=true]');rail+=1
        abutments=0
        for pz in (651,652,719,720):
            for px in range(lo,hi+1):
                j,i=pz-z,px-x
                if not d['walk'][j,i]:continue
                floor,_=road_blocks(d['grade2'][j,i]);floor=int(floor);soil=int(d['old_ground'][j,i])
                for y in range(soil,floor):
                    if preserved((px,y,pz)):continue
                    put((px,y,pz),'minecraft:light_gray_concrete',EMPTY|SOIL|PAVE|{'minecraft:light_gray_concrete'});abutments+=1
        piers=0
        for pz in (666,702):
            xs=np.where(d['road'][pz-z,max(lo,x)-x:min(hi,X)-x+1])[0]+max(lo,x)
            if not len(xs):continue
            centre=int(np.rint(np.median(xs)))
            for Q in (centre-2,centre+2):
                for px in range(Q-1,Q+2):
                    for R in range(pz-1,pz+2):
                        j,i=R-z,px-x;J,I=nearest[:,j,i];floor,_=road_blocks(d['grade2'][J,I]);floor=int(floor)
                        for Y in range(int(d['old_ground'][j,i])-1,floor-1):
                            put((px,Y,R),'minecraft:light_gray_concrete',EMPTY|SOIL|PAVE|{'minecraft:light_gray_concrete'});piers+=1
        details['bridges'].append(dict(id=name,deck_cells=count,parapet_columns=rail,abutment_cells=abutments,pier_cells=piers))
    for pz in range(636,662):
        floor,_=road_blocks(d['grade2'][pz-z,-376-x]);floor=int(floor)
        for px in (-378,-374):
            if preserved((px,floor,pz))or preserved((px,floor+1,pz)):continue
            put((px,floor,pz),'minecraft:stone_bricks');put((px,floor+1,pz),'minecraft:iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]')
            details['entry_handrails'].append([px,floor,pz])
    for centre,axis in [((-376,630),'x'),((-336,614),'z'),((-272,786),'z')]:
        cx,cz=centre;n=0
        for delta in (-2,0,2):
            for cross in range(-5,6):
                px,pz=(cx+delta,cz+cross)if axis=='x'else(cx+cross,cz+delta);j,i=pz-z,px-x
                if not d['road'][j,i]:continue
                floor,slab=road_blocks(d['grade2'][j,i]);p=(px,int(floor),pz)
                put(p,'projectseele:road_marking_slab[type=bottom,waterlogged=false]'if slab else'minecraft:white_concrete');d['marking'][j,i]=True;n+=1
        details['crossings'].append(dict(centre=[cx,cz],cells=n))
    decorate_frontages(e,d,rows,out,details,outdoor,preserved)


def decorate_frontages(e,d,rows,out,details,outdoor,preserved):
    x,z,X,Z=map(int,d['bounds'])
    changes=list(nbtlib.load(out/'block-entities.dat')['Changes']);existing={tuple(int(tag[k])for k in('x','y','z'))for row in changes for tag in [row.get('After',row.get('Before'))]}
    details.setdefault('native_fixtures',[]);details.setdefault('frontage_pads',[])
    def put(p,state,allow=EMPTY|SOIL|PAVE):
        if preserved(p):raise ValueError(('Detail intersects retained native volume',p))
        before=e.state(*p)
        if before==state:return
        if before.split('[')[0]not in allow:raise ValueError(('Unowned detail cell',p,before))
        if any(all(r['new_payload_bounds'][k]<=p[k]<=r['new_payload_bounds'][k+3]for k in range(3))for r in rows):
            outdoor.append(dict(kind='outside frontage pad',pos=list(p),before=before,after=state))
        e.put(*p,state)
    for r in rows:
        if not any(s in r['use']for s in ('喫茶','商店','书店','诊所')):continue
        px,py,pz=r['door'];ax,_,az=r['approach'];dx=int(np.sign(ax-px));dz=int(np.sign(az-pz));floor=r['site']['floor']
        facing={(1,0):'east',(-1,0):'west',(0,1):'south',(0,-1):'north'}[dx,dz]
        kinds=['cafe_table','vending_machine']if '喫茶'in r['use']else['public_phone','notice_board']if '诊所'in r['use']else['parked_bicycle','letter_box']
        for side,kind in zip((-5,5),kinds):
            Q,R=px+4*dx-side*dz,pz+4*dz+side*dx
            volume=[(Q+i,Y,R+j)for i in (-1,0,1)for j in (-1,0,1)for Y in range(floor,floor+4)]
            if any(preserved(p)or p in existing for p in volume):continue
            if any(d['walk'][R+j-z,Q+i-x]for i in (-1,0,1)for j in (-1,0,1)):continue
            if any(e.state(q,Y,t).split('[')[0]not in EMPTY|SOIL for q,Y,t in volume if Y>floor):continue
            for q in range(Q-1,Q+2):
                for t in range(R-1,R+2):
                    for Y in (floor-1,floor):put((q,Y,t),'minecraft:stone'if Y<floor else'minecraft:smooth_stone')
                    for Y in range(floor+1,floor+4):put((q,Y,t),'minecraft:air')
            pos=(Q,floor+1,R);upper=2 if kind=='public_phone'else 1 if kind in ('notice_board','parked_bicycle','vending_machine','letter_box')else 0
            put(pos,f'projectseele:period_fixture[facing={facing},kind={kind}]')
            for off in range(1,upper+1):put((Q,floor+1+off,R),f'projectseele:period_fixture_part[offset={off}]')
            tag=nbtlib.Compound({'id':nbtlib.String('projectseele:period_fixture'),'x':nbtlib.Int(Q),'y':nbtlib.Int(floor+1),'z':nbtlib.Int(R),'Title':nbtlib.String(r['use']),'Lines':nbtlib.List[nbtlib.String]([nbtlib.String('入口の前を空けてください。')])})
            changes.append(nbtlib.Compound({'Pos':nbtlib.Long(packed(pos)),'After':tag}));existing.add(pos)
            details['native_fixtures'].append(dict(parcel=r['id'],kind=kind,pos=list(pos),upper_cells=upper));details['frontage_pads'].append([Q-1,floor,R-1,Q+1,floor,R+1])
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound](changes)}).save(out/'block-entities.dat',gzipped=True)
