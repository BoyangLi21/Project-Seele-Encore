"""Measure curved Midoricho options against cached JR, old streets and soil."""
import argparse, collections, json, math
from pathlib import Path
import numpy as np
from shapely.geometry import Point, LineString, Polygon, box, shape, mapping
from shapely.ops import unary_union
from author_hakone_lakefront import Editor
from author_kamonomiya_station import ALLOWED


def pose(line,s):
    p=np.asarray(line.interpolate(max(0,min(line.length,s))).coords[0])
    a=np.asarray(line.interpolate(max(0,s-4.5)).coords[0]);b=np.asarray(line.interpolate(min(line.length,s+4.5)).coords[0])
    u=(b-a)/np.linalg.norm(b-a);return p,u,np.array([-u[1],u[0]])


def envelope(line):
    polygons=[]
    for s in np.arange(0,line.length+.125,.25):
        p,u,n=pose(line,s)
        polygons.append(Polygon([p+u*4.775+n*1.4625,p-u*4.775+n*1.4625,
                                  p-u*4.775-n*1.4625,p+u*4.775-n*1.4625]))
    return unary_union(polygons)


def run(a):
    a.out.mkdir(exist_ok=False)
    site=json.loads(a.site.read_text('utf8'));rails=site['cached_rail_evidence']
    jr=unary_union([shape(q['geometry'])for q in rails if q['properties'].get('vt_rtcode')=='JR'])
    water=unary_union([shape(q['geometry'])for q in site['nearby_water_interfaces']]).buffer(3)
    samples=json.loads(a.samples.read_text('utf8'));e=Editor(a.source)
    with np.load(a.authority/'network.npz')as f:ax,az,_,_=map(int,f['bounds']);old=f['walk']
    memo={};rows=[]
    def free(x,z):
        if (x,z)not in memo:
            memo[x,z]=not old[z-az,x-ax]and not water.intersects(box(x,z,x+1,z+1))and all(e.state(x,y,z,True).split('[')[0]in ALLOWED for y in range(-82,-69))
        return memo[x,z]
    for sample in samples:
        line=LineString([(p[0],p[2])for p in sample['points']]);body=envelope(line);l,t,r,b=body.bounds
        for outer in (3.5,4,4.5,5):
            cells=[];public=[];foreign=[]
            for z in range(math.floor(t)-5,math.ceil(b)+6):
                for x in range(math.floor(l)-5,math.ceil(r)+6):
                    q=Point(x+.5,z+.5);s=line.project(q);p,u,n=pose(line,s)
                    side=float((np.asarray(q.coords[0])-p)@n);cube=box(x,z,x+1,z+1)
                    if not(0<s<line.length and 0<side<outer)or cube.intersects(body):continue
                    if cube.distance(jr)<4.5:continue
                    if old[z-az,x-ax]:public.append([x,z]);continue
                    if not free(x,z):foreign.append([x,z]);continue
                    cells.append((x,z))
            platform=unary_union([box(x,z,x+1,z+1)for x,z in cells])
            cross=[]
            for s in np.arange(1,line.length,1):
                p,u,n=pose(line,s);ray=LineString([p+n*1.3125,p+n*8]);inter=ray.intersection(platform)
                segments=[inter]if inter.geom_type=='LineString'else list(getattr(inter,'geoms',[]))
                segments=[g for g in segments if g.geom_type=='LineString'and g.length>1e-8]
                if not segments:cross.append(dict(s=float(s),gap=None,width=0));continue
                closest=min(segments,key=lambda q:q.distance(Point(p)))
                cross.append(dict(s=float(s),gap=float(closest.distance(Point(p))-1.3125),width=float(closest.length)))
            known=[q['gap']for q in cross if q['gap']is not None]
            row=dict(id=sample['id'],outer_offset=outer,native_length=sample['native_length'],
                     rail_to_JR_minimum_distance=line.distance(jr),swept_body_to_JR_reference_distance=body.distance(jr),
                     reserved_JR_halfwidth=4.5,JR_reserve_overlap=body.intersection(jr.buffer(4.5)).area,
                     candidate_platform_columns=len(cells),old_public_conflict_columns=public,foreign_columns=foreign,
                     platform_components=len(platform.geoms)if platform.geom_type=='MultiPolygon'else 1,
                     full_length_minimum_width=min(q['width']for q in cross),no_platform_cross_sections=sum(q['width']==0 for q in cross),
                     gap_range=[min(known),max(known)]if known else None,measured_cross_sections=cross,
                     platform_columns=cells,platform_geometry=mapping(platform),swept_body_geometry=mapping(body))
            rows.append(row)
            print(row['id'],outer,'JR overlap',round(row['JR_reserve_overlap'],2),'public',len(public),'width',round(row['full_length_minimum_width'],2),'gaps',list(map(lambda v:round(v,3),row['gap_range']or[])),flush=True)
    (a.out/'probes.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf8')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for k in('source','authority','site','samples','out'):p.add_argument('--'+k,type=Path,required=True)
    run(p.parse_args())
