"""Plan the wider coast and city around retained water, railways and UN land.

This is a geographic programme. No current block, native service, station or
vehicle is claimed complete by this file; measured construction follows later.
"""
import argparse,gzip,heapq,json,math
from collections import defaultdict
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from scipy.spatial import cKDTree
from shapely.geometry import LineString,Point,box,mapping,shape
from shapely.ops import unary_union
from shapely.prepared import prep
from plan_odawara_core_district import line_parts

DISTRICTS=[
    dict(id='northwest-plain',name='小田原西北平原与站旁聚落',bounds=[2384,-1328,3503,271],style='保留田地、水渠及聚落间空地，沿站前与主路形成低层街坊'),
    dict(id='station-west-castle',name='站西与城址周边',bounds=[3008,272,3424,735],style='保留城址与水域，坡地低层居住，站西完整步行入口'),
    dict(id='ogicho-isida',name='井细田与北城区',bounds=[3200,-64,3679,415],style='沿真实街道形成住宅、沿街商业和学校等公共用地'),
    dict(id='kamonomiya-south',name='鸭宫站南与下新田',bounds=[3680,-64,4511,223],style='站南街坊、生活服务、河岸缓冲带；预留站前换乘'),
    dict(id='sakawa-estuary',name='酒匂河口与东北海岸',bounds=[3680,224,4511,783],style='河口水面、防洪通道、沿海低层街坊和连续干岸空间'),
    dict(id='valley-east',name='入生田—风祭—板桥',bounds=[2384,640,3207,1087],style='河谷聚落与山麓坡地；分别保护铁路、河道和道路层次'),
    dict(id='hayakawa-south',name='早川以南海岸',bounds=[2800,960,3743,1599],style='保留原港与船舶，岸线、渔港外街坊及海岸山坡')]

def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),'utf8')

