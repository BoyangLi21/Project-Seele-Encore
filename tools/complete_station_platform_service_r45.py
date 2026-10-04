"""Measured route-map service points on complete original R23 platform frames.

Only the registered fourteen surface-station frames are authoring scopes.
Track/APG, escalator cores, original BEs and passenger lanes stay unchanged.
"""
from pathlib import Path
import math,copy,json
import nbtlib
from query_blocks import AIR, iter_block_entities
from measure_world_r40 import MeasuredWorld
from prepare_school_hakone_native_r45 import ActualGeometry
from station_sign_readers_r44 import reader_visibility
from prepare_b2_stair_component_r45 import full_body_status
from measure_world_r40 import properties


def refresh_existing_route_maps_rows(world, records, diagrams, catalogue):
    """Include original entrance floors omitted by current native station boxes."""
    world = Path(world)
    tags = {}
    w = MeasuredWorld(world)
    scopes = [tuple(map(tuple,s['bounds'])) for s in catalogue['stations']]
    for r in records:
        x,y,z = r['center'];h = r['half']
        dx,dz = (h+3,23) if r['horizontal'] else (23,h+3)
        scopes.append(((x-dx,r['ground']-1,z-dz),(x+dx,y+13,z+dz)))
    for lo,hi in scopes:
        for q,tag in iter_block_entities(world,'projectseele:geofront',lo,hi):
            if str(tag.get('id','')) == 'projectseele:station_departure_board' and 'MapRows' in tag:
                tags[q] = copy.deepcopy(tag)
                w.around(q,0)
    w.load()
    rows,audit,held = [],[],[]
    for q,before in sorted(tags.items()):
        state = w.block(q)
        if state is None or state.split('[',1)[0] not in {'projectseele:station_departure_board','projectseele:nerv_direction_panel'}:
            held.append(dict(pos=q,state=state,why='Actual BE/type mismatch; retain full component for owner migration'))
            continue
        pid = int(before.get('NativePlatformId',-1));face = properties(state).get('facing')
        try:
            diagram = diagrams.diagram(pid,face,str(before.get('Route','')))
        except (RuntimeError,KeyError) as error:
            held.append(dict(pos=q,state=state,why=str(error)))
            continue
        after = copy.deepcopy(before)
        side=str(before.get('TrackSide',''))
        side_label={'north':'北侧','south':'南侧','west':'西侧','east':'东侧'}
        if side and side not in side_label:
            held.append(dict(pos=q,state=state,why='Retained explicit track-side label is not a cardinal direction'))
            continue
        after['Station'] = nbtlib.String(diagram['station']+(' · '+side_label[side]+'轨道' if side else ''))
        after['Route'] = nbtlib.String(diagram['line']+' 全线站序 / 乘车方向')
        after['MapRows'] = nbtlib.List[nbtlib.String]([nbtlib.String(s) for s in diagram['rows']])
        after['AirService'] = nbtlib.Byte(diagram['mode']=='AIRPLANE')
        for i,text in enumerate(diagram['rows'][:3]):after['Row'+str(i)] = nbtlib.String(text)
        changed = after != before
        audit.append(dict(pos=q,state=state,native_platform=pid,physical_face=face,actual_diagram=diagram,changed=changed,
                          before_rows=[str(t) for t in before['MapRows']],after_rows=diagram['rows']))
        if changed:
            rows.append(dict(pos=list(q),before=state,after=state,before_nbt=before.snbt(),after_nbt=after.snbt(),
                owner='r45/retained_complete_native_route_diagrams',reason='Existing complete retained entry/platform map; actual native visits and outgoing rail direction; preserve all non-display NBT'))
    return rows,audit,held


