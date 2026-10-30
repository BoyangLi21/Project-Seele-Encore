"""Export cached GSI heights for fresh chunks; no network or save writes."""
import argparse,gzip,json,struct
from pathlib import Path
import numpy as np
from prepare_hakone_main_terrain import sample_grid


def export(gis,out):
    with np.load(gis/'terrain-design.npz')as f:d={k:f[k]for k in('x','z','height_y','sea')}
    with np.load(gis/'lake-basin-mask.npz')as f:lake=f['lake']
    height=d['height_y'].copy();water=np.full(height.shape,-32768,np.int16)
    # Forty-two missing coastal DEM cells form one small gap. Interpolate
    # only that gap from measured neighbours rather than casting NaN to zero.
    missing=~np.isfinite(height)
    for z,x in zip(*np.where(missing)):
        patch=height[max(0,z-8):z+9,max(0,x-8):x+9]
        samples=patch[np.isfinite(patch)]
        if not len(samples):raise ValueError('DEM gap exceeds the local interpolation limit')
        height[z,x]=float(np.median(samples))
    height[d['sea']]=np.minimum(height[d['sea']],-90);water[d['sea']]=-82
    with np.load(gis/'lake-basin-ready/surface.npz')as f:
        bounds=f['bounds'];bed=f['target'];wet=f['lake']
    z,x=np.nonzero(lake);X=d['x'][x];Z=d['z'][z]
    inside=(X>=bounds[0])&(X<=bounds[2])&(Z>=bounds[1])&(Z<=bounds[3])
    if not inside.all():raise ValueError('Installed Ashi bed does not cover the recorded mask')
    height[z,x]=np.minimum(bed[Z-bounds[1],X-bounds[0]],98);water[lake]=99
    fixed=np.rint(np.clip(height,-120,305)*16).astype('>i2')
    out.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(out,'wb',compresslevel=6)as f:
        f.write(struct.pack('>6i',0x484B3535,int(d['x'][0]),int(d['z'][0]),int(d['x'][1]-d['x'][0]),len(d['x']),len(d['z'])))
        f.write(fixed.tobytes());f.write(water.astype('>i2').tobytes())
    np.savez_compressed(gis/'runtime-surface-field.npz',x=d['x'],z=d['z'],height_y=fixed.astype(np.float64)/16,water=water)
    print(json.dumps(dict(resource=str(out),bytes=out.stat().st_size,shape=height.shape,sea_y=-82,lake_y=99)))


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--gis',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();export(a.gis,a.out)
