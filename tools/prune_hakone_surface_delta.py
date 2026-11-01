"""Keep geometry changes, discard cosmetic soil churn and protect underground."""
import argparse,json
from pathlib import Path
import numpy as np
from query_blocks import AIR

def run(root):
    total=removed=0;rows=[];chunks=[]
    for file in sorted((root/'delta').glob('*.npz')):
        with np.load(file) as d:old={k:d[k] for k in d.files}
        air=np.array([str(s).split('[')[0] in AIR for s in old['palette']]);coords=[];ranges=[0];indices=[];before=[];after=[]
        for i,(cx,cz) in enumerate(old['coordinates']):
            lo,hi=old['ranges'][i:i+2];at=old['indices'][lo:hi];b=old['before'][lo:hi];v=old['after'][lo:hi]
            signed=at.astype(np.int64);col=signed%256;x=int(cx)*16+col%16;z=int(cz)*16+col//16;y=signed//256-128
            radius=np.hypot(x-30,z-296);t=np.clip((radius-600)/1200,0,1)
            bottom=np.where(radius<1800,np.maximum(-128,-478+np.floor(502*np.sqrt(np.maximum(0,1-t*t)))+18),-128)
            cut_columns=np.unique(col[air[v]!=air[b]])
            keep=np.isin(col,cut_columns)&(y>=bottom)
            removed+=int((~keep).sum())
            if not keep.any():continue
            coords.append([cx,cz]);chunks.append([int(cx),int(cz)]);indices.append(at[keep]);before.append(b[keep]);after.append(v[keep]);ranges.append(ranges[-1]+int(keep.sum()))
        if not coords:file.unlink();continue
        np.savez_compressed(file,coordinates=np.asarray(coords,np.int32),ranges=np.asarray(ranges,np.int64),indices=np.concatenate(indices),before=np.concatenate(before),after=np.concatenate(after),palette=old['palette'])
        rows.append(dict(path='delta/'+file.name,cells=ranges[-1]));total+=ranges[-1]
    report=json.loads((root/'manifest.json').read_text('utf8'));report.update(regions=rows,cells=total,unnecessary_surface_recolouring_removed=removed)
    (root/'manifest.json').write_text(json.dumps(report,indent=2),'utf8');(root/'transport-changed-chunks.json').write_text(json.dumps(chunks),'utf8')
    print('Pruned',root.name,'remaining',total,'cells',len(chunks),'chunks; removed',removed,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('candidate',type=Path);run(p.parse_args().candidate)
