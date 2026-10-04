"""Prepare complete current campus/Hakone native actions, without world writes.

Server collision exports do not certify client-only native MTR APG leaves.
Two adjacent APG leaves form one doorway; each source leaf stays accounted for.
"""
from __future__ import annotations

import argparse
import copy
import difflib
import hashlib
import json
import math
from collections import Counter, deque
from pathlib import Path

from measure_world_r40 import MeasuredWorld, properties
from query_blocks import AIR, iter_block_entities
from regional_voxels import canonical_state
from school_hakone_patch_r45 import ROOT, ART, sha

WORLD = ROOT/'run/saves/SEELE_FIELD_R45_REVIEW'
LIFECYCLE = ART/'lifecycle_v2'
NORMAL = {'north': (0, -1), 'south': (0, 1), 'east': (1, 0), 'west': (-1, 0)}


def read(path):
    return json.loads(Path(path).read_text('utf8'))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', 'utf8')


class ActualGeometry:
    def __init__(self, world):
        self.world = world
        self.shapes = {canonical_state(s): b for s, b in read(world.world/'native_collision_shapes.json').items()}
        self.unknown = set()

    def boxes(self, q, opened=()):
        state = self.world.block(q)
        if not state:
            self.unknown.add('UNMEASURED:'+str(q))
            return None
        if state.partition('[')[0] in AIR | {'minecraft:light', 'minecraft:water'}:
            return []
        if tuple(q) in opened:
            state = state.replace('open=false', 'open=true')
        # The part shape depends on the actual base fixture. Never accept the
        # arbitrary part shape captured at a different empty test coordinate.
        if state.startswith('projectseele:period_fixture_part['):
            offset = int(properties(state)['offset'])
            base = self.world.get(q[0], q[1]-offset, q[2])
            boxes = self.shapes.get(base)
            if boxes is None:
                self.unknown.add(base or 'MISSING_FIXTURE_OWNER')
                return None
            return [[b[0], max(0, b[1]-offset), b[2], b[3], min(1, b[4]-offset), b[5]]
                    for b in boxes if b[4] > offset and b[1] < offset+1]
        if state not in self.shapes:
            self.unknown.add(state)
            return None
        return self.shapes[state]

    def clear(self, point, opened=(), target=None):
        x, y, z = point
        dx, dz = (0, 0) if target is None else (target[0]-x, target[2]-z)
        lo = [x-.29+min(0, dx), y+.015, z-.29+min(0, dz)]
        hi = [x+.29+max(0, dx), y+1.785, z+.29+max(0, dz)]
        for X in range(math.floor(lo[0]), math.floor(hi[0])+1):
            for Y in range(math.floor(lo[1]), math.floor(hi[1])+1):
                for Z in range(math.floor(lo[2]), math.floor(hi[2])+1):
                    boxes = self.boxes((X, Y, Z), opened)
                    if boxes is None:
                        return 'UNKNOWN_NATIVE_SHAPE'
                    if any(all((X, Y, Z)[k]+b[k] < hi[k] and (X, Y, Z)[k]+b[k+3] > lo[k] for k in range(3)) for b in boxes):
                        return 'ACTUAL_BODY_OBSTRUCTION'
        return 'CLEAR'

    def standing(self, point, opened=()):
        x, y, z = point
        clear = self.clear(point, opened)
        if clear != 'CLEAR':
            return clear
        for dx in (-.25, 0, .25):
            for dz in (-.25, 0, .25):
                px, pz = x+dx, z+dz
                q = math.floor(px), math.floor(y-.04), math.floor(pz)
                boxes = self.boxes(q, opened)
                if boxes is None:
                    return 'UNKNOWN_NATIVE_SHAPE'
                if not any(q[0]+b[0] <= px <= q[0]+b[3] and q[2]+b[2] <= pz <= q[2]+b[5]
                           and abs(q[1]+b[4]-y) < .02 for b in boxes):
                    return 'NO_FULL_DATUM_BEARING'
        return 'STATIC_STANDING'

    def path(self, start, finish, bounds, feet, opened=()):
        start, finish = tuple(start), tuple(finish)
        queue, before = deque([start]), {start: None}
        while queue:
            q = queue.popleft()
            if q == finish:
                route = []
                while q is not None:
                    route.append([q[0]+.5, feet, q[1]+.5]); q = before[q]
                return route[::-1]
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = q[0]+dx, q[1]+dz
                if nxt in before or not (bounds[0] <= nxt[0] <= bounds[2] and bounds[1] <= nxt[1] <= bounds[3]):
                    continue
                p, n = [q[0]+.5, feet, q[1]+.5], [nxt[0]+.5, feet, nxt[1]+.5]
                if self.standing(n, opened) == 'STATIC_STANDING' and self.clear(p, opened, n) == 'CLEAR':
                    before[nxt] = q; queue.append(nxt)
        return None


