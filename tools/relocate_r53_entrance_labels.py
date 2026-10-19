"""Relocate labels on surveyed original entrances, preserving their full text NBT."""
import argparse
import copy
import gzip
import json
from pathlib import Path
import nbtlib

from query_blocks import AIR, read_box, iter_block_entities
from repair_r53_reported_landings import apply
from station_sign_readers_r44 import NORMAL

DIM = 'projectseele:geofront'


def plan(world, evidence, output, connectors=False, vestibules=False):
    inventory = json.loads((evidence/'inventory.json').read_text('utf8'))
    labels = {tuple(r['pos']):r for r in inventory['rows']}
    shapes = json.loads((world/'native_collision_shapes.json').read_text('utf8'))
    lifts = json.loads((evidence/'lifts.json').read_text('utf8'))
    rooms = json.loads(Path('F:/eva/artifacts/first_battle_world_r10/world_art/pyramid_rooms/places.json').read_text('utf8'))['rooms']
    rows, moves, unresolved = [], [], []
    used = set()

    def move(old, candidates, face, reason):
        if old in used:return
        item=labels[old];tag=nbtlib.parse_nbt(item['nbt'])
        bounds=[old]+candidates+[(p[0]-NORMAL[face][0],p[1],p[2]-NORMAL[face][1]) for p in candidates]
        lo=tuple(min(p[i] for p in bounds) for i in range(3));hi=tuple(max(p[i] for p in bounds) for i in range(3))
        cells=read_box(world,DIM,lo,hi);tags=dict(iter_block_entities(world,DIM,lo,hi))
        assert tags[old]==tag,('Changed original label',old)
        dx,dz=NORMAL[face];chosen=None
        for p in candidates:
            support=cells.get((p[0]-dx,p[1],p[2]-dz),'')
            if p in used or p in tags or cells.get(p) not in AIR:continue
            if any(k in support for k in ('glass','door','strip_light','controller')):continue
            if shapes.get(support)!=[[0,0,0,1,1,1]]:continue
            chosen=p;break
        if chosen is None:
            unresolved.append(dict(old=old,reason=reason,candidates=[dict(pos=p,state=cells.get(p),backing=cells.get((p[0]-dx,p[1],p[2]-dz))) for p in candidates]));return
        state=cells[old];newstate=state.replace('facing='+dict(v.split('=') for v in state.split('[')[1].rstrip(']').split(','))['facing'],'facing='+face)
        newtag=copy.deepcopy(tag)
        for k,v in zip(('x','y','z'),chosen):newtag[k]=nbtlib.Int(v)
        rows.extend([dict(pos=old,before=state,after='minecraft:air',before_nbt=tag.snbt(),after_nbt=None,reason=reason),
                     dict(pos=chosen,before=cells[chosen],after=newstate,before_nbt=None,after_nbt=newtag.snbt(),reason=reason)])
        used.update((old,chosen));moves.append(dict(old=old,new=chosen,face=face,text=item['text'],reason=reason))

    for floor in ([] if connectors or vestibules else lifts):
        for s in floor['signs']:
            old=tuple(s['pos']);item=labels.get(old)
            if not item or item['kind']!='minecraft:sign' or not any('电梯' in line for line in item['text']):continue
            if abs(old[1]-(max(p[1] for p in floor['door'])))>1:continue
            target=tuple(floor['target']);dx,dz=NORMAL[floor['exit']]
            candidates=[(target[0]+dx*d,target[1],target[2]+dz*d) for d in (0,1,2)]
            if old == (31,-455,316):
                unresolved.append(dict(old=old,reason='conference_security_wall_blocks_front_header; review actual vestibule approach'))
                continue
            move(old,candidates,floor['exit'],'original_lift_fixed_header')

    for room in ([] if connectors or vestibules else rooms):
        x0,x1,z0,z1=room['bounds'];x,y,z=room['entry'];y-=93
        face='north' if z==z0 else 'south' if z==z1 else 'east' if x==x1 else 'west'
        # Only the rooms whose authored entrance was moved away from its
        # original side door. No doorway or room is inferred from open air.
        if face in ('east','west') and z==(z0+z1)//2:continue
        old=(x1+1,room['floor']+3-93,(z0+z1)//2+2)
        if old not in labels or room['label'] not in ''.join(labels[old]['text']):
            unresolved.append(dict(old=old,reason='historical_room_label_not_present',room=room['id']));continue
        dx,dz=NORMAL[face]
        candidates=[(x+dx*d,y+3,z+dz*d) for d in ((range(1,10)) if face=='north' else (1,2,3))]
        # If an existing room header already carries this room's name,
        # place the original detailed plaque on its left fixed jamb.
        candidates += [(x+dx*d-dz*2,y+1,z+dz*d+dx*2) for d in (1,2,3)]
        move(old,candidates,face,'room_label_follows_authored_entrance_'+room['id'])

    # The R03 technical rooms retained their original thresholds, but later
    # connector walls covered their labels. Mount them on the connector mouth.
    for z in ((116,182,246) if connectors else ()):
        move((249,-464,z+2),[(257,-463,z),(257,-464,z+2)],'east','technical_room_existing_connector_header')
    for z in ((462,517,572) if connectors else ()):
        move((333,-464,z+2),[(330,-464,z+2)],'west','science_room_existing_connector_header')

    if vestibules:
        move((31,-455,316),[(28,-454,316)],'south','seele_security_fixed_lintel')
        # The old three-metre faces intersect the inner wall's header and
        # pillars. The opposite existing wall has a clear full-size face.
        for z in (365,378):
            move((86,-552,z),[(91,-552,z)],'west','b1_existing_gallery_opposite_wall')

    output.mkdir(parents=True,exist_ok=True)
    (output/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows,ensure_ascii=False).encode('utf8'),mtime=0))
    report=dict(world=str(world),moves=moves,unresolved=unresolved,changed_cells=len(rows),installed=False,
                original_doors_controls_and_progress_unchanged=True)
    (output/'PLAN.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--apply',action='store_true')
    p.add_argument('--connectors',action='store_true')
    p.add_argument('--vestibules',action='store_true')
    a=p.parse_args()
    if a.apply:apply(a.world,a.output)
    else:plan(a.world,a.evidence,a.output,a.connectors,a.vestibules)
