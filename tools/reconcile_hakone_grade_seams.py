"""Jointly solve old batch interfaces while retaining every occupied building."""
import argparse,json
from pathlib import Path
import numpy as np
from hakone_earthworks import grade_development,grade_ground
from repair_hakone_surface_ownership import load_grid,sampled


def design(gis,out):
    out.mkdir(exist_ok=False)
    main=load_grid(gis/'main-district-integration-v1/coupled-grading.npz')
    valley=load_grid(gis/'valley-integration-v12/grading.npz')
    rows=json.loads((gis/'main-district-current-ready-v2/neighbourhood.json').read_text('utf8'))
    rows+=json.loads((gis/'valley-integration-v12/valley-buildings.json').read_text('utf8'))['buildings']
    bounds=[880,560,1151,815];x0,z0,x1,z1=bounds;zz,xx=np.mgrid[z0:z1+1,x0:x1+1]
    target=sampled(main,'target',xx,zz).astype(np.float32)
    use_valley=xx>=1024
    target[use_valley]=sampled(valley,'grade2',xx,zz)[use_valley]/2
    roads=sampled(main,'road',xx,zz).astype(bool)
    walk=sampled(main,'walk',xx,zz).astype(bool)
    roads[use_valley]=sampled(valley,'road',xx,zz)[use_valley]
    walk[use_valley]=sampled(valley,'walk',xx,zz)[use_valley]
    fixed=np.zeros(xx.shape,bool);plots=[];plotmask=fixed.copy()
    for row in rows:
        s=row['site'];x,z=s['centre'];hx,hz=s['half'];hx,hz=(hz,hx)if s['rotation']%2 else(hx,hz)
        if not(x-hx-2>=x0 and x+hx+2<=x1 and z-hz-2>=z0 and z+hz+2<=z1):continue
        area=np.s_[z-hz-2-z0:z+hz+3-z0,x-hx-2-x0:x+hx+3-x0]
        fixed[area]=True;plotmask[area]=True;target[area]=s['floor'];plots.append(area)
    for x,z,X,Z,y in json.loads((gis/'main-district-integration-v1/retained-station-ground.json').read_text('utf8')):
        if not(x0<=x<=X<=x1 and z0<=z<=Z<=z1):continue
        mask=(xx>=x)&(xx<=X)&(zz>=z)&(zz<=Z);fixed[mask]=True;target[mask]=y
    # Preserve the actual interfaces at the outside of this solve. Flexible
    # road interiors adjust between them and the unchanged occupied parcels.
    edge=(xx==x0)|(xx==x1)|(zz==z0)|(zz==z1)
    fixed|=edge&walk
    fitted=grade_development(target*2,walk|plotmask,plots,fixed,slope=2,plot_quantum=2)/2
    ground,conflicts=grade_ground(target,walk|fixed,fitted,slope=1)
    if conflicts.any():raise ValueError('Cannot reconcile seam while retaining building levels')
    np.savez_compressed(out/'gora-seam.npz',bounds=bounds,target=ground,road=roads,walk=walk,grade2=np.rint(fitted*2).astype(np.int16),fixed=fixed,plots=plotmask,old_target=target)
    (out/'design.json').write_text(json.dumps(dict(bounds_xz=bounds,changed_road_columns=int((walk&(target!=fitted)).sum()),
        occupied_parcels=len(plots),building_moves=0,reason='Two installed batches used different grades at X1024'),indent=2),'utf8')
    print((out/'design.json').read_text('utf8'),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--gis',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();design(a.gis,a.out)
