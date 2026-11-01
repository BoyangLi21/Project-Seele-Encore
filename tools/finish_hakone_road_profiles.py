"""Retain measured bridge clearances and finish the final paved assembly."""
import argparse,json
from pathlib import Path
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from author_hakone_lakefront import Editor
from repair_hakone_surface_ownership import load_grid
from hakone_earthworks import road_blocks
from verify_hakone_network_candidate import PAVEMENT
from plan_ashi_landscape_r54 import NATURAL
from query_blocks import AIR


def run(a):
    d=load_grid(a.plan/'network.npz');report=json.loads((a.candidate/'functional-check.json').read_text('utf8'));walk=d['walk'];z,x=np.nonzero(walk);n=len(x);ids=np.full(walk.shape,-1,np.int32);ids[z,x]=np.arange(n)
    x0,z0,_,_=d['bounds'];current=d['grade2'][z,x];original=d['previous_grade2'][z,x];pins={};repave=set()
    for row in report['errors']:
        if row[0]not in ('connector-object','actual-road-floor-or-body'):continue
        X,Y,Z=row[1:4];i=ids[Z-z0,X-x0]
        if i<0:raise ValueError('Error outside commissioned road')
        repave.add(i)
        if row[0]=='connector-object':pins[int(i)]=int(original[i])
    rr=[];cc=[]
    for aa,bb in [(np.s_[1:,:],np.s_[:-1,:]),(np.s_[:,1:],np.s_[:,:-1])]:
        use=walk[aa]&walk[bb];r=ids[aa][use];c=ids[bb][use];rr.extend((r,c));cc.extend((c,r))
    rr=np.concatenate(rr);cc=np.concatenate(cc);weights=np.maximum(1,abs(original[rr].astype(int)-original[cc]))
    result=current.copy()
    if pins:
        pi=np.array(list(pins));pv=np.array(list(pins.values()))
        graph=coo_matrix((np.r_[weights,1000-pv],(np.r_[rr,np.full(len(pi),n)],np.r_[cc,pi])),shape=(n+1,n+1)).tocsr()
        lower=1000-dijkstra(graph,directed=True,indices=n)[:n];result=np.maximum(current,np.rint(lower)).astype(np.int16)
    repave.update(np.flatnonzero(result!=current));d['grade2'][z,x]=result;d['regraded_walk']=walk&(d['grade2']!=d['previous_grade2'])
    e=Editor(a.candidate);remaining=[]
    allowed=NATURAL|PAVEMENT|{'minecraft:light','minecraft:iron_bars','minecraft:sea_lantern'}
    for i in sorted(repave,key=lambda i:((x[i]+x0)//512,(z[i]+z0)//512)):
        X,Z=int(x[i]+x0),int(z[i]+z0);y,slab=road_blocks(result[i]);y=int(y)
        states=[e.state(X,Y,Z)for Y in range(y,y+3)]
        if any(s.split('[')[0]not in allowed for s in states):remaining.append(['road-retained-object',X,y,Z,states]);continue
        oldy=max(int(road_blocks(current[i])[0]),int(road_blocks(original[i])[0]))
        for Y in range(min(y,oldy)-1,max(y+2,oldy+2)+1):
            state=e.state(X,Y,Z).split('[')[0]
            if state not in allowed:continue
            if Y<y:e.put(X,Y,Z,'minecraft:stone')
            elif Y>y:e.put(X,Y,Z,'minecraft:air')
        road=bool(d['road'][z[i],x[i]]);mark=bool(d['marking'][z[i],x[i]])
        name=(('projectseele:road_marking_slab'if mark else 'projectseele:road_asphalt_slab'if road else 'minecraft:smooth_stone_slab')+'[type=bottom,waterlogged=false]')if slab else 'minecraft:white_concrete'if mark else 'minecraft:black_concrete'if road else 'minecraft:smooth_stone'
        e.put(X,y,Z,name)
        if len(e.regions)>2:e.save();e.regions.clear()
    rows=e.save();manifest=json.loads((a.candidate/'manifest.json').read_text('utf8'));manifest.update(regions=rows,cells=sum(r['cells']for r in rows));(a.candidate/'manifest.json').write_text(json.dumps(manifest,indent=2),'utf8')
    # Retain the initial failures as provenance; the caller checks the complete
    # final widths again and reports any still-unresolved geometry.
    report['initial_profile_conflicts']=report['errors'];report['errors']=remaining
    (a.candidate/'functional-check.json').write_text(json.dumps(report,indent=2),'utf8')
    np.savez_compressed(a.plan/'network.npz',**d)
    print('Finished measured road columns',len(repave),'retained ports',len(pins),'unresolved',len(remaining),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('candidate','plan'):p.add_argument('--'+n,type=Path,required=True)
    run(p.parse_args())
