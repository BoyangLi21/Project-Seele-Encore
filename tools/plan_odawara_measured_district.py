"""Plan a finite new district from complete measured soil and geographic streets.

All new streets share one connected reference component. Water, rail, station,
UN and previously authored columns are excluded before choosing parcels.
This emits a candidate layout only; the regular physical/NBT checks follow.
"""
import argparse,gzip,heapq,json,math
from collections import defaultdict,Counter
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from scipy.ndimage import binary_dilation
from scipy.spatial import cKDTree
from shapely.geometry import LineString,Point,Polygon,box,mapping,shape
from shapely.ops import nearest_points,unary_union
from shapely.prepared import prep
from plan_ashi_landscape_r54 import NATURAL
from plan_odawara_core_district import line_parts

def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),'utf8')

def plan(a):
    a.out.mkdir(parents=True,exist_ok=False)
    cfg=json.loads(a.config.read_text('utf8'));cap=json.loads((a.source/'capture.json').read_text('utf8'))
    if cap['unavailable_chunks']or cap['actors']:raise ValueError('Full unoccupied source required')
    with np.load(a.source/'measured.npz')as f:d={k:f[k]for k in f.files}
    bounds=list(map(int,d['bounds']));x,z,X,Z=bounds
    inner=box(x+16,z+16,X-16,Z-16);urban=box(*cfg['core'])
    if not inner.covers(urban):raise ValueError('Core lacks a finite measured margin')
    foreign=np.zeros(d['top'].shape,bool);wet=foreign.copy();yy=np.arange(-128,320)[:,None,None]
    for p in(a.source/'source').glob('*.npz'):
        with np.load(p)as f:coords=f['coordinates'];blocks=f['blocks'];names=list(map(str,f['palette']))
        owned=np.asarray([s.split('[')[0]not in NATURAL|{'minecraft:bedrock'}for s in names]);water=np.asarray([s.split('[')[0]=='minecraft:water'for s in names])
        for(cx,cz),v in zip(coords,blocks):
            sl=np.s_[cz*16-z:cz*16-z+16,cx*16-x:cx*16-x+16];g=d['top'][sl]
            foreign[sl]=(owned[v]&(yy>=g-8)).any(0);wet[sl]=(water[v]&(yy>=g)).any(0)
    # The new-district compiler cannot relocate or grade existing construction.
    # A mixed source requires an explicit separate preservation design.
    oldwalk=np.zeros_like(foreign)
    if cfg.get('preserve_existing_district',False):
        if a.authority is None:raise ValueError('An installed authority is required for retained construction')
        with np.load(a.authority/'network.npz')as f:
            ax,az,aX,aZ=map(int,f['bounds'])
            if not(ax<=x<X<=aX and az<=z<Z<=aZ):raise ValueError('Source exceeds installed authority')
            oldwalk=f['walk'][z-az:Z-az+1,x-ax:X-ax+1].copy()
    elif foreign.any():raise ValueError(('Existing construction in new-district source',int(foreign.sum())))
    blocked_columns=binary_dilation(foreign&~oldwalk,iterations=3)|wet
    def hits_obstacle(g):
        l,t,r,b=g.bounds;l=max(x,int(math.floor(l)));r=min(X,int(math.ceil(r)));t=max(z,int(math.floor(t)));b=min(Z,int(math.ceil(b)))
        if l>r or t>b:return False
        zz,xx=np.mgrid[t:b+1,l:r+1]
        from shapely import contains_xy
        return bool(np.any(contains_xy(g,xx,zz)&blocked_columns[t-z:b-z+1,l-x:r-x+1]))
    src=json.load(gzip.open(a.geography/'features.world.geojson.gz','rt',encoding='utf8'))
    if not src['provenance']['complete']:raise ValueError('Incomplete geographic reference')
    fs=[];clip=box(*bounds)
    for f in src['features']:
        g=shape(f['geometry'])
        if g.intersects(clip):fs.append((g,f['properties']))
    reserves=json.load(gzip.open(a.programme/'reserves.geojson.gz','rt',encoding='utf8'))['features']
    reserved=[g.intersection(clip)for f in reserves if (g:=shape(f['geometry'])).intersects(clip)]
    rail=unary_union([g for g,p in fs if p['source_layer']=='RailCL']).buffer(17)
    water=unary_union([g for g,p in fs if p['source_layer']=='WA']).buffer(4)
    reserved=unary_union([*reserved,rail,water]);road_blocker=prep(reserved.buffer(6.5))
    graph=defaultdict(dict);nodes={}
    for number,(g,p)in enumerate(fs):
        if p['source_layer']!='RdCL'or p.get('vt_rdctg')=='高速自動車国道等'or int(p.get('vt_code',0))in(2721,2731,2703,2713,2704,2714):continue
        level=int(p.get('vt_lvorder',0));major=p.get('vt_rdctg')!='市区町村道等'
        for line in line_parts(g):
            for P,Q in zip(list(line.coords),list(line.coords)[1:]):
                line=LineString([P,Q])
                if not inner.covers(line)or road_blocker.intersects(line)or hits_obstacle(line.buffer(6.5)):continue
                u=tuple(map(int,np.rint(np.asarray(P)*10)))+(level,);v=tuple(map(int,np.rint(np.asarray(Q)*10)))+(level,)
                if u==v:continue
                length=math.dist(P,Q);cost=length*(1 if major else 1.3)
                if v in graph[u]and graph[u][v]['cost']<=cost:continue
                nodes[u]=[u[0]/10,u[1]/10];nodes[v]=[v[0]/10,v[1]/10]
                graph[u][v]=graph[v][u]=dict(length=length,cost=cost,source_feature=number)
    keys=sorted(graph);tree=cKDTree([nodes[k]for k in keys]);joins=0
    for i,j in tree.query_pairs(.25):
        p,q=keys[i],keys[j]
        if p[2]!=q[2]or q in graph[p]:continue
        line=LineString([nodes[p],nodes[q]])
        if road_blocker.intersects(line):continue
        length=math.dist(nodes[p],nodes[q]);graph[p][q]=graph[q][p]=dict(length=length,cost=max(.001,length),source_feature=None);joins+=1
    # Keep the road components visible even when a requested destination would
    # need a railway/water crossing that belongs to the later civil phase.
    remaining=set(graph);components=[]
    while remaining:
        first=min(remaining);component={first};queue=[first];remaining.remove(first)
        while queue:
            for q in graph[queue.pop()]:
                if q in remaining:remaining.remove(q);component.add(q);queue.append(q)
        component_edges=[(p,q,e)for p in component for q,e in graph[p].items()if p<q]
        components.append(dict(length=sum(e['length']for p,q,e in component_edges),
            nodes=[nodes[p]for p in sorted(component)],
            edges=[[nodes[p],nodes[q]]for p,q,e in component_edges]))
    components.sort(key=lambda r:-r['length'])
    save(a.out/'available-road-components.json',dict(bounds_xz=bounds,components=components,world_written=False))
    network_image=Image.new('RGB',((X-x+1)*2,(Z-z+1)*2),'#e4ead8');network_draw=ImageDraw.Draw(network_image)
    colours=['#a13b28','#28518a','#7a3491','#358044','#996510','#305f60','#964f75']
    for rank,c in enumerate(components):
        colour=colours[rank%len(colours)]if rank<14 else '#aeb7a7'
        for p,q in c['edges']:network_draw.line([((v[0]-x)*2,(v[1]-z)*2)for v in(p,q)],fill=colour,width=3)
    for ident,label,pos in cfg['terminals']:
        px,pz=(pos[0]-x)*2,(pos[1]-z)*2
        network_draw.ellipse((px-5,pz-5,px+5,pz+5),fill='black')
        network_draw.text((px+8,pz),ident,fill='black')
    network_image.save(a.out/'available-road-components.png')
    _,index=tree.query(cfg['terminals'][0][2]);start=keys[int(index)]
    component={start};queue=[start]
    while queue:
        for q in graph[queue.pop()]:
            if q not in component:component.add(q);queue.append(q)
    connected=sorted(component);near=cKDTree([nodes[k]for k in connected]);terminals=[]
    for ident,label,pos in cfg['terminals']:
        distance,index=near.query(pos)
        if distance>42:raise ValueError(('Named destination lacks local road',ident,float(distance),nodes[connected[int(index)]]))
        node=connected[int(index)];terminals.append(dict(id=ident,label=label,requested_xz=pos,road_node=nodes[node],node=node,snap_distance=float(distance)))
    start=terminals[0]['node'];best={start:0};parent={};queue=[(0,start)]
    while queue:
        value,p=heapq.heappop(queue)
        if value!=best[p]:continue
        for q,e in graph[p].items():
            v=value+e['cost']
            if v<best.get(q,math.inf):best[q]=v;parent[q]=p;heapq.heappush(queue,(v,q))
    routes=[];edges={}
    for terminal in terminals[1:]:
        path=[terminal['node']]
        while path[-1]!=start:path.append(parent[path[-1]])
        path.reverse()
        for p,q in zip(path,path[1:]):edges[tuple(sorted((p,q)))]=graph[p][q]
        routes.append(dict(id=cfg['id']+'-to-'+terminal['id'],destination=terminal['id'],points_xz=[nodes[p]for p in path],civil_segments=0))
    selected=unary_union([LineString([nodes[p],nodes[q]])for p,q in edges])
    roadside_reserve=cfg.get('carriageway_width',7)/2+cfg.get('sidewalk_width',2)+2
    occupied=unary_union([reserved,selected.buffer(roadside_reserve)])
    old_plot_exclusion=binary_dilation(oldwalk,iterations=3)|blocked_columns
    buildings=unary_union([g for g,p in fs if p['source_layer']=='BldA'and g.intersects(urban)])
    parts=[buildings]if buildings.geom_type=='Polygon'else list(buildings.geoms)
    seeds=[]
    for g in parts:
        if g.geom_type!='Polygon':continue
        p=g.representative_point();distance=p.distance(selected)
        if urban.contains(p)and 14<=distance<=32:seeds.append((distance,-g.area,p.x,p.y,g))
    lots=[];rejected=Counter()
    for _,_,cx0,cz0,original in sorted(seeds,key=lambda r:r[:4]):
        cx,cz=int(round(cx0)),int(round(cz0));p=Point(cx,cz);near=nearest_points(p,selected)[1]
        dx,dz=near.x-cx,near.y-cz;rotation=(3 if dx>0 else 1)if abs(dx)>abs(dz)else(0 if dz>0 else 2)
        hx,hz=cfg.get('building_half',[5,6]);corners=np.asarray([[-hx-2,-hz-2],[hx+2,-hz-2],[hx+2,hz+3],[-hx-2,hz+3]])
        door=np.asarray([0,hz+4])
        for _ in range(rotation):corners=np.column_stack([-corners[:,1],corners[:,0]]);door=np.asarray([-door[1],door[0]])
        corners+=[cx,cz];door+=[cx,cz];footprint=Polygon(corners);approach=LineString([door,[near.x,near.y]])
        if not urban.covers(footprint):rejected['core edge']+=1;continue
        if occupied.intersects(footprint):rejected['road/reservation/earlier plot']+=1;continue
        if reserved.intersects(approach.buffer(1.6)):rejected['reserved approach']+=1;continue
        if any(approach.buffer(1.6).intersects(shape(r['lot_geometry']))for r in lots):rejected['approach through parcel']+=1;continue
        l,t,r,b=map(int,footprint.bounds);sample=d['top'][t-z:b-z+1,l-x:r-x+1]
        if np.ptp(sample)>5:rejected['measured slope']+=1;continue
        if old_plot_exclusion[t-z:b-z+1,l-x:r-x+1].any():rejected['existing construction/water']+=1;continue
        if hits_obstacle(approach.buffer(1.6)):rejected['approach obstruction']+=1;continue
        number=len(lots);programme=('house','house','shop','house','cafe','house','office','inn')[number%8]
        lots.append(dict(id=f"{cfg['id']}/{number+1:03}",programme=programme,centre=[cx,cz],half=[hx,hz],rotation=rotation,
            indicative_floor=int(np.median(sample)),floors=2+(programme=='office'),roof_style='flat'if programme in('shop','office')else'gable',
            lot_geometry=mapping(footprint),approach_xz=[door.tolist(),[near.x,near.y]],source_building_area=original.area,reference_building_centre=[cx0,cz0]))
        occupied=unary_union([occupied,footprint.buffer(3),approach.buffer(2)])
        if len(lots)>=cfg['maximum_buildings']:break
    result=dict(district_config=cfg,bounds_xz=bounds,terminals=terminals,routes=routes,lots=lots,route_unique_length=sum(e['length']for e in edges.values()),
        geographic_conflicts=[],reference_plot_seeds=len(seeds),rejected_plot_seeds=dict(rejected),source=str(a.geography),measured_source=str(a.source),full_chunks=cap['chunk_statuses']['full'],
        no_existing_construction=not bool(foreign.any()),retained_authority=str(a.authority)if a.authority else None,
        station_structures_complete=False,vehicle_clearance_complete=False,world_written=False)
    save(a.out/'district-plan.json',result)
    im=Image.new('RGB',((X-x+1)*2,(Z-z+1)*2),'#e4ead8');dr=ImageDraw.Draw(im)
    def pts(v):return[((p[0]-x)*2,(p[1]-z)*2)for p in v]
    for g,p in fs:
        if p['source_layer']=='RdCL':
            for line in line_parts(g):dr.line(pts(line.coords),fill='#c0c9b8')
        if p['source_layer']=='RailCL':
            for line in line_parts(g):dr.line(pts(line.coords),fill='#846284',width=3)
    for r in routes:dr.line(pts(r['points_xz']),fill='#665647',width=8)
    for r in lots:dr.polygon(pts(shape(r['lot_geometry']).exterior.coords),fill='#b2926f',outline='#665343')
    for r in terminals:
        px,pz=pts([r['road_node']])[0];dr.ellipse((px-4,pz-4,px+4,pz+4),fill='#404b68')
    im.save(a.out/'district-plan.png')
    print(json.dumps(dict(buildings=len(lots),reference_seeds=len(seeds),rejected=dict(rejected),street_length=result['route_unique_length'],terminals=[dict(id=r['id'],snap=round(r['snap_distance'],1))for r in terminals],world_written=False)),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('source','geography','programme','config','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--authority',type=Path)
    plan(p.parse_args())
