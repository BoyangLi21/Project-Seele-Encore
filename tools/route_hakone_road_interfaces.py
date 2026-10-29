"""Reroute surface street approaches around measured retained infrastructure."""
import argparse,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
from prepare_hakone_main_districts import line,route


def plan(folder):
    layout=json.loads((folder/'district-plan.json').read_text('utf8'))
    with np.load(folder/'district-plan.npz')as f:d={k:f[k]for k in f.files}
    with np.load(folder/'district-surface.npz')as f:s={k:f[k]for k in ('target','ground_obstruction')}
    bounds=layout['bounds_xz'];x0,z0,x1,z1=bounds;shape=d['fixed'].shape
    obstacle=s['ground_obstruction'];blocked=obstacle|d['fixed']|d['water']
    for row in json.loads((folder/'neighbourhood.json').read_text('utf8')):
        site=row['site'];x,z=site['centre'];hx,hz=site['half'];hx,hz=(hx,hz)if site['rotation']%2==0 else(hz,hx)
        blocked[z-hz-z0-3:z+hz-z0+4,x-hx-x0-3:x+hx-x0+4]=True
        for px,py,pz in row['footway']:blocked[pz-z0,px-x0]=True
    blocked=np.asarray(Image.fromarray(blocked).filter(ImageFilter.MaxFilter(13)),bool)
    clear=np.asarray(Image.fromarray(obstacle).filter(ImageFilter.MaxFilter(13)),bool)
    paths=[];deferred=[];keys=set()
    for street in layout['streets']:
        if not street['width']or street['tunnel']:continue
        points=[]
        for p,q in zip(street['points'],street['points'][1:]):
            for x,z in line(tuple(map(round,p)),tuple(map(round,q))):
                if x0+8<=x<=x1-8 and z0+8<=z<=z1-8 and(not points or points[-1]!=(x,z)):points.append((x,z))
        if len(points)<3:continue
        mask=[bool(blocked[z-z0,x-x0])for x,z in points]
        i=0
        while i<len(points):
            if not mask[i]:i+=1;continue
            start=i
            while i<len(points)and mask[i]:i+=1
            stop=i
            if start==0 or stop==len(points):continue
            span=points[start:stop]
            if not any(clear[z-z0,x-x0]for x,z in span):continue
            if any(d['fixed'][z-z0,x-x0]for x,z in span):continue
            p=points[max(0,start-3)];q=points[min(len(points)-1,stop+2)];key=tuple(sorted((p,q)))
            if key in keys:continue
            keys.add(key)
            path=route(p,q,blocked,bounds,limit=120000)
            if path and len(path)<600:paths.append(dict(points=path,width=street['width'],original=span))
            else:deferred.append(dict(start=p,end=q,reason='retained native frontage; no new road through it'))
    np.save(folder/'road-retained-interfaces.npy',clear)
    result=dict(paths=paths,retained_frontages=deferred,source='measured retained infrastructure; offline only')
    (folder/'road-detours.json').write_text(json.dumps(result,indent=2),'utf8')
    print('Road detours',len(paths),'retained frontages',len(deferred),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('candidate',type=Path);plan(p.parse_args().candidate)
