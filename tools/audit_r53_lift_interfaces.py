"""Audit declared lift landings against measured states, without world writes.

An open-door projection clears only the manifest's owned door cells. It proves
fixed-throat clearance, not native arrival, door motion, or public access.
"""
import argparse
import collections
import gzip
import json
import math
from pathlib import Path

from measure_world_r40 import MeasuredWorld
from prepare_school_hakone_native_r45 import ActualGeometry, NORMAL
from query_blocks import iter_block_entities
from audit_r53_sign_visibility import literal


def control_readers(m, geometry, pos, facing, feet):
    """Existing standing spots, within five blocks and 60 degrees of the face."""
    dx,dz=NORMAL[facing]
    offset=.25 if 'access_reader' in m.block(pos) else .375
    target=(pos[0]+.5-dx*offset,pos[1]+.5,pos[2]+.5-dz*offset)
    found=[]
    for dy in (0,-1,1,-2,2):
        for depth in (1,2,3,0):
            for side in (0,-1,1,-2,2):
                q=(pos[0]+dx*depth+dz*side,feet+dy,pos[2]+dz*depth-dx*side)
                eye=(q[0]+.5,q[1]+1.62,q[2]+.5)
                distance=math.dist(eye,target)
                front=(eye[0]-target[0])*dx+(eye[2]-target[2])*dz
                if distance>5 or front<.5*math.hypot(eye[0]-target[0],eye[2]-target[2]):continue
                if geometry.standing((q[0]+.5,q[1],q[2]+.5))!='STATIC_STANDING':continue
                clear=True
                for i in range(1,65):
                    point=tuple(eye[k]+(target[k]-eye[k])*i/64 for k in range(3))
                    cell=tuple(math.floor(v) for v in point)
                    if cell==tuple(pos):continue
                    boxes=geometry.boxes(cell)
                    if boxes is None or any(all(cell[k]+b[k]+.001<point[k]<cell[k]+b[k+3]-.001 for k in range(3))for b in boxes):clear=False;break
                if clear:found.append(q)
    return found


def audit(world, output):
    manifest = json.loads((world/'personnel_lifts_r52.json').read_text('utf8'))
    m = MeasuredWorld(world)
    floors = []
    for lift in manifest['lifts']:
        for floor in lift['floors']:
            x, y, z = floor['cabin']
            lo, hi = (x-10, y-2, z-10), (x+10, y+7, z+10)
            m.box(lo, hi)
            floors.append((lift, floor, lo, hi))
    m.load()
    closed = ActualGeometry(m)
    nav = json.loads(gzip.decompress((world/'nerv_routes_r24.json.gz').read_bytes()))
    active = {tuple(p[:3]) for p, a in zip(nav['nodes'], nav['node_active']) if a}
    rows = []
    for lift, floor, lo, hi in floors:
        x, y, z = floor['cabin']
        dx, dz = NORMAL[floor['exit']]
        owned = {tuple(d['pos']) for k in ('landing_doors', 'cabin_doors') for d in floor[k]}
        geometry = ActualGeometry(m)
        original = geometry.boxes
        geometry.boxes = lambda q, opened=(): [] if tuple(q) in owned else original(q, opened)
        door_depth = max((p[0]-x)*dx+(p[2]-z)*dz for p in owned)
        lanes, calls = [], []
        for side in range(-2, 3):
            cells = [(x+dx*d+dz*side, y, z+dz*d-dx*side)
                     for d in range(3, door_depth+2)]
            lanes.append(dict(side=side, cells=[dict(pos=q, state=m.block(q),
                open_projection=geometry.standing((q[0]+.5,y,q[2]+.5)),
                navigation_active=q in active) for q in cells]))
        for call in floor['calls']:
            p = call['position']; cx, cz = NORMAL[call['facing']]
            q = (p[0]+cx, floor['approach_y'], p[2]+cz)
            calls.append(dict(pos=p, state=m.block(p), reader=q,
                reader_status=closed.standing((q[0]+.5,q[1],q[2]+.5)),
                navigation_active=q in active,front_readers=control_readers(m,closed,p,call['facing'],floor['approach_y'])))
        tags = dict(iter_block_entities(world, m.dimension, lo, hi))
        labels = []
        for pos, tag in tags.items():
            state=m.block(pos)
            if not any(k in state for k in ('sign','direction_panel')): continue
            text = [literal(str(v)) for v in tag.get('front_text',{}).get('messages',[])]
            if not text: text=[str(tag.get(k,'')) for k in ('Row0','Row1','Row2','Row3')]
            labels.append(dict(pos=pos,state=state,text=text))
        rows.append(dict(lift=lift['id'],label=floor['label'],cabin=floor['cabin'],
            restricted=floor.get('restricted',False),calls=calls,lanes=lanes,labels=labels,
            owned_door_cells=[dict(pos=p,state=m.block(p)) for p in sorted(owned)],
            unknown_shapes=sorted(geometry.unknown|closed.unknown)))
    counts=collections.Counter(c['open_projection'] for r in rows for a in r['lanes'] for c in a['cells'])
    report=dict(world=str(world),world_written=False,lifts=len(manifest['lifts']),landings=len(rows),
        projection_limits=__doc__,throat_statuses=dict(counts),landings_detail=rows)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('lifts',report['lifts'],'landings',len(rows),'fixed throat',dict(counts))
    for r in rows:
        failures=[c for lane in r['lanes'] for c in lane['cells'] if c['open_projection']!='STATIC_STANDING']
        failed_calls=[c for c in r['calls'] if not c['front_readers']]
        if failures or failed_calls or r['unknown_shapes']:
            print(json.dumps(dict(lift=r['lift'],label=r['label'],failures=failures,calls=failed_calls,unknown=r['unknown_shapes']),ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();audit(a.world,a.output)
