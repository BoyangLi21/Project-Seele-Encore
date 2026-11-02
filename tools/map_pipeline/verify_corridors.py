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
    with np.load(a.plan/'network.npz')as f:p={k:f[k]for k in ('bounds','walk','grade2')}
    px,pz,_,_=map(int,p['bounds'])
    for path in(a.candidate/'earthworks').glob('*.npz'):
        with np.load(path)as f:d={k:f[k]for k in f.files}
        x,z,X,Z=map(int,d['bounds']);walk=d['walk'];floor,slab=road_blocks(d['grade2'])
        observed=np.full(walk.shape,-32768,np.int32)
        for iz,ix in np.argwhere(walk):
            xx,zz,y=x+int(ix),z+int(iz),int(floor[iz,ix]);state=e.state(xx,y,zz)
            if state.split('[')[0]not in PAVEMENT:errors.append(['floor',xx,y,zz,state]);continue
            observed[iz,ix]=2*y+(1 if 'type=bottom'in state else 2)
            for yy in range(y+1,y+int(d.get('clearance',5))+1):
                if e.state(xx,yy,zz).split('[')[0]not in AIR|PLANTS|{'minecraft:light'}:
                    errors.append(['clearance',xx,yy,zz,e.state(xx,yy,zz)])
            for yy in range(min(int(d['old'][iz,ix]),y)-1,y):
                if e.state(xx,yy,zz).split('[')[0]in AIR|{'minecraft:water','minecraft:lava'}:
                    errors.append(['support',xx,yy,zz,e.state(xx,yy,zz)])
        base_walk=p['walk'][z-pz:Z-pz+1,x-px:X-px+1]
        base_grade=p['grade2'][z-pz:Z-pz+1,x-px:X-px+1]
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
        rows.append(dict(id=path.stem,full_width_columns=int(walk.sum()),outside_interfaces=checked_interfaces,
                         actual_paving_layers_in_review=len(points),commissioned_components=len(commissioned)))
        e.regions.clear()
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
