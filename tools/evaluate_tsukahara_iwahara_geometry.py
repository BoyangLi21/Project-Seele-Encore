"""Exact native curves, visible rigid model envelope and diagonal floor edges."""
import argparse,json,math
from pathlib import Path
from collections import Counter
import numpy as np
from shapely.geometry import Point,LineString,Polygon,box,shape,mapping
from shapely.ops import unary_union
from map_pipeline.station_sections import StationSections
from plan_ashi_landscape_r54 import SOIL,NATURAL

def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,default=lambda x:x.item()),'utf8')

def point(line,s):
    if s<0:
        p=np.asarray(line.coords[0]);u=np.asarray(line.coords[1])-p;return p+u/np.linalg.norm(u)*s
    if s>line.length:
        p=np.asarray(line.coords[-1]);u=p-np.asarray(line.coords[-2]);return p+u/np.linalg.norm(u)*(s-line.length)
    return np.asarray(line.interpolate(s).coords[0])

def rect(c,u,n,a,b,d,e):return Polygon([c+u*a+n*d,c+u*b+n*d,c+u*b+n*e,c+u*a+n*e])

def envelope(line,length=9.25,width=2.625):
    polygons=[]
    for s in np.arange(0,line.length+.125,.25):
        c=point(line,min(s,line.length));u=point(line,s+4.5)-point(line,s-4.5);u/=np.linalg.norm(u);n=np.array([-u[1],u[0]])
        polygons.append(rect(c,u,n,-length/2-.04,length/2+.04,-width/2-.04,width/2+.04))
    return unary_union(polygons)

def components(cells):
    remaining=set(cells);result=[]
    while remaining:
        q=remaining.pop();found={q};queue=[q]
        while queue:
            x,z=queue.pop()
            for p in ((x+1,z),(x-1,z),(x,z+1),(x,z-1)):
                if p in remaining:remaining.remove(p);found.add(p);queue.append(p)
        result.append(len(found))
    return sorted(result,reverse=True)