def plan(a):
    a.out.mkdir(parents=True,exist_ok=False)
    src=json.load(gzip.open(a.geography/'features.world.geojson.gz','rt',encoding='utf8'))
    if not src['provenance']['complete']:raise ValueError('Incomplete regional reference')
    features=src['features'];bounds=src['provenance']['bounds_xz'];clip=box(*bounds)
    layers=defaultdict(list);graph=defaultdict(dict);nodes={};original_edges=0
    for number,f in enumerate(features):
        p=f['properties'];layer=p['source_layer'];g=shape(f['geometry']);layers[layer].append((g,p))
        if layer!='RdCL'or p.get('vt_rdctg')=='高速自動車国道等'or int(p.get('vt_code',0))in(2721,2731):continue
        level=int(p.get('vt_lvorder',0));major=p.get('vt_rdctg')!='市区町村道等'
        for line in line_parts(g):
            coords=list(line.coords)
            for P,Q in zip(coords,coords[1:]):
                u=tuple(map(int,np.rint(np.asarray(P)*10)))+(level,);v=tuple(map(int,np.rint(np.asarray(Q)*10)))+(level,)
                if u==v:continue
                length=math.dist(P,Q);cost=length*(1 if major else 1.6)
                if v in graph[u]and graph[u][v]['cost']<=cost:continue
                nodes[u]=[u[0]/10,u[1]/10];nodes[v]=[v[0]/10,v[1]/10]
                graph[u][v]=graph[v][u]=dict(length=length,cost=cost,level=level,code=int(p['vt_code']),source_feature=number)
                original_edges+=1
    keys=sorted(graph);tree=cKDTree([nodes[k]for k in keys]);joins=0
    for i,j in tree.query_pairs(.25):
        p,q=keys[i],keys[j]
        if p[2]!=q[2]or q in graph[p]:continue
        length=math.dist(nodes[p],nodes[q]);graph[p][q]=graph[q][p]=dict(length=length,cost=max(.001,length),level=p[2],code=0,source_feature=None);joins+=1
    components=[];membership={};remaining=set(keys)
    while remaining:
        first=next(iter(remaining));remaining.remove(first);todo=[first];found=[];index=len(components)
        while todo:
            p=todo.pop();found.append(p);membership[p]=index
            for q in graph[p]:
                if q in remaining:remaining.remove(q);todo.append(q)
        components.append(found)
    _,index=tree.query([3395,510]);core=membership[keys[int(index)]];connected=components[core]
    nearby=cKDTree([nodes[k]for k in connected]);stations=[];terminals=[]
    for station in json.loads((a.gis/'stations.json').read_text('utf8')):
        x,z=station['track_centre_xz']
        if not clip.contains(Point(x,z)):continue
        footprint=LineString(station['station_track']).buffer(18)
        # Passenger forecourts are retained on both sides until the actual
        # track datum and grade-separated entrances are compiled in stage 2.
        reserve=footprint.union(Point(x,z).buffer(34))
        stations.append(dict(name=station['name'],track_centre_xz=[x,z],terrain_y=station['terrain_world_y'],
                             geometry=mapping(reserve),status='reserved geographic station; current native inventory and full construction pending stage 2'))
        distance,i=nearby.query([x,z]);node=connected[int(i)]
        terminals.append(dict(id='station-'+station['name'],label=station['name'],requested_xz=[x,z],node=node,road_node=nodes[node],
                              snap_distance=float(distance),valid_local_access=bool(distance<=65),purpose='station forecourt interface; station construction follows'))
    for ident,label,pos in [('city-east','既有小田原东口街区',[3395,510]),('old-port','既有早川港进出接口',[3064,1070]),
                            ('river-mouth','酒匂河口西岸入口',[3690,440]),('coast-east','东北海岸延伸接口',[4250,260]),
                            ('coast-south','早川南侧海岸接口',[3090,1320]),('west-valley','西侧河谷道路接口',[2410,925])]:
        distance,i=nearby.query(pos);node=connected[int(i)]
        terminals.append(dict(id=ident,label=label,requested_xz=pos,node=node,road_node=nodes[node],snap_distance=float(distance),
                              valid_local_access=bool(distance<=65),purpose='named regional access'))
    start=next(r['node']for r in terminals if r['id']=='city-east');distances={start:0};parents={};queue=[(0,start)]
    while queue:
        d,p=heapq.heappop(queue)
        if d!=distances[p]:continue
        for q,e in graph[p].items():
            proposed=d+e['cost']
            if proposed<distances.get(q,math.inf):distances[q]=proposed;parents[q]=p;heapq.heappush(queue,(proposed,q))
    routes=[];edges={};deferred=[]
    for terminal in terminals:
        if terminal['node']==start:continue
        if not terminal['valid_local_access']:deferred.append(terminal);continue
        path=[terminal['node']]
        while path[-1]!=start:path.append(parents[path[-1]])
        path.reverse();parts=[]
        for p,q in zip(path,path[1:]):
            e=graph[p][q];key=tuple(sorted((p,q)));edges[key]=e;parts.append(e)
        routes.append(dict(destination=terminal['id'],purpose=terminal['purpose'],start='city-east',points=[nodes[p]for p in path],
                           length=sum(e['length']for e in parts),source_civil_segments=sum(e['code']in(2703,2713,2704,2714)for e in parts),
                           current_three_dimensional_geometry_verified=False,game_world_written=False))
    water=unary_union([g for g,_ in layers['WA']]);sea=unary_union([g for g,p in layers['WA']if p['vt_code']==5100])
    railway=unary_union([g for g,_ in layers['RailCL']]);bypass=unary_union([g for g,p in layers['RdCL']if p.get('vt_tollsect')=='有料'])
    un_features=json.load(gzip.open(a.un_reservation/'reservation.geojson.gz','rt',encoding='utf8'))['features']
    un_land=unary_union([shape(f['geometry'])for f in un_features]);port=box(3040,960,3360,1216)
    castle=box(3248,576,3424,716)
    station_reserve=unary_union([shape(s['geometry'])for s in stations])
    reserved=unary_union([water.buffer(5),sea.buffer(17),railway.buffer(17),bypass.buffer(9),station_reserve,un_land,port,castle])
    buildings=[g for g,_ in layers['BldA']];building_tree=None
    from shapely.strtree import STRtree
    building_tree=STRtree(buildings)
    districts=[]
    for row in DISTRICTS:
        g=box(*row['bounds']).intersection(clip);free=g.difference(reserved)
        indices=building_tree.query(g,predicate='intersects')
        merged=unary_union([buildings[i]for i in indices]);parts=[merged]if merged.geom_type=='Polygon'else list(merged.geoms)
        seeds=[]
        for part in parts:
            if part.geom_type!='Polygon':continue
            p=part.representative_point()
            if free.contains(p):seeds.append([round(p.x,2),round(p.y,2)])
        districts.append(dict(**row,reference_building_seed_count=len(seeds),reference_seeds=seeds,available_geographic_area=free.area,
                              no_current_full_block_construction_claim=True,status='planned district; measured design and authoring pending'))
    crossings=[];water_test=prep(water);rail_test=prep(railway.buffer(3))
    for (p,q),e in edges.items():
        line=LineString([nodes[p],nodes[q]])
        reasons=[]
        if e['code']in(2703,2713,2704,2714):reasons.append('mapped bridge or tunnel')
        if water_test.intersects(line):reasons.append('water crossing')
        if rail_test.intersects(line):reasons.append('railway interface')
        if reasons:crossings.append(dict(points=[nodes[p],nodes[q]],reasons=reasons,source_feature=e['source_feature'],required_stage=3))
    save(a.out/'district-programme.json',dict(bounds=bounds,districts=districts,stations=stations,routes=routes,terminals=terminals,
        deferred_terminals=deferred,source_civil_interfaces=crossings,unique_backbone_metres=sum(e['length']for e in edges.values()),
        geographic_nodes=len(keys),sub_block_endpoint_joins=joins,component_count=len(components),
        full_city_earthworks_complete=False,station_phase=2,civil_phase=3,un_relocation_allowed=False,world_written=False))
    with gzip.open(a.out/'reserves.geojson.gz','wt',encoding='utf8')as f:
        json.dump(dict(type='FeatureCollection',features=[dict(type='Feature',properties=dict(kind=k),geometry=mapping(g))for k,g in
                  [('water',water),('station-reserve',station_reserve),('coastal-road-reserve',bypass.buffer(9)),('UN-land-only',un_land),('retained-port',port),('castle',castle)]]),f)
    render(a.out,bounds,layers,districts,stations,routes,un_land)
    print(json.dumps(dict(districts=len(districts),mapped_station_reserves=len(stations),named_journeys=len(routes),
                          unique_backbone_metres=round(sum(e['length']for e in edges.values()),1),deferred_terminals=len(deferred),
                          civil_interface_segments=len(crossings),world_written=False),ensure_ascii=False),flush=True)

