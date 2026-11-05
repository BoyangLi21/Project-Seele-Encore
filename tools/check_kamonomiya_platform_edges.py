"""Measure whole boarding edges and each longitudinal island aisle offline."""
import argparse,collections,json,math
from pathlib import Path
import numpy as np
from shapely.geometry import LineString,Point,box
from shapely.ops import unary_union
from author_hakone_lakefront import Editor
from query_blocks import AIR

def run(candidate):
    design=json.loads((candidate/'station-design.json').read_text('utf8'));samples=json.loads((candidate/design.get('native_math_samples','native-straight-samples.json')).read_text('utf8'))
    e=Editor(candidate);nodes={tuple(q[:2]) for q in design['public_columns']if q[2]==-156}
    footprint=set(map(tuple,design['platform_columns']));nodes&=footprint
    geometry=unary_union([box(x,z,x+1,z+1)for x,z in nodes])
    lines=[LineString([(p[0],p[2])for p in s['points']])for s in samples];report=[]
    for index,line in enumerate(lines):
        other=lines[1-index];half={q for q in nodes if line.distance(Point(q[0]+.5,q[1]+.5))<=other.distance(Point(q[0]+.5,q[1]+.5))}
        remaining=set(half);components=[]
        while remaining:
            q=remaining.pop();queue=[q];comp={q}
            while queue:
                p=queue.pop()
                for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
                    Q=p[0]+dx,p[1]+dz
                    if Q in remaining:remaining.remove(Q);comp.add(Q);queue.append(Q)
            distances=[line.project(Point(q[0]+.5,q[1]+.5))for q in comp]
            components.append(dict(columns=len(comp),s_min=min(distances),s_max=max(distances),span=max(distances)-min(distances)))
        rows=[];margin=(line.length-120)/2
        for distance in np.arange(0,line.length+.125,.25):
            distance=min(distance,line.length);c=np.asarray(line.interpolate(distance).coords[0]);front=np.asarray(line.interpolate(min(line.length,distance+10)).coords[0]);rear=np.asarray(line.interpolate(max(0,distance-10)).coords[0]);u=front-rear;u/=np.linalg.norm(u);n=np.asarray([-u[1],u[0]])
            peer=np.asarray(other.interpolate(distance/line.length*other.length).coords[0])
            if n@(peer-c)<0:n=-n
            # Existing 20 m train cars have width 2.0; authoring used width 2.5
            # plus a sweep margin, making this a conservative physical gap.
            start=c+n;ray=LineString([start,start+n*10]);hit=ray.intersection(geometry)
            gap=None if hit.is_empty else Point(start).distance(hit)
            intervals=[]
            geoms=list(hit.geoms)if hasattr(hit,'geoms')else[hit]
            for h in geoms:
                if h.geom_type=='LineString'and not h.is_empty:intervals.append([ray.project(Point(h.coords[0])),ray.project(Point(h.coords[-1]))])
            intervals=[sorted(v)for v in intervals];intervals.sort()
            edge_width=intervals[0][1]-intervals[0][0]if intervals else 0
            rows.append(dict(metres=round(float(distance),4),gap_from_two_metre_car=None if gap is None else round(float(gap),4),first_accessible_width=round(edge_width,4),within_centred_120m_consist=bool(margin<=distance<=line.length-margin)))
        active=[r for r in rows if r['within_centred_120m_consist']];gaps=[r['gap_from_two_metre_car']for r in active if r['gap_from_two_metre_car']is not None]
        report.append(dict(platform=index+1,native_length=line.length,capacity_margin_each_end=margin,aisle_components=sorted(components,key=lambda r:-r['span']),boarding_samples=len(active),uncovered_boarding_samples=sum(r['gap_from_two_metre_car']is None for r in active),gap_min=min(gaps),gap_max=max(gaps),first_accessible_width_min=min(r['first_accessible_width']for r in active),rows=rows))
    result=dict(platforms=report,world_written=False,analysis='Perpendicular door-ray to actual reachable ground-level floor voxels; 0.25m samples and separate side-aisle graphs.',engine_boarding_behavior_verified=False,all_line_vehicle_sweep_complete=False)
    (candidate/'platform-edge-review.json').write_text(json.dumps(result,indent=2),'utf8')
    for r in report:print('Platform',r['platform'],'uncovered',r['uncovered_boarding_samples'],'gap',r['gap_min'],r['gap_max'],'longitudinal span',round(r['aisle_components'][0]['span'],2),'components',len(r['aisle_components']))

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--candidate',type=Path,required=True);run(p.parse_args().candidate)
