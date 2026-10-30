"""Check final composed room/stair/street access without starting the game."""
import argparse,json
from collections import deque
from functools import lru_cache
from pathlib import Path
from author_hakone_lakefront import Editor


def check(a):
    data=json.loads((a.candidate/'valley-buildings.json').read_text('utf8'))
    manifest=json.loads((a.candidate/'manifest.json').read_text('utf8'))
    e=Editor(a.candidate);x0,z0,x1,z1=manifest['bounds_xz'];errors=[];rows=[]
    def clear(state):
        name=state.split('[')[0]
        return name in('minecraft:air','minecraft:cave_air','minecraft:void_air')or name.endswith('_door')
    @lru_cache(maxsize=600000)
    def stand(x,y,z):
        if y<=-127 or y>=318 or not x0<=x<=x1 or not z0<=z<=z1:return False
        if not clear(e.state(x,y,z))or not clear(e.state(x,y+1,z)):return False
        below=e.state(x,y-1,z).split('[')[0]
        return below not in('minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:water','minecraft:iron_bars')and not below.endswith('_leaves')
    for index,row in enumerate(data['buildings']):
        goals={'entrance':tuple(row['entrance']),'street':tuple([row['road'][0],row['road'][1]+1,row['road'][2]])}
        if row.get('upper'):goals['upper floor']=tuple(row['upper'])
        if row.get('platform'):p=row['platform'];goals['platform']=(p[0],p[1]+1,p[2])
        points=list(goals.values());site=row['site'];cx,cz=site['centre'];hx,hz=site['half']
        if site['rotation']%2:hx,hz=hz,hx
        left=max(x0,min([p[0]for p in points]+[cx-hx-4])-5);right=min(x1,max([p[0]for p in points]+[cx+hx+4])+5)
        north=max(z0,min([p[2]for p in points]+[cz-hz-4])-5);south=min(z1,max([p[2]for p in points]+[cz+hz+4])+5)
        bottom=min(p[1]for p in points)-2;top=max(p[1]for p in points)+3
        start=goals['entrance'];queue=deque([start]);seen={start}
        if not stand(*start):errors.append([index,row['label'],'blocked entrance',start])
        remaining=set(goals.values())-{start}
        while queue and remaining:
            x,y,z=queue.popleft()
            for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
                xx,zz=x+dx,z+dz
                if not(left<=xx<=right and north<=zz<=south):continue
                for dy in(0,1,-1):
                    q=(xx,y+dy,zz)
                    if q in seen:break
                    if bottom<=q[1]<=top and stand(*q):
                        seen.add(q);queue.append(q);remaining.discard(q);break
            if len(seen)>80000:raise ValueError('Unexpectedly large local public route')
        missing=[name for name,p in goals.items()if p not in seen]
        if missing:errors.append([index,row['label'],'unreachable',missing])
        rows.append(dict(index=index,label=row['label'],connected=not missing,visited=len(seen),goals=goals))
    report=dict(errors=errors,buildings=len(rows),public_goals=sum(len(r['goals'])for r in rows),rows=rows,method='Final block-state traversal with interactable doors and one-block stairs; offline only')
    (a.candidate/'public-access.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    check=json.loads((a.candidate/'functional-check.json').read_text('utf8'));check['errors']=[*check['errors'],*errors];check['public_routes_pending']=bool(errors);check['public_goals']=report['public_goals']
    (a.candidate/'functional-check.json').write_text(json.dumps(check,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(buildings=len(rows),public_goals=report['public_goals'],errors=errors[:16],error_count=len(errors)),ensure_ascii=False),flush=True)
    if errors:raise ValueError('Public access needs a bounded local repair')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--candidate',type=Path,required=True);check(p.parse_args())
