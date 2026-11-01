"""Independent saved-voxel connected components and terrain discontinuities.

Reads all FULL surface chunks, joins component faces across region boundaries,
and treats missing neighbors as UNKNOWN. No edits or gameplay hooks.
"""
import argparse,json,os,shutil
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from collections import defaultdict
import numpy as np
from scipy.ndimage import label,find_objects,grey_opening,maximum_filter
from query_blocks import AIR
from plan_ashi_landscape_r54 import SOIL

def scan(job):
    source,out,name=map(Path,job);rx,rz=map(int,name.stem.split('.')[1:])
    from author_hakone_lakefront import Editor
    e=Editor(source);r=e.region(rx*512,rz*512)
    coords,chunks,names=r['coords'],r['after'],r['names']
    bare=[s.split('[')[0]for s in names]
    invisible=AIR|{'minecraft:water','minecraft:lava','minecraft:light','minecraft:barrier','minecraft:structure_void'}
    solid_lookup=np.array([s not in invisible for s in bare])
    volume=np.zeros((448,512,512),np.uint16);known=np.zeros((512,512),bool)
    for (cx,cz),v in zip(coords,chunks):
        x,z=int(cx)%32*16,int(cz)%32*16;volume[:,z:z+16,x:x+16]=v;known[z:z+16,x:x+16]=True
    del chunks,r;e.regions.clear()
    ids,n=label(solid_lookup[volume])
    rooted=set(map(int,np.unique(ids[0])));rooted.add(0)
    # Only non-rooted components need union metadata; root 0 is shared ground.
    local=[i for i in range(1,n+1)if i not in rooted]
    mapping=np.zeros(n+1,np.int32);mapping[local]=np.arange(1,len(local)+1)
    objects=find_objects(ids);counts=np.bincount(ids.ravel());rows=[]
    for old in local:
        ar=objects[old-1];mask=ids[ar]==old;pts=np.argwhere(mask);pts+=np.array([s.start for s in ar])
        materials,ns=np.unique(volume[ar][mask],return_counts=True)
        mats={names[int(m)]:int(c)for m,c in zip(materials,ns)}
        # A component touching the uncaptured upper volume can continue into
        # a structure above it. It is not proven detached even with known XZ.
        unknown=bool((pts[:,0]==volume.shape[0]-1).any())
        for dy,dx in ((-1,0),(1,0),(0,-1),(0,1)):
            z=pts[:,1]+dy;x=pts[:,2]+dx;valid=(z>=0)&(z<512)&(x>=0)&(x<512)
            if (~known[z[valid],x[valid]]).any():unknown=True
        rows.append(dict(id=int(mapping[old]),cells=int(counts[old]),bounds=[int(pts[:,2].min()+rx*512),int(pts[:,0].min()-128),int(pts[:,1].min()+rz*512),
            int(pts[:,2].max()+rx*512),int(pts[:,0].max()-128),int(pts[:,1].max()+rz*512)],unknown=unknown,materials=mats))
    ids=mapping[ids]
    nonzero=np.flatnonzero(ids.ravel())
    # Sparse exact coordinates allow later finite-component repair decisions.
    np.savez_compressed(out/name,indices=nonzero.astype(np.uint32),labels=ids.ravel()[nonzero],
        west=ids[:,:,0],east=ids[:,:,-1],north=ids[:,0,:],south=ids[:,-1,:],
        solid_west=solid_lookup[volume[:,:,0]],solid_east=solid_lookup[volume[:,:,-1]],
        solid_north=solid_lookup[volume[:,0,:]],solid_south=solid_lookup[volume[:,-1,:]],
        known=known)
    (out/name.with_suffix('.json')).write_text(json.dumps(dict(region=[rx,rz],components=rows,full_chunks=len(coords))),encoding='utf8')
    return dict(region=[rx,rz],components=len(rows),full_chunks=len(coords))

