"""Verify declared passenger surfaces, without inferring a floor from its blocks.

JSON supplies every floor cell, intended occupancy and retained route evidence.
Reads exported sections only; unknown blocks/shapes fail closed. No world I/O.
"""
import argparse
from collections import Counter, defaultdict, deque
from functools import lru_cache
import json
import math
from pathlib import Path

from audit_hakone_station_walks import Walker
from review_underground_station_evidence import strict_walk


class EnvelopeWalker(Walker):
    """Include collision boxes extending outside their anchor voxel."""
    def __init__(self, source, shapes):
        super().__init__(source, shapes)
        boxes=[b for values in shapes.values() for b in values]
        self.minimum=[min(b[i] for b in boxes) for i in range(3)]
        self.maximum=[max(b[i+3] for b in boxes) for i in range(3)]

    @lru_cache(maxsize=300000)
    def body(self,x,y,z):
        lo=(x-.3,y+.0001,z-.3);hi=(x+.3,y+1.7999,z+.3)
        ranges=[range(math.floor(lo[i]-self.maximum[i])+1,
                      math.ceil(hi[i]-self.minimum[i])) for i in range(3)]
        for X in ranges[0]:
            for Y in ranges[1]:
                for Z in ranges[2]:
                    state,boxes=self.boxes(X,Y,Z)
                    if boxes is None:return dict(kind='unknown',pos=[X,Y,Z],state=state)
                    for b in boxes:
                        if all(lo[i]<[X,Y,Z][i]+b[i+3] and hi[i]>[X,Y,Z][i]+b[i] for i in range(3)):
                            return dict(kind='body_obstruction',pos=[X,Y,Z],state=state)
        return None


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), 'utf8')