def walk_action(point, kind='walk', **extra):
    return dict(kind=kind, target=point, **extra)


def ordinary_doors(world, label, bounds, geometry):
    tags = dict(iter_block_entities(world.world, 'projectseele:geofront', bounds[:3], bounds[3:]))
    result = []
    for (cx, sy, cz), (palette, ids) in world.tiles.items():
        wanted = {i for i, s in enumerate(palette) if s.startswith('projectseele:city_personnel_door[') and 'half=lower' in s}
        for i, pid in enumerate(ids):
            if int(pid) not in wanted:
                continue
            q = cx*16+(i & 15), sy*16+(i >> 8), cz*16+((i >> 4) & 15)
            if not all(bounds[k] <= q[k] <= bounds[k+3] for k in range(3)):
                continue
            state = world.block(q); dx, dz = NORMAL[properties(state)['facing']]
            # +/-1 gives true adjacent-cell centres. The old +/-1.5 integer
            # endpoints touched WC pans rather than the free cubicle landing.
            front = [q[0]+.5+dx, q[1], q[2]+.5+dz]
            rear = [q[0]+.5-dx, q[1], q[2]+.5-dz]
            upper = (q[0], q[1]+1, q[2]); opened = {q, upper}
            result.append(dict(id=f'r45/{label}/door/{q[0]}_{q[1]}_{q[2]}', position=list(q), upper_position=list(upper),
                lower_state=state, upper_state=world.block(upper), full_lower_NBT=tags[q].snbt() if q in tags else None,
                full_upper_NBT=tags[upper].snbt() if upper in tags else None, front=front, rear=rear,
                actual_open_endpoint_status=[geometry.standing(p, opened) for p in [front, rear]],
                native_verified=False))
    return sorted(result, key=lambda d: d['position'])


def door_groups(doors):
    native, physics = [], []
    for d in doors:
        q = d['position']
        for suffix, start, finish in [('front_to_rear', d['front'], d['rear']), ('rear_to_front', d['rear'], d['front'])]:
            ident = d['id']+'/'+suffix
            native.append(dict(id=ident, staging=start, restore_blocks=[q, d['upper_position']],
                steps=[dict(kind='use', block=q, want_open=True), walk_action(finish),
                       dict(kind='use', block=q, want_open=False), dict(kind='observe', block=q, expect_open=False)],
                inventory_or_task_mutation=False, initial_pair_and_full_NBT=d, runtime_required=True))
            physics.append(dict(id=ident, path=[start, finish], door=q, useDoor=True, closeDoorAfter=True))
    return native, physics


def room_group(rooms, doors, geometry):
    result, raster = [], []
    for room in rooms:
        x, y, z, X, _, Z = room['bounds']
        opened = {tuple(q) for d in doors for q in [d['position'], d['upper_position']]}
        cells = [(xx, zz) for zz in range(z, Z+1) for xx in range(x, X+1)
                 if geometry.standing([xx+.5, y, zz+.5], opened) == 'STATIC_STANDING']
        centre = sorted(cells, key=lambda q: (q[1], q[0]))
        if not centre:
            raster.append(dict(id=room['id'], error='No current completely supported standing cell', native_verified=False)); continue
        if room.get('wing'):
            q = [x+4, y, Z+1]
            staging = [q[0]+.5, y, q[2]+1.5]
            first = (x+4, Z)
        elif room.get('level')=='lower_station_hall':
            entrances=[d for d in doors if d['position'][1]==y and x<=d['position'][0]<=X and d['position'][2] in (z-1,Z+1)]
            assert entrances,('No actual complete service-room entrance',room['id'])
            entry=min(entrances,key=lambda d:abs(d['position'][0]+.5-(x+X+1)/2))
            q=entry['position'];staging=entry['front'];first=(math.floor(entry['rear'][0]),math.floor(entry['rear'][2]))
        else:
            q = [275, 73, -742 if 'north_changing' in room['id'] else -734]
            staging = [276.5, 73, q[2]+.5]; first = (274, q[2])
        current = first; visited = set(); steps = [dict(kind='use', block=q, want_open=True), walk_action([first[0]+.5, y, first[1]+.5])]
        disconnected = []
        for target in centre:
            if target in visited:
                continue
            path = geometry.path(current, target, [x, z, X, Z], y, opened)
            if path is None:
                disconnected.append(target); continue
            steps.extend(walk_action(p) for p in path[1:]); visited.update((math.floor(p[0]), math.floor(p[2])) for p in path); current=target
        home = geometry.path(current, first, [x, z, X, Z], y, opened)
        if home:
            steps.extend(walk_action(p) for p in home[1:])
        steps += [walk_action(staging), dict(kind='use', block=q, want_open=False)]
        restore = [d['position'] for d in doors if x-1 <= d['position'][0] <= X+1 and z-1 <= d['position'][2] <= Z+1 and d['position'][1] == y]
        restore += [[p[0], p[1]+1, p[2]] for p in list(restore)]
        result.append(dict(id='r45/actual_room/'+room['id'], staging=staging, steps=steps, restore_blocks=restore,
                           auto_use_ordinary_doors=True, current_room=room, current_supported_cell_count=len(cells),
                           routed_cell_count=len(visited), disconnected_supported_cells=disconnected, native_verified=False))
        raster.append(dict(id=room['id'], bounds=room['bounds'], legal_current_standing_cells=cells,
                           routed_cells=sorted(visited), disconnected_cells=disconnected, native_passed=False))
    return result, raster


