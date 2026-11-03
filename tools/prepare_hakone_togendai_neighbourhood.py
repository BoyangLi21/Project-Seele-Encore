"""Reconstruct the station neighbourhood from current FULL arrays, offline.

Whole retained buildings travel with their complete block payload and NBT.
Road ownership, parcel bounds and retained station volumes are explicit inputs;
the installed save is only read under the common cold-world lock.
"""
import argparse,copy,json,os,shutil
from collections import defaultdict
from pathlib import Path
import numpy as np
import nbtlib
from scipy.ndimage import distance_transform_edt,binary_dilation,binary_erosion,label
from scipy.spatial import cKDTree
from author_hakone_lakefront import Editor
from hakone_earthworks import grade_ground,road_blocks,min_slope_envelope
from map_pipeline.corridors import alignment,fit_ports
from map_pipeline.launch_earthworks import ground
from map_pipeline.launch_protection import load,check_candidate
from prepare_hakone_city_cross import packed
from query_blocks import AIR
from plan_ashi_landscape_r54 import SOIL,PLANTS
from verify_hakone_network_candidate import PAVEMENT

EMPTY=AIR|PLANTS|{'minecraft:light'}
PAVE={'minecraft:black_concrete','minecraft:white_concrete','minecraft:smooth_stone','minecraft:smooth_stone_slab','projectseele:road_asphalt_slab','projectseele:road_marking_slab','minecraft:stone_bricks','minecraft:stone_brick_stairs','minecraft:stone_brick_slab'}

