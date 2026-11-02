"""Fit three low boarding pontoons to native stopped-boat positions.

The existing terminal source is read only. Export a small, rebased finite
candidate; installation checks its exact original states against the cold world.
"""
import argparse,json,math
from collections import defaultdict,deque
from pathlib import Path
import numpy as np
from author_hakone_lakefront import Editor
from check_hakone_boat_clearance import check

WOOD='minecraft:spruce_planks'
SLAB='minecraft:spruce_slab[type=bottom,waterlogged=false]'
AIR='minecraft:air'


def author(source,out,samples,model,circuit,world):
    if out.exists():raise ValueError('A fresh immutable candidate is required')
    if not circuit['passed']:raise ValueError('All three native stops must be proven first')
    e=Editor(source);before={};changes={};decks={};supports=[]
    def put(x,y,z,state):
        old=e.state(x,y,z)
        if old==state:return
        p=(x//16,z//16);r=e.region(x,z)
        if p not in before:before[p]=r['after'][r['index'][p]].copy()
        changes.setdefault((x,y,z),old);e.put(x,y,z,state)
    def deck(key,cells):
        decks[key]=cells
        for (x,z),height in cells.items():
            for y in (99,100):
                state=e.state(x,y,z).split('[')[0]
                if state not in (AIR,'minecraft:cave_air','minecraft:water',WOOD,'minecraft:spruce_slab',
                                 'minecraft:stone','minecraft:stone_bricks','minecraft:smooth_stone'):
                    raise ValueError(('Unexpected boarding substrate',x,y,z,state))
            if e.state(x,99,z).split('[')[0]in(AIR,'minecraft:cave_air','minecraft:water'):put(x,99,z,WOOD)
            put(x,100,z,WOOD if height==101 else SLAB if height==100.5 else AIR)
            for y in (101,102):
                state=e.state(x,y,z)
                if state.startswith('minecraft:spruce_fence') and key=='togendai':put(x,y,z,AIR)
                elif state.split('[')[0]not in (AIR,'minecraft:cave_air'):raise ValueError(('Boarding headroom',x,y,z,state))
    deck('motohakone',{(x,z):100 if x<=496 else 100.5 if x==497 else 101
        for x in range(493,500)for z in range(2015,2022)})
    deck('togendai',{(x,z):101 if z==1081 else 100.5 if z==1082 else 100
        for x in range(-306,-299)for z in range(1081,1085)})
    stop=np.array([389.7322330470335,2291.2677669529667]);u=np.array([1,-1])/math.sqrt(2)
    cells={}
    for x in range(384,405):
        for z in range(2286,2308):
            along=float((np.array([x+.5,z+.5])-stop)@u);n=(x+z+1-2681)/math.sqrt(2)
            if x+z>=2683 and n<=11 and abs(along)<=3.5:
                cells[x,z]=100 if n<5.657 else 100.5 if n<8.486 else 101
    deck('hakonemachi',cells)
    for x,z in ((496,2016),(496,2020),(-306,1083),(-300,1083),(394,2294),(396,2296)):
        y=98
        while e.state(x,y,z).startswith('minecraft:water')and y>80:y-=1
        if y==80:raise ValueError('Unbounded pile')
        for yy in range(y+1,99):put(x,yy,z,'minecraft:stripped_spruce_log[axis=y]')
        supports.append([x,y,z,99])
    # Half-block walking heights: no jumping across water or one-block risers.
    def stand(x,feet2,z):
        feet=feet2/2;floor_y=math.ceil(feet)-1;state=e.state(x,floor_y,z)
        surface=floor_y+(.5 if 'slab['in state and 'type=bottom'in state else 1)
        if abs(feet-surface)>.01 or state.split('[')[0]in(AIR,'minecraft:cave_air','minecraft:water'):return False
        for y in range(math.floor(feet),math.ceil(feet+1.8)):
            if y==floor_y:continue
            block=e.state(x,y,z)
            if block.split('[')[0]not in(AIR,'minecraft:cave_air')and not('_door['in block and 'open=true'in block):return False
        return True
    programmes=[('motohakone',(500,202,2018),(493,200,2018),(490,2005,545,2050)),
                ('togendai',(-286,202,1025),(-303,200,1084),(-318,1018,-250,1088)),
                ('hakonemachi',(398,202,2297),(391,200,2292),(382,2288,410,2330))]
    walks=[]
    for key,start,goal,bounds in programmes:
        if not stand(*start):raise ValueError(('Missing public pier origin',key,start))
        queue=deque([start]);seen={start};parents={}
        while queue and goal not in seen:
            x,y,z=queue.popleft()
            for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
                xx,zz=x+dx,z+dz
                if not(bounds[0]<=xx<=bounds[2]and bounds[1]<=zz<=bounds[3]):continue
                for yy in (y,y+1,y-1):
                    q=(xx,yy,zz)
                    if not 200<=yy<=202 or q in seen:continue
                    if stand(*q):seen.add(q);parents[q]=(x,y,z);queue.append(q);break
        if goal not in seen:raise ValueError(('Disconnected boat landing',key))
        path=[goal]
        while path[-1]!=start:path.append(parents[path[-1]])
        walks.append(dict(port=key,path=[[x,y/2,z]for x,y,z in reversed(path)],reachable_cells=len(seen)))
    clearance=check(e,samples,model)
    if clearance['obstructions']:
        print(json.dumps([r for r in clearance['rows']if r['obstructions']],indent=2));raise ValueError('Pontoon obstructs the moving boat')
    # The established native stop centre is within the longitudinal landing span.
    stop_rows=[]
    for s in circuit['stops']:
        centre=np.asarray(s['bogies']).mean((0,1));key='togendai'if centre[0]<0 else'motohakone'if centre[0]>450 else'hakonemachi'
        edge=[(x,z)for(x,z),height in decks[key].items()if height==100]
        from shapely.geometry import Polygon,box
        a=np.asarray(s['bogies'][0]);forward=(a[0]-a[1])[[0,2]];forward/=np.linalg.norm(forward)
        normal=np.array([-forward[1],forward[0]]);c=centre[[0,2]]
        contacts=[]
        for sign in (-1,1):
            doorway=Polygon([c+normal*sign*w+forward*l for w,l in ((1.125,-1),(1.5,-1),(1.5,1),(1.125,1))])
            contacts.append(min(doorway.distance(box(x,z,x+1,z+1))for x,z in edge))
        if min(contacts)>.15:raise ValueError(('Boat doorway beyond supported edge',key,contacts))
        stop_rows.append(dict(port=key,centre=centre.tolist(),doorway_y=float(centre[1]+1),
                              deck_top_y=100,minimum_doorway_gap=min(contacts)))
    (out/'source').mkdir(parents=True);(out/'delta').mkdir()
    regions=[]
    grouped=defaultdict(list)
    for p in before:grouped[p[0]//32,p[1]//32].append(p)
    for (rx,rz),coords in sorted(grouped.items()):
        coords=sorted(coords);r=e.regions[rx,rz];name=f'r.{rx}.{rz}.npz';ranges=[0];indices=[];old=[];new=[]
        for p in coords:
            b=before[p];a=r['after'][r['index'][p]];at=np.flatnonzero((a!=b).ravel()).astype(np.uint32)
            indices.append(at);old.append(b.ravel()[at]);new.append(a.ravel()[at]);ranges.append(ranges[-1]+len(at))
        np.savez_compressed(out/'source'/name,coordinates=np.array(coords,np.int32),blocks=np.stack([before[p]for p in coords]),palette=np.array(r['names']))
        np.savez_compressed(out/'delta'/name,coordinates=np.array(coords,np.int32),ranges=np.array(ranges,np.int64),
            indices=np.concatenate(indices),before=np.concatenate(old),after=np.concatenate(new),palette=np.array(r['names']))
        regions.append(dict(path='delta/'+name,cells=ranges[-1]))
    manifest=dict(world=str(world),source=str(source),regions=regions,cells=sum(r['cells']for r in regions),
        bounds_xz=[-320,1008,543,2335],boarding_walks=walks,boarding_stops=stop_rows,piles=supports,
        world_written=False,progress_files_written=[],shoreline_earthworks=False)
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    (out/'clearance.json').write_text(json.dumps(clearance,indent=2),'utf8')
    print(json.dumps(dict(cells=manifest['cells'],regions=len(regions),boat_clearance_errors=clearance['obstructions'],
                         walkable_ports=len(walks),boarding_stop_checks=len(stop_rows))),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('source','out','samples','model','circuit','world'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();read=lambda path:json.loads(path.read_text('utf8'))
    author(a.source,a.out,read(a.samples),read(a.model),read(a.circuit),a.world)
