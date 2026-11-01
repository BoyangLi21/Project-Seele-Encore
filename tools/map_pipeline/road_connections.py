"""Join short, surveyed gaps between distinct existing road components.

All edits are prepared in memory and rejected as a unit when they intersect a
building, native transit, water, an unknown chunk or excessive cut/fill. Plot
borders and isolated decorative paving do not qualify as roads.
"""
import argparse,json,math
from pathlib import Path
from collections import Counter
import numpy as np
from author_hakone_lakefront import Editor
from plan_ashi_landscape_r54 import SOIL,PLANTS
from query_blocks import AIR
from verify_hakone_network_candidate import PAVEMENT
from hakone_earthworks import road_blocks


def connect(a):
    f=np.load(a.roads/'retained-components.npz');v=f['points'];labels=f['component']
    asphalt=np.bincount(labels,weights=v[:,4]);sizes=np.bincount(labels)
    proposals=json.loads((a.roads/'terminals.json').read_text('utf8'))['terminals']
    proposals=[r for r in proposals if 'target_component'in r and r['component']!=r['target_component'] and min(sizes[r['component']],sizes[r['target_component']])>=50 and min(asphalt[r['component']],asphalt[r['target_component']])>=25]
    proposals.sort(key=lambda r:r['gap_columns'])
    boxes=[r['occupied_bounds']for r in json.loads((a.plan/'catalog.json').read_text('utf8'))]+json.loads((a.plan/'station-volumes.json').read_text('utf8'))
    boxes+=json.loads((a.candidate/'manifest.json').read_text('utf8'))['preserved_launch_boxes']
    rail=[]
    for row in json.loads((a.plan/'native-curves.json').read_text('utf8'))['trains']:
        rail.extend(row['points'])
    rail=np.asarray(rail)
    e=Editor(a.candidate);done=[];rejected=[];joined=set();evidence=[]
    for row in proposals:
        pair=tuple(sorted((row['component'],row['target_component'])))
        if pair in joined:continue
        x,y,z=row['endpoint'];X,Y,Z=row['target'];distance=math.hypot(X-x,Z-z)
        count=max(2,int(math.ceil(distance*2)));steps=np.linspace(0,1,count+1)
        columns={}
        for t in steps:
            px,pz=round(x+(X-x)*t),round(z+(Z-z)*t);g=round(2*(y+(Y-y)*t)-2)
            for dz in range(-3,4):
                for dx in range(-3,4):
                    if dx*dx+dz*dz<=10:columns[px+dx,pz+dz]=g
        writes={};reason=None;floors=[]
        for (px,pz),g in columns.items():
            hy,slab=road_blocks(np.array(g));hy=int(hy);slab=bool(slab)
            if any(bx<=px<=bX and bz<=pz<=bZ and by<=hy+3 and bY>=hy-8 for bx,by,bz,bX,bY,bZ in boxes):reason='retained building/launch volume';break
            if len(rail) and np.any((abs(rail[:,0]-px)<4)&(abs(rail[:,2]-pz)<4)&(rail[:,1]>=hy-3)&(rail[:,1]<=hy+8)):reason='native rail interface';break
            try:r=e.region(px,pz);c=r['after'][r['index'][px//16,pz//16],:,pz%16,px%16]
            except (FileNotFoundError,KeyError):reason='unknown saved chunk';break
            names=r['names'];bare=[s.split('[')[0]for s in names]
            # Do not trench a fresh tunnel through a mountain or put a road
            # on a tall pedestal merely to make a graph connected.
            geology=[j-128 for j in range(hy+129,min(448,hy+141)) if bare[c[j]]in SOIL]
            if geology and max(geology)>hy+6:reason='requires designed mountain approach';break
            bottom=hy
            while bottom>hy-8 and bare[c[bottom+127]]in AIR|PLANTS:bottom-=1
            if bottom==hy-8:reason='requires bridge or longer embankment';break
            if bare[c[bottom+127]]not in SOIL|PAVEMENT:reason='unsupported or water foundation';break
            for yy in range(bottom,hy+4):
                state=names[c[yy+128]];b=bare[c[yy+128]]
                if b not in SOIL|PLANTS|AIR|PAVEMENT|{'minecraft:light'}:reason='existing non-road object';break
                if yy>hy and b in PAVEMENT:reason='other road layer or structure';break
                # Keep an existing road's precise material and floor level.
                if yy==hy and b in PAVEMENT:
                    fh=2*yy+(1 if 'type=bottom'in state else 2)
                    if abs(fh-(g+2))>1:reason='existing road elevation mismatch';break
                    replacement=state
                else:replacement='minecraft:air'if yy>hy else ('projectseele:road_asphalt_slab[type=bottom,waterlogged=false]'if slab else'minecraft:black_concrete')if yy==hy else'minecraft:stone'
                if replacement!=state:writes[px,yy,pz]=replacement
            if reason:break
            floors.append([px,hy,pz])
        if reason:
            rejected.append(dict(**row,reason=reason));e.regions.clear();continue
        for pos,state in writes.items():e.put(*pos,state)
        for px,hy,pz in floors:
            assert e.state(px,hy,pz).split('[')[0]in PAVEMENT
            assert all(e.state(px,yy,pz).split('[')[0]in AIR|PLANTS|{'minecraft:light'}for yy in(hy+1,hy+2))
        e.save();e.regions.clear();joined.add(pair)
        done.append(dict(**row,width=7,changed_cells=len(writes),columns=len(columns)));evidence.extend(floors)
    rows=e.save();manifest=json.loads((a.candidate/'manifest.json').read_text('utf8'));manifest.update(regions=rows,cells=sum(r['cells']for r in rows))
    (a.candidate/'manifest.json').write_text(json.dumps(manifest,indent=2),'utf8')
    result=dict(connected=done,retained_for_designed_approach=rejected,verified_full_width_floors=evidence,
                graph_only_never_authorizes_edits=True)
    (a.roads/'connections.json').write_text(json.dumps(result,indent=2),'utf8')
    print('Connections',len(done),'deferred',len(rejected),dict(Counter(r['reason']for r in rejected)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for k in('roads','plan','candidate'):p.add_argument('--'+k,type=Path,required=True)
    connect(p.parse_args())