def save_json(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')

def rect(bounds,box):
    x,z,X,Z=map(int,bounds);a,c,A,C=map(int,box)
    return np.s_[max(c,z)-z:min(C,Z)-z+1,max(a,x)-x:min(A,X)-x+1]


def station_forecourt(bounds,old,road,walk,grade2,mark):
    x,z,_,_=map(int,bounds)
    forecourt=rect(bounds,[-326,979,-246,996]);walk[forecourt]=True;grade2[forecourt]=218
    road[forecourt]=False;road[rect(bounds,[-324,980,-248,985])]=True
    walk[rect(bounds,[-326,989,-246,990])]=True;grade2[rect(bounds,[-326,989,-246,990])]=218
    mark[forecourt]=False
    for px in range(-326,-245):
        for pz in range(989,997):
            if any(old.state(px,y,pz).split('[')[0]not in EMPTY|SOIL for y in range(110,113)):
                walk[pz-z,px-x]=False
    walk[rect(bounds,[-289,997,-285,1002])]=True;grade2[rect(bounds,[-289,997,-285,1002])]=218

def design(a):
    a.out.mkdir(parents=True,exist_ok=False)
    with np.load(a.survey/'surface.npz')as f:d={k:f[k]for k in f.files}
    bounds=d['bounds'];x,z,X,Z=map(int,bounds);zz,xx=np.mgrid[z:Z+1,x:X+1];shape=xx.shape
    rows=json.loads((a.survey/'buildings.json').read_text('utf8'))
    old=Editor(a.source);road=np.zeros(shape,bool);walk=road.copy();grade2=np.zeros(shape,np.int16);mark=road.copy()
    design=json.loads(a.design.read_text('utf8'));streets=[]
    for row in design['streets']:
        curve,along=alignment(row);dist,near=cKDTree(curve[:,[0,2]]).query(np.column_stack([xx.ravel(),zz.ravel()]));dist=dist.reshape(shape);near=near.reshape(shape)
        r=dist<=row['width']/2;w=dist<=row['width']/2+row.get('sidewalk',2)
        h2=np.rint((curve[near,1]-1)*2).astype(np.int16)
        conflict=walk&w&(abs(h2-grade2)>4)
        if conflict.any():
            # Shared intersections have one continuous running surface.
            j,i=np.argwhere(conflict)[0];raise ValueError(('incompatible junction',row['id'],int(i+x),int(j+z),int(grade2[j,i]),int(h2[j,i])))
        h2[walk&w]=grade2[walk&w]
        h2=fit_ports(w&~walk,h2,walk,grade2)
        road|=r;walk|=w;grade2[w]=h2[w]
        if row.get('centre_line',True):mark|=r&(dist<.6)&((along[near]//4).astype(int)%2==0)
        streets.append(dict(id=row['id'],length=float(along[-1]),maximum_continuous_grade=float((abs(np.diff(curve[:,1]))/np.linalg.norm(np.diff(curve[:,[0,2]],axis=0),axis=1)).max())))
    # Preserve existing station entrance and shelters. Rebuild its carriageway
    # at one datum, with a generous continuous passenger pavement in front.
    if design.get('togendai_forecourt',True):station_forecourt(bounds,old,road,walk,grade2,mark)
    with np.load(a.catalog.parent/'network.npz')as f:
        bx,bz,_,_=map(int,f['bounds']);area=np.s_[z-bz:Z-bz+1,x-bx:X-bx+1]
        previous_walk=f['walk'][area].copy();previous_grade=f['grade2'][area].copy()
    ports=np.zeros(shape,bool)
    for port in design['retained_ports']:
        row=next(r for r in design['streets']if r['id']==port['street']);px,_,pz=row['points'][port['end']]
        adjacent=np.asarray(row['points'][1 if port['end']==0 else -2])[[0,2]]
        outward=np.asarray([px,pz],float)-adjacent;outward/=np.linalg.norm(outward)
        ports|=(np.hypot(xx-px,zz-pz)<port.get('radius',18))&((xx-px)*outward[0]+(zz-pz)*outward[1]>0)
    retained_walk=previous_walk&ports&~walk
    grade2=fit_ports(walk,grade2,retained_walk,previous_grade)
    # Retained junctions can have curbs, planting strips or a rounded cap.
    # Include only their existing standing pavement, without widening them
    # through protected structures or silently accepting an unpaved cell.
    materials=PAVEMENT|set(design.get('retained_pavement_materials',[]))
    for box in design.get('trim_retained_pavement',[]):
        zone=np.zeros(shape,bool);zone[rect(bounds,box)]=True
        for j,i in np.argwhere(walk&zone):
            h,slab=road_blocks(grade2[j,i]);state=old.state(int(i+x),int(h),int(j+z))
            valid=state.split('[')[0]in materials and ('type=bottom'in state)==bool(slab)
            valid&=all(old.state(int(i+x),int(h)+k,int(j+z)).split('[')[0]in EMPTY for k in (1,2,3))
            if not valid:walk[j,i]=False;road[j,i]=False;mark[j,i]=False
    plots=np.zeros(shape,bool);plotfloor=np.zeros(shape,np.int16);newrows=[]
    for row in rows:
        box=row['payload_bounds'];dx,dz=map(int,design.get('parcel_offsets_xz',{}).get(row['id'],[0,0]))
        px0,_,pz0,px1,_,pz1=box;px0+=dx;px1+=dx;pz0+=dz;pz1+=dz
        if px0<x or px1>X or pz0<z or pz1>Z:raise ValueError(('Relocated parcel outside captured design',row['id']))
        area=rect(bounds,[px0,pz0,px1,pz1]);target=int(design['parcel_floors'].get(row['id'],row['surveyed_floor']))
        if walk[area].any():raise ValueError(('road meets retained parcel',row['id']))
        plots[area]=True;plotfloor[area]=target
        q=copy.deepcopy(row);q['dy']=target-row['site']['floor'];q['site']['floor']=target
        q['translation']=[dx,q['dy'],dz];q['site']['centre']=[q['site']['centre'][0]+dx,q['site']['centre'][1]+dz]
        for key in ('door','approach'):q[key]=[v+q['translation'][i]for i,v in enumerate(q[key])]
        q['new_payload_bounds']=[v+q['translation'][i%3]for i,v in enumerate(box)]
        newrows.append(q)
    # Explicit footways have their own grade; complete surfaces are solved
    # before any terrain is composed. They never cross a retained wall.
    np.savez_compressed(a.out/'debug-streets.npz',bounds=bounds,road=road,walk=walk,grade2=grade2,plots=plots,plotfloor=plotfloor)
    footways=[]
    for spec in design.get('public_paths',[]):
        curve,along=alignment(spec);dist,near=cKDTree(curve[:,[0,2]]).query(np.column_stack([xx.ravel(),zz.ravel()]));dist=dist.reshape(shape);near=near.reshape(shape)
        w=dist<=spec.get('width',3)/2;h2=np.rint((curve[near,1]-1)*2).astype(np.int16)
        if np.any(w&plots):raise ValueError(('public path crosses parcel',spec['id']))
        h2=fit_ports(w&~walk,h2,walk,grade2);use=w&~walk;walk|=w;grade2[use]=h2[use]
        footways.append(dict(id=spec['id'],points=spec['points'],length=float(along[-1])))
    for spec in design['footways']:
        row=next(r for r in newrows if r['id']==spec['parcel']);path=np.asarray(spec['points'],float)
        start=np.asarray(row['approach'],float);end=path[-1]
        if np.linalg.norm(start[[0,2]]-path[0,[0,2]])>.1:raise ValueError(('wrong parcel approach',row['id']))
        path[0,1]=row['site']['floor']+1
        endj,endi=int(end[2])-z,int(end[0])-x
        if not walk[endj,endi]:raise ValueError(('footway has no street',row['id'],end.tolist()))
        path[-1,1]=float(grade2[endj,endi])/2+1
        spec=dict(spec,id=row['id'],points=path.tolist(),maximum_grade=.5,arc_length_grade=True)
        curve,along=alignment(spec);dist,near=cKDTree(curve[:,[0,2]]).query(np.column_stack([xx.ravel(),zz.ravel()]));dist=dist.reshape(shape);near=near.reshape(shape)
        w=dist<=1.45;h2=np.rint((curve[near,1]-1)*2).astype(np.int16)
        # Copied entrance apron is immutable. Begin at its surveyed level.
        targetplot=plots&w
        if np.any(targetplot&(abs(h2-plotfloor*2)>1)):raise ValueError(('footway enters a different plot',row['id']))
        w&=~plots
        if np.any(walk&w&(abs(h2-grade2)>6)):raise ValueError(('footway junction needs approach adjustment',row['id']))
        try:h2=fit_ports(w&~walk,h2,walk|plots,np.where(plots,plotfloor*2,grade2))
        except ValueError as exc:raise ValueError((row['id'],str(exc)))from exc
        use=w&~walk;walk|=w;grade2[use]=h2[use];footways.append(dict(parcel=row['id'],points=path.tolist(),length=float(along[-1])))
    core=np.zeros(shape,bool);core[rect(bounds,design['core'])]=True
    active=binary_dilation(core|walk|plots,iterations=8)
    blend_distance=float(design.get('earthwork_blend_distance',55))
    if blend_distance<=0:raise ValueError('Earthwork blend distance must be positive')
    distance=distance_transform_edt(~(core|walk|plots));blend=np.clip(1-distance/blend_distance,0,1)
    surveyed=d['old_ground']*(1-blend)+d['surveyed']*blend
    # Lake and original station lower floors are not soil anchors for fill.
    wet=np.zeros(shape,bool)
    for (rx,rz) in [(i,j)for i in range(x//512,X//512+1)for j in range(z//512,Z//512+1)]:
        r=old.region(rx*512,rz*512);water=np.array([s.split('[')[0]=='minecraft:water'for s in r['names']])
        for (cx,cz),v in zip(r['coords'],r['before']):
            px,pz=int(cx)*16,int(cz)*16;l,t,R,B=max(x,px),max(z,pz),min(X,px+15),min(Z,pz+15)
            if l>R or t>B:continue
            wet[t-z:B-z+1,l-x:R-x+1]=water[v[227,t-pz:B-pz+1,l-px:R-px+1]]
        old.regions.clear()
    if np.any(wet&walk):
        j,i=np.argwhere(wet&walk)[0];raise ValueError(('new street over measured lake',int(i+x),int(j+z)))
    known=d['old_ground']>-129
    fixed=((distance>=blend_distance)|wet|retained_walk)&known
    retained=[]
    moved_ids={r['id']for r in rows}
    for r in json.loads(a.catalog.read_text('utf8')):
        if r.get('id')in moved_ids:continue
        box=r['occupied_bounds'];px0,_,pz0,px1,_,pz1=box
        if px0>X or px1<x or pz0>Z or pz1<z:continue
        fixed[rect(bounds,[px0-3,pz0-3,px1+3,pz1+3])]=True
        retained.append(box)
    fixed&=known
    station_soil=np.zeros(shape,bool)
    for box in design.get('retained_soil_areas',[[-316,994,-255,1115]]):station_soil[rect(bounds,box)]=True
    # The retained four-level station already has structural walls. Its lower
    # soil is preserved without forcing a natural slope through those rooms.
    fixed&=~station_soil
    bridge=np.zeros(shape,bool)
    for box in design.get('bridge_spans',[]):bridge[rect(bounds,box)]=True
    innerplots=binary_erosion(plots,iterations=2)
    anchor=(walk&~bridge)|innerplots|fixed;anchor_y=d['old_ground'].copy();anchor_y[walk]=(grade2[walk]+1)//2-1;anchor_y[innerplots]=plotfloor[innerplots]-3
    target,conflict=grade_ground(surveyed,anchor,anchor_y,slope=1)
    np.savez_compressed(a.out/'debug-grades.npz',bounds=bounds,road=road,walk=walk,grade2=grade2,plots=plots,plotfloor=plotfloor,fixed=fixed,anchor_y=anchor_y,wet=wet,conflict=conflict,target=target,old_ground=d['old_ground'])
    if np.any(conflict & ((walk&~bridge)|innerplots)):
        j,i=np.argwhere(conflict&((walk&~bridge)|innerplots))[0];raise ValueError(('terrain anchor conflict',int(i+x),int(j+z)))
    target[wet|fixed|station_soil|bridge|~known]=d['old_ground'][wet|fixed|station_soil|bridge|~known]
    if any(np.any(edge)for edge in((target-d['old_ground'])[0],(target-d['old_ground'])[-1],(target-d['old_ground'])[:,0],(target-d['old_ground'])[:,-1])):raise ValueError('Nonzero earthwork at crop edge')
    np.savez_compressed(a.out/'design.npz',bounds=bounds,road=road,walk=walk,grade2=grade2,marking=mark,plots=plots,plotfloor=plotfloor,ground=target,old_ground=d['old_ground'],wet=wet,core=core,retained_walk=retained_walk,ports=ports,bridge=bridge)
    save_json(a.out/'buildings.json',newrows);save_json(a.out/'streets.json',streets);save_json(a.out/'footways.json',footways);shutil.copy2(a.design,a.out/'authored-design.json')
    save_json(a.out/'retained-buildings.json',retained)
    save_json(a.out/'design-report.json',dict(buildings=len(rows),moves=sum(r['dy']!=0 for r in newrows),maximum_lift=max(r['dy']for r in newrows),streets=streets,road_columns=int(road.sum()),public_columns=int(walk.sum()),earthwork_columns=int((target!=d['old_ground']).sum()),world_written=False))
    print((a.out/'design-report.json').read_text('utf8'),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('source','survey','catalog','design','out'):p.add_argument('--'+name,type=Path,required=True)
    design(p.parse_args())
