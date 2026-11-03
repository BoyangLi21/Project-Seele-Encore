"""Enlarge the current Yashima forecourt with supported earthworks.

The cannon well and original rack remain finite three-dimensional voids.
Native launch occupancy, devices and every non-natural original cell stay exact.
This authors a new candidate, never an installed save or an older candidate.
"""
import argparse,json,os,shutil
from pathlib import Path
import numpy as np
from scipy.ndimage import distance_transform_edt
from author_hakone_lakefront import Editor
from map_pipeline.launch_protection import load,check_candidate
from plan_ashi_landscape_r54 import SOIL,PLANTS,NATURAL
from query_blocks import AIR,iter_block_entities
from install_r53_carrier_trays import stopped_world

def run(a):
    capture=json.loads((a.source/'capture.json').read_text('utf8'));world=Path(capture['world'])
    if capture['unavailable_chunks']:raise ValueError('Full current chunks required')
    a.out.mkdir(parents=True,exist_ok=False)
    for n in ('source','delta','plan'):(a.out/n).mkdir()
    for p in (a.source/'source').glob('*.npz'):os.link(p,a.out/'source'/p.name)
    shutil.copy2(a.source/'capture.json',a.out/'capture.json')
    with np.load(a.source/'measured.npz')as f:old=f['top'];bounds=f['bounds']
    x,z,X,Z=map(int,bounds);zz,xx=np.mgrid[z:Z+1,x:X+1]
    # A rounded 209 x 109 m military apron, including the firing stance and
    # the previously unsupported forward rim. It meets the Y175 EVA routes.
    dx=np.maximum(np.maximum(-1346-xx,xx+1138),0);dz=np.maximum(np.maximum(-1496-zz,zz+1388),0)
    core=(dx==0)&(dz==0)
    corner=np.hypot(np.maximum(np.maximum(-1332-xx,xx+1152),0),np.maximum(np.maximum(-1482-zz,zz+1402),0))
    core&=corner<=14
    # Three commissioned launch receivers keep their complete circular rim.
    # The apron joins the outside; it must not bridge their moving door gaps.
    for px in (-1370,-1250,-1130):core&=np.hypot(xx-px,zz+1520.5)>36
    distance=distance_transform_edt(~core)
    # Fill down to continuous measured ground. A 1:1.4 natural batter reaches
    # unchanged terrain before the capture boundary; no rectangular cut edge.
    target=np.maximum(old,np.floor(174-distance*.72).astype(np.int16));target[core]=174
    active=target!=old
    if any(np.any(edge)for edge in (active[0],active[-1],active[:,0],active[:,-1])):raise ValueError('Expand capture until the batter meets terrain')
    wells=[[-1278,157,-1427,-1226,319,-1368],[-1316,110,-1383,-1297,319,-1360]]
    e=Editor(a.out);guard=load(world);yy=np.arange(-128,320)[:,None,None]
    with stopped_world(world):
        shutil.copytree(world/'mtr',a.out/'preserved-native')
        devices={p for p,t in iter_block_entities(world,'projectseele:geofront',(x,-128,z),(X,319,Z))}
    kept_non_natural=0;blocked_core=[];bearing=[]
    for file in sorted((a.out/'source').glob('*.npz')):
        rx,rz=map(int,file.stem.split('.')[1:]);r=e.region(rx*512,rz*512)
        def code(s):
            if s not in r['ids']:r['ids'][s]=len(r['names']);r['names'].append(s)
            return r['ids'][s]
        stone,dirt,grass,deck,air=[code(s)for s in ('minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]','minecraft:gray_concrete','minecraft:air')]
        natural=np.array([s.split('[')[0]in NATURAL-{'minecraft:water'}for s in r['names']]);empty=np.array([s.split('[')[0]in AIR|PLANTS for s in r['names']])
        for (cx,cz),before,v in zip(r['coords'],r['before'],r['after']):
            cx,cz=int(cx),int(cz);a0,b0=cx*16-x,cz*16-z;area=np.s_[b0:b0+16,a0:a0+16]
            g=old[area];h=target[area];c=core[area];change=active[area]|c
            if not change.any():continue
            Zs,Xs=np.mgrid[cz*16:cz*16+16,cx*16:cx*16+16];keep=guard.chunk_mask(cx,cz)
            for q in wells:keep|=(Xs>=q[0])&(Xs<=q[3])&(Zs>=q[2])&(Zs<=q[5])&(yy>=q[1])&(yy<=q[4])
            for p in devices:
                if p[0]//16==cx and p[2]//16==cz:keep[p[1]+128,p[2]%16,p[0]%16]=True
            # Preserve every actual built state (including the original white
            # movement strips, hatches, barrier collisions and cable equipment).
            eligible=natural[before]&~keep
            fill=change&(yy>=g-3)&(yy<=h)&eligible
            v[fill]=stone;v[fill&(yy>=h-2)&~c]=dirt;v[fill&(yy==h)&~c]=grass
            v[fill&(yy==h)&c]=deck
            cut=c&(yy>174)&(yy<=g+1)&eligible
            v[cut]=air
            kept_non_natural+=int(((~natural[before])&(yy>=g-3)&(yy<=h)&change).sum())
        e.save();e.regions.clear()
    # Independently read saved deltas, with the exact full well volumes exempt.
    e=Editor(a.out);errors=[]
    for iz,ix in zip(*np.nonzero(core)):
        px,pz=x+int(ix),z+int(iz)
        if any(q[0]<=px<=q[3]and q[2]<=pz<=q[5]for q in wells):continue
        if e.state(px,174,pz).split('[')[0]in AIR:blocked_core.append([px,174,pz])
        for py in range(int(old[iz,ix])+1,175):
            if e.state(px,py,pz).split('[')[0]in AIR and not guard.chunk_mask(px//16,pz//16)[py+128,pz%16,px%16]:
                errors.append(['unsupported-unreserved-cell',px,py,pz]);break
    if blocked_core:errors.append(['unclosed-apron-columns',len(blocked_core),blocked_core[:12]])
    guard_report=check_candidate(guard,a.out)
    from map_pipeline.launch_earthworks import ground
    actual=ground(Editor(a.out),list(map(int,bounds)))
    np.savez_compressed(a.out/'plan/network.npz',bounds=bounds,ground=actual,old_ground=old,walk=core,road=np.zeros(core.shape,bool),grade2=np.full(core.shape,348,np.int16),tunnel=np.zeros(core.shape,bool),marking=np.zeros(core.shape,bool))
    rows=[]
    for p in (a.out/'delta').glob('*.npz'):
        with np.load(p)as f:rows.append(dict(path='delta/'+p.name,cells=int(f['ranges'][-1])))
    manifest=dict(world=str(world),bounds_xz=list(map(int,bounds)),regions=rows,cells=sum(r['cells']for r in rows),world_written=False,progress_files_written=[])
    report=dict(errors=errors,apron_columns=int(core.sum()),preserved_well_volumes=wells,preserved_non_natural_cells=kept_non_natural,launch=guard_report,visual_verified=False)
    for name,value in [('manifest.json',manifest),('functional-check.json',report),('design.json',dict(floor=174,core_bounds=[-1346,-1496,-1138,-1388],well_volumes=wells,slope=.72))]:
        (a.out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(cells=manifest['cells'],apron_columns=report['apron_columns'],errors=errors[:5])),flush=True)
    if errors:raise ValueError('Forecourt support verification failed')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('source','out'):p.add_argument('--'+n,type=Path,required=True)
    run(p.parse_args())
