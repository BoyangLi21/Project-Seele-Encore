"""Turn the reviewed geographic district into a bounded current-block design.

Only the first downtown roads are compiled here. The Hayakawa bridge/interface
and all station structures retain their later commissioned stages.
"""
import argparse
from collections import defaultdict
import gzip
import heapq
import json
import math
from pathlib import Path

import nbtlib
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter
from shapely.geometry import LineString, Point, shape
from shapely.ops import nearest_points, unary_union
from shapely import contains_xy

from author_hakone_district_blocks import Frontage
from install_r53_carrier_trays import stopped_world
from map_pipeline.corridors import alignment
from plan_ashi_landscape_r54 import NATURAL
from prepare_hakone_main_terrain import sample_grid
from query_blocks import iter_block_entities


def save(path,data): path.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')


def prepare(a):
    a.out.mkdir(parents=True,exist_ok=False); survey=a.out/'survey';survey.mkdir()
    capture=json.loads((a.source/'capture.json').read_text('utf8'))
    if capture['unavailable_chunks'] or capture['actors']: raise ValueError('Full unoccupied source required for this new district')
    bounds=capture['bounds_xz'];x,z,X,Z=bounds
    with np.load(a.source/'measured.npz') as f: old=f['top'];full=f['full']
    if not full.all(): raise ValueError('Unknown current block terrain')
    # This new-district compiler has no ownership of any retained construction.
    # Reject it before grading, including construction below the old Y=32 gate.
    yy=np.arange(-128,320)[:,None,None]
    for path in (a.source/'source').glob('*.npz'):
        with np.load(path)as f:coords=f['coordinates'];blocks=f['blocks'];names=list(map(str,f['palette']))
        foreign=np.asarray([s.split('[')[0]not in NATURAL|{'minecraft:bedrock'}for s in names])
        for (cx,cz),v in zip(coords,blocks):
            ground=old[cz*16-z:cz*16-z+16,cx*16-x:cx*16-x+16]
            if np.any(foreign[v]&(yy>=ground-8)): raise ValueError(('Retained construction needs an explicit preservation plan',int(cx),int(cz)))
    world=Path(capture['world'])
    with stopped_world(world): tags=list(iter_block_entities(world,'projectseele:geofront',(x,-128,z),(X,319,Z)))
    if tags: raise ValueError('Native devices require a separate retention plan')
    nbtlib.File({'Devices':nbtlib.List[nbtlib.Compound]([])}).save(survey/'captured-devices.dat',gzipped=True)
    with np.load(a.gis/'runtime-surface-field.npz')as f: grid={k:f[k]for k in ('x','z','height_y')}
    zz,xx=np.mgrid[z:Z+1,x:X+1];surveyed=sample_grid(grid,'height_y',xx,zz)
    np.savez_compressed(survey/'surface.npz',bounds=bounds,old_ground=old,surveyed=surveyed)
    save(survey/'buildings.json',[])
    layout=json.loads((a.layout/'district-plan.json').read_text('utf8'))
    graph=defaultdict(set)
    for route in layout['routes']:
        if route['destination']=='hayakawa-bank':continue
        if route['civil_segments']: raise ValueError(('Bridge or tunnel belongs to civil phase',route['id']))
        for p,q in zip(route['points_xz'],route['points_xz'][1:]):
            p,q=tuple(p),tuple(q)
            if p==q:continue
            if not all(x+12<=v[0]<=X-12 and z+12<=v[1]<=Z-12 for v in (p,q)): raise ValueError(('Road outside finite source',p,q))
            graph[p].add(q);graph[q].add(p)
    smooth=gaussian_filter(surveyed,6)
    wanted={p:float(smooth[int(round(p[1]))-z,int(round(p[0]))-x])+1 for p in graph}
    def envelope(initial):
        distance=dict(initial);queue=[(value,p)for p,value in initial.items()];heapq.heapify(queue)
        while queue:
            value,p=heapq.heappop(queue)
            if value!=distance[p]:continue
            for q in graph[p]:
                proposed=value+math.dist(p,q)*.05
                if proposed<distance[q]-1e-9:distance[q]=proposed;heapq.heappush(queue,(proposed,q))
        return distance
    upper=envelope(wanted);lower=envelope({p:-h for p,h in wanted.items()})
    heights={p:(upper[p]-lower[p])/2 for p in graph}
    visited=set();chains=[]
    def edge(p,q):return tuple(sorted((p,q)))
    starts=sorted((p for p in graph if len(graph[p])!=2))
    for start in starts:
        for nxt in sorted(graph[start]):
            if edge(start,nxt)in visited:continue
            chain=[start,nxt];visited.add(edge(start,nxt))
            while len(graph[chain[-1]])==2:
                previous,p=chain[-2:];q=next(q for q in graph[p]if q!=previous)
                if edge(p,q)in visited:break
                chain.append(q);visited.add(edge(p,q))
            chains.append(chain)
    if len(visited)!=sum(map(len,graph.values()))//2:raise ValueError('Unconsumed closed road component')
    streets=[];public_paths=[];adaptations=[]
    for chain in chains:
        # Preserve junctions, simplify only the internal geographic samples.
        line=LineString(chain).simplify(layout.get('district_config',{}).get('horizontal_simplification',.4),preserve_topology=True)
        coords=list(line.coords);points=[[p[0],heights[tuple(p)],p[1]]for p in coords]
        if any(math.dist(p,(3421.2,625.2))<.2 for p in coords):
            before=[p.copy()for p in points]
            # The playable roadway is wider than this 1:4 source street. Keep
            # the complete moat and move the east/south bank road onto land.
            for p in points:
                if p[2]>700:p[2]+=8
                if p[0]>3415 and p[2]>620:p[0]+=8
            entry=next(p for p in before if math.dist((p[0],p[2]),(3377.9,705.3))<.2)
            public_paths.append(dict(id='castle-south-bank-entrance',points=[[entry[0],entry[1],entry[2]+8],entry],width=3,maximum_grade=.1))
            adaptations.append(dict(reason='preserve the surveyed moat while allowing playable carriageway and sidewalks',source_points=before,points=points))
        if any(math.dist(p,(3423.0,452.8))<.2 for p in coords):
            before=[p.copy()for p in points]
            for p in points:
                if math.dist((p[0],p[2]),(3409.4,485.0))<.2:p[0]+=8
                if math.dist((p[0],p[2]),(3423.0,452.8))<.2:p[0]+=10;p[2]+=4
            adaptations.append(dict(reason='keep the full paved width east of the mapped Daiyuzan railway corridor',source_points=before,points=points))
        prefix=layout.get('district_config',{}).get('id','odawara-downtown')
        district_cfg=layout.get('district_config',{})
        spec=dict(id=f'{prefix}-street-{len(streets)+1:02}',points=points,width=district_cfg.get('carriageway_width',7),sidewalk=district_cfg.get('sidewalk_width',2),centre_line=False,
                  maximum_grade=.09,arc_length_grade=True,linear_grade=True)
        curve,along=alignment(spec)
        if len(points)<2 or along[-1]<.1:raise ValueError('Collapsed street chain')
        streets.append(spec)
    all_curves=[alignment(row)[0]for row in streets]
    planar=[LineString(curve[:,[0,2]])for curve in all_curves]
    rows=[];footways=[];deferred=[]
    road_footprints=unary_union([p.buffer(6)for p in planar])
    programme_names={'shop':'商店','house':'住居','cafe':'喫茶','office':'事務所','inn':'旅館'}
    for index,lot in enumerate(layout['lots']):
        if shape(lot['lot_geometry']).intersects(road_footprints):
            deferred.append(dict(id=lot['id'],reason='revised full-width bank road requires this land; no building authored'))
            continue
        # Keep the intended facade-side road after bank alignment changes.
        # Choosing a new globally nearest road can send a south entrance back
        # through its own house toward a now-closer western carriageway.
        anchor=Point(*lot['approach_xz'][-1]);nearest=min(range(len(planar)),key=lambda i:anchor.distance(planar[i]));curve=all_curves[nearest]
        goal=nearest_points(anchor,planar[nearest])[1];xz=np.asarray([goal.x,goal.y]);k=int(np.linalg.norm(curve[:,[0,2]]-xz,axis=1).argmin())
        floor=int(round(float(curve[k,1]-1)))
        site=dict(centre=lot['centre'],half=lot['half'],floor=floor,floors=int(lot['floors']),rotation=int(lot['rotation']),variant=index)
        c=Frontage(site);hx,hz=site['half'];lo=c.point(-hx-2,-2,-hz-2);hi=c.point(hx+2,site['floors']*5+9,hz+3)
        occupied=[*map(int,np.minimum(lo,hi)),*map(int,np.maximum(lo,hi))]
        approach=c.point(0,1,hz+4);door=c.point(0,1,hz)
        if LineString([[approach[0],approach[2]],[goal.x,goal.y]]).intersects(shape(lot['lot_geometry']).buffer(-.05)):
            raise ValueError(('Frontage approach enters its own building',lot['id']))
        district_label=layout.get('district_config',{}).get('label','小田原')
        row=dict(id=lot['id'],programme=lot['programme'],label=district_label+' '+programme_names[lot['programme']],use=programme_names[lot['programme']],
                 site=site,occupied_bounds=occupied,approach=approach,door=door,roof_style=lot['roof_style'])
        rows.append(row)
        footways.append(dict(parcel=lot['id'],points=[approach,[round(float(goal.x)),float(curve[k,1]),round(float(goal.y))]]))
    geographic=json.load(gzip.open(a.geography/'features.world.geojson.gz','rt',encoding='utf8'))['features']
    water=Image.new('1',(X-x+1,Z-z+1));draw=ImageDraw.Draw(water)
    for f in geographic:
        if f['properties']['source_layer']!='WA':continue
        g=f['geometry'];polys=[g['coordinates']]if g['type']=='Polygon'else g['coordinates']if g['type']=='MultiPolygon'else[]
        for rings in polys:
            draw.polygon([(round(px-x),round(pz-z))for px,pz in rings[0]],fill=1)
            for hole in rings[1:]:draw.polygon([(round(px-x),round(pz-z))for px,pz in hole],fill=0)
    np.savez_compressed(a.out/'geographic-water.npz',bounds=bounds,wet=np.asarray(water,bool))
    rail=unary_union([shape(f['geometry'])for f in geographic if f['properties']['source_layer']=='RailCL']).buffer(3)
    np.savez_compressed(a.out/'geographic-rail.npz',bounds=bounds,blocked=contains_xy(rail,xx,zz))
    cfg=layout.get('district_config',{})
    spec=dict(name=cfg.get('name','Odawara first downtown district'),odawara_new_district=True,togendai_forecourt=False,surface_water_guard=True,
              geographic_water_mask=str(a.out/'geographic-water.npz'),core=cfg.get('core',[3344,448,3680,768]),earthwork_blend_distance=32,
              geographic_rail_mask=str(a.out/'geographic-rail.npz'),
              streets=streets,new_frontages=rows,footways=footways,public_paths=public_paths,retained_ports=[],parcel_floors={},
              geographic_street_adaptations=adaptations,deferred_geographic_lots=deferred,
              retained_soil_areas=[],protected_volumes=[],preserve_train_corridors=True,
              connectivity_seed=list(map(round,layout['terminals'][0]['road_node'])),
              old_public_retirement_areas=[],un_relocation_allowed=False,station_structures_deferred_to_stage=2,
              hayakawa_civil_interface_deferred_to_stage=3)
    save(a.out/'authored-design.json',spec)
    save(a.out/'compilation.json',dict(streets=len(streets),buildings=len(rows),current_full_chunks=capture['chunk_statuses']['full'],existing_constructions=0,devices=0,
                                     max_road_height_adjustment=max(abs(heights[p]-wanted[p])for p in graph),
                                     measured_save_captured=True,game_world_written=False))
    print('Downtown design ready:',len(streets),'street chains;',len(rows),'building lots',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('source','layout','geography','gis','out'):p.add_argument('--'+name,type=Path,required=True)
    prepare(p.parse_args())
