"""Check saved station-to-platform access without crossing the running railway.

Wooden doors are treated as manually operable. This is a pedestrian voxel
check; train dispatch and rendered train clearance are separate validations.
"""
import argparse,json,math
from collections import deque
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from author_hakone_lakefront import Editor
from query_blocks import AIR
from verify_hakone_network_candidate import PAVEMENT

def verify(candidate):
    rows=[r for r in json.loads((candidate/'plan/buildings.json').read_text('utf8'))if r.get('kind')=='station']
    curves=json.loads((candidate/'plan/native-curves.json').read_text('utf8'))
    rails=np.concatenate([r['points']for r in curves['trains']]);tree=cKDTree(rails[:,[0,2]])
    with np.load(candidate/'plan/network.npz')as f:d={k:f[k]for k in('bounds','walk','grade2')}
    x,z,X,Z=map(int,d['bounds']);e=Editor(candidate);results=[];errors=[]
    floor_materials=PAVEMENT|{'minecraft:gravel','projectseele:period_station_floor','projectseele:nerv_floor_panel','minecraft:stone_bricks','minecraft:polished_andesite'}
    for r in rows:
        a=np.asarray(r['approach'],float);p=np.asarray(r['platform'],float);p[1]+=1
        # The route may go around waiting-room walls, but cannot leave this
        # station to return via an unrelated crossing elsewhere in the map.
        l,t=max(x,int(min(a[0],p[0]))-24),max(z,int(min(a[2],p[2]))-24)
        R,B=min(X,int(max(a[0],p[0]))+24),min(Z,int(max(a[2],p[2]))+24)
        low,high=math.floor(min(a[1],p[1]))-12,math.ceil(max(a[1],p[1]))+12
        standing=set();blocked_rail=0
        for px in range(l,R+1):
            for pz in range(t,B+1):
                distances,indexes=tree.query([px+.5,pz+.5],k=min(12,len(rails)))
                near=rails[np.asarray(indexes)[np.asarray(distances)<2.25]]
                region=e.region(px,pz);v=region['after'][region['index'][px//16,pz//16],:,pz%16,px%16];names=region['names']
                for py in range(low,high+1):
                    floor=names[v[py+127]];mat=floor.split('[')[0]
                    if mat not in floor_materials and not mat.endswith(('_planks','_stairs')):continue
                    # Store standing height in half-block units. Omitting
                    # bottom slabs incorrectly split real entrance paths.
                    standing_y2=2*py-(1 if 'type=bottom'in floor else 0)
                    head=[names[v[Y+128]].split('[')[0]for Y in(py,py+1)]
                    if any(s not in AIR|{'minecraft:light'}and not(s.endswith('_door')and s!='minecraft:iron_door')for s in head):continue
                    if len(near)and np.any((standing_y2/2>=near[:,1]-1)&(standing_y2/2<=near[:,1]+5)):
                        blocked_rail+=1;continue
                    standing.add((px,standing_y2,pz))
        start=(int(a[0]),int(round(a[1]*2)),int(a[2]));goal=(int(p[0]),int(round(p[1]*2)),int(p[2]));previous={start:None}if start in standing else{};queue=deque(previous)
        while queue and goal not in previous:
            px,py,pz=queue.popleft()
            for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
                for dy in(0,1,-1,2,-2):
                    q=px+dx,py+dy,pz+dz
                    if q in standing and q not in previous:previous[q]=(px,py,pz);queue.append(q)
        reached=goal in previous;path=[]
        if reached:
            q=goal
            while q is not None:path.append([q[0],q[1]/2,q[2]]);q=previous[q]
            path.reverse()
        else:errors.append(['station platform unreachable without crossing track',r['id'],a.tolist(),p.tolist()])
        results.append(dict(station=r['station_id'],approach=a.tolist(),platform=p.tolist(),connected=reached,visited=len(previous),running_track_positions_excluded=blocked_rail,path=path,wooden_doors_treated_as_operable=True,half_block_floors_supported=True))
    report=dict(stations=results,errors=errors,world_written=False,game_ui_verification=False)
    (candidate/'station-access-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(stations=[dict(station=r['station'],connected=r['connected'],path_positions=len(r['path']),visited=r['visited'])for r in results],errors=errors),ensure_ascii=False),flush=True)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--candidate',type=Path,required=True);a=p.parse_args()
    if verify(a.candidate)['errors']:raise SystemExit(1)
