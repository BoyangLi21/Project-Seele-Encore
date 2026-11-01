"""Rejoin the two existing geographic road tunnels to their measured street ports.

The authority is the existing road-tunnel footprint, not arbitrary underground
air. NERV rooms, railway volumes, actors and devices are never regenerated.
"""
import argparse,json
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy.ndimage import label,binary_dilation
from scipy.sparse import coo_matrix,diags
from scipy.sparse.linalg import spsolve
from scipy.sparse.csgraph import dijkstra
from author_hakone_lakefront import Editor
from repair_hakone_surface_ownership import load_grid
from hakone_earthworks import road_blocks
from plan_ashi_landscape_r54 import NATURAL
from verify_hakone_network_candidate import PAVEMENT
from query_blocks import AIR


def run(a):
    d=load_grid(a.plan/'network.npz');x0,z0,_,_=map(int,d['bounds'])
    measured=load_grid(a.components);sizes=np.bincount(measured['component']);major=np.zeros(d['walk'].shape,bool)
    coords=measured['xz'][sizes[measured['component']]>10000];cx,cz=coords.T;inside=(cx>=x0)&(cz>=z0)&(cx<x0+major.shape[1])&(cz<z0+major.shape[0]);major[cz[inside]-z0,cx[inside]-x0]=True
    groups,n=label(d['tunnel'],np.ones((3,3),int));selected=np.zeros(groups.shape,bool)
    for x,z in ((80,-266),(-450,-199)):
        i=int(groups[z-z0,x-x0])
        if not i:raise ValueError('Known road-tunnel footprint is absent')
        selected|=groups==i
    z,x=np.nonzero(selected);ids=np.full(selected.shape,-1,np.int32);ids[z,x]=np.arange(len(x));ports=[]
    terminal={}
    for i in np.unique(groups[selected]):
        at=np.flatnonzero(groups[z,x]==i);coords=np.column_stack((x[at],z[at])).astype(float);center=coords.mean(0)
        axis=np.linalg.svd(coords-center,full_matrices=False)[2][0];projection=(coords-center)@axis
        terminal[int(i)]=(at,axis,projection,projection.min(),projection.max())
    rhs=np.zeros(len(x));degree=np.zeros(len(x));rr=[];cc=[]
    for dz,dx in ((0,1),(0,-1),(1,0),(-1,0)):
        inside=selected[z+dz,x+dx];ii=np.flatnonzero(inside);rr.extend(ii);cc.extend(ids[z[ii]+dz,x[ii]+dx]);degree[ii]+=1
        end=np.zeros(len(x),bool)
        for at,axis,projection,lo,hi in terminal.values():
            along=float(np.dot(axis,[dx,dz]))
            end[at]=((projection<=lo+7)&(along<-.5))|((projection>=hi-7)&(along>.5))
        fixed=~inside&end&d['walk'][z+dz,x+dx]&major[z+dz,x+dx];ii=np.flatnonzero(fixed);degree[ii]+=1;rhs[ii]+=d['grade2'][z[ii]+dz,x[ii]+dx]
        ports.extend(zip(ii,d['grade2'][z[ii]+dz,x[ii]+dx]))
    if not ports:raise ValueError('Tunnel has no measured street interface')
    graph=coo_matrix((-np.ones(len(rr)),(rr,cc)),shape=(len(x),len(x))).tocsr()+diags(degree)
    smooth=spsolve(graph,rhs);count=len(x);rr=np.asarray(rr);cc=np.asarray(cc)
    def envelope(indices,values):
        # Duplicate port constraints use the tightest bound, not sparse-matrix
        # addition of two independent interface values.
        sources={}
        for i,h in zip(indices,values):sources[int(i)]=min(float(h),sources.get(int(i),float('inf')))
        si=np.array(list(sources));sv=np.array(list(sources.values()))
        g=coo_matrix((np.r_[np.full(len(rr),2.),sv+1000],(np.r_[rr,np.full(len(si),count)],np.r_[cc,si])),shape=(count+1,count+1)).tocsr()
        return dijkstra(g,indices=count,directed=True)[:count]-1000
    pi,pv=np.array(ports).T;upper=envelope(pi,pv+2);lower=-envelope(pi,-pv+2)
    if a.retain_below:
        ri=[];rv=[]
        for X,Y,Z in a.retain_below:
            i=int(ids[Z-z0,X-x0])
            if i<0:raise ValueError('Retained device is outside this road tunnel')
            ri.append(i);rv.append(-2*(Y+1))
        lower=np.maximum(lower,-envelope(ri,rv))
    if np.any(lower>upper):raise ValueError('Actual portal heights need a longer external ramp')
    grade=np.rint(envelope(np.arange(count),np.clip(smooth,lower,upper))).astype(np.int16)
    jumps=abs(grade[np.array(rr)]-grade[np.array(cc)])
    if jumps.max()>2 or max(abs(int(grade[i])-int(h))for i,h in ports)>2:
        worst=sorted([(abs(int(grade[i])-int(h)),int(x[i]+x0),int(z[i]+z0),int(grade[i]),int(h))for i,h in ports],reverse=True)[:10]
        raise ValueError('Measured tunnel interfaces cannot connect at one block per step: '+str((int(jumps.max()),worst)))
    e=Editor(a.candidate);catalog=json.loads((a.plan/'catalog.json').read_text('utf8'))
    boxes=[r['occupied_bounds']for r in catalog]+json.loads((a.plan/'station-volumes.json').read_text('utf8'))
    proposals=[];errors=[];oldfloors=[];allowed=NATURAL|PAVEMENT|{'minecraft:light','minecraft:sea_lantern','minecraft:iron_bars'}
    for i in np.argsort((x+x0)//512*100+(z+z0)//512):
        X,Z=int(x[i]+x0),int(z[i]+z0);r=e.region(X,Z);v=r['after'][r['index'][X//16,Z//16],:,Z%16,X%16];names=r['names']
        # The lower paved layer is the road; the second six blocks above is
        # its crown. Find it only inside this recorded geographic road bore.
        floors=[y for y in range(60,150)if names[v[y+128]].split('[')[0]in PAVEMENT and all(names[v[Y+128]].split('[')[0]in AIR|{'minecraft:light'}for Y in(y+1,y+2))]
        if not floors:errors.append(['unmeasured-tunnel-floor',X,Z]);continue
        old=floors[0];y,slab=road_blocks(grade[i]);y=int(y);oldfloors.append([X,old,Z]);lo=min(old,y)-1;hi=max(old+6,y+6)
        cover=any(names[v[Y+128]].split('[')[0]in NATURAL-AIR for Y in range(hi+1,min(319,hi+14)))
        for Y in range(lo,hi+1):
            state=names[v[Y+128]];bare=state.split('[')[0]
            new='minecraft:stone'if Y<y else 'minecraft:air'
            if Y==y:
                # Marking follows the recorded tunnel carriage, keeping the
                # whole fifteen-block footprint traversable at both ends.
                new='projectseele:road_asphalt_slab[type=bottom,waterlogged=false]'if slab else 'minecraft:black_concrete'
            elif Y==y+6 and cover:new='minecraft:smooth_stone'
            if state==new:continue
            if Y<y and bare not in allowed:continue
            if bare not in allowed or any(b[0]<=X<=b[3]and b[2]<=Z<=b[5]and b[1]<=Y<=b[4]for b in boxes):
                errors.append(['retained-tunnel-object',X,Y,Z,state]);continue
            proposals.append((X,Y,Z,new))
        if len(e.regions)>2:e.regions.clear()
    report=dict(columns=len(x),interfaces=len(ports),max_adjacent_halfblocks=int(jumps.max()),errors=errors,old_floors=oldfloors,geographic_road_tunnels_only=True)
    (a.candidate/'road-tunnel-reconnection.json').write_text(json.dumps(report,indent=2),'utf8')
    if errors:raise ValueError('Tunnel composition has unresolved measured objects: '+str(errors[:8]))
    touched=set()
    for X,Y,Z,state in proposals:e.put(X,Y,Z,state);touched.add(f'r.{X//512}.{Z//512}.npz')
    rows=e.save();manifest=json.loads((a.candidate/'manifest.json').read_text('utf8'));manifest.update(regions=rows,cells=sum(r['cells']for r in rows));(a.candidate/'manifest.json').write_text(json.dumps(manifest,indent=2),'utf8')
    d['walk'][selected]=True;d['road'][selected]=True;d['grade2'][z,x]=grade
    np.savez_compressed(a.plan/'network.npz',**d)
    report.update(changed_cells=len(proposals),regions=sorted(touched));(a.candidate/'road-tunnel-reconnection.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items()if k!='old_floors'}))


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('candidate','plan','components'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--retain-below',type=int,nargs=3,action='append')
    run(p.parse_args())
