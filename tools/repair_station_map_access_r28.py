"""Give every obstructed station map a supported, reachable public reading position."""
from pathlib import Path
from collections import deque
import copy,json,math,nbtlib,numpy as np
from scipy.spatial import cKDTree
import regional_voxels as v
from query_blocks import read_box,iter_block_entities,AIR
from measure_world_r40 import properties
from station_route_contract_r44 import RouteDiagrams
ROOT=v.ROOT;WORLD=ROOT/'run/saves/SEELE_FIELD_R28_REVIEW';ART=ROOT/'artifacts/facility_r28';OUT=ART/'map_access'
DIR={'north':(0,-1),'south':(0,1),'east':(1,0),'west':(-1,0)}
OPPOSITE={'north':'south','south':'north','east':'west','west':'east'}

def main():
    OUT.mkdir(parents=True,exist_ok=True);v.WORLD=WORLD;v.OUT=OUT;p=v.Painter()
    results=json.loads((ART/'validation/native_full_result.json').read_text());failed=[r for r in results if r['status']=='station_diagram_obstructed']
    shapes=json.loads((WORLD/'native_collision_shapes.json').read_text());roots=[]
    for r in results:
        if r['status']!='pass':continue
        nodes=r.get('path') or [r.get('start'),r.get('end')]
        if any(q is None for q in nodes):continue
        for a,b in zip(nodes,nodes[1:]):roots.extend(np.linspace(a,b,max(2,math.ceil(math.dist(a,b)))))
    roots=np.asarray(roots);tree=cKDTree(roots);overrides=[];moves=[];held=[]
    for r in failed:
        q=tuple(r['readingBoard']);foot=round(r['actual'][1]);lo=(q[0]-35,foot-1,q[2]-35);hi=(q[0]+35,foot+6,q[2]+35)
        cells=read_box(WORLD,v.DIM,lo,hi);tags=dict(iter_block_entities(WORLD,v.DIM,lo,hi));old=cells[q];face=old.split('facing=')[1].split(',')[0].split(']')[0]
        def boxes(state):
            if state.split('[')[0] in AIR|{'minecraft:light'}:return []
            return shapes.get(state.replace(',propagate_property=0',''),[[0,0,0,1,1,1]])
        def complete_map_clear_of_stairs(board,candidate_face):
            proposed=old.replace('facing='+face,'facing='+candidate_face)
            panel=shapes.get(proposed)
            if panel is None:raise RuntimeError(('Unmeasured actual complete route-map shape',proposed))
            for stair,st in cells.items():
                if not st.partition('[')[0].endswith('_stairs'):continue
                spec=properties(st)
                if spec.get('half')!='bottom' or spec.get('shape')!='straight':continue
                samples={'north':[(.5,.9,.5),(.5,.4,1)],'south':[(.5,.1,.5),(.5,.6,1)],'east':[(.1,.5,.5),(.6,.5,1)],'west':[(.9,.5,.5),(.4,.5,1)]}[spec['facing']]
                for dx,dz,dy in samples:
                    p=[stair[0]+dx,stair[1]+dy,stair[2]+dz]
                    low=[p[0]-.3,p[1]+1e-6,p[2]-.3];high=[p[0]+.3,p[1]+1.8,p[2]+.3]
                    if any(all(board[k]+b[k]<high[k]and board[k]+b[k+3]>low[k]for k in range(3))for b in panel):return False
            return True
        def free(x,y,z,height=1):
            return not any(b[0]<.795 and b[3]>.205 and b[2]<.795 and b[5]>.205 and b[1]<height and b[4]>.001 for b in boxes(cells.get((x,y,z),'UNKNOWN')))
        def walkable(x,z):
            floor=boxes(cells.get((x,foot-1,z),'UNKNOWN'))
            return any(b[4]>.90 and b[0]<=.5<=b[3] and b[2]<=.5<=b[5] for b in floor) and free(x,foot,z) and free(x,foot+1,z,.8)
        starts=[]
        for i in tree.query_ball_point([q[0]+.5,foot,q[2]+.5],38):
            x,y,z=roots[i];X,Z=math.floor(x),math.floor(z)
            if abs(y-foot)<.12 and lo[0]<X<hi[0] and lo[2]<Z<hi[2] and walkable(X,Z):starts.append((X,Z))
        visited={k:None for k in starts};queue=deque(visited)
        while queue:
            x,z=queue.popleft()
            for dx,dz in DIR.values():
                nxt=x+dx,z+dz
                if nxt not in visited and lo[0]<nxt[0]<hi[0] and lo[2]<nxt[1]<hi[2] and walkable(*nxt):visited[nxt]=(x,z);queue.append(nxt)
        def ray_clear(reader,board=q):
            eye=np.array(reader)+[.5,1.62,.5];target=np.array(board)+[.5,1.09375,.5]
            for t in np.linspace(0,1,100):
                point=eye*(1-t)+target*t;cell=tuple(np.floor(point).astype(int))
                if cell==board or cell==q:continue
                local=point-np.array(cell)
                if any(all(b[i]-1e-5<=local[i]<=b[i+3]+1e-5 for i in range(3)) for b in boxes(cells.get(cell,'UNKNOWN'))):return False
            return True
        options=[]
        for candidate_face in dict.fromkeys((face,OPPOSITE[face],*DIR)):
            if not complete_map_clear_of_stairs(q,candidate_face):continue
            nx,nz=DIR[candidate_face]
            for distance in (2,3,4):
                reader=(q[0]+nx*distance,foot,q[2]+nz*distance);key=reader[0],reader[2]
                if key not in visited or not ray_clear(reader):continue
                height=sum(free(reader[0],foot+y,reader[2]) for y in range(2,5))
                chain=[key]
                while visited[chain[-1]] is not None:chain.append(visited[chain[-1]])
                score=len(chain)+distance-height*4+(0 if candidate_face==face else .2)
                options.append((score,candidate_face,reader,chain[::-1]))
        newq=q
        if not options:
            # A wall-mounted diagram in an actual public aisle replaces one
            # buried behind a stair. Never carve a walking passage through the stair.
            replacements=[]
            for x,z in visited:
                if math.hypot(x-q[0],z-q[2])>22:continue
                for newface,(nx,nz) in DIR.items():
                    board=(x-nx*3,foot+2,z-nz*3);back=(board[0]-nx,board[1],board[2]-nz)
                    if board in tags or cells.get(board,'UNKNOWN').split('[')[0] not in AIR:continue
                    if not complete_map_clear_of_stairs(board,newface):continue
                    if not boxes(cells.get(back,'minecraft:air')):continue
                    cross=(1,0) if nz else (0,1)
                    if any(cells.get((board[0]+d*cross[0],board[1]+dy,board[2]+d*cross[1]),'UNKNOWN').split('[')[0] not in AIR for d in (-1,0,1) for dy in (0,1)):continue
                    reader=(x,foot,z)
                    if not ray_clear(reader,board):continue
                    chain=[(x,z)]
                    while visited[chain[-1]] is not None:chain.append(visited[chain[-1]])
                    replacements.append((math.dist(board,q)+len(chain)*.2,newface,reader,chain[::-1],board))
            if not replacements:held.append(dict(id=r['id'],board=q,known_public_starts=len(starts)));continue
            _,newface,reader,chain,newq=min(replacements)
        else:_,newface,reader,chain=min(options)
        newstate=old.replace('facing='+face,'facing='+newface)
        if newq!=q:
            p.match((*q,*q),old,'minecraft:air','r28/retire_buried_station_map')
            p.match((*newq,*newq),cells[newq],newstate,'r28/reachable_wall_station_map')
            tag=copy.deepcopy(tags[q])
            for k,value in zip(('x','y','z'),newq):tag[k]=nbtlib.Int(value)
            p.block_entities[newq]=tag
        elif newstate!=old:p.match((*q,*q),old,newstate,'r28/route_diagram_faces_public_forecourt');p.block_entities[q]=copy.deepcopy(tags[q])
        # A turned physical panel needs the corresponding exact rail-direction arrow.
        if newstate!=old or newq!=q:
            final_tag=copy.deepcopy(p.block_entities[newq])
            if 'MapRows'in final_tag:
                diagram=RouteDiagrams(WORLD/'native_transit_r28.json').diagram(int(final_tag['NativePlatformId']),newface,str(final_tag.get('Route','')))
                final_tag['MapRows']=nbtlib.List[nbtlib.String]([nbtlib.String(text)for text in diagram['rows']])
                for k in range(3):final_tag['Row'+str(k)]=nbtlib.String(diagram['rows'][k])
            p.block_entities[newq]=final_tag
        point=[reader[0]+.5,foot,reader[2]+.5]
        overrides.append(dict(id=r['id'],path=[point,point],readingBoard=list(newq)))
        path=[[x+.5,foot,z+.5] for x,z in chain]
        if len(path)==1:path.append(path[0])
        overrides.append(dict(id='r28/map_approach/'+r['id'],path=path))
        moves.append(dict(id=r['id'],old_board=q,board=newq,old_face=face,new_face=newface,reader=point,approach=path))
    retired=[];unresolved=[]
    for row in held:
        counterpart=next((m for m in moves if m['id'].rsplit('/',1)[0]==row['id'].rsplit('/',1)[0]),None)
        if counterpart is None:unresolved.append(row);continue
        q=tuple(row['board']);old=read_box(WORLD,v.DIM,q,q)[q]
        p.match((*q,*q),old,'minecraft:air','r28/retire_unreachable_duplicate_diagram')
        point=counterpart['reader'];overrides.append(dict(id=row['id'],path=[point,point],readingBoard=counterpart['board']))
        retired.append(dict(**row,replacement=counterpart['board'],reader=point))
    # Remove only the original isolated two-post diagram supports, not rails.
    removed_boards=[tuple(m['old_board']) for m in moves if m['old_board']!=m['board']]+[tuple(m['board']) for m in retired]
    post='minecraft:iron_bars[east=false,north=false,south=false,waterlogged=false,west=false]'
    for q in removed_boards:
        old=read_box(WORLD,v.DIM,q,q)[q];along=(1,0) if 'facing=north' in old or 'facing=south' in old else (0,1)
        for side in (-1,1):
            for y in range(q[1]-1,q[1]+2):
                t=(q[0]+side*along[0],y,q[2]+side*along[1]);state=read_box(WORLD,v.DIM,t,t)[t]
                if state==post:p.match((*t,*t),state,'minecraft:air','r28/retired_diagram_stand')
    (OUT/'held.json').write_text(json.dumps(unresolved,indent=2));assert not unresolved,unresolved
    p.meta.update(maps=moves,retired_unreachable_duplicates=retired,walk_nodes=overrides);p.apply('reachable_station_route_diagrams')
    (OUT/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),encoding='utf8')
    print('Reachable station-map readers',len(moves),'native approach cases',len(overrides),flush=True)

if __name__=='__main__':main()
