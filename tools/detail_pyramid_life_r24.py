"""Purpose-specific original equipment in the 34 documented side rooms.

Only measured free slots with intact floors are used. Existing routes, staff
posts, beds, controls and the accepted central command suite are protected.
"""
from pathlib import Path
import argparse,json,math
import numpy as np,nbtlib
from scipy.spatial import cKDTree
import regional_voxels as v
from query_blocks import read_box,iter_block_entities,AIR
ROOT=v.ROOT;WORLD=ROOT/'run/saves/SEELE_R24_TV_REVIEW';OUT=ROOT/'artifacts/facility_r24/pyramid_life'
FLOORS={'projectseele:nerv_floor_panel','projectseele:nerv_structural_panel','minecraft:smooth_stone','minecraft:polished_andesite','minecraft:smooth_quartz','minecraft:quartz_block','minecraft:light_gray_concrete','minecraft:gray_concrete','minecraft:light_gray_terracotta','minecraft:white_concrete'}
NAMES={'計算機運用室':'计算机运维室','技術記録室':'技术档案室','交替勤務室':'轮值休息室','作戦資料室':'作战资料室','通信管制室':'通信管制室','医療支援室':'医疗支援室','機材整備室':'器材整备室','職員食堂':'职员食堂','機関監視室':'动力监视室','通信中継室':'通信中继室','当直準備室':'值班准备室','光学監視室':'光学监视室'}
def main(apply=False):
    OUT.mkdir(parents=True,exist_ok=True);v.WORLD=WORLD;v.OUT=OUT;p=v.Painter();placed=[];labels=[];held=[];walks=[];occupied=set()
    rooms=json.loads((ROOT/'artifacts/first_battle_world_r10/world_art/pyramid_rooms/places.json').read_text(encoding='utf8'))['rooms']
    catalog=json.loads((WORLD/'quality_walk_cases.json').read_text(encoding='utf8'));points=[]
    for route in catalog:
        path=route.get('path',[route.get('start'),route.get('end')])
        if not path or path[0] is None:continue
        for a,b in zip(path,path[1:]):
            a,b=np.array(a),np.array(b)
            if not(-600<a[1]<-300 or -600<b[1]<-300):continue
            points.extend(np.linspace(a,b,max(2,int(np.linalg.norm(a-b)*2)+1)))
    points=np.array(points);tree=cKDTree(points[:,[0,2]])
    roster=json.loads((WORLD/'nerv_staff_r15.json').read_text(encoding='utf8'))['stations'];staff=np.array([r['feet'] for r in roster],float)
    geometry={g['name']:g for g in json.loads((ROOT/'artifacts/facility_r24/props/geometry.json').read_text())}
    for room in rooms:
        if room['id']=='r04/pyramid/435/06':continue  # R54 keeps original equipment and owns the private wards.
        x0,x1,z0,z1=room['bounds'];f=room['floor'];entry=room['entry'];purpose=room['purpose'];name=NAMES[room['label']]
        b=read_box(WORLD,v.DIM,(x0-2,f,z0-2),(x1+2,f+7,z1+2));room_items=[]
        def protected(q):return 6<=q[0]<=52 and -445<=q[1]<=-388 and 262<=q[2]<=365
        def cells(kind,x,z):return [(x,f+1+dy,z) for dy in range(math.ceil(geometry[kind]['hi'][1]))]
        def acceptable(kind,x,z):
            envelope=cells(kind,x,z)
            if not(x0+2<=x<=x1-2 and z0+2<=z<=z1-2) or any(protected(q) for q in envelope):return False
            if b.get((x,f,z),'').split('[')[0] not in FLOORS:return False
            if any(q in occupied or b.get(q,'UNKNOWN') not in AIR|{'minecraft:light'} for q in envelope):return False
            if np.any((np.abs(staff[:,1]-(f+1))<2)&((staff[:,0]-x-.5)**2+(staff[:,2]-z-.5)**2<5)):return False
            for i in tree.query_ball_point([x+.5,z+.5],1.4):
                q=points[i]
                if abs(q[0]-x-.5)<.9 and abs(q[2]-z-.5)<.9 and q[1]+1.9>f+1 and q[1]<f+1+geometry[kind]['hi'][1]:return False
            for dx in range(-1,2):
                for dz in range(-1,2):
                    state=b.get((x+dx,f+1,z+dz),'')
                    if '_bed[' in state or any(k in state for k in ('_chair','station_seat','controller','_button[')):return False
            return True
        def place(kind,x,z,face='south'):
            q=(x,f+1,z);p.match((*q,*q),b[q],f'projectseele:period_fixture[facing={face},kind={kind}]','r24/room/'+room['id'])
            tag=nbtlib.Compound({'id':nbtlib.String('projectseele:period_fixture'),'x':nbtlib.Int(x),'y':nbtlib.Int(f+1),'z':nbtlib.Int(z),'Title':nbtlib.String(name)})
            p.block_entities[q]=tag
            for offset,upper in enumerate(cells(kind,x,z)[1:],1):p.match((*upper,*upper),b[upper],f'projectseele:period_fixture_part[offset={offset}]','r24/room_fixture_upper')
            occupied.update(cells(kind,x,z));item=dict(room=room['id'],purpose=purpose,kind=kind,position=q,facing=face);placed.append(item);room_items.append(item)
        # Candidate bands follow the perimeter, outside the central access
        # lanes; no free air is used to infer an extra room.
        candidates=[]
        for depth in (3,6,9):
            for x in range(x0+4,x1-3,5):candidates.extend([(x,z0+depth,'south'),(x,z1-depth,'north')])
            for z in range(z0+4,z1-3,5):candidates.extend([(x0+depth,z,'east'),(x1-depth,z,'west')])
        programme={'ANALYSIS':['tech_bench','tech_bench','document_cart'],'ARCHIVE':['document_cart','document_cart','tech_bench'],
                   'BRIEFING':['document_cart','tech_bench'],'MEDICAL':['tech_bench','document_cart','drinking_fountain'],
                   'SUPPLIES':['tech_bench','tech_bench','document_cart'],'CAFETERIA':['coffee_machine','cafe_counter','cafe_counter','drinking_fountain'],
                   'QUARTERS':['coffee_machine','document_cart']}[purpose]
        for kind in programme:
            choice=next(((x,z,face) for x,z,face in candidates if acceptable(kind,x,z) and all((x-i['position'][0])**2+(z-i['position'][2])**2>=9 for i in room_items)),None)
            if choice:place(kind,*choice)
            else:held.append(dict(room=room['id'],kind=kind,reason='No clear measured perimeter slot'))
        if purpose in ('CAFETERIA','QUARTERS','ARCHIVE','BRIEFING'):
            for _ in range(2 if purpose=='CAFETERIA' else 1):
                choice=next(((x,z) for x,z,_ in candidates if all(acceptable(k,x,z+dz) for k,dz in [('cafe_table',0),('cafe_stool',-1),('cafe_stool',1)]) and all((x-i['position'][0])**2+(z-i['position'][2])**2>=16 for i in room_items)),None)
                if choice:
                    x,z=choice;place('cafe_table',x,z);place('cafe_stool',x,z-1,'south');place('cafe_stool',x,z+1,'north')
        # A supported translated title above the same documented doorway.
        ex,_,ez=entry
        if abs(ex-x0)<2:normal=(-1,0);face='west'
        elif abs(ex-x1)<2:normal=(1,0);face='east'
        elif abs(ez-z0)<2:normal=(0,-1);face='north'
        else:normal=(0,1);face='south'
        nx,nz=normal;q=(ex+nx,f+4,ez+nz)
        span=[(q[0]+(d if nz else 0),q[1],q[2]+(d if nx else 0)) for d in (-1,0,1)]
        support=[(x-nx,y,z-nz) for x,y,z in span]
        allowed={'projectseele:nerv_wall_panel','projectseele:nerv_structural_panel','projectseele:nerv_wall_datum','minecraft:light_gray_concrete','minecraft:white_concrete','minecraft:gray_concrete'}
        if not any(protected(t) for t in span) and all(b.get(t,'UNKNOWN') in AIR|{'minecraft:light'} for t in span) and all(b.get(t,'').split('[')[0] in allowed for t in support):
            p.match((*q,*q),b[q],f'projectseele:period_fixture[facing={face},kind=shop_sign]','r24/room_name_plate')
            p.block_entities[q]=nbtlib.Compound({'id':nbtlib.String('projectseele:period_fixture'),'x':nbtlib.Int(q[0]),'y':nbtlib.Int(q[1]),'z':nbtlib.Int(q[2]),'Title':nbtlib.String(name),'Lines':nbtlib.List[nbtlib.String]([nbtlib.String(room['label']+' · NERV')])})
            labels.append(dict(room=room['id'],position=q,title=name,support=support))
        for route in catalog:
            if route['id'].startswith(room['id']):walks.append(route)
    p.meta.update(placed=placed,room_labels=labels,held=held,walk_nodes=walks,documented_rooms=len(rooms),accepted_command_suite_preserved=True)
    p.save_plan('documented_room_life_details')
    if apply:p.apply('documented_room_life_details')
    (OUT/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),encoding='utf8');print('Room equipment',len(placed),'supported labels',len(labels),'held',len(held),'native routes',len(walks))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');main(ap.parse_args().apply)
