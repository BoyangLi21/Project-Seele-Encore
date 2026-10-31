"""Keep established station halls out of a neighbouring road regrade."""
import argparse,json
from pathlib import Path
import numpy as np
from author_hakone_lakefront import Editor
from repair_hakone_surface_ownership import load_grid,sampled

def apply(a):
    manifest=json.loads((a.candidate/'manifest.json').read_text('utf8'))
    specs=[load_grid(a.candidate.parent/'seams-v1/gora-seam.npz'),load_grid(Path(manifest['terrain_atlas'])/'shore-seam.npz')]
    e=Editor(a.candidate);regions=set();columns=set();restored=0
    for s in specs:
        x,z,X,Z=map(int,s['bounds'])
        for rx in range(x//512,X//512+1):
            for rz in range(z//512,Z//512+1):regions.add((rx,rz))
    for rx,rz in sorted(regions):
        r=e.region(rx*512,rz*512)
        for (cx,cz),b,v in zip(r['coords'],r['before'],r['after']):
            zz,xx=np.mgrid[cz*16:cz*16+16,cx*16:cx*16+16];mask=np.zeros((16,16),bool)
            for s in specs:mask|=sampled(s,'fixed',xx,zz).astype(bool)
            if not mask.any():continue
            changed=(b!=v)&mask
            if not changed.any():continue
            # These retained halls lie outside the city future recipe domain.
            # Refuse to leave an overlapping stale recipe silently in place.
            file=a.candidate/'after/dimensions/projectseele/geofront/data/city_rigid_generation_r45/surface'/f'{cx}_{cz}.dat'
            if file.exists():raise ValueError('Fixed station also requires recipe reconciliation: '+str(file))
            restored+=int(changed.sum());v[changed]=b[changed]
            columns.update((int(xx[iz,ix]),int(zz[iz,ix]))for iz,ix in np.argwhere(mask))
        e.save();e.regions.clear()
    kept=[];resolved=[];check=json.loads((a.candidate/'functional-check.json').read_text('utf8'))
    for error in check['errors']:
        if error[0]=='retained-object-on-regraded-road':
            _,x,y,z=error
            if any(s['bounds'][0]<=x<=s['bounds'][2]and s['bounds'][1]<=z<=s['bounds'][3]and s['fixed'][z-s['bounds'][1],x-s['bounds'][0]]for s in specs):resolved.append(error);continue
        kept.append(error)
    regions=e.save();manifest.update(regions=regions,cells=sum(r['cells']for r in regions),fixed_station_cells_restored=restored)
    check.update(errors=kept,retained_station_hall_columns=len(resolved),visual_verified=False)
    (a.candidate/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    (a.candidate/'functional-check.json').write_text(json.dumps(check,indent=2),'utf8')
    print('Retained original station cells',restored,'resolved classified hall columns',len(resolved),'remaining issues',len(kept),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--candidate',type=Path,required=True);apply(p.parse_args())
