"""Independent saved-block/NBT checks for the composed station neighbourhood."""
import argparse,copy,json
from pathlib import Path
from collections import deque,Counter
import numpy as np
import nbtlib
from scipy.ndimage import label
from author_hakone_lakefront import Editor
from hakone_earthworks import road_blocks
from map_pipeline.corridors import alignment
from prepare_hakone_togendai_neighbourhood import save_json
from verify_hakone_network_candidate import PAVEMENT
from query_blocks import AIR

def verify(candidate):
    with np.load(candidate/'plan/network.npz')as f:d={k:f[k]for k in f.files}
    x,z,X,Z=map(int,d['bounds']);e=Editor(candidate);errors=[];walk=d['walk'];g=d['grade2'];checked=0
    empty=AIR|{'minecraft:light','minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern'}
    for j,i in np.argwhere(walk):
        px,pz=int(i+x),int(j+z);floor,slab=road_blocks(g[j,i]);floor=int(floor);state=e.state(px,floor,pz)
        if state.split('[')[0]not in PAVEMENT or ('type=bottom'in state)!=bool(slab):errors.append(['pavement',px,floor,pz,state,bool(slab)])
        for Y in range(floor+1,floor+4):
            state=e.state(px,Y,pz)
            if state.split('[')[0]not in empty:errors.append(['headroom',px,Y,pz,state])
        checked+=1
    seen=np.zeros(walk.shape,bool);start=(1000-z,-287-x);queue=deque([start]);seen[start]=True
    while queue:
        j,i=queue.popleft()
        for J,I in ((j-1,i),(j+1,i),(j,i-1),(j,i+1)):
            if 0<=J<walk.shape[0] and 0<=I<walk.shape[1] and walk[J,I] and not seen[J,I] and abs(int(g[J,I])-int(g[j,i]))<=1:
                seen[J,I]=True;queue.append((J,I))
    disconnected=walk&~seen
    groups,n=label(disconnected);sizes=np.bincount(groups.ravel())
    if disconnected.any():
        for k in range(1,n+1):
            j,i=np.argwhere(groups==k)[0];errors.append(['disconnected public surface',int(i+x),int(j+z),int(sizes[k])])
    outdoor={tuple(r['pos']):r for r in json.loads((candidate/'outdoor-apron-corrections.json').read_text('utf8'))}
    payload_cells=0;payload_exceptions=0;payloads=list(sorted((candidate/'payloads').glob('*.npz'),key=lambda p:int(p.stem)))
    for path in payloads:
        with np.load(path)as f:box=f['bounds'];dy=int(f['dy']);v=f['blocks'];names=list(map(str,f['palette']))
        for px in range(int(box[0]),int(box[3])+1):
            for pz in range(int(box[2]),int(box[5])+1):
                r=e.region(px,pz);col=r['after'][r['index'][px//16,pz//16],int(box[1])+dy+128:int(box[4])+dy+129,pz%16,px%16]
                actual=np.asarray(r['names'])[col];expected=np.asarray(names)[v[:,pz-box[2],px-box[0]]]
                expected=expected.astype(object)
                for k in range(len(expected)):
                    correction=outdoor.get((px,int(box[1])+dy+k,pz))
                    if correction:
                        payload_exceptions+=1
                        if expected[k]!=correction['before']:errors.append(['unmatched outdoor exception',px,int(box[1])+dy+k,pz])
                        expected[k]=correction['after']
                if not np.array_equal(actual,expected):errors.append(['parcel payload changed',path.name,px,pz,int(np.sum(actual!=expected))])
                payload_cells+=len(col)
    rows=json.loads((candidate/'plan/buildings.json').read_text('utf8'));goals=[]
    for row in rows:
        px,py,pz=row['approach'];floor=py-1
        if e.state(px,floor,pz).split('[')[0]not in PAVEMENT:errors.append(['parcel landing floor',row['id'],px,py,pz])
        reached=False
        for dz,dx in ((1,0),(-1,0),(0,1),(0,-1),(0,0)):
            j,i=pz+dz-z,px+dx-x
            if seen[j,i] and abs(int(g[j,i])-2*floor)<=1:reached=True
        if not reached:errors.append(['parcel approach disconnected',row['id'],px,py,pz])
        goals.append(dict(id=row['id'],approach=row['approach'],connected=reached))
        door=e.state(*row['door'])
        if 'door'not in door:errors.append(['retained entrance changed',row['id'],door])
    originals={tuple(int(t[k])for k in ('x','y','z')):t for t in nbtlib.load(candidate/'captured-devices.dat')['Devices']}
    cable_columns={}
    for row in json.loads((candidate/'plan/native-curves.json').read_text('utf8'))['ropeway']:
        for px,py,pz in row['points']:
            px,py,pz=map(int,np.floor([px,py,pz]))
            if px<x-3 or px>X+3 or pz<z-3 or pz>Z+3:continue
            for Q in range(px-3,px+4):
                for R in range(pz-3,pz+4):
                    if x<=Q<=X and z<=R<=Z:cable_columns.setdefault((Q,R),set()).update(range(py-10,py+7))
    cable_cells=0
    for (px,pz),ys in cable_columns.items():
        for py in ys:
            if e.state(px,py,pz)!=e.state(px,py,pz,True):errors.append(['native cable swept volume changed',px,py,pz])
            cable_cells+=1
    changes=nbtlib.load(candidate/'block-entities.dat')['Changes'];before={};after={}
    for r in changes:
        for key,table in [('Before',before),('After',after)]:
            if key in r:
                tag=r[key];pos=tuple(int(tag[k])for k in ('x','y','z'));table[pos]=tag
    checked_tags=0
    for row in rows:
        for pos in row['devices']:
            pos=tuple(pos);tag=originals[pos];q=(pos[0],pos[1]+row['dy'],pos[2]);new=copy.deepcopy(tag);new['y']=nbtlib.Int(q[1])
            if before.get(pos)!=tag or after.get(q)!=new:errors.append(['full device NBT changed',row['id'],pos])
            checked_tags+=1
    specs=json.loads((candidate/'plan/authored-design.json').read_text('utf8'));profiles=[]
    for row in specs['streets']:
        curve,s=alignment(row);samples=np.arange(0,s[-1]+.1,1.0);cx=np.rint(np.interp(samples,s,curve[:,0])).astype(int);cz=np.rint(np.interp(samples,s,curve[:,2])).astype(int)
        y=g[cz-z,cx-x]/2+1;ten=abs(y[10:]-y[:-10])/10
        profiles.append(dict(id=row['id'],length=float(s[-1]),maximum_actual_10m_grade=float(ten.max()),maximum_continuous_grade=float((abs(np.diff(curve[:,1]))/np.linalg.norm(np.diff(curve[:,[0,2]],axis=0),axis=1)).max())))
    # A retained seam must remain in the same standing component, including
    # its full surveyed width. No rounded road cap may erase its continuation.
    seams=[]
    for port in specs['retained_ports']:
        row=next(r for r in specs['streets']if r['id']==port['street']);px,py,pz=row['points'][port['end']]
        ys,xs=np.where(d['retained_walk']&((np.indices(walk.shape)[1]+x-px)**2+(np.indices(walk.shape)[0]+z-pz)**2<18**2));contacts=0
        for j,i in zip(ys,xs):
            for J,I in ((j-1,i),(j+1,i),(j,i-1),(j,i+1)):
                if not (0<=J<walk.shape[0]and 0<=I<walk.shape[1]and seen[J,I]):continue
                h=int((g[J,I]+1)//2)
                for fy in range(h-2,h+3):
                    state=e.state(int(i+x),fy,int(j+z));height2=2*fy+(1 if 'type=bottom'in state else 2)
                    if state.split('[')[0]in PAVEMENT and abs(height2-int(g[J,I])-2)<=1 and all(e.state(int(i+x),fy+k,int(j+z)).split('[')[0]in empty for k in (1,2,3)):
                        contacts+=1;break
        seams.append(dict(street=row['id'],contacts=contacts))
        if contacts==0:errors.append(['retained street disconnected',row['id']])
    report=dict(errors=errors,full_width_columns=checked,reachable_columns=int(seen.sum()),parcel_payload_cells_checked=payload_cells,parcel_payload_cells_exact=payload_cells-payload_exceptions,approved_outdoor_cells=payload_exceptions,complete_device_tags_exact=checked_tags,native_cable_swept_cells_unchanged=cable_cells,parcel_goals=goals,streets=profiles,retained_interfaces=seams,visual_verified=False,world_written=False)
    save_json(candidate/'independent-check.json',report)
    prior=json.loads((candidate/'functional-check.json').read_text('utf8'));prior.setdefault('composition_errors',prior['errors']);prior['independent_verification_errors']=errors;prior['errors']=prior['composition_errors']+errors;save_json(candidate/'functional-check.json',prior)
    print(json.dumps({k:v for k,v in report.items()if k not in ('errors','parcel_goals')},ensure_ascii=False),flush=True)
    print('Errors',len(errors),Counter(r[0]for r in errors),errors[:18],flush=True)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--candidate',type=Path,required=True);verify(p.parse_args().candidate)
