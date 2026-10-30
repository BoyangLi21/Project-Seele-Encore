"""Trace the surveyed Tozan railway, cable railway and three real switchbacks."""
import argparse,gzip,heapq,json,math
from pathlib import Path
import numpy as np
from shapely.geometry import LineString,Point
from shapely.ops import unary_union,snap
from prepare_hakone_main_terrain import sample_grid


def shortest(graph,start,end):
    queue=[(0,start)];cost={start:0};parent={}
    while queue:
        d,u=heapq.heappop(queue)
        if d!=cost[u]:continue
        if u==end:
            result=[u]
            while u!=start:u=parent[u];result.append(u)
            return result[::-1]
        for v in graph[u]:
            alt=d+math.dist(u,v)
            if alt<cost.get(v,1e20):cost[v]=alt;parent[v]=u;heapq.heappush(queue,(alt,v))
    raise ValueError('Disconnected surveyed railway')


def trace(a):
    features=json.load(gzip.open(a.gis/'features.world.geojson.gz','rt',encoding='utf8'))['features']
    railway=[f for f in features if f['properties'].get('vt_rtcode')=='JR以外'and f['geometry']['type']=='LineString'
             and min(p[0]for p in f['geometry']['coordinates'])<2450 and max(p[0]for p in f['geometry']['coordinates'])>600
             and min(p[1]for p in f['geometry']['coordinates'])<1400 and max(p[1]for p in f['geometry']['coordinates'])>500]
    geometries=[LineString(f['geometry']['coordinates'])for f in railway]
    network=unary_union(geometries);network=unary_union(snap(network,network,.4));graph={}
    for geometry in network.geoms:
        coords=list(geometry.coords)
        for u,v in zip(coords,coords[1:]):
            u,v=tuple(round(x,2)for x in u),tuple(round(x,2)for x in v)
            if u!=v:graph.setdefault(u,set()).add(v);graph.setdefault(v,set()).add(u)
    nearest=lambda p:min(graph,key=lambda q:math.dist(p,q))
    records=json.loads((a.gis/'stations.json').read_text('utf8'));by_name={r['name']:r for r in records}
    gora=nearest(by_name['強羅駅']['track_centre_xz']);yumoto=nearest(by_name['箱根湯本駅']['track_centre_xz'])
    main=shortest(graph,gora,yumoto);mainline=LineString(main)
    # These are observed dead-end branches of the GSI topology, in the correct
    # order confirmed by Hakone Navi's description of the three switchbacks.
    switchbacks=[('kami_ohiradai','上大平台信号场',(1559.81,1091.49)),('ohiradai','大平台駅',(1512.59,979.80)),('deyama','出山信号场',(1840.23,1162.34))]
    branch_rows=[]
    with np.load(a.gis/'terrain-design.npz')as d:grid={k:d[k]for k in ('x','z','height_y')}
    for key,name,p in switchbacks:
        endpoint=nearest(p)
        if len(graph[endpoint])!=1:raise ValueError('Expected measured switchback end')
        current=endpoint;last=None;chain=[current]
        while current not in main:
            candidates=graph[current]-({last}if last else set())
            if len(candidates)!=1:raise ValueError('Ambiguous switchback junction')
            nxt=next(iter(candidates));last,current=current,nxt;chain.append(current)
        y=round(float(sample_grid(grid,'height_y',*endpoint)))+1
        branch_rows.append(dict(id=key,name=name,endpoint=endpoint,junction=current,points=chain[::-1],
                                rail_y=y,main_chainage=mainline.project(Point(current)),passenger=key=='ohiradai'))
    stops=[]
    for key,name in [('gora','強羅駅'),('chokoku','彫刻の森駅'),('kowakudani','小涌谷駅'),('miyanoshita','宮ノ下駅'),
                     ('kami_ohiradai','上大平台信号场'),('ohiradai','大平台駅'),('deyama','出山信号场'),('tonosawa','塔ノ沢駅'),('yumoto','箱根湯本駅')]:
        branch=next((r for r in branch_rows if r['id']==key),None)
        if branch:
            p=branch['endpoint'];y=branch['rail_y'];chainage=branch['main_chainage']
        else:
            row=by_name[name];p=nearest(row['track_centre_xz']);y=round(row['terrain_world_y'])+1;chainage=mainline.project(Point(p))
        stops.append(dict(id=key,name=name,point=p,rail_y=y,main_chainage=chainage,passenger=key not in('kami_ohiradai','deyama'),switchback=branch is not None))
    anchors=sorted((s['main_chainage'],s['rail_y'])for s in stops)
    sections=[];all_points=[]
    for begin,end in zip(stops,stops[1:]):
        points=shortest(graph,tuple(begin['point']),tuple(end['point']));line=LineString(points)
        controls=list(line.simplify(.8,preserve_topology=True).coords)
        full=[]
        for x,z in controls:
            y=float(np.interp(mainline.project(Point(x,z)),*[np.asarray(anchors)[:,i]for i in (0,1)]))
            full.append([x,y,z])
        pieces=[]
        for p,q in zip(points,points[1:]):
            middle=Point((p[0]+q[0])/2,(p[1]+q[1])/2);i=min(range(len(geometries)),key=lambda i:geometries[i].distance(middle))
            pieces.append(dict(points=[p,q],structure=railway[i]['properties'].get('vt_railstate','通常部')))
        sections.append(dict(start=begin['id'],end=end['id'],length=line.length,points=points,controls_xyz=full,structures=pieces));all_points.extend(points)
    cable=shortest(graph,nearest(by_name['早雲山駅']['track_centre_xz']),gora)
    result=dict(source='Cached GSI RailCL vectors; unified 1:4 world coordinates',world_written=False,stations=stops,switchbacks=branch_rows,
                main_points=main,sections=sections,cable_railway=cable,total_operating_length=sum(r['length']for r in sections),
                official_switchback_source='https://www.hakonenavi.jp/hakone-tozan/history/',
                pending=['adapt platforms to player dimensions','native track/path authoring','railway earthworks and retained infrastructure interfaces','stations and complete valley neighbourhoods'])
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(stations=len(stops),passenger_stations=sum(s['passenger']for s in stops),switchbacks=len(branch_rows),operating_length=round(result['total_operating_length']),cable_length=round(LineString(cable).length)),ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('gis','out'):p.add_argument('--'+name,type=Path,required=True)
    trace(p.parse_args())
