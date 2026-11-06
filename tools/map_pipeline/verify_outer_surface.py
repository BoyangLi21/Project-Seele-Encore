"""Compare exact pending native terrain with its measured FULL neighbors."""
import argparse,json
from pathlib import Path
import numpy as np
from map_pipeline.outer_surface_field import Sampler


def verify(a):
    field=Sampler(a.field,a.blend)
    rows=np.loadtxt(a.native,skiprows=1,delimiter=',',dtype=np.int32).reshape(-1,256,4)
    tiles={}
    def tile(rx,rz):
        if(rx,rz)not in tiles:tiles[rx,rz]=[np.full((512,512),-129,np.int16),np.full((512,512),-32768,np.int16),np.zeros((512,512),bool),np.zeros((512,512),bool)]
        return tiles[rx,rz]
    for row in rows:
        x=row[:,0].reshape(16,16);z=row[:,1].reshape(16,16);cx=int(x[0,0])//16;cz=int(z[0,0])//16
        h,w=field.sample(x,z,row[:,2].reshape(16,16));d=tile(cx//32,cz//32)
        s=np.s_[cz%32*16:cz%32*16+16,cx%32*16:cx%32*16+16]
        d[0][s]=h;d[1][s]=w;d[2][s]=True;d[3][s]=True
    for p in a.survey.glob('r.*.npz'):
        rx,rz=map(int,p.stem.split('.')[1:]);d=tile(rx,rz)
        with np.load(p)as f:h=f['ground'].copy();w=f['water'].copy();known=f['full']
        bank=a.banks/'earthworks'/p.name
        if bank.exists():
            with np.load(bank)as f:h[f['active']]=f['target'][f['active']];w[f['wet']]=62
        d[0][known]=h[known];d[1][known]=w[known];d[2][known]=True
    if a.water_closures:
        for r in json.loads(a.water_closures.read_text())['columns']:
            x,z=r['x'],r['z'];d=tiles[x//512,z//512]
            if not d[3][z%512,x%512]:raise ValueError('Water closure is not a pending column')
            d[1][z%512,x%512]=r['water']
    bad=[];small=0;minor=[]
    def difference(h,w,H,W):
        return np.maximum(np.where(w>h,w-np.maximum(H,W),0),np.where(W>H,W-np.maximum(h,w),0))
    for (rx,rz),(h,w,k,proto)in tiles.items():
        for axis in(0,1):
            l=[slice(None),slice(None)];r=l.copy();l[axis]=slice(None,-1);r[axis]=slice(1,None);l=tuple(l);r=tuple(r)
            diff=difference(h[l],w[l],h[r],w[r]);valid=k[l]&k[r]&(proto[l]|proto[r])
            small+=int((valid&(diff>0)&(diff<=3)).sum())
            for j,i in np.argwhere(valid&(diff>0)&(diff<=3)):
                if len(minor)<100:minor.append([rx*512+int(i),rz*512+int(j),axis,int(diff[j,i])])
            for j,i in np.argwhere(valid&(diff>3)):bad.append([rx*512+int(i),rz*512+int(j),axis,int(diff[j,i])])
        for dx,dz in((1,0),(0,1)):
            if(rx+dx,rz+dz)not in tiles:continue
            H,W,K,P=tiles[rx+dx,rz+dz];l=np.s_[:,-1]if dx else np.s_[-1,:];r=np.s_[:,0]if dx else np.s_[0,:]
            diff=difference(h[l],w[l],H[r],W[r]);valid=k[l]&K[r]&(proto[l]|P[r])
            small+=int((valid&(diff>0)&(diff<=3)).sum())
            for i in np.flatnonzero(valid&(diff>0)&(diff<=3)):
                if len(minor)<100:minor.append([rx*512+(511 if dx else int(i)),rz*512+(int(i)if dx else 511),2+dx,int(diff[i])])
            for i in np.flatnonzero(valid&(diff>3)):
                bad.append([rx*512+(511 if dx else int(i)),rz*512+(int(i)if dx else 511),2+dx,int(diff[i])])
    report=dict(exposed_edges_above3=len(bad),exposed_edges_1to3=small,examples=bad[:100],minor_examples=minor,
        exact_native_proto_chunks=len(rows),full_outer_regions=len(list(a.survey.glob('r.*.npz'))))
    a.out.write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report,indent=2),flush=True)
    if bad:raise ValueError('Outer water interface is not closed')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for k in('native','field','blend','survey','banks','out'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--water-closures',type=Path)
    verify(p.parse_args())
