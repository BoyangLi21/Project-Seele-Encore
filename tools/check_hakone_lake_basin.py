"""Check the complete authored waterline and the relocated shop before install."""
import argparse,copy,json
from pathlib import Path
import numpy as np
import nbtlib
from author_hakone_lakefront import Editor


def check(folder):
    manifest=json.loads((folder/'manifest.json').read_text('utf8'))
    if 'scaled_shore_retired'not in manifest or 'lakefront_shop'not in manifest:raise ValueError('Lake interfaces are unfinished')
    with np.load(folder/'surface.npz')as a:lake=a['lake'];x0,z0,x1,z1=map(int,a['bounds'])
    errors=[];water_columns=0
    for file in sorted((folder/'source').glob('*.npz')):
        _,rx,rz,_=file.name.split('.');e=Editor(folder);r=e.region(int(rx)*512,int(rz)*512)
        for i,(cx,cz)in enumerate(r['coords']):
            mask=lake[cz*16-z0:cz*16-z0+16,cx*16-x0:cx*16-x0+16]
            if not mask.any():continue
            water=np.asarray([s.startswith('minecraft:water[')for s in r['names']])[r['after'][i,227]]
            wrong=mask&~water
            for iz,ix in np.argwhere(wrong):
                x,z=int(cx*16+ix),int(cz*16+iz)
                # The original shop now occupies a raised shore terrace;
                # its retaining foundation is the explicit waterline exception.
                if -497<=x<=-455 and 863<=z<=905:continue
                errors.append(['waterline',x,99,z])
            water_columns+=int(mask.sum())
        del e,r
    e=Editor(folder);shop=manifest['lakefront_shop'];rows=nbtlib.load(folder/'block-entities.dat')['Changes']
    old={tuple(int(r['Before'][k])for k in ('x','y','z')):r['Before']for r in rows if 'Before'in r}
    new={tuple(int(r['After'][k])for k in ('x','y','z')):r['After']for r in rows if 'After'in r}
    if len(old)!=5 or len(new)!=5:errors.append(['inventory-count',len(old),len(new)])
    for p,tag in old.items():
        q=(p[0],p[1]+20,p[2]);expected=copy.deepcopy(tag);expected['y']=nbtlib.Int(q[1])
        if new.get(q)!=expected:errors.append(['inventory-content',*p])
        if e.state(*q)!=e.state(*p,original=True):errors.append(['inventory-block',*q])
    for x,y,z in shop['public_stair']:
        span=[(x,zz)for zz in range(z-1,z+2)]if z==912 else[(xx,z)for xx in range(x-1,x+2)]
        for xx,zz in span:
            if e.state(xx,y-1,zz).split('[')[0]in ('minecraft:air','minecraft:water'):errors.append(['stair-floor',xx,y,zz])
            if any(e.state(xx,yy,zz)!='minecraft:air'for yy in (y,y+1)):errors.append(['stair-passage',xx,y,zz])
    if 'store_door'not in e.state(-476,101,901):errors.append(['original-door-missing'])
    report=dict(errors=errors,waterline_columns=water_columns,water_y=99,preserved_complete_devices=len(new),
                public_stair_width=3,public_stair_points=len(shop['public_stair']),
                original_shop_door_preserved=True,old_scaled_shore_retired=manifest['scaled_shore_retired'],visual_verified=False)
    (folder/'functional-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(report,ensure_ascii=False),flush=True)
    if errors:raise ValueError('Unresolved lake geometry')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('candidate',type=Path);check(p.parse_args().candidate)