def platform_service_rows(world, records, diagrams, reserved=()):
    world = Path(world)
    reserved = set(reserved)
    platforms = {int(p['id']): p for p in diagrams.native['platforms']}
    active = set(diagrams.served)
    changes, maps, held = {}, [], []
    for record in records:
        pids = [int(p) for p in record['platform_ids'] if int(p) in active]
        if not pids:
            continue
        x, y, z = record['center']
        h, horizontal = record['half'], record['horizontal']
        def at(u, Y, cross):
            return (x + u, Y, z + cross) if horizontal else (x + cross, Y, z + u)
        lo, hi = at(-h-3, y-2, -20), at(h+3, y+13, 20)
        w = MeasuredWorld(world)
        w.box(lo, hi)
        w.load()
        if not all(s == 'full' for s in w.status.values()):
            raise RuntimeError(('Incomplete registered station image', record['station']))
        tags = dict(iter_block_entities(world, 'projectseele:geofront', lo, hi))
        original = ActualGeometry(w)
        cross_axis = 'z' if horizontal else 'x'
        axis_origin = z if horizontal else x
        cross_positions = {p: (platforms[p]['position1'][cross_axis] + platforms[p]['position2'][cross_axis])/2 - axis_origin for p in pids}
        for side in (-1, 1):
            pid = min(pids, key=lambda p: side * -cross_positions[p])
            face = ('south' if side < 0 else 'north') if horizontal else ('east' if side < 0 else 'west')
            for u in range(-h+8, h-7, 16):
                q = at(u, y+3, side*16)
                panel = [at(u+a, y+3+dy, side*16) for a in (-1,0,1) for dy in (0,1)]
                backing = [at(u+a, y+3+dy, side*17) for a in (-1,0,1) for dy in (0,1)]
                reason = None
                if any(p in reserved or p in tags or w.block(p) not in AIR for p in panel):
                    reason = 'Existing fixture, mechanism or reserved complete display envelope'
                allowed_frame = {'projectseele:clear_glass', 'minecraft:green_concrete', 'minecraft:orange_concrete', 'minecraft:light_gray_concrete'}
                lower = [p for p in backing if p[1] == y+3]
                if not reason and any(original.boxes(p) != [[0,0,0,1,1,1]] or w.block(p) not in allowed_frame for p in lower):
                    reason = 'Complete three-wide retained full-cube attachment absent'
                if not reason and any(p in reserved or p in tags or w.block(p) not in AIR | allowed_frame for p in backing):
                    reason = 'Different backing owner or original BE'
                reader = at(u, y+1, side*13)
                if reason:
                    held.append(dict(station=record['station'], line=record['line'], platform=pid, anchor=q, reader=reader, why=reason))
                    continue
                diagram = diagrams.diagram(pid, face, record['line'])
                state = f'projectseele:station_departure_board[facing={face},wayfinding=true]'
                trim = w.block(at(u,y+3,side*17))
                trim = trim if trim in {'minecraft:green_concrete','minecraft:orange_concrete','minecraft:light_gray_concrete'} else 'minecraft:light_gray_concrete'
                proposed = {q: state, **{p: trim for p in backing if w.block(p) in AIR}}
                class Image:
                    def __init__(self):
                        self.world = world
                    def block(self, p):
                        return proposed.get(tuple(p), changes.get(tuple(p), {}).get('after', w.block(p)))
                    def get(self, X, Y, Z):
                        return self.block(tuple(map(math.floor, (X,Y,Z))))
                image = Image()
                geometry = ActualGeometry(image)
                point = [reader[0]+.5, reader[1], reader[2]+.5]
                optical = reader_visibility(image.block, lambda s: [] if s in AIR else geometry.shapes.get(s), q, face, reader, direction=True, route_map=True)
                if geometry.standing(point) != 'STATIC_STANDING' or not optical['clear']:
                    held.append(dict(station=record['station'], line=record['line'], platform=pid, anchor=q, reader=reader, why='Real front bearing/body or complete nine lettering rays not clear'))
                    continue
                approach = None
                for delta in (-1,1):
                    start = [point[0]+(delta if horizontal else 0),point[1],point[2]+(0 if horizontal else delta)]
                    if geometry.standing(start)=='STATIC_STANDING' and full_body_status(geometry,start,point)=='CLEAR':
                        approach = [start,point]
                        break
                if approach is None:
                    held.append(dict(station=record['station'],line=record['line'],platform=pid,anchor=q,reader=reader,why='Complete local aisle approach and body sweep absent'))
                    continue
                tag = nbtlib.Compound({'id': nbtlib.String('projectseele:station_departure_board'), 'x': nbtlib.Int(q[0]), 'y': nbtlib.Int(q[1]), 'z': nbtlib.Int(q[2]), 'Wayfinding': nbtlib.Byte(1), 'Station': nbtlib.String(diagram['station']), 'Route': nbtlib.String(diagram['line']+' 全线站序 / 乘车方向'), 'NativePlatformId': nbtlib.Long(pid), 'AirService': nbtlib.Byte(diagram['mode'] == 'AIRPLANE'), 'MapRows': nbtlib.List[nbtlib.String]([nbtlib.String(s) for s in diagram['rows']]), 'Clock': nbtlib.Long(0), **{'Row'+str(i): nbtlib.String(s) for i,s in enumerate(diagram['rows'][:3])}})
                for p, after in proposed.items():
                    row = dict(pos=list(p), before=w.block(p), after=after, before_nbt=None, after_nbt=tag.snbt() if p==q else None, owner='r45/active_station/complete_platform_route_map_service', reason='Registered R23 outer-frame service point; exact real native departure direction; whole backing and front reader')
                    if p in changes and changes[p] != row:
                        raise RuntimeError(('Conflicting complete station components', p))
                    changes[p] = row
                maps.append(dict(station=record['station'], line=record['line'], platform=pid, anchor=q, reader=reader, front0p6x1p8=point, reader_approach=approach, actual_diagram=diagram, full9ray=optical, complete_attachment=backing))
                reserved.update(panel + backing)
        if original.unknown:
            raise RuntimeError(('Unknown retained frame shapes', sorted(original.unknown)))
    return [changes[q] for q in sorted(changes)], maps, held