def footprint(a, source, shapes):
    w = EnvelopeWalker(source, shapes)
    cells, failures, unknown, clear = [], [], set(), {}
    declared = {tuple(c['floor']): c for c in a['cells']}
    for p, c in sorted(declared.items()):
        x,y,z=p
        feet=(x+.5,c.get('feet_y',y+1),z+.5)
        heights, gaps=w.floors(*feet)
        for g in gaps: unknown.add(tuple(g['pos']))
        own_state,own_boxes=w.boxes(*p)
        supported=own_boxes is not None and any(abs(y+b[4]-feet[1])<.00001
                  and b[0]<.8 and b[3]>.2 and b[2]<.8 and b[5]>.2 for b in own_boxes)
        obstacle=w.body(*feet)
        if obstacle and obstacle['kind']=='unknown':unknown.add(tuple(obstacle['pos']))
        allowed=obstacle and any((obstacle.get('state') or '').startswith(s) for s in c.get('allowed_occupants',[]))
        if not supported: status='missing_declared_support'
        elif obstacle and not allowed: status='unclassified_obstruction'
        elif obstacle: status='declared_occupied_floor'
        elif c.get('role')=='structural_underlay':status='structural_underlay'
        else:status='clear_public_floor';clear[feet]=c
        row=dict(floor=p,feet=feet,role=c.get('role','public'),support=supported,
                 status=status,obstacle=obstacle,source=c['source'])
        cells.append(row)
        if status in ('missing_declared_support','unclassified_obstruction'):failures.append(row)
    # Existing successful paths provide anchors, not a new run of those paths.
    anchors=set(); inherited=[]
    for path in a.get('retained_paths',[]):
        for point in path['path']:
            p=tuple(map(float,point))
            if p in clear:anchors.add(p)
    columns=defaultdict(list)
    for p in clear:columns[math.floor(p[0]),math.floor(p[2])].append(p)
    links=defaultdict(set)
    for lane in a.get('retained_stair_lanes',[]):
        if not lane['clear']:raise ValueError('Cannot inherit a failed stair lane')
        pts=[tuple(map(float,p)) for p in lane['path']]
        # Only current declared supported/clear nodes can inherit a connection.
        valid_links=0
        for p,q in zip(pts,pts[1:]):
            if p not in clear or q not in clear:continue
            links[p].add(q);links[q].add(p)
            valid_links+=1
        inherited.append(dict(points=sum(p in clear for p in pts),links=valid_links,
                              source=a['retained_evidence']))
    edge_checks={};seen=set(anchors);queue=deque(anchors)
    while queue:
        p=queue.popleft()
        adjacent=set(links[p]);x,z=math.floor(p[0]),math.floor(p[2])
        for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
            adjacent.update(q for q in columns[x+dx,z+dz] if abs(p[1]-q[1])<=.600001)
        for q in adjacent:
            if q in seen:continue
            key=tuple(sorted((p,q)))
            if q not in links[p] and key not in edge_checks:
                edge_checks[key]=all(strict_walk(w,r)['kind']=='strict_static_clear' for r in ([p,q],[q,p]))
            if q in links[p] or edge_checks[key]:seen.add(q);queue.append(q)
    disconnected=[list(p) for p in clear if p not in seen]
    borders=[]
    for p,c in clear.items():
        x,z=math.floor(p[0]),math.floor(p[2]);fy=p[1]
        for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
            targets=columns[x+dx,z+dz]
            if any(abs(q[1]-fy)<=.600001 for q in targets):continue
            if any(q in links[p] for q in targets):continue
            q=(p[0]+dx,fy,p[2]+dz)
            current=w.reader.state(x,math.floor(fy),z)
            other=w.reader.state(x+dx,math.floor(fy),z+dz)
            state_list=[current or '',other or '']
            heights,gaps=w.floors(*q)
            for g in gaps:unknown.add(tuple(g['pos']))
            blocked=next((w.body(p[0]+dx*k/8,fy,p[2]+dz*k/8) for k in range(1,9)
                          if w.body(p[0]+dx*k/8,fy,p[2]+dz*k/8)),None)
            if blocked and blocked['kind']=='unknown':unknown.add(tuple(blocked['pos']))
            if any(s.startswith(('mtr:apg_door[','mtr:psd_door[')) for s in state_list):kind='dynamic_boarding_boundary_stage3'
            elif blocked and blocked['kind']!='unknown':kind='fixed_collision_boundary'
            elif any(abs(h-fy)<=.600001 for h in heights):kind='supported_continuation_outside_declared_surface'
            elif any(q[1]>fy for q in targets):kind='higher_declared_stair_or_landing'
            elif blocked or gaps:kind='unknown_boundary'
            else:kind='unguarded_drop_candidate'
            borders.append(dict(feet=p,normal=[dx,0,dz],kind=kind,neighbor_floor_heights=heights,
                                blocker=blocked,states=state_list))
    # A real hole and an overhead obstruction must fail the same detector.
    negative=[]
    if clear:
        p=next(iter(clear));x,y,z=math.floor(p[0]),int(p[1])-1,math.floor(p[2])
        class Overlay:
            def __init__(self,base,changes):self.base=base;self.changes=changes
            def state(self,x,y,z):return self.changes.get((x,y,z),self.base.state(x,y,z))
        for name,changes in [('declared_floor_removed',{(x,y,z):'minecraft:air'}),
                             ('headroom_blocked',{(x,y+2,z):'minecraft:stone'})]:
            nw=EnvelopeWalker(source,shapes);nw.reader=Overlay(nw.reader,changes)
            proof=strict_walk(nw,[p,p]);negative.append(dict(case=name,changes=[dict(pos=k,state=v) for k,v in changes.items()],result=proof,rejected=proof['kind']!='strict_static_clear'))
        if not all(r['rejected'] for r in negative):raise ValueError('Negative control was not rejected')
    gaps=defaultdict(list)
    for x,y,z in unknown:gaps[x//16,z//16].append(y)
    capture_requests=[dict(chunk=list(k),y_range=[min(ys),max(ys)]) for k,ys in sorted(gaps.items())]
    return dict(site=a['site'],name=a['name'],declared_floor_cells=len(cells),
                floor_status=dict(Counter(c['status'] for c in cells)),cells=cells,failures=failures,
                clear_cells=len(clear),connected_to_retained_routes=len(seen),disconnected=disconnected,
                retained_route_anchor_cells=len(anchors),retained_stair_links=inherited,
                new_lateral_connections_checked=len(edge_checks),edge_counts=dict(Counter(b['kind'] for b in borders)),
                borders=borders,capture_requests=capture_requests,negative_controls=negative,
                shape_scope='Recorded offline shapes; dynamic runtime confirmation remains stage 3',
                old_paths_repeated=False,world_opened=False,world_written=False,
                whole_station_complete=False)


def run(args):
    spec=json.loads(args.declaration.read_text('utf8'))
    shapes=json.loads(Path(spec['shape_export']).read_text('utf8'))
    args.out.mkdir(parents=True,exist_ok=True)
    summary=[]
    for a in spec['stations']:
        result=footprint(a,Path(spec['source']),shapes)
        write(args.out/(a['site']+'.json'),result)
        compact={k:v for k,v in result.items() if k not in ('cells','failures','disconnected','borders','retained_stair_links')}
        compact['failure_count']=len(result['failures']);compact['disconnected_count']=len(result['disconnected'])
        summary.append(compact);print(a['site'],compact['floor_status'],compact['edge_counts'],flush=True)
    write(args.out/'review.json',dict(declaration=str(args.declaration),stations=summary,
          world_opened=False,world_written=False,old_paths_repeated=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--declaration',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    run(p.parse_args())
