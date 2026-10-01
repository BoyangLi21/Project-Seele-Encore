"""Mounted platform maps from actual boarding mouths, never from empty space.

Plans only. Root applies exact forward/inverse cells after independent review.
Every added panel has a real roof attachment, full rendered volume clearance,
and a supported reader reached from each assigned boarding mouth.
"""
from pathlib import Path
from collections import defaultdict, Counter
import argparse, copy, hashlib, itertools, json, math
import nbtlib
import regional_voxels as v
from query_blocks import AIR, iter_block_entities
from measure_world_r40 import MeasuredWorld, properties
from audit_facility_transit_r44 import Geometry, NORMAL
from station_route_contract_r44 import RouteDiagrams

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'artifacts/rebuild_r44/facility_transit_r44'
WORLD = ROOT / 'run/saves/SEELE_FIELD_R44_REVIEW'
CHAIN = 'minecraft:chain[axis=y,waterlogged=false]'
POST = 'minecraft:iron_bars[east=false,north=false,south=false,waterlogged=false,west=false]'


def main(world=WORLD, out=None, platform=None):
    world, out = Path(world), Path(out or ART / 'platform_information_v1')
    out.mkdir(parents=True, exist_ok=False)
    before = json.loads((ART / 'station_signs/full_sign_audit.json').read_text(encoding='utf8'))
    platforms = [p for p in before['door_coverage'] if platform is None or str(p['platform']) == str(platform)]
    assert platforms
    w = MeasuredWorld(world)
    for p in platforms:
        points = [r['approach'] for r in p['door_pairs']]
        w.box(tuple(min(q[i] for q in points) - (12 if i != 1 else 2) for i in range(3)),
              tuple(max(q[i] for q in points) + (12 if i != 1 else 13) for i in range(3)))
    w.load()
    geometry, diagrams = Geometry(w), RouteDiagrams()
    changes, dependencies, reserved, tags, cards, unresolved = {}, {}, set(), {}, [], []
    native_cases = []
    station_bounds = {int(p['id']): s['bounds'] for s in json.loads(
        (ROOT/'artifacts/repair_r43/facility_catalogue/catalogue.json').read_text(encoding='utf8'))['stations'] for p in s['platforms']}
    def block(q):
        q = tuple(q)
        state = w.block(q)
        dependencies[q] = state
        return state
    def safe_air(q):
        state = block(q)
        return state is not None and state.partition('[')[0] in AIR and tuple(q) not in reserved
    def path(a, b):
        if geometry.standing(a)['status'] != 'STATIC_STANDING' or geometry.standing(b)['status'] != 'STATIC_STANDING':
            return None
        result = geometry.flat_path(tuple(a), tuple(b), radius=13)
        if result and len(result) - 1 <= 8:
            # New low wall panels have a three-cell rendered/collision span;
            # the saved geometry does not contain them until installation.
            if any((q[0], q[1] + dy, q[2]) in reserved for q in result for dy in (0, 1)):
                return None
            return result
        return None
    def wall_candidate(door):
        x, fy, z = door['approach']; lower = door['door_lower']
        nx, nz = x - lower[0], z - lower[2]; tx, tz = nz, -nx
        face = next(k for k, normal in NORMAL.items() if normal == (-nx, -nz))
        for inset, along in itertools.product((3, 4, 5, 6, 7), (-2, 2, 0, -3, 3, -1, 1)):
            q = (x + nx * inset + tx * along, fy + 1, z + nz * inset + tz * along)
            volume = {(q[0] + tx*a, yy, q[2] + tz*a) for a in (-1, 0, 1) for yy in (q[1], q[1]+1)}
            if not all(safe_air(cell) for cell in volume):
                continue
            bearing = []
            for a in (-1, 0, 1):
                cell = (q[0] + nx + tx*a, q[1], q[2] + nz + tz*a)
                state = block(cell); base = (state or '').partition('[')[0]
                boxes = geometry.boxes(state)
                if base not in {'minecraft:smooth_stone', 'minecraft:stone', 'minecraft:gray_concrete',
                    'minecraft:light_gray_concrete', 'minecraft:white_concrete', 'projectseele:clear_glass',
                    'projectseele:nerv_structural_panel', 'projectseele:nerv_wall_panel', 'projectseele:nerv_machine_panel'} or not boxes:
                    break
                # Require a complete fixed backing face; a narrow post or
                # neighbouring device is not the back of this panel.
                if not any(b[0] <= .01 and b[1] <= .01 and b[2] <= .01 and b[3] >= .99 and b[4] >= .99 and b[5] >= .99 for b in boxes):
                    break
                bearing.append({'position':cell,'state':state})
            if len(bearing) != 3:
                continue
            for distance in (2, 3):
                reader = (q[0]-nx*distance, fy, q[2]-nz*distance)
                walk = path(door['approach'], reader)
                if not walk or any((point[0],point[1]+dy,point[2]) in volume for point in walk for dy in (0,1)):
                    continue
                # Full three-cell wall backing, plus a straight supported
                # read approach. Current full-size board's rear bracket
                # physically reaches the fixed backing face.
                line = [(q[0]-nx*d, fy, q[2]-nz*d) for d in range(1,distance+1)]
                if all(geometry.standing(a)['status']=='STATIC_STANDING' for a in line):
                    return q, face, volume, set(), bearing, (reader,walk)
        return None
    def floor_candidate(p, door):
        x, fy, z = door['approach']; lower = door['door_lower']
        nx, nz = x-lower[0], z-lower[2]; tx, tz = nz,-nx
        face = next(k for k,normal in NORMAL.items() if normal == (-nx,-nz))
        lo, hi = station_bounds[int(p['platform'])]
        choices = []
        for inset, along in itertools.product((5,6,4), (-2,2,-3,3,0)):
            q = (x+nx*inset+tx*along,fy+1,z+nz*inset+tz*along)
            volume = {(q[0]+tx*a,yy,q[2]+tz*a) for a in (-1,0,1) for yy in (fy,fy+1,fy+2)}
            if not all(all(lo[i] <= cell[i] <= hi[i] for i in range(3)) and safe_air(cell) for cell in volume):
                continue
            bearing=[]
            for a in (-1,0,1):
                standing=(q[0]+tx*a,fy,q[2]+tz*a)
                floor=(standing[0],fy-1,standing[2]);state=block(floor)
                # A side information fixture needs a fixed station slab;
                # platforms/APG, belts, stairs and roofs are not a plinth.
                if (state or '').partition('[')[0] not in {'minecraft:smooth_stone','minecraft:light_gray_concrete',
                    'minecraft:gray_concrete','minecraft:white_concrete','projectseele:nerv_floor_panel'}:
                    break
                if geometry.standing(standing)['status']!='STATIC_STANDING':
                    break
                bearing.append({'position':floor,'state':state,'structure':'floor_poster'})
            if len(bearing)!=3:
                continue
            for distance in (2,3):
                reader=(q[0]-nx*distance,fy,q[2]-nz*distance)
                walk=path(door['approach'],reader)
                if not walk or any((point[0],point[1]+dy,point[2]) in volume for point in walk for dy in (0,1)):
                    continue
                # Keep a separate continuous two-metre passenger lane in
                # front of the whole fixture, not just one standing point.
                front=[(q[0]-nx*d+tx*a,fy,q[2]-nz*d+tz*a) for d in (1,2) for a in range(-2,3)]
                if not all(geometry.standing(cell)['status']=='STATIC_STANDING' for cell in front):
                    continue
                feet={(q[0]+tx*a,yy,q[2]+tz*a) for a in (-1,1) for yy in (fy,fy+1,fy+2)}
                choices.append((q,face,volume,feet,bearing,(reader,walk)))
        return choices
    def candidate(p, door):
        mounted = wall_candidate(door)
        choices = ([mounted] if mounted is not None else []) + floor_candidate(p,door)
        x, fy, z = door['approach']
        lower = door['door_lower']
        nx, nz = x - lower[0], z - lower[2]
        if (nx, nz) not in NORMAL.values():
            raise RuntimeError(('Invalid real passenger normal', door))
        face = next(k for k, normal in NORMAL.items() if normal == (nx, nz))
        tx, tz = nz, -nx
        # The panel remains above the public head clearance and wholly on
        # the passenger side of the actual APG strip. No rail/door is changed.
        for inset, along in itertools.product((1, 2, 3, 4), (-2, 2, -3, 3, 0, 1, -1)):
            q = (x + nx * inset + tx * along, fy + 2, z + nz * inset + tz * along)
            volume = {(q[0] + tx * a, yy, q[2] + tz * a)
                      for a in (-1, 0, 1) for yy in (q[1], q[1] + 1)}
            if not all(safe_air(cell) for cell in volume):
                continue
            chains, bearing = set(), []
            for a in (-1, 1):
                bx, bz = q[0] + tx * a, q[2] + tz * a
                fixed = None
                for yy in range(q[1] + 2, fy + 12):
                    cell = (bx, yy, bz)
                    state = block(cell)
                    if state is None:
                        break
                    if state.partition('[')[0] in AIR:
                        if cell in reserved:
                            break
                        chains.add(cell)
                        continue
                    # Roof suspension belongs to fixed building fabric;
                    # lights, signs, escalators, rails and unknown devices
                    # cannot silently become bearing structure.
                    base = state.partition('[')[0]
                    bs = geometry.boxes(state)
                    if bs and base in {'minecraft:smooth_stone', 'minecraft:stone', 'minecraft:gray_concrete',
                                        'minecraft:light_gray_concrete', 'minecraft:white_concrete',
                                        'projectseele:nerv_structural_panel', 'projectseele:nerv_wall_panel',
                                        'projectseele:nerv_machine_panel', 'projectseele:nerv_ceiling_panel'}:
                        if any(b[0] <= .5 <= b[3] and b[2] <= .5 <= b[5] and b[1] <= .01 for b in bs):
                            fixed = {'position': cell, 'state': state}
                    break
                if fixed is None:
                    break
                bearing.append(fixed)
                chains.add((bx, q[1] + 1, bz))
            if len(bearing) != 2:
                continue
            readers = []
            # A graph-nearest point directly under the panel is not a
            # comfortable reading position. Actual R44 shader photographs
            # showed severe foreshortening at one metre; preserve a real
            # three-metre front approach even if coverage counts decrease.
            for distance in (3, 4):
                reader = (q[0] + nx * distance, fy, q[2] + nz * distance)
                walk = path(door['approach'], reader)
                if not walk:
                    continue
                # Rendered glyphs lie on the panel's real front face.
                eye = (reader[0] + .5, fy + 1.62, reader[2] + .5)
                target = (q[0] + .5 + nx * .21, q[1] + 1.0, q[2] + .5 + nz * .21)
                clear = True
                for i in range(1, 81):
                    t = i / 80
                    at = tuple(eye[j] * (1-t) + target[j] * t for j in range(3))
                    cell = tuple(map(math.floor, at))
                    if cell == q:
                        continue
                    boxes = geometry.boxes(block(cell))
                    if boxes is None or any(all(cell[j] + b[j] + .001 < at[j] < cell[j] + b[j+3] - .001
                                                for j in range(3)) for b in boxes):
                        clear = False
                        break
                if clear:
                    readers.append((reader, walk))
            if readers:
                for reader in readers:
                    choices.append((q, face, volume, chains, bearing, reader))
        if not choices:
            return None
        def benefit(choice):
            reader = choice[5][0]
            distances = [abs(reader[0]-d['approach'][0])+abs(reader[2]-d['approach'][2])
                         for d in p['_remaining'] if reader[1] == d['approach'][1]]
            mount_rank=2 if choice[4][0].get('structure')=='floor_poster' else 1 if choice[3] else 0
            return (sum(n <= 8 for n in distances), -mount_rank, -len(choice[3]), -sum(n for n in distances if n <= 8))
        # Minimise duplicated diagrams by selecting the clearest shared
        # information point. Final coverage still requires actual swept paths.
        return max(choices, key=benefit)

    for p in platforms:
        remaining = list(p['door_pairs'])
        existing = [b for b in before['boards'] if b['kind'] == 'route_map' and b['reader']
                    and int(b['native_platform_id']) == int(p['platform'])]
        covered = []
        for door in remaining[:]:
            for b in existing:
                walk = path(door['approach'], b['reader'])
                if walk:
                    covered.append({'door': door['door_lower'], 'map': b['position'], 'reader': b['reader'],
                                    'walk': walk, 'new': False})
                    remaining.remove(door)
                    break
        # Each success serves a measured consecutive set of boarding mouths;
        # unmatched mouths remain explicitly unresolved, never silently passed.
        while remaining:
            seed = remaining[0]
            p['_remaining'] = remaining
            found = candidate(p, seed)
            if found is None:
                unresolved.append({'platform': p['platform'], 'station': p['station'], 'door': seed,
                                   'reason': 'No full-sized clear suspended panel with two real roof anchors and a reachable front reader'})
                remaining.remove(seed)
                continue
            q, face, volume, chains, bearing, (reader, seed_walk) = found
            state = f'projectseele:station_departure_board[facing={face},wayfinding=true]'
            changes[q] = state
            is_floor = bearing[0].get('structure')=='floor_poster'
            for cell in chains:
                changes[cell] = POST if is_floor else CHAIN
            reserved.update(volume | chains)
            diagram = diagrams.diagram(p['platform'], face)
            tag = nbtlib.Compound(id=nbtlib.String('projectseele:station_departure_board'),
                x=nbtlib.Int(q[0]), y=nbtlib.Int(q[1]), z=nbtlib.Int(q[2]),
                Station=nbtlib.String(diagram['station']), Route=nbtlib.String(diagram['line']+' 全线站序'),
                NativePlatformId=nbtlib.Long(p['platform']), PlatformCentre=nbtlib.Long(0),
                Wayfinding=nbtlib.Byte(1), MapRows=nbtlib.List[nbtlib.String]([nbtlib.String(s) for s in diagram['rows']]))
            for i in range(3):
                tag['Row'+str(i)] = nbtlib.String(diagram['rows'][i] if len(diagram['rows']) > i else '')
            tags[q] = tag
            served = []
            for door in remaining[:]:
                walk = path(door['approach'], reader)
                if walk:
                    served.append(door['door_lower'])
                    covered.append({'door': door['door_lower'], 'map': q, 'reader': reader, 'walk': walk, 'new': True})
                    remaining.remove(door)
                    native_cases.append({'id': f'r44/platform_map/{p["platform"]}/{len(native_cases)}',
                                         'path': [[float(a)+.5 if j != 1 else float(a) for j,a in enumerate(point)] for point in walk]})
            assert seed['door_lower'] in served
            cards.append({'position': q, 'facing': face, 'reader': reader, 'suspended_from': bearing,
                          'chains': sorted(chains), 'full_render_volume': sorted(volume),
                          'mount': 'floor_poster' if is_floor else 'roof_suspended' if chains else 'fixed_wall',
                          'head_clearance': 2.25 if chains and not is_floor else None, 'diagram': diagram, 'served_doors': served})
        p['information_coverage_current_plan'] = covered
        p.pop('_remaining', None)
    v.WORLD, v.OUT = world, out
    forward, inverse = v.Painter(), v.Painter()
    for q, after in sorted(changes.items()):
        current = block(q)
        assert current is not None and current.partition('[')[0] in AIR, (q, current)
        forward.match((*q, *q), current, after, 'r44/platform_information/mounted_map')
        inverse.match((*q, *q), after, current, 'inverse/r44/platform_information/mounted_map')
    forward.block_entities.update(tags)
    report = {'world': str(world), 'platforms': len(platforms), 'new_panels': len(cards), 'cells': len(changes),
              'total_boarding_mouths': sum(len(p['door_pairs']) for p in platforms),
              'covered_mouths': sum(len(p['information_coverage_current_plan']) for p in platforms),
              'unresolved': unresolved, 'unknown_shapes': sorted(geometry.unknown),
              'reference': 'https://www.fujifilm.com/jp/ja/business/signage/railway/sign — actual page images inspected; roof suspension is project engineering, not a traced historical station',
              'scope': 'Plan only; native whole-width walk, exact text legibility, cold reload, other clients and final copy NOT VERIFIED'}
    forward.meta.update(report); inverse.meta.update({'forward': 'mounted_platform_maps', 'complete_inverse': True})
    forward.save_plan('mounted_platform_maps'); inverse.save_plan('inverse_mounted_platform_maps')
    (out/'contract.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    (out/'panels.json').write_text(json.dumps(cards, ensure_ascii=False, indent=2), encoding='utf8')
    (out/'platform_coverage.json').write_text(json.dumps(platforms, ensure_ascii=False, indent=2), encoding='utf8')
    (out/'native_cases.json').write_text(json.dumps(native_cases, ensure_ascii=False, indent=2), encoding='utf8')
    (out/'dependencies.json').write_text(json.dumps([{'position': q, 'state': s} for q,s in sorted(dependencies.items())], ensure_ascii=False), encoding='utf8')
    print({k: report[k] for k in ('platforms', 'new_panels', 'cells', 'total_boarding_mouths', 'covered_mouths')}, 'unresolved', len(unresolved), flush=True)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--world', type=Path, default=WORLD)
    p.add_argument('--out', type=Path); p.add_argument('--platform')
    args = p.parse_args(); main(args.world, args.out, args.platform)
