"""Offline, current-section access proof for the five deep native stations.

This is a conservative pedestrian graph, not a replacement for live gates or
train boarding. Track space is excluded. Historical walks are evidence only;
they never authorize editing a station. Nothing in this tool opens a world.
"""
import argparse
from collections import Counter, defaultdict, deque
import json
import math
from pathlib import Path

import numpy as np

from audit_hakone_station_walks import Walker


ENTRIES = {
    'EVA 机库': [93.5, -442, -46.5],
    'NERV 总部': [30.5, -559, 450.5],
    '研究模拟区': [280.5, -466, 552.5],
    '地下都市入口': [-335.5, -466, 752.5],
    '整备补给中心': [270.5, -466, 180.5],
}
PAVEMENT = {
    'minecraft:smooth_stone', 'minecraft:smooth_stone_slab',
    'minecraft:light_gray_concrete', 'minecraft:gray_concrete',
    'minecraft:white_concrete', 'minecraft:polished_deepslate',
    'minecraft:stone_bricks', 'minecraft:polished_andesite',
    'minecraft:smooth_quartz', 'minecraft:smooth_quartz_stairs',
    'projectseele:nerv_floor_panel', 'projectseele:station_tactile_warning',
    'mtr:platform', 'mtr:escalator_step',
}


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), 'utf8')


def xyz(p):
    return [p[k] for k in ('x', 'y', 'z')]


def line_distance(x, z, a, b):
    dx, dz = b[0]-a[0], b[2]-a[2]
    f = max(0, min(1, ((x-a[0])*dx+(z-a[2])*dz)/(dx*dx+dz*dz)))
    return math.hypot(x-a[0]-f*dx, z-a[2]-f*dz)


class Graph:
    def __init__(self, walker, site, platforms):
        self.w = walker
        self.site = site
        self.platforms = platforms
        self.nodes = []
        self.by_column = defaultdict(list)
        self.links = defaultdict(list)
        self.link_routes = {}
        self.edge_cache = {}
        self.stair_records = []
        self.track_excluded = 0

    def on_track(self, p):
        x, y, z = p
        for q in self.platforms:
            a, b = xyz(q['position1']), xyz(q['position2'])
            a[0] += .5; a[2] += .5; b[0] += .5; b[2] += .5
            if a[1]-1 <= y <= a[1]+4 and line_distance(x, z, a, b) < 2.0:
                return True
        return False

    def add(self, p):
        key = math.floor(p[0]), math.floor(p[2])
        for i in self.by_column[key]:
            if abs(self.nodes[i][1]-p[1]) < 1e-6:
                return i
        i = len(self.nodes); self.nodes.append(p); self.by_column[key].append(i)
        return i

    def nearest(self, p, radius=0.01):
        rows = []
        for x in range(math.floor(p[0]-radius), math.floor(p[0]+radius)+1):
            for z in range(math.floor(p[2]-radius), math.floor(p[2]+radius)+1):
                for i in self.by_column.get((x,z), []):
                    d = math.dist(p, self.nodes[i])
                    if d <= radius: rows.append((d,i))
        return min(rows)[1] if rows else None

    def build(self):
        x, y, z, X, Y, Z = self.site['bounds']
        floor_low = min(p['position1']['y'] for p in self.platforms)
        floor_high = max(p['position1']['y'] for p in self.platforms)+7
        arr, pal = self.w.reader.box([x,floor_low,z,X,floor_high,Z])
        stairs = defaultdict(list)
        for iz, ix in np.ndindex(arr.shape[1:]):
            for iy in range(arr.shape[0]):
                state = pal[int(arr[iy,iz,ix])]
                if state.split('[')[0] not in PAVEMENT: continue
                xx, yy, zz = x+ix, floor_low+iy, z+iz
                boxes = self.w.shapes.get(state)
                if boxes is None: continue
                if 'smooth_quartz_stairs' in state:
                    stairs[state].append((xx,yy,zz))
                tops = {yy+b[4] for b in boxes if b[0]<.8 and b[3]>.2 and b[2]<.8 and b[5]>.2}
                for top in tops:
                    p = [xx+.5, top, zz+.5]
                    if self.on_track(p): self.track_excluded += 1; continue
                    if self.w.body(*p) is None: self.add(p)
        # Whole-block graph nodes alone cannot represent the two half steps
        # of a stair. Add independently swept, bidirectional stair flights.
        for state, points in stairs.items():
            if 'facing=east' in state: axis=0; cross=2
            elif 'facing=south' in state: axis=2; cross=0
            else: continue
            groups=defaultdict(list)
            for p in points: groups[p[cross]].append(p)
            for width, lane in sorted(groups.items()):
                lane=sorted(lane,key=lambda p:p[axis]); runs=[]; run=[]
                for p in lane:
                    if run and (p[axis]!=run[-1][axis]+1 or p[1]!=run[-1][1]+1):
                        runs.append(run);run=[]
                    run.append(p)
                if run:runs.append(run)
                for run in runs:
                    if len(run)<2: continue
                    a=list(map(float,run[0]));b=list(map(float,run[-1]))
                    a[axis]-=1; a[0]+=.5;a[2]+=.5
                    b[axis]+=1;b[1]+=1;b[0]+=.5;b[2]+=.5
                    ai,bi=self.nearest(a,.01),self.nearest(b,.01)
                    route=[a]+[[p[0]+.5,p[1]+1,p[2]+.5] for p in run]+[b]
                    proof=self.w.follow(route); reverse=self.w.follow(list(reversed(route)))
                    clear=ai is not None and bi is not None and proof['kind']==reverse['kind']=='static_clear_provisional'
                    row=dict(path=route,stair_blocks=len(run),forward=proof,reverse=reverse,endpoints_in_graph=ai is not None and bi is not None,clear=clear)
                    self.stair_records.append(row)
                    if clear:
                        self.links[ai].append(bi);self.links[bi].append(ai)
                        self.link_routes[ai,bi]=route;self.link_routes[bi,ai]=list(reversed(route))

    def neighbors(self, i):
        p=self.nodes[i];x,z=math.floor(p[0]),math.floor(p[2])
        yield from self.links[i]
        for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
            for j in self.by_column.get((x+dx,z+dz),[]):
                q=self.nodes[j]
                if abs(p[1]-q[1])>.600001:continue
                key=min(i,j),max(i,j)
                if key not in self.edge_cache:
                    proof=self.w.follow([p,q]);back=self.w.follow([q,p])
                    self.edge_cache[key]=proof['kind']==back['kind']=='static_clear_provisional'
                if self.edge_cache[key]:yield j

    def walk(self, start):
        root=self.nearest(start,.01)
        if root is None:return {},None
        parents={root:None};queue=deque([root])
        while queue:
            i=queue.popleft()
            for j in self.neighbors(i):
                if j not in parents:parents[j]=i;queue.append(j)
        return parents,root

    def path(self, parents, i):
        indices=[]
        while i is not None:indices.append(i);i=parents[i]
        indices.reverse();out=[self.nodes[indices[0]]]
        for a,b in zip(indices,indices[1:]):
            out.extend(self.link_routes.get((a,b),[self.nodes[a],self.nodes[b]])[1:])
        return out