def main(a):
    a.out.mkdir(exist_ok=False);evidence=json.loads((a.geometry/'site-evidence.json').read_text('utf8'));samples={q['id']:q for q in json.loads((a.geometry/'native-samples.json').read_text('utf8'))}
    source=StationSections(a.source);rows=[]
    for variant in evidence['variants']:
        order=[variant['transition_ids'][0],variant['platform_ids'][0],variant['link_id'],variant['platform_ids'][1],variant['transition_ids'][1]]
        sections=[np.asarray(samples[k]['points'])for k in order];combined=LineString(np.concatenate([p[:,[0,2]]if i==0 else p[1:,[0,2]]for i,p in enumerate(sections)]));sweep=envelope(combined)
        tangents=[]
        for left,right in zip(sections,sections[1:]):
            u=left[-1,[0,2]]-left[-2,[0,2]];v=right[1,[0,2]]-right[0,[0,2]]
            tangents.append(float(np.degrees(np.arccos(np.clip(u@v/np.linalg.norm(u)/np.linalg.norm(v),-1,1)))))
        stations=[]
        for number,(station,key)in enumerate(zip(evidence['stations'],variant['platform_ids'])):
            q=samples[key];pts=np.asarray(q['points']);line=LineString(pts[:,[0,2]]);rail_y=int(pts[0,1]);u=pts[-1,[0,2]]-pts[0,[0,2]];u/=np.linalg.norm(u);n=np.array([-u[1],u[0]]);centre=point(line,line.length/2)
            region=rect(centre,u,n,-line.length/2,line.length/2,0,8);l,b,r,t=region.bounds;cells=[]
            for x in range(math.floor(l),math.ceil(r)):
                for z in range(math.floor(b),math.ceil(t)):
                    cube=box(x,z,x+1,z+1)
                    if region.covers(Point(x+.5,z+.5))and not cube.intersects(sweep):cells.append((x,z))
            platform=unary_union([box(x,z,x+1,z+1)for x,z in cells]);edges=[];margin=(line.length-18.25)/2
            for distance in np.arange(0,line.length+.125,.125):
                distance=min(distance,line.length);c=point(line,distance);uu=point(line,distance+4.5)-point(line,distance-4.5);uu/=np.linalg.norm(uu);nn=np.array([-uu[1],uu[0]])
                ray=LineString([c,c+nn*12]);hit=ray.intersection(platform);gap=None if hit.is_empty else Point(c).distance(hit)-1.3125
                edges.append(dict(s=float(distance),gap_from_visible_half_width=gap,active_18_25m_consist=margin<=distance<=line.length-margin))
            doors=[]
            for car in(-4.5,4.5):
                s=line.length/2+car;c=point(line,s);uu=point(line,s+4.5)-point(line,s-4.5);uu/=np.linalg.norm(uu);nn=np.array([-uu[1],uu[0]])
                trigger=rect(c,uu,nn,-.875,.875,1.25,1.5);car_floor=rect(c,uu,nn,-1.1875,1.1875,0,1.25);floor=platform.union(car_floor);solutions=[]
                for shift in np.arange(-.4,.4001,.025):
                    longitudinal=c+uu*shift;ray=LineString([longitudinal+nn*1.25,longitudinal+nn*8]);hit=ray.intersection(platform)
                    if hit.is_empty:continue
                    gap=Point(longitudinal+nn*1.25).distance(hit)
                    if gap>.35:continue
                    start=longitudinal+nn*3;end=longitudinal+nn*.8;okay=True;least=1.;trigger_contact=False
                    for f in np.linspace(0,1,100):
                        p=start+(end-start)*f;body=box(p[0]-.3,p[1]-.3,p[0]+.3,p[1]+.3)
                        corners=np.asarray(body.exterior.coords)[:-1];along=(corners-c)@uu
                        if max(abs(along.min()),abs(along.max()))>.85:okay=False;break
                        bearing=body.intersection(floor).area;least=min(least,bearing)
                        if bearing<.025:okay=False;break
                        trigger_contact|=body.intersection(trigger).area>.005
                    if okay and trigger_contact:solutions.append(dict(longitudinal_offset=float(shift),gap_from_visible_door_floor=gap,min_footprint_bearing=least,from_xz=start.tolist(),to_xz=end.tolist(),assumes_fully_open_native_door=True))
                doors.append(dict(car_centre_s=s,solutions=sorted(solutions,key=lambda s:s['gap_from_visible_door_floor']),doorway_is_nonvisible_trigger=True))
            nearby=station['nearby_gis'];waters=[shape(f['geometry'])for f in nearby if f['properties']['source_layer']in('WA','RvrCL','WStrL')]
            water=unary_union(waters).buffer(3);wet=[list(c)for c in cells if box(c[0],c[1],c[0]+1,c[1]+1).intersects(water)]
            conflict=[];soil_heights=[]
            for x,z in cells:
                for y in range(rail_y-4,rail_y+6):
                    st=source.state(x,y,z)
                    if st is None or st.split('[')[0]not in NATURAL|{'minecraft:light'}:conflict.append([x,y,z,st])
                soil_heights.append(max([rail_y-8]+[y for y in range(rail_y-7,rail_y+5)if (source.state(x,y,z)or'').split('[')[0]in SOIL]))
            active=[e for e in edges if e['active_18_25m_consist']]
            stations.append(dict(name=station['name'],rail_id=key,rail_y=rail_y,platform_native_length=line.length,actual_visible_consist_length=18.25,end_margin=margin,
                platform_columns=[list(c)for c in cells],platform_four_connected_components=components(cells),boarding_edges=edges,
                active_uncovered=sum(r['gap_from_visible_half_width']is None for r in active),active_gap_min=min(r['gap_from_visible_half_width']for r in active if r['gap_from_visible_half_width']is not None),active_gap_max=max(r['gap_from_visible_half_width']for r in active if r['gap_from_visible_half_width']is not None),
                doorway_candidates=doors,water_buffer_intersections=wet,original_object_conflicts=conflict,ground_range=[min(soil_heights),max(soil_heights)],platform_geometry=mapping(platform)))
        row=dict(variant=variant['id'],native_segments=order,joint_tangent_errors_degrees=tangents,maximum_native_grade=max(samples[k]['maximum_sampled_grade']for k in order),stations=stations,geometry_only=True,world_written=False)
        rows.append(row)
        print(variant['id'],'joint',round(max(tangents),3),'grade',round(row['maximum_native_grade'],4),flush=True)
        for s in stations:print(s['name'],'cells',len(s['platform_columns']),'components',s['platform_four_connected_components'],'gap',round(s['active_gap_min'],3),round(s['active_gap_max'],3),'door solutions',[len(d['solutions'])for d in s['doorway_candidates']],'water',len(s['water_buffer_intersections']),'objects',len(s['original_object_conflicts']),flush=True)
    write(a.out/'review.json',dict(variants=rows,model_assumptions=dict(visible_width=2.625,visible_length=9.25,native_car_length=9,consist_cars=2,doorway_width=3,doorway_longitudinal_width=1.75,visible_door_floor_width=2.5),world_written=False,operating_service_claimed=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('geometry','source','out'):p.add_argument('--'+n,type=Path,required=True)
    main(p.parse_args())
