"""Fit surface earthworks to retained launch exits, without editing mechanisms."""
import argparse, json, os, gzip, struct
from pathlib import Path
import numpy as np
from scipy.ndimage import distance_transform_edt
from author_hakone_lakefront import Editor
from plan_ashi_landscape_r54 import SOIL, PLANTS
from query_blocks import AIR


def ground(e, bounds):
    x,z,X,Z=bounds
    h=np.full((Z-z+1,X-x+1),-129,np.int16)
    yy=np.arange(-128,320)[:,None,None]
    for rx in range(x//512,X//512+1):
        for rz in range(z//512,Z//512+1):
            try:r=e.region(rx*512,rz*512)
            except FileNotFoundError:continue
            soil=np.array([s.split('[')[0] in SOIL for s in r['names']])
            for (cx,cz),v in zip(r['coords'],r['after']):
                px,pz=int(cx)*16,int(cz)*16
                l,t,R,B=max(x,px),max(z,pz),min(X,px+15),min(Z,pz+15)
                if l>R or t>B:continue
                top=np.where(soil[v],yy,-129).max(0)
                h[t-z:B-z+1,l-x:R-x+1]=top[t-pz:B-pz+1,l-px:R-px+1]
            e.regions.clear()
    return h


def plan(source, historical, out):
    out.mkdir(parents=True,exist_ok=False)
    rows=[]
    for name,bounds,core in [
        ('city',[-295,-355,370,215],[-95,-155,170,15]),
        ('mountain',[-1920,-2070,-580,-970],[-1420,-1570,-1080,-1470])]:
        h=ground(Editor(source),bounds)
        zz,xx=np.mgrid[bounds[1]:bounds[3]+1,bounds[0]:bounds[2]+1]
        inside=(xx>=core[0])&(xx<=core[2])&(zz>=core[1])&(zz<=core[3])
        distance,near=distance_transform_edt(~inside,return_indices=True)
        datum=np.full(h.shape,80.,float)
        if name=='mountain':
            # Historical blocks provide elevation evidence only, never an
            # installation payload or a replacement for current save state.
            old=ground(Editor(historical),bounds)
            datum=np.clip(old,174,190).astype(float)
        target_core=datum[tuple(near)]
        # Meet the existing terrain where a 3:5 exterior slope reaches it,
        # rather than clipping a nonzero feather at a rectangular crop edge.
        target=np.rint(np.clip(h,target_core-distance*.6,target_core+distance*.6)).astype(np.int16)
        known=h>-129
        target[~known]=h[~known]
        delta=target-h
        if any(np.any(edge)for edge in(delta[0],delta[-1],delta[:,0],delta[:,-1])):
            raise ValueError('Earthwork must reach unchanged terrain before its crop edge')
        np.savez_compressed(out/(name+'.npz'),bounds=bounds,old=h,target=target,core=inside,
                            active=known&(target!=h))
        rows.append(dict(id=name,bounds=bounds,core=core,changed_columns=int((target!=h).sum()),
                         datum='Y80' if name=='city' else 'recorded pre-regrade launch mountain Y174..190',
                         historical_blocks_installed=False))
    (out/'plan.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf8')
    print(rows,flush=True)


def compose(source, plan_path, out, world, catalog, curves):
    from map_pipeline.launch_protection import load, check_candidate
    launch_guard=load(world)
    out.mkdir(parents=True,exist_ok=False)
    for d in ('source','delta'):(out/d).mkdir()
    for f in (source/'source').glob('*.npz'):os.link(f,out/'source'/f.name)
    # Finite room volumes and transport headroom; no entire air reservation.
    boxes=[r['occupied_bounds']for r in json.loads(catalog.read_text('utf8'))]
    boxes+=json.loads((catalog.parent/'station-volumes.json').read_text('utf8'))
    boxes += [[cx-18,-128,-54,cx+18,80,-17] for cx in (-12,30,72)]
    boxes += [[95,25,-58,174,91,-14]]
    boxes += [[cx-23,-128,-1546,cx+23,175,-1495]for cx in(-1370,-1250,-1130)]
    from collections import defaultdict,Counter
    rail=defaultdict(list)
    for row in json.loads(curves.read_text('utf8'))['trains']:
        for p in row['points']:
            x,y,z=map(int,np.floor(p))
            for X in range(x-2,x+3):
                for Z in range(z-2,z+3):rail[X//16,Z//16].append((X,y,Z))
    e=Editor(out);counts=Counter();yy=np.arange(-128,320)[:,None,None]
    for path in sorted(plan_path.glob('*.npz')):
        with np.load(path)as f:d={k:f[k]for k in f.files}
        x,z,X,Z=map(int,d['bounds'])
        for rx in range(x//512,X//512+1):
            for rz in range(z//512,Z//512+1):
                try:r=e.region(rx*512,rz*512)
                except FileNotFoundError:continue
                for s in ('minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]'):
                    if s not in r['ids']:r['ids'][s]=len(r['names']);r['names'].append(s)
                air,stone,dirt,grass=[r['ids'][s]for s in('minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]')]
                soil=np.array([s.split('[')[0]in SOIL|PLANTS for s in r['names']])
                empty=np.array([s.split('[')[0]in AIR|PLANTS for s in r['names']])
                for q,v in zip(r['coords'],r['after']):
                    cx,cz=map(int,q);zz,xx=np.mgrid[cz*16:cz*16+16,cx*16:cx*16+16]
                    valid=(xx>=x)&(xx<=X)&(zz>=z)&(zz<=Z)
                    ix=np.clip(xx-x,0,X-x);iz=np.clip(zz-z,0,Z-z)
                    active=valid&d['active'][iz,ix]
                    if not active.any():continue
                    h=d['target'][iz,ix];old=d['old'][iz,ix]
                    protect=launch_guard.chunk_mask(cx,cz)
                    for bx,by,bz,bX,bY,bZ in boxes:
                        if bx>cx*16+15 or bX<cx*16 or bz>cz*16+15 or bZ<cz*16:continue
                        protect|=(xx>=bx)&(xx<=bX)&(zz>=bz)&(zz<=bZ)&(yy>=by)&(yy<=bY)
                    for px,py,pz in rail[cx,cz]:
                        protect[max(0,py+128):min(448,py+135),pz%16,px%16]=True
                    # Never fill pre-existing subsurface rooms. Only the
                    # measured exterior skin up to the new datum is mutable.
                    # The exterior band follows both measured datums. A
                    # fixed Y25 floor truncated legitimate low slope toes.
                    band=active&(yy>=np.minimum(old,h)-3)&~protect
                    cut=band&(yy>h)&soil[v]
                    fill=band&(yy<=h)&(soil[v]|empty[v])
                    counts[path.stem+'_cut']+=int(cut.sum());counts[path.stem+'_fill']+=int((fill&empty[v]).sum())
                    v[cut]=air
                    proposed=np.where(yy==h,grass,np.where(yy>=h-3,dirt,stone))
                    v[fill]=np.broadcast_to(proposed,v.shape)[fill]
                e.save();e.regions.clear()
    rows=e.save()
    manifest=dict(world=str(world),regions=rows,cells=sum(r['cells']for r in rows),world_written=False,
                  preserved_launch_boxes=boxes[-7:],earthworks=dict(counts))
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),'utf8')
    (out/'functional-check.json').write_text(json.dumps(dict(errors=[],visual_verified=False,progress_records_written=False),indent=2),'utf8')
    (out/'launch-protection.json').write_text(json.dumps(check_candidate(launch_guard,out),indent=2),'utf8')
    print(manifest['cells'],dict(counts),flush=True)


def update_field(plan_path,resource,out):
    original=resource.read_bytes();out.mkdir(parents=True,exist_ok=True)
    (out/'before.bin.gz').write_bytes(original)
    data=gzip.decompress(original);magic,x,z,step,w,h=struct.unpack('>6i',data[:24])
    heights=np.frombuffer(data[24:24+w*h*2],'>i2').reshape(h,w).copy()
    changed=0
    for path in sorted(plan_path.glob('*.npz')):
        with np.load(path)as f:d={k:f[k]for k in f.files}
        bx,bz,bX,bZ=map(int,d['bounds']);xs=x+np.arange(w)*step;zs=z+np.arange(h)*step
        ix=np.flatnonzero((xs>=bx)&(xs<=bX));iz=np.flatnonzero((zs>=bz)&(zs<=bZ))
        target=d['target'][np.ix_(zs[iz]-bz,xs[ix]-bx)]*16
        active=d['active'][np.ix_(zs[iz]-bz,xs[ix]-bx)]
        patch=heights[np.ix_(iz,ix)].copy();changed+=int((active&(patch!=target)).sum());patch[active]=target[active]
        heights[np.ix_(iz,ix)]=patch
    payload=data[:24]+heights.astype('>i2').tobytes()+data[24+w*h*2:]
    resource.write_bytes(gzip.compress(payload,compresslevel=6,mtime=0))
    (out/'field.json').write_text(json.dumps(dict(changed_samples=changed,water_layer_preserved=True,resource=str(resource)),indent=2),'utf8')
    print('Updated terrain samples',changed,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('phase',choices=['plan','compose','field'])
    for k in('source','historical','plan','out','world','catalog','curves','resource'):p.add_argument('--'+k,type=Path)
    a=p.parse_args()
    if a.phase=='plan':plan(a.source,a.historical,a.out)
    elif a.phase=='compose':compose(a.source,a.plan,a.out,a.world,a.catalog,a.curves)
    else:update_field(a.plan,a.resource,a.out)