def parallel_track_inside(platform, platforms, nx, nz, side):
    a,b=xyz(platform['position1']),xyz(platform['position2'])
    cx,cz=(a[0]+b[0])/2,(a[2]+b[2])/2
    for other in platforms:
        if other['id']==platform['id']:continue
        q,r=xyz(other['position1']),xyz(other['position2'])
        if q[1]!=a[1]:continue
        distance=((q[0]+r[0])/2-cx)*nx*side+((q[2]+r[2])/2-cz)*nz*side
        cross=(q[0]-r[0])*nx+(q[2]-r[2])*nz
        if 4<=distance<=9 and abs(cross)<.01:return str(other['id'])
    return None


def run(a):
    a.out.mkdir(exist_ok=False)
    shape_path=a.metadata/'native_collision_shapes.json'
    shapes=json.loads(shape_path.read_text('utf8'))
    snap=json.loads(a.native.read_text('utf8'))
    cases=json.loads((a.metadata/'quality_walk_cases.json').read_text('utf8'))
    stations=[]
    for name, entry in ENTRIES.items():
        w=Walker(a.source,shapes)
        site=next(s for s in w.reader.report['sites'] if s['name']==name and s['kind']=='existing')
        ids={r['platform_id'] for r in snap['resolved_platforms'] if r['station_name']==name}
        platforms=[p for p in snap['platforms'] if str(p['id']) in ids]
        print('Building current deep access graph:', name, flush=True)
        graph=Graph(w,site,platforms);graph.build();parents,root=graph.walk(entry)
        goals=[]
        for p in platforms:
            start,end=xyz(p['position1']),xyz(p['position2'])
            dx,dz=end[0]-start[0],end[2]-start[2];length=math.hypot(dx,dz)
            nx,nz=-dz/length,dx/length
            for side in (-1,1):
                for fraction in (.1,.3,.5,.7,.9):
                    cx=start[0]+fraction*dx+.5;cz=start[2]+fraction*dz+.5
                    possible=[]
                    for offset in (3,4,5,6,7,8):
                        pos=[math.floor(cx+nx*side*offset)+.5,start[1]+1,math.floor(cz+nz*side*offset)+.5]
                        i=graph.nearest(pos,.07)
                        if i is not None:possible.append((offset,i))
                    reached=[(d,i) for d,i in possible if i in parents]
                    chosen=min(reached or possible) if possible else None
                    edge_states=[]
                    for offset in (2,3,4,5,6):
                        xx=math.floor(cx+nx*side*offset);zz=math.floor(cz+nz*side*offset)
                        edge_states.append(dict(pos=[xx,start[1],zz],state=w.reader.state(xx,start[1],zz)))
                    edge_present=any((q['state'] or '').startswith(('mtr:platform[','projectseele:station_tactile_warning')) for q in edge_states)
                    inside=parallel_track_inside(p,platforms,nx,nz,side)
                    non_boarding=not possible and not edge_present and inside is not None
                    route=graph.path(parents,chosen[1]) if reached else None
                    proof=w.follow(route) if route else None
                    reverse=w.follow(list(reversed(route))) if route else None
                    if route and (proof['kind']!='static_clear_provisional' or reverse['kind']!='static_clear_provisional'):
                        raise ValueError('Emitted graph path failed independent sweep: '+str((name,p['id'],side,fraction,proof,reverse))[:400])
                    goals.append(dict(platform_id=str(p['id']),platform_name=p['name'],side=side,fraction=fraction,
                        status='reached' if reached else 'separate_component' if possible else 'non_boarding_track_interior' if non_boarding else 'no_safe_deck_sample',
                        deck=graph.nodes[chosen[1]] if chosen else None,
                        lateral_offset=chosen[0] if chosen else None,
                        path=route,forward=proof,reverse=reverse,edge_states=edge_states,adjacent_parallel_platform=inside))
        historical=[]
        for c in cases:
            ident=c.get('id','')
            route=c.get('path')or[c.get('start'),c.get('end')]
            if 'station' not in ident or any(p is None for p in route) or min(p[1] for p in route)>-128:continue
            in_horizontal=all(site['bounds'][0]<=p[0]<=site['bounds'][3]+1 and site['bounds'][2]<=p[2]<=site['bounds'][5]+1 for p in route)
            if not in_horizontal:continue
            if abs(route[0][1]-(platforms[0]['position1']['y']+1))>20:
                result=dict(kind='historical_layer_not_current_station',current_feet_y=platforms[0]['position1']['y']+1)
            else:result=w.follow(route)
            historical.append(dict(id=ident,path=route,result=result,repair_authorized=False))
        arr,pal=w.reader.box(site['bounds']);counts=Counter(map(int,arr.ravel()))
        unknown=[dict(state=pal[i],count=int(n)) for i,n in counts.items() if pal[i] not in shapes and pal[i] not in {'minecraft:air','minecraft:cave_air','minecraft:void_air'}]
        gates=[]
        for i in counts:
            if 'ticket_barrier' not in pal[i]:continue
            for iy,iz,ix in np.argwhere(arr==i):gates.append(dict(pos=[int(ix)+site['bounds'][0],int(iy)+site['bounds'][1],int(iz)+site['bounds'][2]],state=pal[i],interaction_test_pending=True))
        row=dict(name=name,native_station_id=site['native_id'],bounds=site['bounds'],platforms=platforms,
            entry=entry,entry_supported=w.follow([entry,entry]),nodes=len(graph.nodes),reachable_nodes=len(parents),
            track_space_excluded_samples=graph.track_excluded,goal_counts=dict(Counter(g['status'] for g in goals)),
            deck_goals=goals,stair_flights=graph.stair_records,historical_walks=historical,gates=gates,
            unknown_shapes=unknown,whole_station_accepted=False,static_deck_reachability_complete=all(g['status'] in ('reached','non_boarding_track_interior') for g in goals),
            surface_lift_and_remote_destination_outside_snapshot_not_verified=True)
        write(a.out/(site['id']+'.json'),row)
        stations.append({k:row[k] for k in ('name','native_station_id','entry','nodes','reachable_nodes','goal_counts','static_deck_reachability_complete','whole_station_accepted')})
        print(name, row['goal_counts'], 'stair lanes',sum(r['clear'] for r in graph.stair_records),'/',len(graph.stair_records),flush=True)
    report=dict(stations=stations,source=str(a.source),native_snapshot=str(a.native),shape_export=str(shape_path),
        pedestrian_width=.6,pedestrian_height=1.8,maximum_up_step=.6,edge_samples_per_block=8,
        native_track_space_excluded=True,world_read=False,world_written=False,repair_candidates=[],
        live_gate_and_boarding_validation_pending=True,historical_shapes_require_current_runtime_confirmation=True,
        no_static_failure_authorizes_automatic_excavation=True)
    write(a.out/'review.json',report)


if __name__=='__main__':
    parser=argparse.ArgumentParser(__doc__)
    for name in ('source','metadata','native','out'):parser.add_argument('--'+name,type=Path,required=True)
    run(parser.parse_args())
