"""Read a compiled corridor's actual floors, supports and boundary interfaces."""
import argparse,json
from pathlib import Path
import numpy as np
from author_hakone_lakefront import Editor
from hakone_earthworks import road_blocks
from map_pipeline.roads import road_layers,layer_graph
from query_blocks import AIR
from plan_ashi_landscape_r54 import PLANTS
from verify_hakone_network_candidate import PAVEMENT


def write_replay_expected(candidate):
    import nbtlib
    from prepare_hakone_city_cross import packed
    from apply_s20_approved_semantic_repairs import parse_state
    chunks=[]
    for path in sorted((candidate/'delta').glob('*.npz')):
        with np.load(path)as f:
            coordinates,ranges,indices,values,names=(f[k]for k in ('coordinates','ranges','indices','after','palette'))
        for i,(cx,cz)in enumerate(coordinates):
            cells=[];lo,hi=ranges[i:i+2]
            for offset,value in zip(indices[lo:hi],values[lo:hi]):
                offset=int(offset);pos=(int(cx)*16+offset%16,offset//256-128,int(cz)*16+offset%256//16)
                cells.append(nbtlib.Compound({'Pos':nbtlib.Long(packed(pos)),'State':parse_state(str(names[value]))}))
            chunks.append(nbtlib.Compound({'X':nbtlib.Int(int(cx)),'Z':nbtlib.Int(int(cz)),
                'Cells':nbtlib.List[nbtlib.Compound](cells)}))
    nbtlib.File({'Chunks':nbtlib.List[nbtlib.Compound](chunks)}).save(candidate/'recipe-replay-expected.dat',gzipped=True)


def main(a):
    e=Editor(a.candidate);errors=[];rows=[]
    final_plan=a.candidate/'plan/network.npz'
    with np.load(final_plan if final_plan.exists() else a.plan/'network.npz')as f:p={k:f[k]for k in ('bounds','walk','grade2')}
    design_path=a.candidate/'authored-design.json'
    design={r['id']:r for r in json.loads(design_path.read_text('utf8'))['streets']} if design_path.exists() else {}
    px,pz,_,_=map(int,p['bounds'])
    for path in(a.candidate/'earthworks').glob('*.npz'):
        with np.load(path)as f:d={k:f[k]for k in f.files}
        spec=design.get(path.stem,{})
        keep={tuple(q['pos']):q['state']for q in spec.get('retire_keep_points',[])}
        x,z,X,Z=map(int,d['bounds']);walk=d['walk'];floor,slab=road_blocks(d['grade2'])
        observed=np.full(walk.shape,-32768,np.int32)
        for iz,ix in np.argwhere(walk):
            xx,zz,y=x+int(ix),z+int(iz),int(floor[iz,ix]);state=e.state(xx,y,zz)
            if state.split('[')[0]not in PAVEMENT:errors.append(['floor',xx,y,zz,state]);continue
            observed[iz,ix]=2*y+(1 if 'type=bottom'in state else 2)
            for yy in range(y+1,y+int(d.get('clearance',5))+1):
                if e.state(xx,yy,zz).split('[')[0]not in AIR|PLANTS|{'minecraft:light'}:
                    errors.append(['clearance',xx,yy,zz,e.state(xx,yy,zz)])
            span=d.get('bridge_span',np.zeros(walk.shape,bool))
            support_start=y-int(d['deck_depth']) if span[iz,ix] else min(int(d['old'][iz,ix]),y)-1
            for yy in range(support_start,y):
                if e.state(xx,yy,zz).split('[')[0]in AIR|{'minecraft:water','minecraft:lava'}:
                    errors.append(['support',xx,yy,zz,e.state(xx,yy,zz)])
        base_walk=p['walk'][z-pz:Z-pz+1,x-px:X-px+1].copy()
        base_grade=p['grade2'][z-pz:Z-pz+1,x-px:X-px+1]
        retired=d.get('retired_walk',np.zeros(walk.shape,bool))&~base_walk
        base_walk[retired]=False
        for iz,ix in np.argwhere(retired):
            yy,_=road_blocks(base_grade[iz,ix]);yy=int(yy)
            pos=(x+int(ix),yy,z+int(iz))
            if pos in keep:
                if e.state(*pos)!=keep[pos]:errors.append(['retained underlying support changed',*pos])
                continue
            if e.state(x+int(ix),yy,z+int(iz)).split('[')[0] in PAVEMENT:
                errors.append(['old retired pavement remains',x+int(ix),yy,z+int(iz)])
        checked_interfaces=0
        for dz,dx in ((1,0),(0,1)):
            joined=walk&np.roll(walk,(-dz,-dx),(0,1))
            jumps=joined&(abs(observed-np.roll(observed,(-dz,-dx),(0,1)))>1)
            for iz,ix in np.argwhere(jumps):
                errors.append(['internal full-width step',x+int(ix),z+int(iz),dx,dz])
        for dz,dx in ((1,0),(-1,0),(0,1),(0,-1)):
            border=walk&np.roll(base_walk&~walk,(-dz,-dx),(0,1))
            for iz,ix in np.argwhere(border):
                xx,zz=x+int(ix)+dx,z+int(iz)+dz
                y,_=road_blocks(base_grade[iz+dz,ix+dx]);y=int(y);s=e.state(xx,y,zz)
                if s.split('[')[0]not in PAVEMENT:errors.append(['outside port floor',xx,y,zz]);continue
                h=2*y+(1 if 'type=bottom'in s else 2);checked_interfaces+=1
                if abs(h-int(observed[iz,ix]))>1:
                    errors.append(['outside port step',xx,y,zz,h-int(observed[iz,ix])])
        # Independently discover all clear paving within the review volume,
        # including adjacent retained streets outside the design mask.
        points=[]
        for rx in range(x//512,X//512+1):
            for rz in range(z//512,Z//512+1):
                r=e.region(rx*512,rz*512)
                for (cx,cz),v in zip(r['coords'],r['after']):
                    if cx*16>X or cx*16+15<x or cz*16>Z or cz*16+15<z:continue
                    q=road_layers(v,r['names']);q[:,0]+=int(cx)*16;q[:,2]+=int(cz)*16
                    q=q[(q[:,0]>=x)&(q[:,0]<=X)&(q[:,2]>=z)&(q[:,2]<=Z)&(q[:,5]==0)&(q[:,6]==0)]
                    if len(q):points.append(q)
        points=np.concatenate(points);labels=layer_graph(points)
        lookup={(int(v[0]),int(v[2]),int(v[3])):int(c)for v,c in zip(points,labels)}
        commissioned=set()
        for iz,ix in np.argwhere(walk):
            key=(x+int(ix),z+int(iz),int(observed[iz,ix]))
            if key not in lookup:errors.append(['not in actual clear paving graph',*key])
            else:commissioned.add(lookup[key])
        if len(commissioned)!=1:errors.append(['disconnected full-width pavement',path.stem,len(commissioned)])
        crossfall=None
        spec=design.get(path.stem,{})
        if spec and not spec.get('pedestrian',False):
            from map_pipeline.corridors import alignment
            curve,_=alignment(spec);crossfall=0
            radius=spec['carriage_width']/2-.5
            for i in range(1,len(curve)-1,4):
                t=curve[i+1,[0,2]]-curve[i-1,[0,2]];t/=np.linalg.norm(t)
                normal=np.array([-t[1],t[0]])
                left=np.rint(curve[i,[0,2]]+radius*normal).astype(int)
                right=np.rint(curve[i,[0,2]]-radius*normal).astype(int)
                crossfall=max(crossfall,abs(int(observed[left[1]-z,left[0]-x])-int(observed[right[1]-z,right[0]-x]))/2)
            if crossfall>spec.get('maximum_crossfall',.5):errors.append(['carriage crossfall',path.stem,crossfall])
        rows.append(dict(id=path.stem,full_width_columns=int(walk.sum()),outside_interfaces=checked_interfaces,
                         actual_paving_layers_in_review=len(points),commissioned_components=len(commissioned),
                         retired_exterior_pavement_columns=int(retired.sum()),maximum_carriage_crossfall=crossfall))
        e.regions.clear()
    catalog=json.loads((a.plan/'catalog.json').read_text('utf8'))
    for path in (a.candidate/'delta').glob('*.npz'):
        with np.load(path)as f:
            names=f['palette'];air=np.asarray([s.split('[')[0]in AIR for s in names])
            for i,(cx,cz)in enumerate(f['coordinates']):
                lo,hi=f['ranges'][i:i+2];at=f['indices'][lo:hi].astype(np.int64)
                removed=air[f['after'][lo:hi]]&~air[f['before'][lo:hi]]
                q=np.column_stack((cx*16+at[removed]%16,at[removed]//256-128,cz*16+(at[removed]//16)%16))
                for record in catalog:
                    bx,by,bz,bX,bY,bZ=record['occupied_bounds']
                    if bx>cx*16+15 or bX<cx*16 or bz>cz*16+15 or bZ<cz*16:continue
                    bad=(q[:,0]>=bx)&(q[:,0]<=bX)&(q[:,2]>=bz)&(q[:,2]<=bZ)&(q[:,1]<by)
                    if bad.any():errors.append(['retained building undermined',record['id'],q[bad][0].tolist(),int(bad.sum())])
    report=dict(errors=errors,streets=rows,scope='candidate volumes and their existing street interfaces',
                whole_map_completion=False,visual_verified=False)
    (a.candidate/'independent-check.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps(report if len(errors)<10 else dict(errors=len(errors),examples=errors[:10],streets=rows)),flush=True)
    if errors:raise ValueError('Corridor verification failed')
    write_replay_expected(a.candidate)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--candidate',type=Path,required=True);p.add_argument('--plan',type=Path,required=True)
    main(p.parse_args())
