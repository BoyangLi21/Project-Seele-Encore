"""Verify authored city entrances, original contents and actual street links."""
import argparse,copy,json
from pathlib import Path
import nbtlib,numpy as np


def verify(candidate,source,retained=None):
    with np.load(source/'blocks.npz')as a:blocks=a['blocks'].copy();palette=list(map(str,a['palette']))
    ids={s:i for i,s in enumerate(palette)};x0,z0=-352,-128
    for file in (candidate/'delta').glob('*.npz'):
        with np.load(file)as a:
            codes=[]
            for s in map(str,a['palette']):
                if s not in ids:ids[s]=len(palette);palette.append(s)
                codes.append(ids[s])
            codes=np.asarray(codes,np.uint16)
            points,ranges,indices,after=(a[k]for k in ('coordinates','ranges','indices','after'))
            for n,(cx,cz)in enumerate(points):
                l,r=ranges[n:n+2];at=indices[l:r];y=at//256;z=(at//16)%16;x=at%16
                blocks[y,cz*16+z-z0,cx*16+x-x0]=codes[after[l:r]]
    def state(x,y,z):return palette[int(blocks[y+128,z-z0,x-x0])]
    def air(x,y,z):return state(x,y,z).split('[')[0]in ('minecraft:air','minecraft:cave_air','minecraft:void_air')
    def content(t):
        t=copy.deepcopy(t)
        for k in ('x','y','z'):t.pop(k,None)
        return t
    changes=nbtlib.load(candidate/'block-entities.dat')['Changes'];before={};after={}
    for r in changes:
        for key,target in [('Before',before),('After',after)]:
            if key in r:
                t=r[key];target[tuple(int(t[k])for k in ('x','y','z'))]=t
    errors=[];devices=0;walk=0
    def check_walk(points,kind):
        nonlocal walk
        for x,y,z in points:
            if not air(x,y,z)or not air(x,y+1,z):errors.append([kind+'-headroom',x,y,z,state(x,y,z),state(x,y+1,z)])
            if air(x,y-1,z):errors.append([kind+'-floor',x,y,z])
            walk+=1
    for row in json.loads((candidate/'neighbourhood.json').read_text('utf8')):
        for device in row['devices']:
            if content(before[tuple(device['source'])])!=content(after[tuple(device['target'])]):errors.append(['inventory',device])
            devices+=1
        check_walk(row['footway'],'neighbourhood')
        if row['kind']!='building':continue
        a,f,b,d,_,e=row['bounds'];x,y,z=row['door']
        for dx in (0,1):
            if 'oak_door'not in state(x+dx,y,z)or 'oak_door'not in state(x+dx,y+1,z):errors.append(['door',row['id']])
        for level in range(row['floors']-1):
            check_walk([[a+4,f+level*5+step+2,b+3+step]for step in range(5)],'interior-stair')
    maint=json.loads((candidate/'maintenance.json').read_text('utf8'));check_walk(maint['stairs'],'maintenance')
    for row in maint['connections']:
        x,z=row['ladder'];base=row['landing']
        for y in (-111,base,base+1):
            if 'ladder'not in state(x,y,z):errors.append(['ladder',row['index'],x,y,z])
        if air(x,base,z-1):errors.append(['lower-apron',row['index']])
    links=json.loads((candidate/'street-connections.json').read_text('utf8'))
    for row in links:check_walk(row['points'],'street-link')
    retained_count=0
    if retained:
        current=candidate/'retained-neighbourhood.json'
        for row in json.loads((current if current.exists()else retained).read_text('utf8')):
            for item in row['devices']:
                if tuple(item['target'])in before or tuple(item['target'])in after:errors.append(['retained-inventory',item])
                retained_count+=1
            check_walk(row.get('footway',[]),'retained-footway')
    report=dict(errors=errors,preserved_parcel_devices=devices,retained_parcel_devices=retained_count,
                walk_points=walk,lower_connections=len(maint['connections']),street_links=len(links),visual_verified=False)
    (candidate/'functional-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(report,ensure_ascii=False),flush=True)
    np.savez_compressed(candidate/'assembled.npz',blocks=blocks,palette=np.asarray(palette))
    if errors:raise ValueError('Unresolved authored city interfaces')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('candidate',type=Path);p.add_argument('source',type=Path);p.add_argument('--retained',type=Path)
    a=p.parse_args();verify(a.candidate,a.source,a.retained)