def pool_group():
    gate, gates = [277, 73, -747], [[277, 73, -747], [278, 73, -747]]
    restore = gates + [[275, y, z] for z in (-742, -734) for y in (73, 74)]
    base = [dict(kind='use', block=gate, want_open=False),dict(kind='blocked', target=[277.5,73,-746.5], block=gate, ticks=35),
            dict(kind='use', block=gate, want_open=True), walk_action([277.5,73,-745.5])]
    steps = copy.deepcopy(base)
    # The full dry ring comes before swimming; no stage teleport enters water.
    steps += [walk_action(q) for q in [[306.5,73,-745.5],[306.5,73,-731.5],[277.5,73,-731.5],[277.5,73,-745.5]]]
    for room, z in [('north_changing',-742),('south_changing',-734)]:
        q = [275,73,z]
        steps += [walk_action([276.5,73,z+.5]), dict(kind='use',block=q,want_open=True),
                  walk_action([274.5,73,z+.5]),walk_action([270.5,73,z+.5]),
                  walk_action([274.5,73,z+.5]),walk_action([276.5,73,z+.5]),dict(kind='use',block=q,want_open=False)]
    # Five independent lengthwise lanes, including deep and shallow water.
    for lane, z in enumerate([-742.5,-740.5,-738.5,-736.5,-734.5],1):
        if lane == 1:
            steps += [walk_action([282.5,73,-744.5]),walk_action([282.5,71.2,-742.5],'swim',water_required=True)]
        else:
            steps += [walk_action([282.5,71.2,z],'swim',water_required=True)]
        steps += [walk_action([302.5,72,z],'swim',water_required=True,minimum_water_ticks=20),
                  walk_action([282.5,71.2,z],'swim',water_required=True,require_actual_swimming=True)]
    for x in (282,298):
        steps += [walk_action([x+.5,72,-742.5],'swim',water_required=True),
                  walk_action([x+.5,73,-744.5],'ladder',ladder_block=[x,72,-743]),
                  dict(kind='observe',dry_grounded=True), walk_action([x+.5,72,-742.5],'swim',water_required=True)]
    for z in (-739,-738):
        steps += [walk_action([302.5,72,z+.5],'swim',water_required=True),
                  walk_action([306.5,73,z+.5],'shallow_exit',exit_step=[304,72,z]),
                  dict(kind='observe',dry_grounded=True)]
        if z == -739:
            steps += [walk_action([302.5,72,z+.5],'swim',water_required=True)]
    steps += [walk_action([306.5,73,-745.5]),walk_action([277.5,73,-745.5]),
              walk_action([277.5,73,-749.5]),dict(kind='use',block=gate,want_open=False)]
    # The other leaf also receives its own natural blocked/open/cross/close.
    steps += [walk_action([278.5,73,-749.5]),dict(kind='use',block=gates[1],want_open=False),dict(kind='blocked',target=[278.5,73,-746.5],block=gates[1],ticks=35),
              dict(kind='use',block=gates[1],want_open=True),walk_action([278.5,73,-745.5]),
              walk_action([278.5,73,-749.5]),dict(kind='use',block=gates[1],want_open=False)]
    return [dict(id='r45/school/pool/full_native_lifecycle',staging=[277.5,73,-749.5],steps=steps,
                 restore_blocks=restore,all_five_lanes=True,ladder_exits=2,shallow_exit_width_cells=2,
                 actual_inputs_only=True,mid_case_teleports_allowed=False,native_verified=False)]


