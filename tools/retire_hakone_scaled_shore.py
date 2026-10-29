"""Retire only the recorded R55 scaled-shore construction into real relief.

Unrelated roads and later edits remain protected. The old inverse patch is
never replayed: the new surface comes from the cached GSI elevation grid.
"""
import argparse,gzip,json,shutil
from collections import defaultdict
from pathlib import Path
import numpy as np
from PIL import Image,ImageFilter
from author_hakone_lakefront import Editor
from plan_ashi_landscape_r54 import NATURAL
from prepare_hakone_main_terrain import sample_grid,smooth
from prepare_hakone_lake_basin import distance_from


def retire(a):
    manifest=json.loads((a.candidate/'manifest.json').read_text('utf8'))
    if 'scaled_shore_retired'in manifest:raise ValueError('Already authored')
    with np.load(a.candidate/'surface.npz')as data:s={k:data[k]for k in data.files}
    x0,z0,x1,z1=map(int,s['bounds']);known=defaultdict(list);scope=np.zeros(s['top'].shape,bool)
    with gzip.open(a.forward,'rt',encoding='utf8')as f:
        for line in f:
            r=json.loads(line);x,y,z=r['pos'];state=r['after']
            if r['owner']!='r55/ashi_surface' or r.get('after_nbt') or r.get('before_nbt'):raise ValueError('Unexpected patch owner/device')
            scope[z-z0,x-x0]=True
            if state.split('[')[0]not in NATURAL:known[x//512,z//512].append((x,y,z,state))
    protected=s['protected'].copy();matched=0;preserved=0
    for key,rows in known.items():
        e=Editor(a.candidate);region=e.region(key[0]*512,key[1]*512);allowed=defaultdict(list)
        for x,y,z,state in rows:
            if e.state(x,y,z,True)==state:allowed[x//16,z//16].append((y+128,z%16,x%16));matched+=1
            else:preserved+=1
        natural=np.asarray([n.split('[')[0]in NATURAL for n in region['names']])
        for i,(cx,cz)in enumerate(region['coords']):
            original=region['before'][i];unsafe=~natural[original]
            for p in allowed[cx,cz]:unsafe[p]=False
            area=np.s_[cz*16-z0:cz*16-z0+16,cx*16-x0:cx*16-x0+16]
            protected[area]=unsafe[160:].any(0)
        del e,region
    if 'lakefront_shop'in manifest:
        protected[863-z0:906-z0,-497-x0:-454-x0]=True
        for x,y,z in manifest['lakefront_shop']['public_stair']:
            protected[z-z0-2:z-z0+3,x-x0-2:x-x0+3]=True
    held=protected|~s['full']
    held=np.asarray(Image.fromarray(held).filter(ImageFilter.MaxFilter(13)),bool)
    distance=distance_from(held,64)
    zz,xx=np.mgrid[z0:z1+1,x0:x1+1]
    border=np.minimum.reduce([xx-x0,x1-xx,zz-z0,z1-zz])
    with np.load(a.gis/'terrain-design.npz')as data:grid={k:data[k]for k in ('x','z','height_y')}
    height=sample_grid(grid,'height_y',xx,zz)
    target=np.rint(s['top']+(height-s['top'])*smooth(np.minimum(distance,border)/64)).astype(np.int16)
    scope=np.asarray(Image.fromarray(scope).filter(ImageFilter.MaxFilter(129)),bool)
    active=scope&~held&~s['lake']&s['full']&(border>0)&np.isfinite(height)
    yy=np.arange(-128,320)[:,None,None];changed=[]
    keys=[]
    for rx in range(x0//512,x1//512+1):
        for rz in range(z0//512,z1//512+1):
            if active[max(0,rz*512-z0):min(z1-z0+1,(rz+1)*512-z0),max(0,rx*512-x0):min(x1-x0+1,(rx+1)*512-x0)].any():keys.append((rx,rz))
    for key in sorted(keys):
        rows=known.get(key,[])
        e=Editor(a.candidate);r=e.region(key[0]*512,key[1]*512);allowed=defaultdict(list)
        for x,y,z,state in rows:
            if e.state(x,y,z,True)==state:allowed[x//16,z//16].append((y+128,z%16,x%16))
        natural=np.asarray([n.split('[')[0]in NATURAL for n in r['names']])
        codes=[]
        for state in ('minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]'):
            if state not in r['ids']:r['ids'][state]=len(r['names']);r['names'].append(state)
            codes.append(r['ids'][state])
        for i,(cx,cz)in enumerate(r['coords']):
            area=np.s_[cz*16-z0:cz*16-z0+16,cx*16-x0:cx*16-x0+16];mask=active[area]
            if not mask.any():continue
            b=r['before'][i];h=target[area];permitted=natural[b]
            for p in allowed[cx,cz]:permitted[p]=True
            lower=np.minimum(s['top'][area],h)-3;upper=np.maximum(s['highest'][area],h)
            band=mask[None,:,:]&(yy>=lower)&(yy<=upper)
            unsafe=(band&~permitted).any(0);band&=~unsafe[None,:,:]
            proposed=np.where(yy>h,codes[0],np.where(yy==h,codes[3],np.where(yy>=h-3,codes[2],codes[1])))
            r['after'][i][band]=np.broadcast_to(proposed,b.shape)[band]
        changed+=e.save();del e,r
        print('Retired scaled shoreline in region',key,flush=True)
    regions={r['path']:r for r in manifest['regions']};regions.update({r['path']:r for r in changed})
    manifest.update(regions=list(regions.values()),cells=sum(r['cells']for r in regions.values()),
                    scaled_shore_retired=dict(source=str(a.forward),known_authored_cells=matched,later_edits_preserved=preserved))
    (a.candidate/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    print(manifest['scaled_shore_retired'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for key in ('candidate','gis','forward'):p.add_argument('--'+key,type=Path,required=True)
    retire(p.parse_args())
