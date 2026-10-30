"""Reconnect three old shop entrances around the later native station buildings."""
import argparse,heapq,json
from functools import lru_cache
from pathlib import Path
import numpy as np
from author_hakone_lakefront import Editor
from plan_ashi_landscape_r54 import NATURAL,AIR


def repair(folder):
    editor=Editor(folder);rows=json.loads((folder/'neighbourhood.json').read_text('utf8'))
    names={'tokyo_west/08-11','tokyo_south/08-05','tokyo_south/11-06'};reports=[]
    with np.load(folder/'district-surface.npz')as f:d={k:f[k]for k in('bounds','road','target')}
    x0,z0,x1,z1=map(int,d['bounds'])
    for row in rows:
        if row['id']not in names:continue
        start=tuple(row['footway'][0]);sx,sy,sz=start
        @lru_cache(maxsize=100000)
        def stand(x,y,z):
            if not(max(x0,sx-80)<=x<=min(x1,sx+80)and max(z0,sz-80)<=z<=min(z1,sz+80)and 32<=y<=305):return False
            if any(editor.state(x,Y,z).split('[')[0]not in AIR for Y in(y,y+1)):return False
            floor=editor.state(x,y-1,z).split('[')[0]
            return floor not in AIR|{'minecraft:water','minecraft:iron_bars'}and not floor.endswith(('_fence','_wall','_leaves'))
        def goal(p):
            x,y,z=p
            return d['road'][z-z0,x-x0]and editor.state(x,y-1,z).split('[')[0]in('minecraft:black_concrete','minecraft:white_concrete','projectseele:road_asphalt_slab','projectseele:road_marking_slab')
        queue=[(0,start)];cost={start:0};previous={};end=None
        while queue:
            value,p=heapq.heappop(queue)
            if value!=cost[p]:continue
            if goal(p):end=p;break
            x,y,z=p
            for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
                for dy in(0,1,-1):
                    q=(x+dx,y+dy,z+dz)
                    if not stand(*q):continue
                    # The side lanes must also be traversable; retain native
                    # pavement and doors rather than cutting through them.
                    side=True
                    for sign in(-1,1):
                        X,Z=q[0]-dz*sign,q[2]+dx*sign
                        if not any(stand(X,q[1]+h,Z)for h in(0,1,-1)):side=False;break
                    if not side:continue
                    step=1 if editor.state(q[0],q[1]-1,q[2]).split('[')[0]not in NATURAL else 2
                    next_cost=value+step+abs(dy)
                    if next_cost<cost.get(q,10**9):cost[q]=next_cost;previous[q]=p;heapq.heappush(queue,(next_cost,q))
                    break
        if end is None:raise ValueError('No existing full-width public route around station '+row['id'])
        path=[end]
        while path[-1]!=start:path.append(previous[path[-1]])
        path.reverse();paved=set()
        for x,y,z in path:
            for X in range(x-1,x+2):
                for Z in range(z-1,z+2):
                    levels=[Y for Y in(y,y-1,y+1)if stand(X,Y,Z)]
                    if not levels:continue
                    Y=levels[0]-1;state=editor.state(X,Y,Z)
                    if state.split('[')[0]in NATURAL-AIR-{'minecraft:water'}:
                        editor.put(X,Y,Z,'minecraft:smooth_stone');paved.add((X,Y,Z))
        row['footway']=[list(p)for p in path];row['site']['street']=[end[0],end[2]]
        reports.append(dict(id=row['id'],start=start,end=end,path=path,new_paving=len(paved)))
        print('Station frontage',row['id'],'connected',len(path),'steps;',len(paved),'paving cells',flush=True)
    regions=editor.save();manifest=json.loads((folder/'manifest.json').read_text('utf8'));manifest['regions']=regions;manifest['cells']=sum(r['cells']for r in regions)
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2),'utf8')
    (folder/'neighbourhood.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf8')
    (folder/'station-frontage-repair.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),'utf8')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('candidate',type=Path);repair(p.parse_args().candidate)
