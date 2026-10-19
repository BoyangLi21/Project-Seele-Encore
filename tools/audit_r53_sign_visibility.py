"""Inspect saved labels through their full text face; never alter the world."""
import argparse
import json
import gzip
import math
from collections import Counter
from pathlib import Path

from measure_world_r40 import MeasuredWorld, properties
from audit_facility_transit_r44 import Geometry
from query_blocks import AIR
from station_sign_readers_r44 import NORMAL, reader_visibility


def literal(raw):
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return raw
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get('text', '') + ''.join(literal(json.dumps(v)) for v in value.get('extra', []))
    return str(value)


def scan(inventory, output, delta=None):
    source = json.loads(inventory.read_text('utf8'))
    rows = source['rows']
    world = MeasuredWorld(Path(source['world']), source['dimension'])
    labels = []
    for row in rows:
        row['text'] = [literal(t) for t in row['text']]
        if not any(t.strip() for t in row['text']) or row['kind'].startswith('mtr:'):
            continue
        labels.append(row)
        x,y,z = row['pos']
        world.box((x-6,y-13,z-6),(x+6,y+4,z+6))
    world.load()
    if delta:
        edits=json.loads(gzip.decompress(delta.read_bytes()))
        override={tuple(r['pos']):r['after'] for r in edits}
        base_get=world.get
        world.get=lambda x,y,z: override.get(tuple(map(math.floor,(x,y,z))),base_get(x,y,z))
    geometry = Geometry(world)

    def optical(state):
        if state and ('glass' in state or 'lift_door_interlock' in state):
            return []
        return geometry.boxes(state)

    def visible(q, face, reader, state):
        if 'station_departure_board' in state or 'nerv_direction_panel' in state:
            return reader_visibility(world.block,optical,q,face,reader,
                                     direction=True,compact='nerv_direction_panel' in state)['clear']
        dx,dz = NORMAL[face]
        eye = (reader[0]+.5,reader[1]+1.62,reader[2]+.5)
        shop='kind=shop_sign' in state
        width=1.2 if shop else .40
        plane=.347 if shop else .39
        for side in (-width,0,width):
            for height in ((.22,.46,.65) if shop else (.35,.55,.75)):
                target = (q[0]+.5-dx*plane+dz*side,q[1]+height,q[2]+.5-dz*plane-dx*side)
                for i in range(1,49):
                    point = tuple(eye[j]+(target[j]-eye[j])*i/48 for j in range(3))
                    cell = tuple(map(math.floor,point))
                    if cell == tuple(q):
                        continue
                    boxes = optical(world.block(cell))
                    if boxes is None or any(all(cell[j]+b[j]+.001 < point[j] < cell[j]+b[j+3]-.001 for j in range(3)) for b in boxes):
                        return False
        return True

    for index,row in enumerate(labels):
        q = row['pos'];state = world.block(q);face = properties(state or '').get('facing')
        row.update(state=state,face=face,reader=None,issues=[])
        if face not in NORMAL:
            row['issues'].append('standing_or_non_wall_label');continue
        dx,dz = NORMAL[face]
        back = (q[0]-dx,q[1],q[2]-dz);support = world.block(back)
        row['backing'] = dict(pos=back,state=support)
        if support and any(k in support for k in ('door','controller','floor_display','button')):
            row['issues'].append('mounted_on_device_or_door')
        for y in range(q[1]-1,q[1]-12,-1):
            for distance in (2,3,4,1):
                for lateral in (0,-1,1,-2,2):
                    reader = (q[0]+dx*distance+dz*lateral,y,q[2]+dz*distance-dx*lateral)
                    if geometry.standing(reader)['status'] != 'STATIC_STANDING':continue
                    if visible(q,face,reader,state):row['reader']=reader;break
                if row['reader']:break
            if row['reader']:break
        if not row['reader']:row['issues'].append('no_clear_front_reader')
        if index%200 == 0:print('labels inspected',index,flush=True)
    report = dict(world=source['world'],dimension=source['dimension'],inventory_count=len(rows),
                  labeled_count=len(labels),counts=dict(Counter(i for r in labels for i in r['issues'])),
                  labels=labels,unknown_shapes=sorted(geometry.unknown),world_written=False,
                  limits='Saved geometry screening; a front standing sample is not proof of public access. Relocations require the existing entrance and native visual review.')
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('Audit:',report['counts'],'labels',len(labels),'unknown shapes',len(geometry.unknown),flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('inventory',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--delta',type=Path)
    a=p.parse_args();scan(a.inventory,a.output,a.delta)
