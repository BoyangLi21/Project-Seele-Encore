"""Gentler whole-width street grades with fixed door, tunnel and bridge ports."""
import argparse,json,shutil
from pathlib import Path
import numpy as np
from scipy.ndimage import binary_dilation
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree
from repair_hakone_surface_ownership import load_grid


def run(a):
    a.out.mkdir(exist_ok=False);d=load_grid(a.base/'network.npz');walk=d['walk'];grade=d['grade2'];z,x=np.nonzero(walk);n=len(x)
    ids=np.full(walk.shape,-1,np.int32);ids[z,x]=np.arange(n);rr=[];cc=[]
    for aa,bb in [(np.s_[1:,:],np.s_[:-1,:]),(np.s_[:,1:],np.s_[:,:-1])]:
        both=walk[aa]&walk[bb];r=ids[aa][both];c=ids[bb][both];rr.extend((r,c));cc.extend((c,r))
    rr=np.concatenate(rr);cc=np.concatenate(cc)
    fixed=walk&(d['core']|d['crossing']|binary_dilation(d['tunnel'],iterations=4))
    # Preserve complete fronts close to original occupied parcels, plus actual
    # footway landings. These are interface pins, never arbitrary slope checks.
    catalog=json.loads((a.base/'catalog.json').read_text('utf8'));x0,z0,_,_=d['bounds'];tree=cKDTree(np.column_stack((x+x0,z+z0)))
    for row in catalog:
        for p in row.get('footway',[])[:3]:
            dist,i=tree.query([p[0],p[2]])
            if dist<6:fixed[z[i],x[i]]=True
    fixed|=walk&binary_dilation(d['held'],iterations=3)
    if a.obstacles:
        mask=np.zeros(walk.shape,bool)
        for r in json.loads(a.obstacles.read_text('utf8'))['errors']:
            if r[0]not in ('actual-road-floor-or-body','connector-object'):continue
            X,Y,Z=r[1:4]
            if x0<=X<x0+walk.shape[1]and z0<=Z<z0+walk.shape[0]:mask[Z-z0,X-x0]=True
        fixed|=walk&binary_dilation(mask,iterations=4)
    edge=np.zeros(walk.shape,bool);edge[[0,-1],:]=True;edge[:,[0,-1]]=True;fixed|=walk&edge
    fids=ids[fixed];values=grade[fixed].astype(float);weights=np.full(len(rr),.5,np.float32)
    original=grade[z,x].astype(float)
    def envelope(indices,heights):
        graph=coo_matrix((np.r_[weights,heights+1000],(np.r_[rr,np.full(len(indices),n)],np.r_[cc,indices])),shape=(n+1,n+1)).tocsr()
        return dijkstra(graph,directed=True,indices=n)[:n]-1000
    retained=np.zeros(n,bool)
    for iteration in range(12):
        hi=envelope(fids,values);lo=-envelope(fids,-values);bad=lo>hi+.01
        if not bad.any():break
        retained|=bad
        # Some existing fixed entrances are too close for a shallower ramp.
        # Keep their existing admissible grade instead of moving the building
        # or averaging incompatible interface elevations.
        use=bad[rr]|bad[cc];weights[use]=np.maximum(1.0,abs(original[rr[use]]-original[cc[use]]))
    else:raise ValueError('Street grade constraints did not converge')
    initial=np.clip(original,lo,hi);result=envelope(np.arange(n),initial)
    # This refinement keeps the established street alignment. Limit cuts to
    # six blocks; larger grade corrections need an explicit new alignment.
    result=np.clip(np.rint(result),original-12,original).astype(np.int16)
    if np.any(result[ids[fixed]]!=grade[fixed]):raise ValueError('A fixed street port moved')
    out=grade.copy();out[z,x]=result;d['grade2']=out
    d['previous_grade2']=grade;d['regraded_walk']=walk&(out!=grade)
    np.savez_compressed(a.out/'network.npz',**d)
    for name in ('catalog.json','station-volumes.json','native-curves.json','street-connectivity.json'):shutil.copy2(a.base/name,a.out/name)
    (a.out/'building-moves.json').write_text('[]','utf8')
    report=dict(road_columns=n,regraded_columns=int(d['regraded_walk'].sum()),fixed_ports=int(fixed.sum()),retained_steeper_interface_columns=int(retained.sum()),maximum_change_halfblocks=int(abs(result-original).max()),target_continuous_grade=.25)
    (a.out/'road-grades.json').write_text(json.dumps(report,indent=2),'utf8');print(report,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('base','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--obstacles',type=Path)
    run(p.parse_args())
