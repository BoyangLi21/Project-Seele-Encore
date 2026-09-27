"""Route around the installed sign's entire native shape, then pave its reading approach."""
from pathlib import Path
from heapq import heappush,heappop
from functools import lru_cache
import argparse,json,math
import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR
from plan_station_entrances_r42 import FLOORS

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R42_REVIEW';OUT=ROOT/'artifacts/rebuild_r42/station_reader_paths'


def main(apply=False):
    layout=json.loads((ROOT/'artifacts/rebuild_r42/station_entrances/contract.json').read_text('utf8'));w=MeasuredWorld(WORLD)
    for row in layout['placements']:w.around(row['start'],20)
    w.load();shapes={v.canonical_state(k):b for k,b in json.loads((WORLD/'native_collision_shapes.json').read_text()).items()}
    v.WORLD=WORLD;v.OUT=OUT;p=v.Painter();changed=set();walks=[];details=[]
    for index,row in enumerate(layout['placements']):
        sx,y,sz=row['start'];goal=row['reader'];cx,cz=math.floor(sx),math.floor(sz);y=int(y)
        @lru_cache(None)
        def floor(x,z):
            state=w.get(x,y-1,z);name=(state or '').partition('[')[0]
            if name not in FLOORS|{'minecraft:grass_block'}:return False
            return any(b[0]<=.2 and b[3]>=.8 and b[2]<=.2 and b[5]>=.8 and b[4]>=.999 for b in shapes.get(state,[]))
        def blocked(a,b):
            low=(min(a[0],b[0])-.3,y+.000001,min(a[1],b[1])-.3)
            high=(max(a[0],b[0])+.3,y+1.8,max(a[1],b[1])+.3)
            # Some baked models span neighbouring cells (signs, native MTR
            # escalators). Their owner blocks must be included in the sweep.
            for X in range(math.floor(low[0])-2,math.floor(high[0])+3):
                for Z in range(math.floor(low[2])-2,math.floor(high[2])+3):
                    for Y in range(y-2,y+3):
                        state=w.get(X,Y,Z)
                        if state in AIR:continue
                        boxes=shapes.get(state)
                        if boxes is None:boxes=[[0,0,0,1,1,1]]
                        for b in boxes:
                            if all(low[i]<b[i+3]+(X,Y,Z)[i]-1e-7 and high[i]>b[i]+(X,Y,Z)[i]+1e-7 for i in range(3)):return True
            return False
        @lru_cache(None)
        def clear(x,z):return floor(x,z) and not blocked((x+.5,z+.5),(x+.5,z+.5))
        @lru_cache(None)
        def link(x,z,X,Z):return not blocked((x+.5,z+.5),(X+.5,Z+.5))
        start=(cx,cz);goals=[]
        for X in range(math.floor(goal[0])-1,math.floor(goal[0])+2):
            for Z in range(math.floor(goal[2])-1,math.floor(goal[2])+2):
                if clear(X,Z) and math.hypot(X+.5-goal[0],Z+.5-goal[2])<=1.6 and not blocked((X+.5,Z+.5),(goal[0],goal[2])):goals.append((X,Z))
        assert clear(*start) and goals,('No supported clear approach',row['station'],start,goal)
        frontier=[];heappush(frontier,(0,0,start));cost={start:0};prev={};end=None
        while frontier:
            _,g,at=heappop(frontier)
            if g!=cost[at]:continue
            if at in goals:end=at;break
            for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
                n=(at[0]+dx,at[1]+dz)
                if abs(n[0]-cx)>17 or abs(n[1]-cz)>17 or not clear(*n) or not link(*at,*n):continue
                ng=g+1
                if ng<cost.get(n,1e9):
                    cost[n]=ng;prev[n]=at;h=min(abs(n[0]-q[0])+abs(n[1]-q[1]) for q in goals);heappush(frontier,(ng+h,ng,n))
        assert end is not None,('Isolated sign requires relocation',row['station'],row['board'])
        nodes=[end]
        while nodes[-1]!=start:nodes.append(prev[nodes[-1]])
        nodes.reverse();assert len(nodes)<35,('Overlong reading detour',row['station'],len(nodes))
        # Preserve every turn; simplify only straight segments, never diagonal
        # shortcuts through posts or the sign's overhanging physical panel.
        route=[row['start']]
        for k,at in enumerate(nodes[1:-1],1):
            before=nodes[k-1];after=nodes[k+1]
            if (at[0]-before[0],at[1]-before[1])!=(after[0]-at[0],after[1]-at[1]):route.append([at[0]+.5,y,at[1]+.5])
        route.extend([[end[0]+.5,y,end[1]+.5],goal])
        ident=f'r42/station_entrance/{index}/board_approach';walks.extend([dict(id=ident,path=route),dict(id=ident+'/return',path=list(reversed(route)))])
        for X,Z in nodes:
            for dx,dz in ((0,0),(1,0),(0,1)):
                q=(X+dx,y-1,Z+dz)
                if q in changed or not (w.block(q) or '').startswith('minecraft:grass_block') or not clear(q[0],q[2]):continue
                p.match((*q,*q),w.block(q),'projectseele:period_station_floor','r42/station/connected_reading_approach');changed.add(q)
        details.append(dict(station=row['station'],board=row['board'],walk=route,length=cost[end]))
    p.meta.update(reading_approaches=details,walk_nodes=walks,rule='Sweep the 0.6 x 1.8 player across actual post-install native shapes, including neighbouring owner cells; preserve original barriers')
    p.save_plan('connected_reader_paths');OUT.mkdir(parents=True,exist_ok=True);(OUT/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),'utf8')
    print('Connected all',len(details),'reading areas; paving',len(changed))
    if apply:
        from release_combat_r36 import guard
        guard();p.apply('connected_reader_paths')
        cases=json.loads((WORLD/'r42_walk_cases.json').read_text());cases=[r for r in cases if not r['id'].startswith('r42/station_entrance/')]+walks
        (WORLD/'r42_walk_cases.json').write_text(json.dumps(cases,ensure_ascii=False),'utf8')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');main(ap.parse_args().apply)
