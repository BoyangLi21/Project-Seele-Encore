"""Rebuild HC-1..4 civil works around the unchanged native railway curve.

Check the complete swept corridor rather than declaring old obstructing road
blocks protected. Existing commissioned road bridges keep their deck volumes.
"""
import argparse,json,os,shutil,math
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from scipy.ndimage import distance_transform_edt
from author_hakone_lakefront import Editor
from query_blocks import AIR,iter_block_entities
from plan_ashi_landscape_r54 import NATURAL,SOIL,PLANTS
from install_r53_carrier_trays import stopped_world
from map_pipeline.launch_protection import load,check_candidate
from map_pipeline.launch_earthworks import ground
from hakone_earthworks import road_blocks

CIVIL={'minecraft:'+n for n in ('light_gray_concrete','gray_concrete','white_concrete','black_concrete','smooth_stone','smooth_stone_slab','stone_bricks','stone_brick_slab','stone_brick_stairs','polished_andesite','polished_deepslate','iron_bars','sea_lantern','stone_brick_wall')}
CIVIL|={'projectseele:road_asphalt_slab','projectseele:road_marking_slab'}

def run(a):
    capture=json.loads((a.source/'capture.json').read_text('utf8'));world=Path(capture['world'])
    a.out.mkdir(parents=True,exist_ok=False)
    for n in ('source','delta','plan'):(a.out/n).mkdir()
    for p in (a.source/'source').glob('*.npz'):os.link(p,a.out/'source'/p.name)
    shutil.copy2(a.source/'capture.json',a.out/'capture.json')
    curves=json.loads(a.curves.read_text('utf8'));rows=[r for r in curves['trains']if r['id']in ('HC-1','HC-2','HC-3','HC-4')]
    assert len(rows)==4
    pts=np.concatenate([r['points']for r in rows]);tree=cKDTree(pts[:,[0,2]])
    x,z,X,Z=capture['bounds_xz'];zz,xx=np.mgrid[z:Z+1,x:X+1];dist,idx=tree.query(np.column_stack([xx.ravel()+.5,zz.ravel()+.5]));dist=dist.reshape(xx.shape);idx=idx.reshape(xx.shape);rail_y=pts[idx,1]
    with np.load(a.source/'measured.npz')as f:old=f['top']
    with np.load(a.streets/'plan/network.npz')as f:
        bx,bz,bX,bZ=map(int,f['bounds']);l,t,r,b=max(x,bx),max(z,bz),min(X,bX),min(Z,bZ)
        walk=np.zeros(xx.shape,bool);grade=np.zeros(xx.shape,np.int16)
        dst=np.s_[t-z:b-z+1,l-x:r-x+1];src=np.s_[t-bz:b-bz+1,l-bx:r-bx+1]
        walk[dst]=f['walk'][src];grade[dst]=f['grade2'][src]
    # Include physical bridge parapets outside the walkable centre. Preserve
    # their finite vertical envelope, never all old blocks near the railway.
    road_distance,road_near=distance_transform_edt(~walk,return_indices=True)
    road_guard=road_distance<=2
    guarded_grade=grade[tuple(road_near)]
    owned=[]
    for row in json.loads((a.authority/'catalog.json').read_text('utf8')):
        if 'occupied_bounds'in row:owned.append(row['occupied_bounds'])
    for row in json.loads((a.authority/'installed-public-spaces.json').read_text('utf8')):
        if isinstance(row,dict)and'bounds'in row:owned.append(row['bounds'])
    core=(dist<=2.25)&(xx>=674)&(xx<=895);sweep=(dist<=2.8)&(xx>=674)&(xx<=895);shoulder=(dist<=12)&(xx>=674)&(xx<=895)
    protected=[];e=Editor(a.out);guard=load(world);masks={};errors=[];removed=[];bearings=[]
    with stopped_world(world):
        shutil.copytree(world/'mtr',a.out/'preserved-native')
        devices={p for p,t in iter_block_entities(world,'projectseele:geofront',(x,-128,z),(X,319,Z))}
    def put(px,py,pz,s,reason):
        before=e.state(px,py,pz)
        if before==s:return
        key=px//16,pz//16
        if key not in masks:masks[key]=guard.chunk_mask(*key)
        if (px,py,pz)in devices or masks[key][py+128,pz%16,px%16]:raise ValueError(('Native protected cell',px,py,pz,reason))
        if before.split('[')[0]not in CIVIL|NATURAL|{'minecraft:light'}:raise ValueError(('Unclassified original object',px,py,pz,before,reason))
        e.put(px,py,pz,s)
    def road_kept(ix,iz,py):
        if not road_guard[iz,ix]:return False
        fy,_=road_blocks(guarded_grade[iz,ix]);return fy-2<=py<=fy+6
    for iz,ix in zip(*np.nonzero(shoulder)):
        px,pz=x+int(ix),z+int(iz);y=float(rail_y[iz,ix]);d=float(dist[iz,ix]);g=int(old[iz,ix]);top2=math.floor(y*2)-2;bed,half=road_blocks(top2)
        # Old road asphalt below the track was previously frozen along with
        # the rails. Remove the whole civil cross-section before building the
        # new bearing; leaving its lower ledges produces the same ragged mess.
        for py in range(max(32,g-3),math.ceil(y+12)+1):
            state=e.state(px,py,pz);mat=state.split('[')[0]
            if mat not in CIVIL or road_kept(ix,iz,py):continue
            if any(q[0]<=px<=q[3]and q[1]<=py<=q[4]and q[2]<=pz<=q[5]for q in owned):continue
            if (px,py,pz)in devices:continue
            removed.append([px,py,pz,state,'retired-complete-old-road-section'])
            put(px,py,pz,'minecraft:air'if py>g else'minecraft:grass_block[snowy=false]'if py==g else'minecraft:dirt','retired-old-road')
        if core[iz,ix]:
            for py in range(g-1,bed):
                if road_kept(ix,iz,py):raise ValueError(('Street under rail support',px,py,pz))
                put(px,py,pz,'minecraft:stone','continuous-bearing')
            mat='minecraft:stone_brick_slab[type=bottom,waterlogged=false]'if top2%2 else'minecraft:gravel'
            put(px,bed,pz,mat,'graded-ballast')
            bearings.append([px,int(bed),pz,int(top2)])
        elif d<=5.8:
            # Symmetric low embankment shoulder: no unsupported white tray.
            h=min(bed-1,math.floor(bed-(d-2.25)*1.3))
            for py in range(g+1,h+1):
                if road_kept(ix,iz,py):continue
                put(px,py,pz,'minecraft:grass_block[snowy=false]'if py==h else'minecraft:dirt'if py>=h-2 else'minecraft:stone','embankment')
        start=bed+1 if core[iz,ix]else max(g+1,bed-1)
        for py in range(start,math.ceil(y+10)+1):
            state=e.state(px,py,pz);mat=state.split('[')[0]
            if road_kept(ix,iz,py):
                if sweep[iz,ix]and py<y+5.0 and mat not in AIR:errors.append(['insufficient-road-crossing-clearance',px,py,pz,y])
                continue
            in_clear=sweep[iz,ix]and py<=math.ceil(y+5.0)
            obsolete=mat in CIVIL and py>=bed-1
            if in_clear or obsolete:
                if mat not in AIR:removed.append([px,py,pz,state,'swept-clearance'if in_clear else'old-road-overlap'])
                put(px,py,pz,'minecraft:air','rail-clearance'if in_clear else'old-road-overlap')
    regions=e.save();e.regions.clear()
    # Independent saved-array verification of every swept column and support.
    for iz,ix in zip(*np.nonzero(sweep)):
        px,pz=x+int(ix),z+int(iz);y=float(rail_y[iz,ix]);top2=math.floor(y*2)-2;bed,_=road_blocks(top2)
        for py in range(bed+1,math.ceil(y+5)+1):
            if e.state(px,py,pz).split('[')[0]not in AIR:errors.append(['rail-swept-solid',px,py,pz,e.state(px,py,pz)])
    for px,bed,pz,top2 in bearings:
        for py in range(int(old[pz-z,px-x]),bed):
            if e.state(px,py,pz).split('[')[0]in AIR:errors.append(['unborne-track',px,py,pz])
    report=dict(errors=errors,retained_native_segments=[r['id']for r in rows],track_columns=len(bearings),swept_columns=int(sweep.sum()),retired_cells=len(removed),launch=check_candidate(guard,a.out),visual_verified=False)
    actual=ground(Editor(a.out),capture['bounds_xz'])
    np.savez_compressed(a.out/'plan/network.npz',bounds=capture['bounds_xz'],ground=actual,old_ground=old,walk=walk,grade2=grade,road=walk,tunnel=np.zeros(walk.shape,bool),marking=np.zeros(walk.shape,bool))
    for name,value in [('manifest.json',dict(world=str(world),bounds_xz=capture['bounds_xz'],regions=regions,cells=sum(r['cells']for r in regions),world_written=False,progress_files_written=[])),('functional-check.json',report),('retired-civil-cells.json',removed),('bearing-columns.json',bearings)]:
        (a.out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items()if k!='launch'}),flush=True)
    if errors:raise ValueError('Rail civil verification failed')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('source','out','curves','streets','authority'):p.add_argument('--'+n,type=Path,required=True)
    run(p.parse_args())