def airport_service_rows(world,diagrams):
    world=Path(world);w=MeasuredWorld(world);w.box((489,70,98),(669,112,158));w.load()
    assert all(s=='full'for s in w.status.values())
    tags=dict(iter_block_entities(world,'projectseele:geofront',(489,70,98),(669,112,158)))
    changes=[];maps=[];held=[];g=ActualGeometry(w)
    for pid,wall,face,reader_z in((3535656344258112120,104,'south',108),(8421791502937934869,152,'north',148)):
        platform=next(p for p in diagrams.native['platforms']if int(p['id'])==pid)
        assert platform['position1']['y']==platform['position2']['y']==104
        assert {platform['position1']['x'],platform['position2']['x']}=={520,650}
        diagram=diagrams.diagram(pid,face,'S1')
        assert diagram['station']=='NERV 航空基地'
        z=wall+(1 if face=='south'else-1)
        for x in (550,574,598,622,644):
            q=(x,107,z);back=[(x+a,107+dy,wall)for a in(-1,0,1)for dy in(0,1)];panel=[(x+a,107+dy,z)for a in(-1,0,1)for dy in(0,1)]
            if any(p in tags or w.block(p)not in AIR for p in panel):held.append(dict(anchor=q,why='Whole panel envelope occupied'));continue
            if any(p in tags or w.block(p)not in{'projectseele:clear_glass','projectseele:nerv_structural_panel','projectseele:nerv_wall_panel'}or g.boxes(p)!=[[0,0,0,1,1,1]]for p in back):held.append(dict(anchor=q,why='Whole original R28 three-by-two sidewall backing absent'));continue
            state=f'projectseele:station_departure_board[facing={face},wayfinding=true]'
            class Image:
                def __init__(self):self.world=world
                def block(self,p):return state if tuple(p)==q else w.block(p)
                def get(self,X,Y,Z):return self.block(tuple(map(math.floor,(X,Y,Z))))
            image=Image();new=ActualGeometry(image);reader=(x,105,reader_z);point=[x+.5,105,reader_z+.5]
            proof=reader_visibility(image.block,lambda s:[]if s in AIR else new.shapes.get(s),q,face,reader,direction=True,route_map=True)
            approach=None
            for dx in(-1,1):
                start=[point[0]+dx,point[1],point[2]]
                if new.standing(start)==new.standing(point)=='STATIC_STANDING'and full_body_status(new,start,point)=='CLEAR':approach=[start,point];break
            if not proof['clear']or approach is None:held.append(dict(anchor=q,reader=reader,why='Actual body/bearing/local aisle sweep or full9 lettering rays blocked'));continue
            tag=nbtlib.Compound({'id':nbtlib.String('projectseele:station_departure_board'),'x':nbtlib.Int(x),'y':nbtlib.Int(107),'z':nbtlib.Int(z),'Wayfinding':nbtlib.Byte(1),'Station':nbtlib.String(diagram['station']),'Route':nbtlib.String('S1 全线站序 / 乘车方向'),'NativePlatformId':nbtlib.Long(pid),'AirService':nbtlib.Byte(0),'MapRows':nbtlib.List[nbtlib.String]([nbtlib.String(s)for s in diagram['rows']]),'Clock':nbtlib.Long(0),**{'Row'+str(i):nbtlib.String(t)for i,t in enumerate(diagram['rows'][:3])}})
            changes.append(dict(pos=list(q),before=w.block(q),after=state,before_nbt=None,after_nbt=tag.snbt(),owner='r45/airbase/whole_R28_sidewall_map_service',reason='Original complete raised passenger platform sidewall and continuous reader aisle; exact current S1 departure'))
            maps.append(dict(anchor=q,reader=reader,reader_approach=approach,backing=[dict(pos=p,state=w.block(p),full_nbt=None)for p in back],full9ray=proof,actual_diagram=diagram))
    assert not g.unknown
    return changes,maps,held
