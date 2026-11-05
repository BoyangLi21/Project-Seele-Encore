"""Lay out bounded Odawara districts from detailed GSI road/building geometry.

This is a reviewable geographic layout, not a block installation. Every route
has named endpoints, retains its source road geometry, and flags bridge/tunnel
segments for the later three-dimensional civil pass. Playable lots adapt the
surveyed density; they are not exact reproductions of real businesses.
"""
import argparse
from collections import Counter, defaultdict
import gzip
import heapq
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point, Polygon, box, mapping, shape
from shapely.ops import unary_union

from prepare_hakone_main_terrain import sample_grid


TERMINALS = [
    ('odawara-east', '小田原站东口预留广场', [3396, 510]),
    ('midoricho', '绿町站换乘入口预留', [3450, 414]),
    ('sakaecho-north', '荣町北侧商业街', [3460, 445]),
    ('sakaecho-centre', '荣町中心商业街', [3460, 570]),
    ('civic-quarter', '本町公共服务街区', [3465, 645]),
    ('honcho-main', '本町干道交叉口', [3440, 727]),
    ('miyukinohama', '御幸海滨步行入口', [3493, 743]),
    ('hamacho-east', '滨町东侧街区', [3583, 648]),
    ('coast-northeast', '北侧海滨延伸接口', [3665, 573]),
    ('castle-northeast', '城址东北入口', [3419, 610]),
    ('castle-south', '城址南侧街道', [3390, 705]),
    ('minamicho', '南町居住街区', [3335, 750]),
    ('hayakawa-bank', '早川北岸接口', [3266, 853]),
]


def line_parts(geometry):
    if geometry.geom_type == 'LineString':
        return [geometry]
    if geometry.geom_type in ('MultiLineString', 'GeometryCollection'):
        return [p for g in geometry.geoms for p in line_parts(g)]
    return []


