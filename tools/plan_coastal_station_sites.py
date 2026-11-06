"""Check explicit coastal station actor/road preservation against frozen captures.

Generic companion for JSON regional plans. No world or native registry writes.
"""
import argparse
import copy
import math
from pathlib import Path
import numpy as np
from author_hakone_lakefront import Editor
from author_station_layout import read,write,source_contract,collision


def check(a):
    c=a.candidate;s=read(c/'layout-authoring.json');source=Path(s['source'])
    cap=read(source/'capture.json');after=read(c/'capture.json');e=Editor(c)
    with np.load(source/'measured.npz')as f:m={k:f[k].copy()for k in f.files}
    with np.load(Path(s['authority'])/'network.npz')as f:
        ax,az,_,_=map(int,f['bounds']);public=f['walk']|f['road'];road=f['road'].copy();grade=f['grade2'].copy()
    actor,overhead=source_contract(s,cap,m,public,road,grade,(ax,az))
    changes=read(c/'exact-edits.json');errors=[];negative=[]
    def records_equal(q):return q.get('actors',[])==cap.get('actors',[])
    if not records_equal(after):errors.append('Actor record changed')
    actorhits=[q['pos']for q in changes if actor(q['pos'])]
    if actorhits:errors.append('Edit touches actor protected mask/body envelope')
    for kind in ('delete','move'):
        bad=copy.deepcopy(after)
        if bad.get('actors'):
            if kind=='delete':bad['actors'].pop()
            else:bad['actors'][0]['pos'][0]+=1
            negative.append(dict(name='actor-record-'+kind,rejected=not records_equal(bad)))
    if cap.get('actors'):
        x,y,z=map(math.floor,cap['actors'][0]['pos'])
        for name,dy in [('body',0),('foot-support',-1),('headroom',2)]:
            p=[x,y+dy,z];negative.append(dict(name='actor-'+name+'-edit',pos=p,rejected=actor(p)))
    bounds=s['bounds'];preserved=[]
    for x in range(bounds[0],bounds[3]+1):
        for z in range(bounds[2],bounds[5]+1):
            if not public[z-az,x-ax]:continue
            feet=float(grade[z-az,x-ax])/2+1;clear=4 if road[z-az,x-ax]else 2
            # Check every paving/headroom voxel, not merely route centre points.
            mismatches=[];new_collisions=[]
            for y in range(math.floor(feet)-1,math.ceil(feet+clear)):
                before=e.state(x,y,z,original=True);state=e.state(x,y,z)
                if before!=state:mismatches.append([x,y,z])
                if y>=feet and collision(state)and not collision(before):new_collisions.append([x,y,z])
            preserved.append(dict(x=x,z=z,feet=feet,clearance=clear,changed=mismatches,new_collisions=new_collisions))
            if mismatches or new_collisions:errors.append('Retained road/walk surface or clearance changed')
    crossings=[q for q in changes if public[q['pos'][2]-az,q['pos'][0]-ax]]
    if any(not overhead(q['pos'],q['before'])for q in crossings):errors.append('Undeclared or low retained-public overpass edit')
    if crossings:
        x,_,z=crossings[0]['pos'];feet=float(grade[z-az,x-ax])/2+1
        for name,y in [('low-bridge-beam',math.floor(feet)+3),('pier-in-carriageway',math.floor(feet)),('original-paving-change',math.floor(feet)-1)]:
            p=[x,y,z];negative.append(dict(name=name,pos=p,rejected=not overhead(p,e.state(*p,original=True))))
    # Exercise the same exception gate at an actual captured carriageway even
    # when the selected candidate avoids crossing it after geographic revision.
    l,t,r,b=cap['bounds_xz'];roadcells=np.argwhere(road[t-az:b-az+1,l-ax:r-ax+1])
    if len(roadcells):
        iz,ix=roadcells[len(roadcells)//2];x,z=int(ix+l),int(iz+t);feet=float(grade[z-az,x-ax])/2+1
        test=copy.deepcopy(s);test['retained_public_overpasses']=[[x,math.floor(feet),z,x,math.ceil(feet+8),z]]
        _,test_over=source_contract(test,cap,m,public,road,grade,(ax,az))
        for name,y in [('low-bridge-beam',math.floor(feet)+3),('pier-in-carriageway',math.floor(feet)),('original-paving-change',math.floor(feet)-1)]:
            p=[x,y,z];negative.append(dict(name=name,pos=p,rejected=not test_over(p,e.state(*p,original=True)),declared_exception_test=True))
        p=[x,math.ceil(feet+5),z];negative.append(dict(name='safe-high-bridge-air-edit-is-accepted',pos=p,rejected=test_over(p,e.state(*p,original=True)),positive_control=True))
        test['retained_public_overpasses']=[];_,closed_over=source_contract(test,cap,m,public,road,grade,(ax,az))
        negative.append(dict(name='undeclared-overpass-rejected',pos=p,rejected=not closed_over(p,e.state(*p,original=True))))
    if cap.get('actors'):
        test=copy.deepcopy(s);test.pop('actor_preservation',None)
        try:source_contract(test,cap,m,public,road,grade,(ax,az));rejected=False
        except ValueError:rejected=True
        negative.append(dict(name='undeclared-actors-rejected',rejected=rejected))
    if not all(q['rejected']for q in negative):errors.append('Preservation negative failed')
    report=dict(errors=errors,world_written=False,original_actors_equal=records_equal(after),actors_retained=len(cap.get('actors',[])),actor_body_or_mask_edits=actorhits,original_public_columns_checked=len(preserved),original_public_columns=preserved,overhead_edits=len(crossings),negative_cases=negative,scope='Exact records plus every unchanged source paving/headroom voxel; source actor masks and conservative individual body envelopes retained')
    write(c/'three-dimensional-source-preservation.json',report)
    print('3D preservation',len(preserved),'street columns',len(cap.get('actors',[])),'actors',errors)
    if errors:raise SystemExit(1)


def survey_stops(a):
    """Find bounded common stopped poses; this is a precheck, not release proof."""
    import shapely
    from shapely.geometry import box,LineString
    from shapely.ops import unary_union
    from map_pipeline.vehicle_envelopes import point,rectangle
    from map_pipeline.mtr_vehicle_pose import pose
    c=read(a.config)['sites'][0];d=read(a.candidate/'station-design.json');native=read(c['native_geometry']);y=c['rail_y'];nodes=set(map(tuple,d['station_multi_level_nodes']));platform=set(map(tuple,d['platform_columns']))
    floor=unary_union([box(x,z,x+1,z+1)for x,g,z in nodes if g in(2*y,2*y-1)and(x,z)in platform]);lines=[LineString(np.asarray(q['points'])[:,[0,2]])for q in native['rails']];middle=np.mean([point(q,q.length/2)for q in lines],axis=0);models={k:read(Path(c['model_source'])/(k+'.json'))for k in c['models']};rows=[]
    offsets=c.get('car_offsets',[-50,-30,-10,10,30,50])
    for stop in sorted(np.arange(-c.get('maximum_stopped_offset',4.5),c.get('maximum_stopped_offset',4.5)+.00001,.125),key=abs):
        fail=[]
        for ri,line in enumerate(lines):
            for ci,off in enumerate(offsets):
                model=models[c['models'][0]if ci==len(offsets)-1 else c['models'][2]if ci==0 else c['models'][1]];ctr,u,n=pose(line,line.length/2+off+stop,c.get('bogie1_position',-4.5),c.get('bogie2_position',4.5),consist_end_distances=(10,10));n=n if np.dot(middle-ctr,n)>0 else -n
                for di,door in enumerate(p for p in model['parts']if p['kind']=='DOORWAY'and p['closed_bounds'][0][0]>=1.249):
                    db=np.asarray(door['closed_bounds']);localz=float(db[:,2].mean());cp=ctr+u*localz;span=float(db[1,2]-db[0,2]);parts=[p for p in model['parts']if p['kind']=='FLOOR'and p['closed_bounds'][0][2]<=localz<=p['closed_bounds'][1][2]and p['closed_bounds'][1][0]>0];half=max(p['closed_bounds'][1][0]for p in parts);combined=floor.union(rectangle(cp,u,n,-.8125,.8125,0,half));valid=False
                    limit=span/2-.3*(abs(u[0])+abs(u[1]))-.001
                    for shift in np.arange(-limit,limit+.00001,.025):
                        p=cp+u*shift+np.linspace(4,.9,129)[:,None]*n;body=shapely.box(p[:,0]-.3,p[:,1]-.3,p[:,0]+.3,p[:,1]+.3);bearing=shapely.area(shapely.intersection(body,combined))
                        if bearing.min()>.025:valid=True;break
                    if not valid:fail.append([ri,ci,di])
        rows.append(dict(stop_offset=float(stop),failed=len(fail),doors=fail));print(float(stop),len(fail),flush=True)
        if not fail:break
    write(a.candidate/'boarding-stop-precheck.json',dict(release_proof=False,rows=rows))

def ports(a):
    """Finite composed native approaches, full model Y bands and rigid-car poses."""
    import gzip
    from shapely.geometry import box,LineString,shape
    from shapely.ops import unary_union
    from shapely.prepared import prep
    from map_pipeline.mtr_vehicle_pose import envelope
    from check_kamonomiya_visible_models import clipped_half_width
    c=read(a.config)['sites'][0];native=read(a.geometry);byid={q['input_rail_id']:q for q in native['rails']};e=Editor(a.candidate);y=c['rail_y'];errors=[];results=[];lines=[];water=unary_union([shape(q['geometry'])for q in read(a.candidate/'layout-authoring.json')['water_features']]).buffer(3)
    for chain in c['port_chains']:
        points=[]
        for segment in chain:
            q=byid[segment['id']];ps=q['points'][::-1]if segment.get('reverse')else q['points']
            if points and not np.allclose(points[-1],ps[0]):raise ValueError('Finite native approach is discontinuous')
            points.extend(ps if not points else ps[1:])
        pts=np.asarray(points)
        if not np.allclose(pts[:,1],y):raise ValueError('This port checker requires the declared level alignment; sloped ports need pitch-aware cubes')
        lines.append(LineString(pts[:,[0,2]]))
    for ri,line in enumerate(lines):
        for ident in c['models']:
            report=read(Path(c['model_source'])/(ident+'.json'))
            with np.load(Path(c['model_source'])/(ident+'-visible-cubes.npz'))as f:cubes=f['cubes'];slides=f['door_slides']
            extent=max(abs(report['visible_motion_bounds'][i][2])for i in(0,1))+.03;hits=[];tested=0;bands=[];cache={}
            for h in range(5):
                widths=[q for v,s in zip(cubes,slides)if(q:=clipped_half_width(v,s,h-.03,h+1+.03))is not None]
                if not widths:continue
                width=max(widths)+.03;poly=envelope(line,length=2*extent,width=2*width,bogie1_position=c['bogie1_position'],bogie2_position=c['bogie2_position'],lateral_margin=0,longitudinal_margin=0,spacing=.125);prepared=prep(poly);bands.append(dict(y=[h,h+1],half_width=width))
                for x in range(math.floor(poly.bounds[0]),math.ceil(poly.bounds[2])):
                    for z in range(math.floor(poly.bounds[1]),math.ceil(poly.bounds[3])):
                        if not prepared.intersects(box(x,z,x+1,z+1)):continue
                        state=e.state(x,y+h,z);tested+=1
                        for q in collision(state):
                            key=h+q[1],h+q[4]
                            if key not in cache:
                                ww=[v for cube,slide in zip(cubes,slides)if(v:=clipped_half_width(cube,slide,key[0]-.03,key[1]+.03))is not None]
                                cache[key]=prep(envelope(line,length=2*extent,width=2*(max(ww)+.03),bogie1_position=c['bogie1_position'],bogie2_position=c['bogie2_position'],lateral_margin=0,longitudinal_margin=0,spacing=.125))if ww else None
                            if cache[key]and cache[key].intersects(box(x+q[0],z+q[2],x+q[3],z+q[5])):hits.append(dict(pos=[x,y+h,z],state=state));break
            results.append(dict(track=ri,model=ident,bands=bands,tested_blocks=tested,obstacles=hits))
            if hits:errors.append('Finite approach full model collision '+str(ri)+'/'+ident)
        bed=line.buffer(1.55,cap_style=2);reserved=bed.intersection(water)
        bed_obstacles=[];water_clearances=[];street_clearances=[]
        source=Path(read(a.candidate/'layout-authoring.json')['source'])
        with np.load(source/'measured.npz')as f:mx,mz,_,_=map(int,f['bounds']);highest=f['highest'].copy()
        with np.load(Path(c['authority'])/'network.npz')as f:ax,az,_,_=map(int,f['bounds']);road=f['road'];walk=f['walk'];grade=f['grade2']
        for x in range(math.floor(bed.bounds[0]),math.ceil(bed.bounds[2])):
            for z in range(math.floor(bed.bounds[1]),math.ceil(bed.bounds[3])):
                if not bed.covers(__import__('shapely').geometry.Point(x+.5,z+.5)):continue
                for h in (y-2,y-1):
                    state=e.state(x,h,z,original=True)
                    if not __import__('author_station_layout').open_state(state):bed_obstacles.append(dict(pos=[x,h,z],state=state))
                if water.intersects(box(x,z,x+1,z+1)):water_clearances.append(y-2-(int(highest[z-mz,x-mx])+1))
                if road[z-az,x-ax]or walk[z-az,x-ax]:street_clearances.append(dict(x=x,z=z,road=bool(road[z-az,x-ax]),clearance=y-2-(float(grade[z-az,x-ax])/2+1)))
        if bed_obstacles:errors.append('Proposed finite rail bed intersects original structure or terrain '+str(ri))
        if any(q['clearance']<(4 if q['road']else 2)for q in street_clearances):errors.append('Finite rail bed would obstruct original street '+str(ri))
        results.append(dict(track=ri,future_bed_obstacles=bed_obstacles,minimum_reserved_water_underside_clearance=min(water_clearances)if water_clearances else None,retained_street_clearances=street_clearances,river_piers_must_remain_on_dry_banks=True))
        results.append(dict(track=ri,complete_composed_length=line.length,water_crossing_centreline_length=line.intersection(water).length,water_reserved_bed_area=reserved.area,vertical_grade=0,finite_endpoints=[list(line.coords[0]),list(line.coords[-1])]))
    report=dict(errors=errors,world_written=False,stage_three_construction_pending=True,native_geometry=str(a.geometry),source=read(a.candidate/'layout-authoring.json')['source'],rail_y=y,rigid_car_bogie1_position=c['bogie1_position'],bogie2_position=c['bogie2_position'],maximum_grade=max(q['maximum_grade']for q in native['rails']),checks=results,remaining_beyond_finite_endpoints_unverified=True,port_chains=c['port_chains'],scope='Both directions use the same continuous rigid full-model envelope with complete cached height bands and 0.125m native samples; no empty-space inference outside capture')
    write(a.candidate/'finite-port-feasibility.json',report);print('Finite ports',errors,flush=True)
    if errors:raise SystemExit(1)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--config',type=Path);p.add_argument('--geometry',type=Path);p.add_argument('--mode',choices=('check','survey-stops','ports'),default='check');a=p.parse_args()
    dict(check=check,**{'survey-stops':survey_stops,'ports':ports})[a.mode](a)