def render(out,bounds,layers,districts,stations,routes,un_land):
    x,z,X,Z=bounds;scale=.36;margin=45
    im=Image.new('RGB',(round((X-x)*scale)+margin*2,round((Z-z)*scale)+margin*2),'#e8edda');d=ImageDraw.Draw(im)
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',17);small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',13)
    def pts(v):return [(margin+(p[0]-x)*scale,margin+(p[1]-z)*scale)for p in v]
    def polygon(g,color):
        parts=[g]if g.geom_type=='Polygon'else g.geoms
        for p in parts:
            if p.geom_type!='Polygon':continue
            d.polygon(pts(p.exterior.coords),fill=color)
            for ring in p.interiors:d.polygon(pts(ring.coords),fill='#e8edda')
    for g,_ in layers['WA']:polygon(g,'#a8cbd4')
    polygon(un_land,'#d6b7cc')
    for row in districts:
        a,b,c,e=row['bounds'];d.rectangle([*pts([(a,b)])[0],*pts([(c,e)])[0]],outline='#768577',width=2)
        d.text(pts([(a+10,b+15)])[0],row['name'],font=font,fill='#3b5148')
    for g,_ in layers['RailCL']:
        for line in line_parts(g):d.line(pts(line.coords),fill='#7e7b87',width=1)
    for r in routes:d.line(pts(r['points']),fill='#b58148',width=2)
    for r in stations:
        q=pts([r['track_centre_xz']])[0];d.ellipse([q[0]-3,q[1]-3,q[0]+3,q[1]+3],fill='#4b567e')
    d.rectangle((0,0,im.width,34),fill='#f6f4ef');d.text((18,8),'小田原扩大范围：分区与交通预留（规划图，未完成实装）',font=font,fill='#33453d')
    d.rectangle((0,im.height-30,im.width,im.height),fill='#f6f4ef');d.text((15,im.height-23),'蓝：水域｜紫：UN预留地｜褐：有终点的道路参考｜圆点：第二阶段车站预留',font=small,fill='#33453d')
    im.save(out/'district-programme.png')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('geography','gis','un-reservation','out'):p.add_argument('--'+n,type=Path,required=True)
    plan(p.parse_args())
