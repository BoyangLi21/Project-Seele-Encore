"""Check the actual paired triangles, including face and edge interior probes."""
from pathlib import Path
import argparse,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.Codex/geometry-runtime'))
import igl


def main(folder):
    hero=np.load(folder/'hero_frames.npz');angel=np.load(folder/'surface_frames.npz')
    hf=np.arange(hero['positions'].shape[1]).reshape(-1,3);af=angel['indices'].reshape(-1,3)
    edge=np.unique(np.sort(np.vstack([af[:,[0,1]],af[:,[1,2]],af[:,[2,0]]]),axis=1),axis=0);rows=[]
    for i,(h,a) in enumerate(zip(hero['positions'],angel['positions'])):
        h=h.astype(float);points=np.vstack([a,a[af].mean(1),a[edge].mean(1)])
        winding=igl.fast_winding_number(h,hf,points);distance,_,_=igl.point_mesh_squared_distance(points,h,hf)
        bad=(abs(winding)>.5)&(distance>.15**2);n=len(a);t=len(af)
        rows.append(dict(frame=489+i,vertices=int(sum(bad[:n])),triangle_centres=int(sum(bad[n:n+t])),edge_centres=int(sum(bad[n+t:])),
                         deepest=float(np.sqrt(distance[bad]).max()) if bad.any() else 0))
    out=dict(method='Actual private rendered mesh; generalized winding number plus closest triangle distance. Vertex/face/edge sampling, not proof of zero exact triangle intersections.',
             tolerance_blocks=.15,worst=max(rows,key=lambda x:x['deepest']),frames=rows)
    (folder/'actual_mesh_audit.json').write_text(json.dumps(out,indent=2));print(out['worst'],flush=True)
    print('Frames with interior probes',sum(r['deepest']>0 for r in rows),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);main(p.parse_args().folder)