def join(out):
    records={};nodes={};rows=[];parent=[0];unknown=[False]
    for file in out.glob('r.*.*.json'):
        r=json.loads(file.read_text());key=tuple(r['region']);records[key]=r
        for c in r['components']:
            i=len(parent);parent.append(i);unknown.append(c['unknown']);nodes[key+(c['id'],)]=i;rows.append((key,c,i))
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b:parent[max(a,b)]=min(a,b)
    for (rx,rz),rec in records.items():
        with np.load(out/f'r.{rx}.{rz}.npz')as a:
            for direction,other,dx,dz in [('east','west',1,0),('south','north',0,1),('west','east',-1,0),('north','south',0,-1)]:
                neighbor=(rx+dx,rz+dz)
                if neighbor not in records:
                    for k in np.unique(a[direction]):
                        if k:unknown[nodes[(rx,rz,int(k))]]=True
                    continue
                if dx<0 or dz<0:continue
                with np.load(out/f'r.{neighbor[0]}.{neighbor[1]}.npz')as b:
                    sa,sb=a['solid_'+direction],b['solid_'+other]
                    ka=a['known'][:,-1] if dx else a['known'][-1,:]
                    kb=b['known'][:,0] if dx else b['known'][0,:]
                    for k in np.unique(a[direction][:,~kb]):
                        if k:unknown[nodes[(rx,rz,int(k))]]=True
                    for k in np.unique(b[other][:,~ka]):
                        if k:unknown[nodes[neighbor+(int(k),)]]=True
                    pairs=np.unique(np.column_stack((a[direction][sa&sb],b[other][sa&sb])),axis=0)
                    for u,v in pairs:
                        i=nodes.get((rx,rz,int(u)),0);j=nodes.get(neighbor+(int(v),),0);union(i,j)
    grouped={}
    for key,c,i in rows:
        root=find(i)
        if root==0:continue
        if root not in grouped:grouped[root]=dict(cells=0,bounds=c['bounds'].copy(),unknown=False,materials=defaultdict(int),parts=[])
        g=grouped[root];g['cells']+=c['cells'];g['unknown']|=unknown[i]
        g['bounds'][:3]=list(map(min,zip(g['bounds'][:3],c['bounds'][:3])));g['bounds'][3:]=list(map(max,zip(g['bounds'][3:],c['bounds'][3:])))
        for m,n in c['materials'].items():g['materials'][m]+=n
        g['parts'].append([*key,c['id']])
    results=sorted(grouped.values(),key=lambda r:-r['cells'])
    for i,r in enumerate(results):r['id']=i;r['materials']=dict(r['materials'])
    report=dict(scope='All captured FULL geofront chunks, Y -128..319, six-neighbor solids, cross-region union; water is not structural support.',
                full_chunks=sum(r['full_chunks']for r in records.values()),components=results,definite_floating=sum(not r['unknown']for r in results),
                unknown_components=sum(r['unknown']for r in results),not_a_delete_list=True)
    (out/'floating-components.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print('GLOBAL FLOATING',report['full_chunks'],report['definite_floating'],report['unknown_components'],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--workers',type=int,default=2)
    p.add_argument('--baseline',type=Path,help='Reuse unchanged-region component records; changed region faces are joined again.')
    p.add_argument('--regions',nargs='*',help='Exact changed-region list from a bounded later pass; other baseline records are reused.')
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    names=sorted(f.name for f in (a.source/'source').glob('*.npz'))
    if a.baseline:
        changed=set(a.regions) if a.regions else {f.name for f in (a.source/'delta').glob('*.npz')}
        for name in names:
            if name in changed:continue
            for file in (a.baseline/name,(a.baseline/name).with_suffix('.json')):os.link(file,a.out/file.name)
        names=[n for n in names if n in changed]
    jobs=[(str(a.source),str(a.out),name)for name in names]
    with ProcessPoolExecutor(max_workers=a.workers)as pool:
        fs=[pool.submit(scan,j)for j in jobs]
        for i,f in enumerate(as_completed(fs),1):print('Scanned solid components',i,'/',len(jobs),f.result(),flush=True)
    join(a.out)

