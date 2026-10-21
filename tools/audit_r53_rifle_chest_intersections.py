"""Count triangle edge crossings between a captured rifle and both chest parts.

Consumes native EvaMeshAuditR05 output. Zero crossings must be combined with
visual review; it does not by itself prove all enclosed volumes are disjoint.
"""
from pathlib import Path
import gzip,json,sys
import numpy as np

def intersections(a,b):
    alo,ahi=a.min(1),a.max(1);blo,bhi=b.min(1),b.max(1)
    hits=0
    for i,tri in enumerate(a):
        near=b[(bhi>=alo[i]-1e-6).all(1)&(blo<=ahi[i]+1e-6).all(1)]
        if not len(near):continue
        for first,other in [(np.repeat(tri[None],len(near),0),near),(near,np.repeat(tri[None],len(near),0))]:
            e1=other[:,1]-other[:,0];e2=other[:,2]-other[:,0]
            for k in range(3):
                start=first[:,k];d=first[:,(k+1)%3]-start
                p=np.cross(d,e2);det=np.einsum('ij,ij->i',e1,p);good=np.abs(det)>1e-10
                inv=np.divide(1.,det,out=np.zeros_like(det),where=good)
                t=start-other[:,0];u=np.einsum('ij,ij->i',t,p)*inv
                q=np.cross(t,e1);v=np.einsum('ij,ij->i',d,q)*inv
                frac=np.einsum('ij,ij->i',e2,q)*inv
                hits+=int(np.sum(good&(u>1e-5)&(v>1e-5)&(u+v<1-1e-5)&(frac>1e-5)&(frac<1-1e-5)))
    return hits

if __name__=='__main__':
 for directory in map(Path,sys.argv[1:]):
  rows=[]
  for p in sorted(directory.glob('mesh_*/mesh_0025.json.gz')):
   mesh=json.loads(gzip.decompress(p.read_bytes()));parts=mesh['parts'];gun=np.array(parts['rifle']).reshape(-1,3,3)
   chest=np.concatenate([np.array(parts[n]).reshape(-1,3,3) for n in ['torso_upper','torso_lower']])
   hits=intersections(gun,chest);rows.append(dict(pose=p.parent.name,triangle_edge_crossings=hits))
  (directory/'CHEST_CROSSINGS.json').write_text(json.dumps(rows,indent=2));print(directory.name,rows,flush=True)
