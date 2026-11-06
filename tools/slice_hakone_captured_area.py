"""Extract complete measured chunks from an immutable larger saved snapshot."""
import argparse,json
from pathlib import Path
import numpy as np

def extract(a):
    c=json.loads((a.source/'capture.json').read_text('utf8'));x,z,X,Z=a.bounds;ox,oz,oX,oZ=c['bounds_xz']
    if x%16 or z%16 or (X+1)%16 or (Z+1)%16:raise ValueError('Crop must contain whole chunks')
    if not(ox<=x<X<=oX and oz<=z<Z<=oZ):raise ValueError('Crop exceeds captured source')
    q=np.s_[z-oz:Z-oz+1,x-ox:X-ox+1]
    with np.load(a.source/'measured.npz')as f:d={k:(np.asarray(a.bounds)if k=='bounds'else f[k][q].copy())for k in f.files}
    if not d['full'].all():raise ValueError('Crop includes unmeasured saved terrain')
    a.out.mkdir(parents=True,exist_ok=False);(a.out/'source').mkdir();(a.out/'delta').mkdir();files=[];seen=set()
    for rx in range(x//512,X//512+1):
        for rz in range(z//512,Z//512+1):
            name=f'r.{rx}.{rz}.npz'
            with np.load(a.source/'source'/name)as f:
                coords=f['coordinates'];keep=(coords[:,0]*16>=x)&(coords[:,0]*16<=X)&(coords[:,1]*16>=z)&(coords[:,1]*16<=Z)
                if not keep.any():continue
                blocks=f['blocks'][keep];palette=f['palette'];coords=coords[keep]
            for p in coords:
                key=tuple(map(int,p))
                if key in seen:raise ValueError('Duplicate source chunk')
                seen.add(key)
            np.savez_compressed(a.out/'source'/name,coordinates=coords,palette=palette,blocks=blocks);files.append('source/'+name)
    expected=(X-x+1)*(Z-z+1)//256
    if len(seen)!=expected:raise ValueError('Incomplete crop chunk set')
    # Keep nearby actor records as well as the sliced occupancy mask; a centre
    # outside the crop is not evidence that its physical body is absent.
    actors=[r for r in c['actors']if x-32<=r['pos'][0]<=X+32 and z-32<=r['pos'][2]<=Z+32]
    np.savez_compressed(a.out/'measured.npz',**d)
    report=dict(world=c['world'],bounds_xz=a.bounds,source_files=files,actors=actors,chunk_statuses=dict(full=expected),unavailable_chunks=[],
        parent_capture=str(a.source),parent_capture_scope=c['bounds_xz'],nearby_actor_records_retained=True,world_written=False)
    (a.out/'capture.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('Extracted',expected,'measured FULL chunks;',len(actors),'nearby actor records; no world writes.',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('source','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--bounds',nargs=4,type=int,required=True);extract(p.parse_args())