def make_plan(a):
    a.out.mkdir(parents=True, exist_ok=False)
    source = json.load(gzip.open(a.geography / 'features.world.geojson.gz', 'rt', encoding='utf8'))
    if not source['provenance']['complete']:
        raise ValueError('The selected geographic reference is incomplete')
    features = source['features']
    bounds = source['provenance']['bounds_xz']
    boundary = box(*bounds)
    graph = defaultdict(dict)
    node_points = {}
    reference_roads = []
    rails = []
    waters = []
    buildings = []
    for number, f in enumerate(features):
        props = f['properties']; layer = props['source_layer']; geom = shape(f['geometry'])
        if layer == 'RailCL':
            rails.extend(line_parts(geom))
        elif layer == 'WA':
            waters.append(geom)
        elif layer == 'BldA':
            buildings.extend([geom] if geom.geom_type == 'Polygon' else list(geom.geoms))
        elif layer == 'RdCL':
            reference_roads.extend(line_parts(geom))
            if props.get('vt_rdctg') == '高速自動車国道等' or int(props.get('vt_code', 0)) in (2721, 2731):
                continue
            level = int(props.get('vt_lvorder', 0))
            major = props.get('vt_rdctg') != '市区町村道等' or props.get('vt_rnkwidth') in ('13m-19.5m未満', '19.5m以上')
            for line in line_parts(geom):
                coords = list(line.coords)
                for p, q in zip(coords, coords[1:]):
                    kp = tuple(map(int, np.rint(np.asarray(p) * 10))) + (level,)
                    kq = tuple(map(int, np.rint(np.asarray(q) * 10))) + (level,)
                    if kp == kq:
                        continue
                    length = math.dist(p, q)
                    cost = length * (1 if major else 1.6)
                    node_points[kp] = [kp[0] / 10, kp[1] / 10]
                    node_points[kq] = [kq[0] / 10, kq[1] / 10]
                    old = graph[kp].get(kq)
                    if old is None or cost < old['cost']:
                        edge = dict(cost=cost, length=length, source_feature=number, code=int(props['vt_code']), major=major, level=level)
                        graph[kp][kq] = graph[kq][kp] = edge
    # Tile-buffer clipping can leave sub-block gaps. Join endpoints only when
    # they coincide within 0.25 blocks at the same source transport level.
    keys = sorted(graph); points = np.asarray([node_points[k] for k in keys]); tree = cKDTree(points)
    snapped = 0
    for i, j in sorted(tree.query_pairs(.25)):
        p, q = keys[i], keys[j]
        if p[2] != q[2] or q in graph[p]:
            continue
        length = float(np.linalg.norm(points[i] - points[j]))
        graph[p][q] = graph[q][p] = dict(cost=max(length, .001), length=length, source_feature=None, code=0, major=False, level=p[2])
        snapped += 1
    components = []; remaining = set(keys)
    while remaining:
        first = next(iter(remaining)); found = {first}; stack = [first]; remaining.remove(first)
        while stack:
            for q in graph[stack.pop()]:
                if q in remaining:
                    remaining.remove(q); found.add(q); stack.append(q)
        components.append(found)
    # Anchor to the component containing the station east-side approach, then
    # require every other destination to be reachable within its own locality.
    _, first_i = tree.query(TERMINALS[0][2]); station_node = keys[int(first_i)]
    component = next(c for c in components if station_node in c)
    local_keys = sorted(component); local_tree = cKDTree([node_points[k] for k in local_keys])
    terminals = []
    for ident, label, pos in TERMINALS:
        distance, index = local_tree.query(pos)
        if distance > 24:
            raise ValueError(('Destination lacks a nearby connected geographic road', ident, float(distance)))
        node = local_keys[int(index)]
        terminals.append(dict(id=ident, label=label, requested_xz=pos, road_node=node_points[node], node=node, snap_distance=float(distance)))
    start = terminals[0]['node']; distance = {start: 0}; parents = {}; queue = [(0, start)]
    while queue:
        cost, p = heapq.heappop(queue)
        if cost != distance[p]:
            continue
        for q, edge in graph[p].items():
            value = cost + edge['cost']
            if value < distance.get(q, float('inf')):
                distance[q] = value; parents[q] = p; heapq.heappush(queue, (value, q))
    routes = []; selected_edges = {}
    for terminal in terminals[1:]:
        path = [terminal['node']]
        while path[-1] != start:
            path.append(parents[path[-1]])
        path.reverse(); edges = [graph[p][q] for p, q in zip(path, path[1:])]
        points = [node_points[p] for p in path]
        if len(set(map(tuple, points))) < 2:
            raise ValueError(('Collapsed geographic journey', terminal['id']))
        for p, q in zip(path, path[1:]):
            selected_edges[tuple(sorted((p, q)))] = graph[p][q]
        routes.append(dict(id='odawara-east-to-' + terminal['id'], start=terminals[0]['id'], destination=terminal['id'],
                           points_xz=points, length=sum(e['length'] for e in edges), source_features=sorted({e['source_feature'] for e in edges if e['source_feature'] is not None}),
                           civil_segments=sum(e['code'] in (2703, 2713, 2704, 2714) for e in edges),
                           installed=False, three_dimensional_clearance_verified=False))
    rail_geometry = unary_union(rails)
    water_geometry = unary_union(waters)
    selected_geometry = unary_union([LineString([node_points[p], node_points[q]]) for p, q in selected_edges])
    # Major streets retain playable width; minor real alleys remain a separate
    # reference, rather than widening every source line through neighbouring lots.
    public_reserve = unary_union([LineString([node_points[p], node_points[q]]).buffer(6 if edge['major'] else 4.5, cap_style=1, join_style=2)
                                 for (p, q), edge in selected_edges.items()])
    station_reserves = [dict(id='odawara', bounds_xz=[3290, 420, 3410, 555]),
                        dict(id='midoricho', bounds_xz=[3427, 392, 3472, 432]),
                        dict(id='hakone-itabashi', bounds_xz=[3099, 780, 3152, 822]),
                        dict(id='hayakawa', bounds_xz=[3112, 948, 3159, 1004])]
    castle = Polygon([(3260, 610), (3320, 576), (3406, 596), (3422, 641), (3419, 697), (3370, 713), (3288, 685)])
    port = box(3040, 960, 3360, 1216)
    excluded = unary_union([public_reserve.buffer(2), rail_geometry.buffer(17), water_geometry.buffer(4), castle, port,
                            *[box(*r['bounds_xz']) for r in station_reserves]])
    with np.load(a.gis / 'runtime-surface-field.npz') as f:
        terrain = {k: f[k] for k in ('x', 'z', 'height_y')}
    # Unite overlapping tile copies before choosing locations. Surveyed building
    # centres seed adapted playable lots; no lot may erase water or a station.
    urban = box(3330, 436, 3696, 786)
    merged = unary_union([p for p in buildings if p.intersects(urban)])
    pieces = [merged] if merged.geom_type == 'Polygon' else list(merged.geoms)
    samples = []
    for polygon in pieces:
        point = polygon.representative_point(); road_distance = point.distance(selected_geometry)
        if not urban.contains(point) or not 13 <= road_distance <= 34:
            continue
        samples.append((road_distance, -polygon.area, point.x, point.y, polygon))
    occupied = excluded; lots = []
    approach_blockers = unary_union([rail_geometry.buffer(17), water_geometry.buffer(3), castle,
                                    *[box(*r['bounds_xz']) for r in station_reserves]])
    for _, _, cx0, cz0, original in sorted(samples, key=lambda p: p[:4]):
        cx, cz = int(round(cx0)), int(round(cz0)); centre = Point(cx, cz)
        near = selected_geometry.interpolate(selected_geometry.project(centre)) if selected_geometry.geom_type == 'LineString' else None
        if near is None:
            from shapely.ops import nearest_points
            near = nearest_points(centre, selected_geometry)[1]
        dx, dz = near.x - cx, near.y - cz
        rotation = (3 if dx > 0 else 1) if abs(dx) > abs(dz) else (0 if dz > 0 else 2)
        hx, hz = 5, 6
        corners = np.asarray([[-hx-2, -hz-2], [hx+2, -hz-2], [hx+2, hz+3], [-hx-2, hz+3]], dtype=int)
        for _ in range(rotation):
            corners = np.column_stack([-corners[:, 1], corners[:, 0]])
        corners += [cx, cz]; footprint = Polygon(corners)
        if not urban.contains(footprint) or occupied.intersects(footprint):
            continue
        floor_values = sample_grid(terrain, 'height_y', corners[:, 0], corners[:, 1])
        if float(np.ptp(floor_values)) > 3:
            continue
        door_offset = np.array([0, hz + 3])
        for _ in range(rotation):
            door_offset = np.array([-door_offset[1], door_offset[0]])
        door = np.asarray([cx, cz]) + door_offset
        approach = LineString([door.tolist(), [near.x, near.y]])
        if approach.buffer(1.5).intersects(approach_blockers) or any(approach.buffer(1.5).intersects(shape(r['lot_geometry'])) for r in lots):
            continue
        floor = int(round(float(np.median(floor_values))))
        number = len(lots); programme = ('shop', 'house', 'cafe', 'house', 'office', 'inn')[number % 6]
        lots.append(dict(id=f'odawara-core/{number+1:03}', programme=programme, centre=[cx, cz], half=[hx, hz], rotation=rotation,
                         indicative_floor=floor, floors=2 + (number % 3 == 0), roof_style='flat' if programme in ('shop', 'office') else 'gable',
                         lot_geometry=mapping(footprint), approach_xz=[door.tolist(), [round(near.x, 2), round(near.y, 2)]],
                         source_building_area=float(original.area), reference_building_centre=[cx0, cz0],
                         measured_save_clearance_required=True, installed=False))
        occupied = unary_union([occupied, footprint.buffer(3), approach.buffer(2)])
    errors = []
    for i, row in enumerate(lots):
        p = shape(row['lot_geometry'])
        if p.intersects(excluded): errors.append(['reserved geometry', row['id']])
        for other in lots[:i]:
            if p.intersects(shape(other['lot_geometry'])): errors.append(['overlapping lots', row['id'], other['id']])
    result = dict(stage=1, status='geographic layout; current FULL block survey still required', bounds_xz=bounds,
                  source=str(a.geography), terminals=terminals, routes=routes, lots=lots, station_reserves=station_reserves,
                  castle_reserve=mapping(castle), retained_port_bounds_xz=[3040, 960, 3360, 1216],
                  un_relocation_allowed=False, station_construction_stage=2, civil_completion_stage=3,
                  geographic_road_components=len(components), selected_component_nodes=len(component), sub_block_endpoint_joins=snapped,
                  route_unique_length=sum(e['length'] for e in selected_edges.values()),
                  route_unique_edges=len(selected_edges), geographic_conflicts=errors,
                  whole_map_complete=False, game_world_written=False)
    (a.out / 'district-plan.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf8')
    # Keep the actual selected source geometry separately from any later cubic
    # street interpolation; the renderer cannot silently change the road plan.
    selected = [dict(type='Feature', properties=edge, geometry=mapping(LineString([node_points[p], node_points[q]]))) for (p, q), edge in selected_edges.items()]
    with gzip.open(a.out / 'selected-roads.geojson.gz', 'wt', encoding='utf8') as f:
        json.dump(dict(type='FeatureCollection', features=selected), f)
    render(a.out, features, result)
    print(json.dumps(dict(routes=len(routes), terminals=len(terminals), unique_road_length=round(result['route_unique_length'], 1), lots=len(lots), conflicts=len(errors), installed=False)), flush=True)
    if errors: raise ValueError(errors[:10])


