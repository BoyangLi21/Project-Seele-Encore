"""Native platform gates and readable direction maps for every live train stop."""
import argparse,json,math,nbtlib
from collections import Counter
import regional_voxels as v
from measure_world_r40 import MeasuredWorld,WORLD,ROOT,properties
from query_blocks import AIR,iter_block_entities
from build_station_boards_r19 import packed

OUT=ROOT/'artifacts/world_combat_r40/station_completion'
EMPTY=AIR|{'minecraft:light'}
NORMAL={'north':(0,-1),'south':(0,1),'east':(1,0),'west':(-1,0)}

def main(apply=False):
    OUT.mkdir(parents=True,exist_ok=True);v.WORLD=WORLD;v.OUT=OUT;p=v.Painter()
    audit=json.loads((ROOT/'artifacts/world_combat_r40/stations/actual_platforms.json').read_text())['platforms']
    native=json.loads((WORLD/'native_transit_r28.json').read_text());titles={q['id']:q['station'] for q in audit};w=MeasuredWorld()
    for r in audit:
        x,y,z=map(int,r['centre']);span=(r['ends'][1]-r['ends'][0])//2+5
        w.box((x-(span if r['axis']=='x' else 24),y-2,z-(24 if r['axis']=='x' else span)),(x+(span if r['axis']=='x' else 24),y+16,z+(24 if r['axis']=='x' else span)))
    w.load();changes={};gates=[];boards=[];held=[];occupied=set()
    shapes={v.canonical_state(k):q for k,q in json.loads((WORLD/'native_collision_shapes.json').read_text()).items()}
    def empty(q):return (w.block(q) or '').partition('[')[0] in EMPTY
    def supported(q):
        s=w.block(q)
        if s is None or any(k in s for k in ('air','water','lcl','door','sign','light','escalator','fence','bars','chair','bench')):return False
        bs=shapes.get(s,[[0,0,0,1,1,1]])
        return any(b[0]<=.2 and b[3]>=.8 and b[2]<=.2 and b[5]>=.8 and b[4]>=.99 for b in bs)
    def put(q,s,why):
        q=tuple(map(int,q));old=w.block(q)
        if old is None:raise RuntimeError(('Unmeasured',q))
        if q in changes and changes[q][0]!=s:raise RuntimeError(('Conflicting desired states',q))
        if old!=v.canonical_state(s):changes[q]=(v.canonical_state(s),why)
    def sequence(pid):
        routes=[r for r in native['routes'] if r['transportMode']=='TRAIN' and any(q['platformId']==pid for q in r['routePlatformData'])]
        rows=[]
        for route in routes:
            seq=[q['platformId'] for q in route['routePlatformData']];i=seq.index(pid)
            onward=seq[i+1:]
            # A terminal platform has the next outgoing leg at the beginning
            # of the same route. Preserve the engine's order, never sort names.
            if not onward:onward=seq[1:]
            names=[]
            for q in onward:
                title=titles.get(q,'')
                if title and (not names or names[-1]!=title):names.append(title)
            rows.append(route['routeNumber']+'  '+(' → '.join(names[:3]) if names else '终点站'))
            rows.extend('│ '+n for n in names[3:])
        return routes,rows
    for r in audit:
        x,y,z=map(int,r['centre']);horizontal=r['axis']=='x';routes,rows=sequence(r['id'])
        for offset in ('-2','2'):
            edge=r['edges'].get(offset,[])
            if not edge:held.append(dict(platform=r['id'],reason='no native platform edge',offset=offset));continue
            side=int(offset)//2;axis=0 if horizontal else 2;centre=x if horizontal else z
            # The installed Eidan vehicles have 5-metre door spacing (native
            # positionDefinitions door offsets ±40/±120 sixteenths).
            edge_points={tuple(c['pos']) for c in edge}
            for c in edge:
                q=tuple(c['pos']);face=properties(c['state'])['facing'];lower=(q[0],q[1]+1,q[2]);upper=(q[0],q[1]+2,q[2])
                if not empty(lower) or not empty(upper):continue
                # Require a real boarding apron behind the edge. A legacy
                # platform marker hanging over a void is not a gate site.
                outward=(0,side) if horizontal else (side,0)
                reader=(q[0]+outward[0],q[1],q[2]+outward[1])
                if not supported(reader):held.append(dict(platform=r['id'],pos=q,reason='missing boarding apron'));continue
                u=q[axis]-centre;phase=(u-2)%5;isdoor=phase in (0,1)
                if isdoor:
                    partner=list(q);partner[axis]+=1 if phase==0 else -1
                    isdoor=tuple(partner) in edge_points
                part=phase if isdoor else u%2
                if face in ('south','west'):part=1-part
                base=c['state'].replace('door_type=none','door_type=apg');put(q,base,'native_apg_base')
                for half,at in [('lower',lower),('upper',upper)]:
                    props=f'facing={face},half={half},side={"left" if part==0 else "right"}'
                    state=f'mtr:apg_door[end=false,{props},unlocked=true]' if isdoor else f'mtr:apg_glass[{props}]'
                    put(at,state,'native_apg_door' if isdoor else 'native_apg_glass')
                gates.append(dict(platform=r['id'],base=q,door=isdoor))
            # Wall maps follow the lane actually adjacent to this rail. Find
            # a supported fixed wall, with a clear approach and 3x2 envelope.
            face=('south' if side<0 else 'north') if horizontal else ('east' if side<0 else 'west');nx,nz=NORMAL[face]
            count=0
            for u in [centre-18,centre+18,centre-32,centre+32,centre]:
                if count>=2:break
                for lateral in (14,16,12,10,8,6):
                    q=(u,y+3,z+side*lateral) if horizontal else (x+side*lateral,y+3,u)
                    cells=[(q[0]+(d if nz else 0),q[1]+h,q[2]+(d if nx else 0)) for d in (-1,0,1) for h in (0,1)]
                    if any(c in occupied or not empty(c) for c in cells):continue
                    back=[(X-nx,Y,Z-nz) for X,Y,Z in cells]
                    if not all(supported(c) for c in back):continue
                    approach=[(q[0]+nx*d,y+1,q[2]+nz*d) for d in (1,2,3)]
                    if not all(supported((X,Y-1,Z)) and empty((X,Y,Z)) and empty((X,Y+1,Z)) for X,Y,Z in approach):continue
                    block=f'projectseele:station_departure_board[facing={face},wayfinding=true]';put(q,block,'station_route_board');occupied.update(cells)
                    tag=nbtlib.Compound({'id':nbtlib.String('projectseele:station_departure_board'),'x':nbtlib.Int(q[0]),'y':nbtlib.Int(q[1]),'z':nbtlib.Int(q[2]),'Wayfinding':nbtlib.Byte(1),'Station':nbtlib.String(r['station']),'Route':nbtlib.String('本站出发 · 沿途停靠'),'PlatformCentre':nbtlib.Long(packed((x,y,z))),'NativePlatformId':nbtlib.Long(r['id']),'MapRows':nbtlib.List[nbtlib.String]([nbtlib.String(s) for s in rows+['每分钟一班 · 站台门开后上车']])})
                    p.block_entities[q]=tag;boards.append(dict(platform=r['id'],station=r['station'],position=q,face=face,rows=rows));count+=1;break
            if count==0:
                choice=None
                for u in [centre-18,centre+18,centre,centre-26,centre+26]:
                    if choice:break
                    for lateral in (7,9,5,4):
                        q=(u,y+3,z+side*lateral) if horizontal else (x+side*lateral,y+3,u)
                        cells=[(q[0]+(d if nz else 0),q[1]+h,q[2]+(d if nx else 0)) for d in (-1,0,1) for h in (0,1)]
                        if any(c in occupied or not empty(c) for c in cells):continue
                        # The board must be reached from this edge without
                        # crossing any other live rail or its platform gate.
                        approach=[(u,y+1,z+side*d) if horizontal else (x+side*d,y+1,u) for d in range(3,lateral)]
                        if not approach or not all(supported((X,Y-1,Z)) and empty((X,Y,Z)) and empty((X,Y+1,Z)) for X,Y,Z in approach):continue
                        rods=[]
                        for shift in (-1,1):
                            X,Z=q[0]+(shift if nz else 0),q[2]+(shift if nx else 0);line=[]
                            for Y in range(q[1]+2,y+15):
                                if supported((X,Y,Z)):break
                                if not empty((X,Y,Z)):line=[];break
                                line.append((X,Y,Z))
                            else:line=[]
                            if not line:rods=[];break
                            rods.extend(line)
                        if not rods:continue
                        choice=q,cells,rods;break
                if choice:
                    q,cells,rods=choice
                    put(q,f'projectseele:station_departure_board[facing={face},wayfinding=true]','suspended_route_map');occupied.update(cells+rods)
                    for rod in rods:put(rod,'minecraft:iron_bars[east=false,north=false,south=false,waterlogged=false,west=false]','ceiling_suspension')
                    tag=nbtlib.Compound({'id':nbtlib.String('projectseele:station_departure_board'),'x':nbtlib.Int(q[0]),'y':nbtlib.Int(q[1]),'z':nbtlib.Int(q[2]),'Wayfinding':nbtlib.Byte(1),'Station':nbtlib.String(r['station']),'Route':nbtlib.String('本站出发 · 沿途停靠'),'PlatformCentre':nbtlib.Long(packed((x,y,z))),'NativePlatformId':nbtlib.Long(r['id']),'MapRows':nbtlib.List[nbtlib.String]([nbtlib.String(s) for s in rows+['每分钟一班 · 站台门开后上车']])})
                    p.block_entities[q]=tag;boards.append(dict(platform=r['id'],station=r['station'],position=q,face=face,rows=rows,suspension=rods));count=1
            if count==0:held.append(dict(platform=r['id'],offset=offset,reason='no measured wall/ceiling mount; existing signs retained'))
    for q,(after,why) in sorted(changes.items()):p.match((*q,*q),w.block(q),after,'r40/'+why)
    p.meta.update(native_platforms=len(audit),gates=gates,boards=boards,held=held,vehicle_door_reference='MTR 4.0.5 assets/mtr/properties/definition/eidan_9000*.json; native train opening must be exercised in-game')
    p.save_plan('all_native_platforms')
    if apply:p.apply('all_native_platforms')
    (OUT/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),encoding='utf8');print('Gate columns',len(gates),'route maps',len(boards),'held',len(held),'changes',len(changes))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');main(p.parse_args().apply)