def pool_approach_group(paths, geometry, doors):
    """Operate the real gate along both already-authored campus connections."""
    gate=[277,73,-747]
    forward=next(r for r in paths if r['id']=='r45/school/pool/from_school_north_port')
    backward=next(r for r in paths if r['id']==forward['id']+'/return')
    assert backward['path']==list(reversed(forward['path']))
    assert forward['gate']==backward['gate']==gate
    old_path=[[233.5,73,-730.5],[233.5,73,-750.5],[277.5,73,-750.5],
              [277.5,73,-746.5],[277.5,73,-732.5]]
    corrected=[[233.5,73,-730.5],[233.5,73,-749.5],[277.5,73,-749.5],
               [277.5,73,-746.5],[277.5,73,-732.5]]
    assert forward['path'] in [old_path,corrected],'Current authored campus connector changed independently'
    saved_forward=copy.deepcopy(forward);saved_backward=copy.deepcopy(backward)
    forward=dict(forward,path=corrected,native_passed=False)
    backward=dict(backward,path=list(reversed(corrected)),native_passed=False)
    inside=[277.5,73,-745.5]; outside=forward['path'][2]
    restored=[gate]+[q for d in doors for q in [d['position'],d['upper_position']]]
    opened={tuple(gate)}|{tuple(q) for q in restored[1:]}
    sequences=[(forward,saved_forward,[walk_action(forward['path'][1]),walk_action(outside),
        dict(kind='use',block=gate,want_open=True),walk_action(inside),
        dict(kind='use',block=gate,want_open=False),walk_action(forward['path'][-1])]),
        (backward,saved_backward,[walk_action(inside),dict(kind='use',block=gate,want_open=True),walk_action(outside),
        dict(kind='use',block=gate,want_open=False),walk_action(forward['path'][1]),walk_action(forward['path'][0])])]
    results=[]
    for source,saved,steps in sequences:
        assert geometry.standing(source['path'][0],opened)=='STATIC_STANDING'
        assert all(geometry.standing(a['target'],opened)=='STATIC_STANDING' for a in steps if a['kind']=='walk')
        results.append(dict(id=source['id']+'/actual_gate_lifecycle',staging=source['path'][0],steps=steps,
            restore_blocks=restored,auto_use_ordinary_doors=True,source_saved_route_before=saved,
            effective_corrected_route_record=source,derived_correction_already_installed=source==saved,
            existing_named_port_connection_only=True,mid_case_teleports_allowed=False,native_verified=False))
    return results


def transit_patch(out):
    source = ROOT/'src/main/java/com/projectseele/client/visual/RegionalTransitR44Checks.java'
    before = source.read_text('utf8'); after = before
    if 'var selected=HakonePlatformLifecycleR45.select(mc,v,current);' in before:
        (out/'regional_transit_exact_apg.patch').write_text('','utf8')
        write(out/'regional_transit_patch_precondition.json',dict(source=str(source.resolve()),sha256=sha(source),
              root_source_modified=False,root_only_merge=True,exact_hook_already_in_root_source=True))
        return
    old = 'Object c=cars.get(0),resource=resourceCache(v,c);if(resource==null)continue;\n                    var d=RegionalTransitRidingChecks.measuredDoorway(v,resource,c,mc.player.position(),aircraft(),p->eligibleDoor(mc,p,false));if(d==null)continue;'
    new = '''Object c,resource;RegionalTransitRidingChecks.NativeDoorway d;
                    if(current.has("r45_apg"))
                    {
                        var selected=HakonePlatformLifecycleR45.select(mc,v,current);
                        if(selected==null)continue;
                        c=selected.car();resource=selected.resource();d=selected.doorway();
                        result.add("r45_exact_source_APG",selected.evidence());
                    }
                    else
                    {
                        c=cars.get(0);resource=resourceCache(v,c);if(resource==null)continue;
                        d=RegionalTransitRidingChecks.measuredDoorway(v,resource,c,mc.player.position(),aircraft(),p->eligibleDoor(mc,p,false));if(d==null)continue;
                    }'''
    assert old in after, 'Root transit source changed; regenerate against its exact current source'
    after = after.replace(old,new,1)
    old = 'if(onNativeVehicle())\n                {setWalk(List.of(doorway.inside()));result.addProperty("actual_native_door_crossing",true);phase(4);}'
    new = '''if(onNativeVehicle())
                {if(current.has("r45_apg"))HakonePlatformLifecycleR45.requireCrossing(mc,current,doorway,result);
                    setWalk(List.of(doorway.inside()));result.addProperty("actual_native_door_crossing",true);phase(4);}'''
    assert old in after; after=after.replace(old,new,1)
    old='Vec3 point=vec(profile(false).getAsJsonArray("staging"));staged=false;'
    new='HakonePlatformLifecycleR45.beginCase(current);Vec3 point=vec(profile(false).getAsJsonArray("staging"));staged=false;'
    assert old in after;after=after.replace(old,new,1)
    old='doorway=RegionalTransitRidingChecks.measuredDoorway(vehicle,cache,car,preferred,aircraft(),q->eligibleDoor(mc,q,true));require(doorway!=null,"No supported destination doorway");'
    new='doorway=current.has("r45_apg")?HakonePlatformLifecycleR45.destinationDoorway(vehicle,cache,car,preferred,q->eligibleDoor(mc,q,true)):RegionalTransitRidingChecks.measuredDoorway(vehicle,cache,car,preferred,aircraft(),q->eligibleDoor(mc,q,true));require(doorway!=null,"No supported destination doorway");'
    assert old in after;after=after.replace(old,new,1)
    old='if(!staged)return;\n            if(stage==0)'
    new='if(!staged)return;\n            if(current.has("r45_apg"))HakonePlatformLifecycleR45.observe(mc,current,result,stage);\n            if(stage==0)'
    assert old in after;after=after.replace(old,new,1)
    old='result.addProperty("actual_exit_path",true);result.addProperty("native_interface_pass",true);'
    new='if(current.has("r45_apg"))HakonePlatformLifecycleR45.completeCase(result);result.addProperty("actual_exit_path",true);result.addProperty("native_interface_pass",true);'
    assert old in after;after=after.replace(old,new,1)
    patch=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),
              fromfile='a/src/main/java/com/projectseele/client/visual/RegionalTransitR44Checks.java',
              tofile='b/src/main/java/com/projectseele/client/visual/RegionalTransitR44Checks.java'))
    (out/'regional_transit_exact_apg.patch').write_text(patch,'utf8')
    write(out/'regional_transit_patch_precondition.json',dict(source=str(source.resolve()),sha256=sha(source),
          root_source_modified=False,root_only_merge=True,ordinary_38_unbound_behavior_preserved=True))


