"""Offline 3-D road and landform survey of saved blocks; never a gameplay gate."""
import argparse,json
from pathlib import Path
import numpy as np
from scipy.ndimage import label,maximum_filter,minimum_filter,binary_dilation
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from author_hakone_lakefront import Editor
from repair_hakone_surface_ownership import load_grid,sampled
from verify_hakone_network_candidate import PAVEMENT
from query_blocks import AIR
from plan_ashi_landscape_r54 import SOIL

EMPTY=AIR|{'minecraft:light','minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:dead_bush'}
ASPHALT={'minecraft:black_concrete','projectseele:road_asphalt_slab','projectseele:road_marking_slab'}

def components(mask,bounds,values=None,minimum=1):
    groups,n=label(mask,np.ones((3,3),int));counts=np.bincount(groups.ravel());rows=[]
    from scipy.ndimage import find_objects
    for i,area in enumerate(find_objects(groups),1):
        if area is None or counts[i]<minimum:continue
        zs,xs=np.nonzero(groups[area]==i);zs+=area[0].start;xs+=area[1].start
        row=dict(columns=int(counts[i]),bounds=[int(xs.min()+bounds[0]),int(zs.min()+bounds[1]),int(xs.max()+bounds[0]),int(zs.max()+bounds[1])])
        if values is not None:
            at=int(np.argmax(values[zs,xs]));row.update(maximum=float(values[zs[at],xs[at]]),witness=[int(xs[at]+bounds[0]),int(zs[at]+bounds[1])])
        rows.append(row)
    return sorted(rows,key=lambda r:(-r.get('maximum',0),-r['columns']))

