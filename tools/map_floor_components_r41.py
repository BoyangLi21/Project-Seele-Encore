"""Expand declared passage seeds to whole measured floor components globally.

Full blocks and half slabs have separate standing elevations. Historical test
lines provide named-use seeds, not a mask that hides their adjacent floor edges.
Safety probes deliberately targeting voids are not passage seeds.
"""
from pathlib import Path
import json,time,gc
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from audit_spatial_envelopes_r41 import Atlas

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/spatial_repair_r41';WORLD=ART/'source_world_backup'
OUT=ART/'floor_components';XOFF=1<<19;YOFF=2048


def keys(x,y2,z):return ((np.asarray(x,np.int64)+XOFF)<<33)|((np.asarray(z,np.int64)+XOFF)<<12)|(np.asarray(y2,np.int64)+YOFF)


def main():
    OUT.mkdir(exist_ok=True);cores=json.loads((ART/'envelopes/index.json').read_text('utf8'))['sections'];atlas=Atlas(WORLD,cores)
    import regional_voxels as v
    shapes={v.canonical_state(k):b for k,b in json.loads((WORLD/'native_collision_shapes.json').read_text('utf8')).items()}
    half=[];upper=[];third=[];stairs=[];doors=[];platforms=[]
    for state in atlas.palette:
        boxes=shapes.get(state,[] if state.startswith(('minecraft:air','minecraft:void_air','minecraft:cave_air','minecraft:light[')) else [[0,0,0,1,1,1]])
        relevant=[b for b in boxes if b[0]<.8 and b[3]>.2 and b[2]<.8 and b[5]>.2]
        top=max((b[4] for b in relevant),default=-1)
        half.append(abs(top-.5)<.001);upper.append(not any(b[4]>.5001 and b[1]<1 for b in relevant));third.append(not any(b[4]>.001 and b[1]<.3 for b in relevant))
        stairs.append(1 if ('stairs' in state or 'escalator_step' in state) and any('facing='+f in state for f in ['east','west']) else 2 if ('stairs' in state or 'escalator_step' in state) else 0)
        name=state.partition('[')[0]
        doors.append(name.endswith('_door') and 'trapdoor' not in name and ('half=lower' in state or 'part=lower' in state))
        platforms.append(name.startswith('mtr:platform'))
    half,upper,third=np.array(half),np.array(upper),np.array(third);stairs=np.asarray(stairs,np.uint8)
    doors=np.asarray(doors,bool);platforms=np.asarray(platforms,bool)
    chunks=[];axes=[];port_keys=[];started=time.monotonic()
    for i,core in enumerate(cores):
        a,lo=atlas.volume(core);walk=np.zeros(a.shape,bool);walk[1:-1]=atlas.support[a[:-2]]&atlas.free[a[1:-1]]&atlas.head[a[2:]]
        for mask,offset in [(walk,0),(half[a]&upper[a],1)]:
            if offset:
                mask=mask.copy();mask[:-2]&=atlas.free[a[1:-1]]&third[a[2:]];mask[-2:]=False
            yy,zz,xx=np.where(mask[8:24,2:18,2:18]);yy+=8;zz+=2;xx+=2
            if not len(xx):continue
            x=xx+lo[0];z=zz+lo[2];y2=(yy+lo[1])*2+offset
            chunks.append(keys(x,y2,z));axes.append(stairs[a[yy-1,zz,xx]] if offset==0 else np.zeros(len(xx),np.uint8))
        for flags,height in [(doors,0),(platforms,1)]:
            yy,zz,xx=np.where(flags[a][8:24,2:18,2:18]);yy+=8;zz+=2;xx+=2
            if len(xx):port_keys.append(keys(xx+lo[0],(yy+lo[1]+height)*2,zz+lo[2]))
        if i and i%5000==0:print('Floor census',i,'/',len(cores),round(time.monotonic()-started,1),'seconds',flush=True)
    nodes=np.concatenate(chunks);axis=np.concatenate(axes);order=np.argsort(nodes);nodes=nodes[order];axis=axis[order]
    unique=np.r_[True,nodes[1:]!=nodes[:-1]];nodes=nodes[unique];axis=axis[unique]
    del atlas,chunks,axes,a,order;gc.collect();n=len(nodes);print('Measured standing nodes',n,flush=True)
    rr=[];cc=[]
    for distance,direction in [(1<<33,1),(1<<12,2)]:
        # Purpose is established independently on each elevation. A ground
        # street seed must not silently authorize an entire reachable roof.
        for dy in (0,):
            target=nodes+distance+dy;at=np.searchsorted(nodes,target);valid=at<n;source=np.flatnonzero(valid);dest=at[valid];same=nodes[dest]==target[valid];source=source[same];dest=dest[same]
            if abs(dy)==2:
                keep=(axis[source]==direction)|(axis[dest]==direction);source=source[keep];dest=dest[keep]
            rr.append(source.astype(np.int32));cc.append(dest.astype(np.int32))
    r=np.concatenate(rr);c=np.concatenate(cc);del rr,cc
    graph=coo_matrix((np.ones(len(r),np.uint8),(r,c)),shape=(n,n)).tocsr();count,labels=connected_components(graph,directed=False);del graph,r,c;gc.collect()
    cases=json.loads((WORLD/'quality_walk_cases.json').read_text('utf8'));points=[]
    for case in cases:
        if 'barrier' in case:continue
        p=case.get('path') or [case.get('start'),case.get('end')]
        if any(q is None for q in p):continue
        for a,b in zip(p,p[1:]):
            a=np.asarray(a);b=np.asarray(b);points.extend(np.linspace(a,b,max(2,int(np.linalg.norm(a-b)/.5)+1)))
    points=np.asarray(points);seedkeys=np.unique(np.concatenate([keys(np.floor(points[:,0]).astype(int),np.rint(points[:,1]*2).astype(int),np.floor(points[:,2]).astype(int)),*port_keys]))
    matched=[]
    for dx,dz in [(0,0),(1,0),(-1,0),(0,1),(0,-1)]:
        want=seedkeys+dx*(1<<33)+dz*(1<<12);at=np.searchsorted(nodes,want);valid=at<n;at=at[valid];same=nodes[at]==want[valid];matched.extend(at[same])
    used=np.unique(labels[np.asarray(matched,int)]);selected=np.isin(labels,used)
    findings=json.loads((ART/'envelopes/findings.json').read_text('utf8'))['findings'];out=[]
    for row in findings:
        if row['kind']!='unguarded_drop':continue
        x,y,z=row['pos'];key=keys(x,round(y*2),z);at=int(np.searchsorted(nodes,key))
        if at<n and nodes[at]==key and selected[at]:out.append(row)
    np.savez_compressed(OUT/'measured_floor_components.npz',nodes=nodes,labels=labels,used_components=used)
    (OUT/'connected_floor_edges.json').write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')),'utf8')
    report=dict(world=str(WORLD),standing_nodes=n,components=int(count),seeded_components=len(used),reachable_floor_nodes=int(selected.sum()),edges=len(out),passage_seed_samples=len(points),
                scope='All indexed constructed sections and actual 3D standing clearances, including half-slab elevations. Declared passages, real lower door blocks and native platform blocks seed complete floor components separately at each elevation. This does not authorize roof/structural edits.')
    (OUT/'report.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)


if __name__=='__main__':main()