def render(out, features, plan):
    l, t, r, b = 3240, 360, 3712, 896; scale = 1.6
    im = Image.new('RGB', (int((r-l)*scale)+80, int((b-t)*scale)+100), '#f5f1e8'); d = ImageDraw.Draw(im)
    font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 16)
    small = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 12)
    def xy(p): return (40+(p[0]-l)*scale, 55+(p[1]-t)*scale)
    for layer in ('WA', 'BldA', 'RailCL'):
        for f in features:
            if f['properties']['source_layer'] != layer: continue
            g = f['geometry']; coords = g['coordinates']
            if g['type'] in ('Polygon', 'MultiPolygon'):
                for rings in ([coords] if g['type']=='Polygon' else coords):
                    d.polygon([xy(p) for p in rings[0]], fill='#91c1d0' if layer=='WA' else '#d8d2c7')
                    for hole in rings[1:]: d.polygon([xy(p) for p in hole], fill='#f5f1e8')
            elif layer == 'RailCL':
                for line in line_parts(shape(g)): d.line([xy(p) for p in line.coords], fill='#585e74', width=3)
    for row in plan['station_reserves']:
        a,b,c,e = row['bounds_xz']; d.rectangle([xy([a,b]),xy([c,e])], outline='#927bb4', width=3)
    for row in plan['routes']: d.line([xy(p) for p in row['points_xz']], fill='#b87646', width=6)
    d.line([xy(p) for p in plan['castle_reserve']['coordinates'][0]], fill='#528c63', width=3)
    for row in plan['lots']:
        d.polygon([xy(p) for p in row['lot_geometry']['coordinates'][0]], fill='#688d96', outline='#25444c')
        d.line([xy(p) for p in row['approach_xz']], fill='#307678', width=3)
    for terminal in plan['terminals']:
        q=xy(terminal['road_node']); d.ellipse([q[0]-4,q[1]-4,q[0]+4,q[1]+4],fill='#92283a')
    d.rectangle((0,0,im.width,44), fill='#f5f1e8')
    d.text((20,12), f"小田原首期布局：{len(plan['lots'])}处可用建筑候选地块 / 尚未施工", font=font, fill='#273c40')
    d.text((20,im.height-30),'棕：有明确终点的道路参考；紫：车站预留；绿：城址；蓝灰：候选地块',font=small,fill='#39464a')
    im.save(out/'district-plan.png')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(__doc__)
    for name in ('geography','gis','out'): parser.add_argument('--'+name,type=Path,required=True)
    make_plan(parser.parse_args())