def run(a):
    a.out.mkdir(parents=True,exist_ok=True)
    m=load_grid(a.source/'measured.npz');bounds=m['bounds'];x0,z0,x1,z1=map(int,bounds);shape=m['top'].shape
    d=load_grid(a.plan/'network.npz')
    expected=np.zeros(shape,bool);carriage=np.zeros(shape,bool);grade=np.full(shape,-32768,np.int16);legacy=np.zeros(shape,bool)
    legacy_grade=np.full(shape,-32768,np.int16)
    def overlay(v,key,target):
        x,z,X,Z=map(int,v['bounds']);l,t,R,B=max(x,x0),max(z,z0),min(X,x1),min(Z,z1)
        if l>R or t>B:return
        target[t-z0:B-z0+1,l-x0:R-x0+1]|=v[key][t-z:B-z+1,l-x:R-x+1].astype(bool)
    overlay(d,'walk',expected);overlay(d,'road',carriage)
    x,z,X,Z=map(int,d['bounds']);area=np.s_[z-z0:Z-z0+1,x-x0:X-x0+1];grade[area]=d['grade2']+2
    for name in ('road_contract_final.npz','extension_contract_final.npz'):
        v=load_grid(a.gis.parent/'world_rebuild_r20/road_actual'/name);x,z=map(int,v['origin']);v['bounds']=[x,z,x+v['mask'].shape[1]-1,z+v['mask'].shape[0]-1]
        overlay(v,'mask',legacy)
        l,t,R,B=max(x,x0),max(z,z0),min(v['bounds'][2],x1),min(v['bounds'][3],z1)
        ar=np.s_[t-z0:B-z0+1,l-x0:R-x0+1];sr=np.s_[t-z:B-z+1,l-x:R-x+1]
        use=v['mask'][sr].astype(bool);legacy_grade[ar][use]=v['height2'][sr][use]
        overlay(v,'carriage',carriage)
    reserved=np.zeros(shape,bool);overlay(d,'core',reserved);overlay(d,'held',reserved)
    footprint=expected|(legacy&~reserved);floor=np.full(shape,-32768,np.int16);gap=np.zeros(shape,np.int16);unclassified=np.zeros(shape,bool)
    previous_report=None
    if a.reuse:
        saved=load_grid(a.reuse/'measured-3d.npz');floor=saved['floor2'];gap=saved['deck_air']
        previous_report=json.loads((a.reuse/'survey.json').read_text('utf8'))
    e=Editor(a.source);yy=np.arange(-128,320,dtype=np.int16)[:,None,None];known=m['full']
    for file in ([]if a.reuse else sorted((a.source/'source').glob('*.npz'))):
        rx,rz=map(int,file.stem.split('.')[1:]);r=e.region(rx*512,rz*512);names=r['names'];bare=[s.split('[')[0]for s in names]
        pave=np.array([s in PAVEMENT for s in bare]);empty=np.array([s in EMPTY for s in bare]);asphalt=np.array([s in ASPHALT for s in bare]);natural=np.array([s in SOIL for s in bare])
        offset=np.array([1 if 'slab'in s and 'type=bottom'in s else 2 for s in names],np.int16)
        for (cx,cz),v in zip(r['coords'],r['after']):
            cx,cz=int(cx),int(cz);ar=np.s_[cz*16-z0:cz*16-z0+16,cx*16-x0:cx*16-x0+16]
            use=footprint[ar]
            if not use.any()and not asphalt[v].any():continue
            clear=np.zeros(v.shape,bool);clear[:-2]=empty[v[1:-1]]&empty[v[2:]]
            hit=pave[v]&clear;surface=2*yy+offset[v]
            target=np.where(expected[ar],grade[ar],2*m['top'][ar]+2)
            distance=np.where(hit,abs(surface-target),32767)
            at=distance.argmin(0);iz,ix=np.mgrid[:16,:16];ok=distance[at,iz,ix]<32767
            ok&=use;floor[ar]=np.where(ok,surface[at,iz,ix],-32768)
            # Continuous empty air directly under the actual selected deck.
            below=np.zeros((16,16),np.int16);alive=ok.copy()
            for k in range(1,49):
                idx=np.maximum(0,at-k);alive&=(at>=k)&empty[v[idx,iz,ix]];below+=alive
            gap[ar]=below
            raw=(asphalt[v]&clear).any(0);unclassified[ar]=raw&~use
        e.regions.clear();print('3D measured',file.name,flush=True)
    # Exclude roofs and solid foundations outside the road's explicit corridor.
    floor[~footprint]=-32768
    # Retired surface-road footprints must not select distant floors inside
    # old city shafts or upper railway decks merely because their X/Z overlap.
    floor[~expected&(abs(floor.astype(np.int32)-(m['top'].astype(np.int32)*2+2))>16)]=-32768
    # A recorded street may pass under a bridge or a mountain. Its authored
    # floor, not the nearest roof or natural surface, identifies that layer.
    from collections import defaultdict
    tunnels=defaultdict(list);layers=[]
    if a.tunnels:
        for x,y,z in json.loads(a.tunnels.read_text('utf8'))['points']:
            tunnels[x//16,z//16].append((x,y,z))
    for file in sorted((a.source/'source').glob('*.npz')):
        rx,rz=map(int,file.stem.split('.')[1:]);ar=np.s_[max(0,rz*512-z0):min(shape[0],rz*512+512-z0),max(0,rx*512-x0):min(shape[1],rx*512+512-x0)]
        if not (legacy[ar]&~expected[ar]&~reserved[ar]).any() and not any(cx//32==rx and cz//32==rz for cx,cz in tunnels):continue
        r=e.region(rx*512,rz*512);bare=[s.split('[')[0]for s in r['names']]
        pave=np.array([s in PAVEMENT for s in bare]);empty=np.array([s in EMPTY for s in bare]);offset=np.array([1 if 'slab'in s and 'type=bottom'in s else 2 for s in r['names']],np.int16)
        for (cx,cz),v in zip(r['coords'],r['after']):
            cx,cz=int(cx),int(cz);ar=np.s_[cz*16-z0:cz*16-z0+16,cx*16-x0:cx*16-x0+16];use=legacy[ar]&~expected[ar]&~reserved[ar]
            if use.any():
                clear=np.zeros(v.shape,bool);clear[:-2]=empty[v[1:-1]]&empty[v[2:]]
                surface=2*yy+offset[v];distance=np.where(pave[v]&clear,abs(surface-legacy_grade[ar]),32767)
                at=distance.argmin(0);iz,ix=np.mgrid[:16,:16];ok=use&(distance[at,iz,ix]<=2)
                floor[ar][use]=-32768;floor[ar][ok]=surface[at,iz,ix][ok]
            for x,y,z in tunnels[cx,cz]:
                if pave[v[y+128,z%16,x%16]]and empty[v[y+129:y+131,z%16,x%16]].all():
                    height=2*y+offset[v[y+128,z%16,x%16]]
                    layers.append((x,z,int(height)))
                    if not expected[z-z0,x-x0]:floor[z-z0,x-x0]=height
                    carriage[z-z0,x-x0]=True
        e.regions.clear()
    valid=floor!=-32768
    zs,xs=np.nonzero(valid);node=np.full(shape,-1,np.int32);node[zs,xs]=np.arange(len(xs),dtype=np.int32)
    rows=[];cols=[];jumps=np.zeros(shape,np.float32)
    for dz,dx in ((0,1),(1,0),(1,1),(1,-1)):
        za=slice(max(0,-dz),shape[0]-max(0,dz));zb=slice(max(0,dz),shape[0]-max(0,-dz))
        xa=slice(max(0,-dx),shape[1]-max(0,dx));xb=slice(max(0,dx),shape[1]-max(0,-dx))
        aa=(za,xa);bb=(zb,xb);both=valid[aa]&valid[bb];delta=abs(floor[aa].astype(np.int32)-floor[bb])
        connected=both&(delta<=2);rows.append(node[aa][connected]);cols.append(node[bb][connected])
        if dx==0 or dz==0:jumps[aa]=np.maximum(jumps[aa],np.where(both,delta/2,0))
    # Keep both elevations where a road crosses a tunnel. Collapsing each X/Z
    # to one floor invents a break in one of the two otherwise valid routes.
    base=floor[zs,xs];extras=sorted(set((x,z,y)for x,z,y in layers if floor[z-z0,x-x0]!=y))
    lookup={(x,z,y):len(xs)+i for i,(x,z,y)in enumerate(extras)};er=[];ec=[]
    for (x,z,y),i in lookup.items():
        for dx in (-1,0,1):
            for dz in (-1,0,1):
                if dx==dz==0:continue
                iz,ix=z+dz-z0,x+dx-x0
                if not(0<=iz<shape[0]and 0<=ix<shape[1]):continue
                j=node[iz,ix]
                if j>=0 and abs(int(floor[iz,ix])-y)<=2:er.append(i);ec.append(j)
                for dy in range(-2,3):
                    j=lookup.get((x+dx,z+dz,y+dy))
                    if j is not None:er.append(i);ec.append(j)
    if extras:
        ex=np.array(extras);xs=np.r_[xs,ex[:,0]-x0];zs=np.r_[zs,ex[:,1]-z0];base=np.r_[base,ex[:,2]]
    rr=np.r_[np.concatenate(rows),np.array(er,int)];cc=np.r_[np.concatenate(cols),np.array(ec,int)]
    graph=coo_matrix((np.ones(len(rr),np.uint8),(rr,cc)),shape=(len(xs),len(xs))).tocsr()
    n,labels=connected_components(graph,directed=False);sizes=np.bincount(labels)
    links=[]
    for i in np.argsort(sizes)[::-1]:
        if sizes[i]<20:continue
        where=labels==i;links.append(dict(component=int(i),columns=int(sizes[i]),commissioned_columns=int(expected[zs[where],xs[where]].sum()),bounds=[int(xs[where].min()+x0),int(zs[where].min()+z0),int(xs[where].max()+x0),int(zs[where].max()+z0)]))
    # Propagate along connected road cells, not across nearby parallel streets
    # at another elevation. Sixteen hops expose sustained steep grades.
    keep=carriage[zs,xs];er=rr[keep[rr]&keep[cc]];ec=cc[keep[rr]&keep[cc]]
    high=base.copy();low=base.copy()
    for _ in range(16):
        hi=high.copy();lo=low.copy()
        np.maximum.at(hi,er,high[ec]);np.maximum.at(hi,ec,high[er])
        np.minimum.at(lo,er,low[ec]);np.minimum.at(lo,ec,low[er]);high,low=hi,lo
    relief=np.zeros(shape,np.float32);relief[zs,xs]=np.maximum(high-base,base-low)/2
    steep=valid&carriage&(relief>5)
    # Full landform edge survey: natural surface discontinuities, not roof tops.
    cliffs=np.zeros(shape,np.float32)
    for axis in (0,1):
        aa=[slice(None),slice(None)];bb=aa.copy();aa[axis]=slice(None,-1);bb[axis]=slice(1,None);aa,bb=tuple(aa),tuple(bb)
        good=known[aa]&known[bb]&(m['top'][aa]>-128)&(m['top'][bb]>-128)
        delta=abs(m['top'][aa].astype(np.int32)-m['top'][bb]);cliffs[aa]=np.maximum(cliffs[aa],np.where(good,delta,0))
    roadedge=binary_dilation(valid,iterations=5)&~valid
    roadside=(cliffs>4)&roadedge
    report=dict(bounds=list(map(int,bounds)),source=str(a.source),road_columns=len(xs),full_saved_columns=int(known.sum()),
        three_dimensional_components=links,missing_expected_columns=int((expected&known&~valid).sum()),
        road_step_components=components((jumps>1)&valid,bounds,jumps,3),
        sustained_grade_components=components(steep,bounds,relief,15),
        roadside_cliff_components=components(roadside,bounds,cliffs,5),
        terrain_cliff_components=components(cliffs>8,bounds,cliffs,8),
        unclassified_paving_components=previous_report['unclassified_paving_components']if previous_report else components(unclassified,bounds,None,30),
        suspended_deck_components=components((gap>3)&valid,bounds,gap,8),
        note='Slope and cliff candidates require bridge/tunnel/building classification; not automatic edit permission.',world_written=False)
    report['additional_tunnel_layers']=len(extras)
    np.savez_compressed(a.out/'road-components.npz',xz=np.column_stack((xs+x0,zs+z0)),floor2=base,component=labels)
    np.savez_compressed(a.out/'measured-3d.npz',bounds=bounds,floor2=floor,deck_air=gap,road=carriage,expected=expected,legacy=legacy,step=jumps,local_relief=relief,cliff=cliffs)
    (a.out/'survey.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps({k:v if not isinstance(v,list)else len(v) for k,v in report.items()}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('source','plan','gis','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--reuse',type=Path,help='Reuse the same captured voxel measurements for refined surface classification')
    p.add_argument('--tunnels',type=Path,help='Known tunnel coordinates, re-read against the captured blocks')
    run(p.parse_args())