def prepare(world_path, out):
    out=Path(out)
    followup=ROOT/'artifacts/rebuild_r45/school_hakone_readonly_followup'
    assert any(p.resolve() in out.resolve().parents for p in [ART,followup]) and not out.exists()
    out.mkdir(parents=True)
    current=MeasuredWorld(world_path)
    campus=[216,48,-790,314,102,-668]; station=[-1560,90,610,-1396,151,700]
    for box in [campus,station]:current.box(tuple(box[:3]),tuple(box[3:]))
    current.load();assert all(s=='full' for s in current.status.values())
    geometry=ActualGeometry(current)
    school=ordinary_doors(current,'school',campus,geometry); hakone=ordinary_doors(current,'hakone',station,geometry)
    assert len(school)==32 and len(hakone)==16
    group=out/'groups';group.mkdir()
    school_client,school_physics=door_groups(school); hakone_client,hakone_physics=door_groups(hakone)
    write(group/'10_school_all32_doors_client.json',school_client);write(group/'11_school_all32_doors_physics.json',school_physics)
    write(group/'40_hakone_all16_personnel_doors_client.json',hakone_client);write(group/'41_hakone_all16_personnel_doors_physics.json',hakone_physics)
    rooms=read(current.world/'r45_school_hakone_components.json')['school']['rooms']
    roomcases,raster=room_group(rooms,school,geometry)
    assert len(roomcases)==20
    write(group/'20_school_whole20_rooms_client.json',roomcases);write(out/'school_current_full_room_raster.json',raster)
    write(out/'current_ordinary_door_endpoints.json',school+hakone)
    paths=read(current.world/'quality_walk_cases.json')
    pool_approaches=pool_approach_group(paths,geometry,school)
    write(group/'33_school_pool_actual_campus_approaches_client.json',pool_approaches)
    route_changes=[dict(id=c['source_saved_route_before']['id'],before=c['source_saved_route_before'],
        after=c['effective_corrected_route_record'],reason='Preserve named school/pool endpoints; follow the installed Z=-750 bearing row rather than absent Z=-751',
        inverse=dict(before=c['effective_corrected_route_record'],after=c['source_saved_route_before']))
        for c in pool_approaches if not c['derived_correction_already_installed']]
    write(out/'pool_approach_route_plan.json',dict(target=str(current.world/'quality_walk_cases.json'),
        expected_current_file_sha256=sha(current.world/'quality_walk_cases.json'),exact_record_changes=route_changes,
        preserve_all_other_records_and_order=True,world_block_patch_cells=0,world_written=False,native_pass=False))
    source_stairs=read(LIFECYCLE/'native_groups/20_school_stairs_and_roof.json')
    stairs=[]
    for row in source_stairs:
        steps=[walk_action(p,'walk',allow_step=True) for p in row['path'][1:]]
        if row.get('door'):steps.insert(0,dict(kind='use',block=row['door'],want_open=True))
        stairs.append(dict(id=row['id'],staging=row['path'][0],steps=steps,auto_use_ordinary_doors=True,
                           restore_blocks=[q for d in school for q in [d['position'],d['upper_position']]],native_verified=False))
    write(group/'30_school_all_stairs_roof_client.json',stairs)
    write(group/'31_school_stairs_physics.json',source_stairs)
    write(group/'32_school_pool_client.json',pool_group())
    school_other=[r for r in read(LIFECYCLE/'native_groups/10_school_room_and_floor_walks.json') if not any(t in r['id'] for t in ['complete_room','stair'])]
    write(group/'21_school_corridors_gym_field_physics.json',school_other)
    def client_journeys(rows,all_doors):
        result=[]
        restored=[q for d in all_doors for q in [d['position'],d['upper_position']]]
        for r in rows:
            points=r.get('path') or [r.get('start'),r.get('end')]
            assert points and points[0] is not None and points[-1] is not None,('Current authored journey lacks coordinates',r['id'])
            steps=[walk_action(p,allow_step=True) for p in points[1:]]
            if r.get('door'):steps.insert(0,dict(kind='use',block=r['door'],want_open=True))
            if not steps:steps=[dict(kind='observe',dry_grounded=True)]
            result.append(dict(id=r['id'],staging=points[0],steps=steps,auto_use_ordinary_doors=True,
                restore_blocks=restored,source_current_route_record=r,
                board_reading_separate_native_contract_and_photos_required=bool(r.get('readingBoard')),native_verified=False))
        return result
    # Ordinary classroom thresholds already have complete32-door/whole20-room
    # cases, while these preserve the full actual public corridors/genkan/gym.
    school_circulation=[r for r in school_other if '/main/' not in r['id'] or '/main/public_entry' in r['id']
                        or any(t in r['id'] for t in ['sports_side_entry','genkan/'])]
    write(group/'22_school_current_occupied_routes_client.json',client_journeys(school_circulation,school))
    pool_sports=[r for r in paths if r['id'] in ['r45/school/pool/to_retained_sports_field',
                                               'r45/school/pool/to_retained_sports_field/return']]
    assert len(pool_sports)==2
    for route in pool_sports:
        assert all(geometry.standing(point)=='STATIC_STANDING' for point in route['path'])
    write(group/'34_school_pool_sports_field_connections_client.json',client_journeys(pool_sports,school))
    profiles=read(ART/'hakone_v5/boarding_interfaces.json')
    owned_ids={r['id'] for r in read(LIFECYCLE/'native_groups/50_hakone_service_and_transfers.json')}
    for profile in profiles:owned_ids.update(profile['source']['station_walk_case_ids'])
    station_walks=[r for r in paths if r['id'] in owned_ids]
    assert len(station_walks)==len(owned_ids),('Missing exact actual Hakone route IDs',owned_ids-{r['id'] for r in station_walks})
    assert not any(r.get('requires_actual_APG_open') or r.get('door') and current.block(r['door']).startswith('mtr:apg_door[') for r in station_walks)
    write(group/'42_hakone_current_entries_service_transfers_physics.json',station_walks)
    write(group/'43_hakone_current122_journeys_client.json',client_journeys(station_walks,hakone))
    station_rooms=read(current.world/'r45_school_hakone_components.json')['hakone']['rooms']
    service_cases,service_raster=room_group(station_rooms,hakone,geometry)
    assert len(service_cases)==6
    write(group/'44_hakone_whole6_service_rooms_client.json',service_cases)
    write(out/'hakone_current_full_service_room_raster.json',service_raster)
    floor_rows=[];floor_coverage=[]
    opened={tuple(q) for d in school for q in [d['position'],d['upper_position']]}|{(277,73,-747),(278,73,-747)}
    for region in read(current.world/'r45_school_hakone_components.json')['school']['floors']:
        x,z,X,Z=region['bounds'];feet=region['feet'];legal=[];unknown=[];counts=Counter()
        def in_room(xx,zz):
            return any(r['bounds'][1]==feet and r['bounds'][0]<=xx<=r['bounds'][3] and r['bounds'][2]<=zz<=r['bounds'][5] for r in rooms)
        for zz in range(z,Z+1):
            spans=[];span=[]
            for xx in range(x,X+1):
                if in_room(xx,zz):counts['SEPARATE_COMPLETE_ROOM_SUITE']+=1;state='ROOM'
                else:
                    state=geometry.standing([xx+.5,feet,zz+.5],opened);counts[state]+=1
                    if state=='STATIC_STANDING':legal.append([xx,zz])
                    if state=='UNKNOWN_NATIVE_SHAPE':unknown.append([xx,zz])
                if state!='STATIC_STANDING' or span and geometry.clear([span[-1]+.5,feet,zz+.5],opened,[xx+.5,feet,zz+.5])!='CLEAR':
                    if span:spans.append(span);span=[]
                if state=='STATIC_STANDING':span.append(xx)
            if span:spans.append(span)
            for part,xs in enumerate(spans):
                floor_rows.append(dict(id=region['id']+f'/whole_public_row/{zz}/{part}',path=[[xs[0]+.5,feet,zz+.5],[xs[-1]+.5,feet,zz+.5]],
                    supported_columns=[[xx,zz] for xx in xs],current_region=region,
                    interactBlocks=[[277,73,-747],[278,73,-747]] if region['id']=='r45/school/pool_deck' else [],
                    closeDoorAfter=True,native_passed=False,scope='Native horizontal whole-width physics; separate true entrances/stairs/lifecycle still required'))
        floor_coverage.append(dict(id=region['id'],current_region=region,classified_columns=dict(counts),
            all_non_room_static_standing_cells=legal,unknown_cells=unknown,native_or_visual_pass=False))
    write(group/'23_school_all_declared_public_floor_rows_physics.json',floor_rows)
    write(out/'school_declared_full_public_floor_classification.json',floor_coverage)
    allgate=read(ROOT/'artifacts/rebuild_r44/facility_transit_r44/public_station_gates_v2/native_cases.json')
    assert len(allgate)==160
    current_gate=read(current.world/'r44_public_station_gates.json')['gates']
    wanted={tuple(p['position']) for p in current_gate if str(p['station_id'])=='6131386888082811228'}
    assert len(wanted)==8
    indices=[i for i,r in enumerate(allgate) if tuple(r['actualAutomaticGate']) in wanted]
    assert len(indices)==16
    write(group/'50_all160_gate_denominator_hakone16_ranges.json',allgate)
    gate_ranges=[]
    for i in indices:
        if gate_ranges and gate_ranges[-1]['end']==i:gate_ranges[-1]['end']=i+1
        else:gate_ranges.append(dict(start=i,end=i+1))
    source=ROOT/'artifacts/rebuild_r44/facility_transit_r44/native_transit_cases/cases.json'
    alltransit=read(source); assert len(alltransit['cases'])==38
    native_doors=read(LIFECYCLE/'object_inventory/hakone_all_actual_doors.json')
    bypos={tuple(d['position']):d for d in native_doors if d['actual_state'].startswith('mtr:apg_door[')}
    platform_ids={p['source_platform'] for p in profiles}; apertures=[]
    for profile in profiles:
        pid=profile['source_platform'];p=profile['source'];lo=p['platform_lo'];hi=p['platform_hi'];rows=[]
        for q,d in bypos.items():
            if q[1]==p['staging'][1] and lo[0]<=q[0]<=hi[0] and q[2] in [lo[2],hi[2]]:
                rows.append((q,d))
        seen=set()
        for q,d in sorted(rows):
            if q in seen:continue
            partner=next(((Q,D) for Q,D in rows if Q not in seen and Q[2]==q[2] and abs(Q[0]-q[0])==1 and
                         properties(D['actual_state'])['facing']==properties(d['actual_state'])['facing'] and
                         properties(D['actual_state'])['side']!=properties(d['actual_state'])['side']),None)
            assert partner,('No actual opposite native APG leaf',q)
            Q,D=partner;seen.update([q,Q]);face=properties(d['actual_state'])['facing'];dx,dz=NORMAL[face]
            public=[min(q[0],Q[0])+1, q[1],q[2]+.5-dz]
            apertures.append(dict(id=f'r45/hakone/APG/{pid}/{min(q[0],Q[0])}_{q[2]}',platform_id=pid,
                leaves=[list(q),list(Q)],upper_leaves=[[a[0],a[1]+1,a[2]] for a in [q,Q]],
                actual_states=[current.block(q),current.block(Q)],actual_NBT=[d['actual_full_NBT'],D['actual_full_NBT']],
                facing=face,public_approach=public,source_platform_lo=lo,source_platform_hi=hi,
                actual_approach_status=geometry.standing(public),native_client_closed_collision_required=True,
                personnel_useDoor_allowed=False,native_verified=False))
        assert len(seen)==p['actual_APG_pairs']
    assert len(apertures)==184 and sum(len(a['leaves']) for a in apertures)==368
    write(out/'all184_complete_APG_apertures_368_leaves.json',apertures)
    windows=[];ports=out/'apg_port_cases';ports.mkdir()
    for a in apertures:
        blob=copy.deepcopy(alltransit);idx=next(i for i,c in enumerate(blob['cases']) if c['source_platform']==a['platform_id'])
        case=blob['cases'][idx];case['id']=a['id'];case['source']['staging']=a['public_approach'];case['r45_apg']=a
        name=f'{len(windows):03d}_{idx:02d}.json';write(ports/name,blob)
        windows.append(dict(id=a['id'],cases=str((ports/name).resolve()),start=idx,end=idx+1,
                            both_native_leaves=a['leaves'],client_APG_closed_and_open_required=True,served_door_not_assumed=True))
    write(out/'184_exact_native_APG_journey_windows.json',windows)
    direction=[dict(index=i,source=c['source_platform'],destination=c['destination_platform'],start=i,end=i+1,
                    role=('Hakone outgoing' if c['source_platform'] in platform_ids else 'Hakone incoming'))
               for i,c in enumerate(alltransit['cases']) if c['source_platform'] in platform_ids or c['destination_platform'] in platform_ids]
    assert len(direction)==8
    write(group/'60_all38_current_transit_denominator.json',alltransit)
    transit_patch(out)
    pending=ROOT/'artifacts/rebuild_r45/transport_controls_agent/current_audit_v1'
    route_plan=read(pending/'exact_derived_plan.json');actual_routes={r['id']:r for r in paths}
    route_states=[dict(id=r['id'],installed_actual_record=actual_routes.get(r['id'])==r['after']) for r in route_plan['changed_cases']]
    nbt_states=[]
    for q in [(135,-441,-54),(123,-441,-26)]:
        tag=dict(iter_block_entities(current.world,'projectseele:geofront',q,q)).get(q)
        nbt_states.append(dict(position=list(q),actual_native_BE_installed=tag is not None and str(tag.get('id'))=='mtr:route_sign_wall_light'
                              and int(tag.get('platform_id',0))==-4991105154196472855))
    write(out/'transport_candidate_actual_install_readback.json',dict(route_records=route_states,native_upper_BE=nbt_states,
        root_statement_installed=True,actual_saved_records_checked=True,world_written=False))
    write(out/'native_order.json',dict(schema=45,world=str(current.world.resolve()),world_written=False,
        school_door_pairs=32,hakone_personnel_pairs=16,school_rooms=20,school_stairs_cases=len(stairs),
        school_pool_cases=1,school_pool_approach_cases=len(pool_approaches),school_pool_sports_cases=len(pool_sports),hakone_ticket_gate_cells=8,hakone_gate_ranges=gate_ranges,hakone_gate_cases=16,
        hakone_direction_windows=direction,complete_APG_apertures=184,APG_leaves=368,
        groups={p.stem:dict(path=str(p.resolve()),sha256=sha(p),cases=len(read(p))) for p in group.glob('*.json') if 'denominator' not in p.stem},
        required_root_patch=str((out/'regional_transit_exact_apg.patch').resolve()),
        transport_candidates_actual_readback=str((out/'transport_candidate_actual_install_readback.json').resolve()),
        transport_candidate_paths=[str((pending/'native_sign_BE_integrity').resolve()),str((pending/'exact_derived_plan.json').resolve())],
        those_candidates_used_as_installed=all(r['installed_actual_record'] for r in route_states) and all(r['actual_native_BE_installed'] for r in nbt_states),
        native_or_visual_passed=False,
        unknown_native_states=sorted(geometry.unknown),
        current_source_sha256={name:sha(ROOT/'src/main/java/com/projectseele/client/visual'/name) for name in
            ['SchoolPoolLifecycleR45.java','RegionalTransitR44Checks.java','HakonePlatformLifecycleR45.java']},
        pending=['Root compiles current client source; existing exact APG hook is independently checked',
                 'Execute complete groups including both current campus/pool approach directions',
                 'Native client still photographs; video recording is not requested',
                 'Cold restart and same JVM reload','Delivered-copy inventory/traffic/player-progress readback']))
    print('Prepared current doors32/16 rooms20 pool1 APG184/368 gates8 directions8; no MC, build or world write',out,flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--world',type=Path,default=WORLD)
    p.add_argument('--out',type=Path,default=ROOT/'artifacts/rebuild_r45/school_hakone_readonly_followup/native_lifecycle_v7');args=p.parse_args();prepare(args.world,args.out)


if __name__=='__main__':main()
