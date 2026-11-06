"""Check new frontage entries, complete device tags, rooms and stair landings."""
import argparse,json
from collections import deque,Counter
from pathlib import Path
import nbtlib
import numpy as np
from author_hakone_lakefront import Editor
from author_hakone_district_blocks import Frontage
from query_blocks import AIR
from plan_ashi_landscape_r54 import PLANTS
from hakone_earthworks import road_blocks
from prepare_hakone_togendai_neighbourhood import save_json
from verify_hakone_togendai_neighbourhood import verify

EMPTY=AIR|PLANTS|{'minecraft:light'}


def check(candidate):
    original=verify(candidate);e=Editor(candidate);spec=json.loads((candidate/'new-frontages.json').read_text('utf8'));errors=[]
    changes=nbtlib.load(candidate/'block-entities.dat')['Changes'];tags={tuple(int(r['After'][k])for k in ('x','y','z')):r['After']for r in changes if 'After'in r}
    originals={tuple(int(r[k])for k in ('x','y','z'))for r in nbtlib.load(candidate/'captured-devices.dat')['Devices']}
    with np.load(candidate/'plan/network.npz')as f:bounds=f['bounds'];walk=f['walk'];g=f['grade2']
    x,z,_,_=map(int,bounds);entries=[];checked_tags=0;rooms=0;stairs=0;reachable_rooms=0
    for row in spec['buildings']:
        c=Frontage(row['site']);hx,hz=row['site']['half'];box=row['occupied_bounds']
        for device in row['devices']:
            pos=tuple(device['pos']);tag=tags.get(pos);state=e.state(*pos);kind=device['id']
            if pos in originals or tag is None or str(tag.get('id'))!=kind:errors.append(['new device NBT identity',row['id'],pos,kind])
            if kind=='minecraft:bed':
                if '_bed['not in state:errors.append(['new bed block',row['id'],pos,state])
                facing=state.split('facing=')[1].split(',')[0];dx,dz={'north':(0,-1),'south':(0,1),'east':(1,0),'west':(-1,0)}[facing]
                sign=1 if 'part=foot'in state else-1;other=(pos[0]+dx*sign,pos[1],pos[2]+dz*sign)
                if other not in tags or ('part=head'if sign==1 else'part=foot')not in e.state(*other):errors.append(['new bed pair',row['id'],pos,other])
            elif kind=='minecraft:chest'and ('chest['not in state or tag is not None and list(tag.get('Items',[]))):errors.append(['new empty storage',row['id'],pos])
            elif kind=='minecraft:sign'and ('_wall_sign['not in state or tag is not None and len(tag.get('front_text',{}).get('messages',[]))!=4):errors.append(['new address sign',row['id'],pos])
            checked_tags+=1
        for px in (-1,0):
            lower=c.point(px,1,hz);upper=c.point(px,2,hz)
            if 'half=lower'not in e.state(*lower)or 'half=upper'not in e.state(*upper):errors.append(['complete entrance door',row['id'],lower])
        ax,ay,az=row['approach'];j,i=az-z,ax-x
        if not walk[j,i]or abs(g[j,i]-2*(ay-1))>1:errors.append(['new entrance public connection',row['id'],row['approach']])
        # Check the short frontage aisle independently of the public road mask.
        for pz in range(hz-2,hz+5):
            pos=c.point(0,1,pz);floor=e.state(pos[0],pos[1]-1,pos[2]).split('[')[0]
            if floor in EMPTY:errors.append(['frontage aisle floor',row['id'],pos])
            for dy in (0,1):
                state=e.state(pos[0],pos[1]+dy,pos[2]);mat=state.split('[')[0]
                if mat not in EMPTY and '_door['not in state:errors.append(['frontage aisle obstruction',row['id'],pos,state])
        entries.append(dict(id=row['id'],door=row['door'],approach=row['approach']))
        allowed_floors={'minecraft:spruce_planks','minecraft:smooth_stone','minecraft:stone_bricks','minecraft:oak_stairs'}
        nodes={}
        for px in range(box[0],box[3]+1):
            for pz in range(box[2],box[5]+1):
                for py in range(row['site']['floor']+1,row['site']['floor']+(row['site']['floors']-1)*5+2):
                    state=e.state(px,py-1,pz);mat=state.split('[')[0]
                    if mat not in allowed_floors:continue
                    head=[e.state(px,py+k,pz)for k in (0,1)]
                    if all(s.split('[')[0]in EMPTY or '_door['in s for s in head):nodes[px,py,pz]='_stairs['in state
        start=tuple(c.point(0,1,hz-1));seen={start};queue=deque([start])
        if start not in nodes:errors.append(['interior start',row['id'],start])
        while queue:
            px,py,pz=queue.popleft()
            for dx,dz in ((-1,0),(1,0),(0,-1),(0,1)):
                for dy in (-1,0,1):
                    q=px+dx,py+dy,pz+dz
                    if q not in nodes or q in seen or dy and not(nodes.get((px,py,pz),False)or nodes[q]):continue
                    seen.add(q);queue.append(q)
        for goal in spec['room_goals']:
            if goal['parcel']!=row['id']:continue
            if tuple(goal['feet'])not in seen:errors.append(['room unreachable from entrance',goal])
            else:reachable_rooms+=1
    for goal in spec['room_goals']:
        px,py,pz=goal['feet'];floor=e.state(px,py-1,pz).split('[')[0]
        if floor in EMPTY or any(e.state(px,py+k,pz).split('[')[0]not in EMPTY for k in (0,1)):errors.append(['interior room or landing',goal])
        rooms+=1
    for row in spec['stairs']:
        if '_stairs['not in e.state(*row['block'])or any(e.state(*p).split('[')[0]not in EMPTY for p in row['head']):errors.append(['usable stair',row])
        stairs+=1
    report=dict(errors=errors,entries=entries,new_device_tags_checked=checked_tags,room_and_landing_goals=rooms,reachable_room_and_landing_goals=reachable_rooms,stair_columns=stairs,world_written=False,visual_verified=False)
    save_json(candidate/'new-frontages-check.json',report)
    functional=json.loads((candidate/'functional-check.json').read_text('utf8'));functional['frontage_verification_errors']=errors;functional['errors']+=errors;save_json(candidate/'functional-check.json',functional)
    print('New frontage check',len(entries),'entries',checked_tags,'NBT tags',rooms,'room/landing goals',stairs,'stair columns; errors',len(errors),Counter(r[0]for r in errors),errors[:8],flush=True)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--candidate',type=Path,required=True);candidate=p.parse_args().candidate;check(candidate)
    if json.loads((candidate/'functional-check.json').read_text('utf8'))['errors']:raise SystemExit(1)
