"""Build and check a single regional station in an immutable offline candidate.

The current HT miniature vehicle is explicitly two 9 m cars. No real save,
Simulator or native database is opened. Existing streets, devices, buildings,
water and all non-natural source blocks remain exact.
"""
import argparse, collections, copy, json, math, shutil
from pathlib import Path
import nbtlib
import numpy as np
from shapely.geometry import box, shape, Point, LineString
from shapely.ops import unary_union
from scipy.ndimage import label
from author_hakone_lakefront import Editor
from author_hakone_togendai import Station
from author_kamonomiya_station import ALLOWED, OPEN, voxel_box
from prepare_hakone_city_cross import packed
from plan_ashi_landscape_r54 import SOIL
from verify_hakone_network_candidate import PAVEMENT

Y = -77
ID = 'itabashi'
NAME = '箱根板橋駅'
CX, CZ = 3126, 799
STAIR = 'minecraft:stone_brick_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]'


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), 'utf8')


def solid_boxes(state):
    """Conservative collision bounds for the small exact authored palette."""
    if state.split('[')[0] in OPEN:
        return []
    if state == STAIR:
        return [[0, 0, 0, 1, .5, 1], [0, .5, 0, 1, 1, .5]]
    if 'slab[' in state and 'type=bottom' in state:
        return [[0, 0, 0, 1, .5, 1]]
    return [[0, 0, 0, 1, 1, 1]]


def public_network(e, rows):
    nodes, failures = {}, []
    for x, z, g in rows:
        y = (g + 1) // 2
        st = e.state(x, y, z)
        if st.split('[')[0] not in PAVEMENT | {'projectseele:station_tactile_warning'}:
            failures.append(['floor', x, y, z, st]); continue
        if ('type=bottom' in st) != (g % 2 != 0):
            failures.append(['grade', x, y, z, st]); continue
        if any(e.state(x, yy, z).split('[')[0] not in OPEN for yy in (y + 1, y + 2)):
            failures.append(['head', x, y, z]); continue
        nodes[x, g + 2, z] = 1
    return nodes, failures


def reach(nodes, start):
    parents = {start: None} if start in nodes else {}
    queue = collections.deque(parents)
    while queue:
        x, g, z = queue.popleft()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for dg in (-1, 0, 1):
                q = x + dx, g + dg, z + dz
                if q in nodes and q not in parents:
                    parents[q] = (x, g, z); queue.append(q)
    return parents


def author(a):
    a.out.mkdir(exist_ok=False)
    shutil.copytree(a.source / 'source', a.out / 'source')
    (a.out / 'delta').mkdir()
    for filename in ('capture.json', 'measured.npz', 'captured-devices.dat'):
        shutil.copy2(a.source / filename, a.out / filename)
    # This is the root-supplied offline copy, never the production native path.
    shutil.copytree(a.native, a.out / 'preserved-native')
    cap = json.loads((a.source / 'capture.json').read_text('utf8'))
    l, t, r, b = cap['bounds_xz']
    with np.load(a.authority / 'network.npz') as f:
        ax, az, _, _ = map(int, f['bounds']); oldwalk = f['walk']; oldgrade = f['grade2']
    with np.load(a.source / 'measured.npz') as f:
        ground = f['top'].copy()
    devices = {tuple(int(q[k]) for k in ('x', 'y', 'z')) for q in nbtlib.load(a.source / 'captured-devices.dat')['Devices']}
    site = json.loads(a.site.read_text('utf8'))
    water = unary_union([shape(q['geometry']) for q in site.get('nearby_water_interfaces', [])]).buffer(3)
    e = Editor(a.out); signs = Station(e); public = {}; owned = set(); parts = []

    def put(x, y, z, state):
        if not (l <= x <= r and t <= z <= b and -128 <= y <= 319):
            raise ValueError(('Unknown source', x, y, z))
        if e.state(x, y, z) == state:
            return
        before = e.state(x, y, z, True)
        if before.split('[')[0] not in ALLOWED or (x, y, z) in devices:
            raise ValueError(('Protected source', x, y, z, before))
        if oldwalk[z - az, x - ax]:
            raise ValueError(('Retained public column', x, y, z))
        # Only the explicitly designed high footbridge may occupy air above
        # the future channel. Its foundations remain outside the bank buffer.
        bridge_air = 3136 <= x <= 3140 and 732 <= z <= 746 and y >= -73
        if water.intersects(box(x, z, x + 1, z + 1)) and not bridge_air:
            raise ValueError(('Water buffer', x, y, z))
        e.put(x, y, z, state); owned.add((x, y, z))

    def fill(x, y, z, X, Y, Z, state):
        for px in range(x, X + 1):
            for pz in range(z, Z + 1):
                for py in range(y, Y + 1):
                    put(px, py, pz, state)

    def column(x, z, grade, declare=True):
        if oldwalk[z - az, x - ax]:
            if declare:
                public[x, z] = int(oldgrade[z - az, x - ax])
            return
        top = (grade + 1) // 2
        bottom = int(ground[z - t, x - l]) - 1
        if bottom < Y - 8 or bottom > top:
            raise ValueError(('Unreasonable bearing', x, z, bottom, top))
        for y in range(bottom, top):
            put(x, y, z, 'minecraft:stone_bricks')
        put(x, top, z, 'minecraft:smooth_stone' if grade % 2 == 0 else 'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]')
        for y in range(top + 1, top + 4):
            put(x, y, z, 'minecraft:air')
        if declare:
            public[x, z] = grade

    def floor(x, z, X, Z):
        for px in range(x, X + 1):
            for pz in range(z, Z + 1):
                column(px, pz, Y * 2)

    # The station keeps the cached non-JR corridor and requires a later graded
    # connection on either end; no parallel JR line is repurposed for HT.
    fill(3102, Y - 2, 798, 3150, Y - 2, 801, 'minecraft:stone')
    fill(3102, Y - 1, 798, 3150, Y - 1, 801, 'minecraft:gravel')
    fill(3097, Y, 798, 3155, Y + 5, 801, 'minecraft:air')
    floor(3101, 790, 3151, 797)
    fill(3101, Y, 797, 3151, Y, 797, 'projectseele:station_tactile_warning')
    # Hall and forecourt sit north of the through track. Passengers never cross
    # the railway at grade; the sole platform connects directly to the hall.
    floor(3130, 764, 3146, 784)
    floor(3135, 785, 3141, 789)
    floor(3133, 759, 3143, 763)
    for zz in (764, 784):
        fill(3130, Y + 1, zz, 3146, Y + 4, zz, 'minecraft:light_gray_concrete')
    for xx in (3130, 3146):
        fill(xx, Y + 1, 764, xx, Y + 4, 784, 'minecraft:light_gray_concrete')
    for zz in (764, 784):
        for xx in (3131, 3142):
            fill(xx, Y + 2, zz, xx + 3, Y + 3, zz, 'minecraft:light_gray_stained_glass')
        fill(3136, Y + 1, zz, 3140, Y + 3, zz, 'minecraft:air')
    for xx in (3130, 3146):
        for zz in (768, 776):
            fill(xx, Y + 2, zz, xx, Y + 3, zz + 4, 'minecraft:light_gray_stained_glass')
    fill(3129, Y + 5, 763, 3147, Y + 5, 785, 'minecraft:gray_concrete')
    fill(3130, Y + 6, 764, 3146, Y + 6, 784, 'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]')
    fill(3131, Y + 1, 769, 3133, Y + 1, 771, 'minecraft:smooth_quartz')
    for xx in (3134, 3142):
        for zz in (768, 780):
            put(xx, Y + 4, zz, 'minecraft:sea_lantern')
    # Canopy piers are 6.5 m from the running centre. Every canopy component
    # has grounded piers; no decorative posts are left floating.
    fill(3100, Y + 6, 789, 3152, Y + 6, 797, 'minecraft:light_gray_concrete')
    fill(3101, Y + 7, 790, 3151, Y + 7, 795, 'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]')
    for xx in (3102, 3114, 3126, 3138, 3150):
        fill(xx, Y + 1, 790, xx, Y + 5, 790, 'minecraft:dark_oak_log[axis=y]')
        fill(xx, Y + 5, 790, xx, Y + 5, 796, 'minecraft:dark_oak_log[axis=z]')
        put(xx + 1, Y + 5, 794, 'minecraft:sea_lantern')
    # One grounded continuous rear edge; openings align to the hall path.
    for xx in range(3101, 3152):
        if not 3135 <= xx <= 3141 and xx not in (3102, 3114, 3126, 3138, 3150):
            put(xx, Y + 1, 790, 'minecraft:light_gray_stained_glass')
    for xx in (3107, 3119, 3146):
        for px in range(xx, xx + 3):
            put(px, Y + 1, 792, 'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]')
    # The cached drain separates the north street from the station. Keep its
    # present soil and future 3 m bank buffer untouched, and span it in air.
    # Deck underside -73 is four metres above conservative future water -77.
    route = [(3138, z) for z in range(762, 732, -1)] + [(x, 733) for x in range(3139, 3166)]
    ramps = []
    for zz in range(746, 763):
        grade = Y * 2 + min(8, (762 - zz) // 2)
        for xx in range(3137, 3140):
            column(xx, zz, grade)
        if zz < 760:
            for xx in (3136, 3140):
                column(xx, zz, grade, False)
                put(xx, (grade + 1) // 2 + 1, zz, 'minecraft:light_gray_stained_glass')
        ramps.append([3138, zz, grade])
    for xx in range(3138, 3167):
        grade = -146 - min(6, max(0, (xx - 3141) // 3))
        for zz in range(732, 735):
            column(xx, zz, grade)
        if 3141 <= xx <= 3158:
            for zz in (731, 735):
                column(xx, zz, grade, False)
                put(xx, (grade + 1) // 2 + 1, zz, 'minecraft:light_gray_stained_glass')
        ramps.append([xx, 733, grade])
    # Grounded bridge abutments at both measured banks; they do not intrude
    # into any cached water polygon or its three-metre protected strip.
    for zz in (734, 744):
        for xx in range(3136, 3141):
            if water.intersects(box(xx, zz, xx + 1, zz + 1)):
                raise ValueError(('Footbridge support in protected bank', xx, zz))
            fill(xx, -79, zz, xx, -74, zz, 'minecraft:stone_bricks')
    fill(3136, -73, 732, 3140, -73, 746, 'minecraft:gray_concrete')
    for zz in range(732, 747):
        for xx in range(3137, 3140):
            put(xx, -73, zz, 'minecraft:smooth_stone'); public[xx, zz] = -146
        for xx in (3136, 3140):
            if xx == 3140 and zz <= 734: continue  # north landing turns east
            put(xx, -72, zz, 'minecraft:light_gray_stained_glass')
    for zz in range(732, 735):
        put(3140, -73, zz, 'minecraft:smooth_stone'); public[3140, zz] = -146
    for xx in range(3136, 3140):
        put(xx, -72, 731, 'minecraft:light_gray_stained_glass')
        put(xx, -73, 731, 'minecraft:gray_concrete')
    expected_signs = [
        (3138, Y + 4, 763, 'north', [NAME, 'HAKONE-ITABASHI', '箱根登山線', '入口 / 改札']),
        (3134, Y + 3, 770, 'east', [NAME, 'きっぷ / Tickets', '小田原・箱根湯本', '1 番線']),
        (3126, Y + 4, 795, 'south', [NAME, 'HAKONE-ITABASHI', '箱根湯本 ← → 小田原', '1 番線'])]
    backing = {'north': (0, 1), 'south': (0, -1), 'east': (-1, 0), 'west': (1, 0)}
    for i, (x, y, z, facing, words) in enumerate(expected_signs):
        dx, dz = backing[facing]
        put(x + dx, y, z + dz, 'minecraft:gray_concrete')
        if i == 1:
            for yy in range(Y + 2, y):
                put(x + dx, yy, z + dz, 'minecraft:gray_concrete')
        else:
            for yy in range(y + 1, Y + 6):
                put(x + dx, yy, z + dz, 'minecraft:chain[axis=y,waterlogged=false]')
        # Check the exact sign cell before the payload helper writes it.
        put(x, y, z, 'minecraft:oak_wall_sign[facing=' + facing + ',waterlogged=false]')
        signs.sign(x, y, z, words, facing)
    rows = []
    for (x, z), g in sorted(public.items()):
        y = (g + 1) // 2
        if all(e.state(x, yy, z).split('[')[0] in OPEN for yy in (y + 1, y + 2)):
            rows.append([x, z, g])
    goals = dict(street=[3165, -75, 733], forecourt=[3135, -76, 760],
                 entrance=[3138, -76, 765], ticket=[3135, -76, 770], hall=[3138, -76, 776],
                 bridge=[3138, -72, 739], south_ramp=[3138, -75, 758], north_ramp=[3150, -73.5, 733],
                 platform_west=[3103, -76, 796], platform_centre=[3126, -76, 796],
                 platform_east=[3149, -76, 796])
    regions = e.save(); e.regions.clear()
    payload = [nbtlib.Compound({'Pos': nbtlib.Long(packed(tuple(int(d['After'][k]) for k in ('x', 'y', 'z')))),
                               'After': copy.deepcopy(d['After'])}) for d in signs.devices]
    nbtlib.File({'Changes': nbtlib.List[nbtlib.Compound](payload)}).save(a.out / 'block-entities.dat', gzipped=True)
    bounds = [min(p[i] for p in owned) for i in range(3)] + [max(p[i] for p in owned) for i in range(3)]
    native = dict(rails=[dict(id=ID + '-platform-1', **{'from': [3102, Y, CZ], 'to': [3150, Y, CZ]},
                             from_angle='E', to_angle='W', shape='QUADRATIC', vertical_radius=40,
                             mode='TRAIN', kind='platform', platform_name='1')],
                  stations=[dict(id=ID, name=NAME, min=[3099, -81, 731], max=[3168, -68, 803], color=0x35875C)], lines=[])
    for filename in ('native-input.json', 'native-samples.json'):
        shutil.copy2(a.math / filename, a.out / filename)
    shutil.copytree(a.model, a.out / 'vehicle-model')
    access = [q for q in rows if q[1] < 790 and q[2] / 2 <= int(ground[q[1] - t, q[0] - l]) + 1]
    design = dict(station=NAME, station_id=ID, parts=[dict(kind='side platform, north hall and street link', bounds=bounds)],
                  public_columns=rows, ground_access_columns=access, ground_access_format=['x', 'z', 'grade2'],
                  station_multi_level_nodes=[[x, g, z] for x, z, g in rows], station_multi_level_node_format=['x', 'grade2', 'z'],
                  network_single_grade2_update_scope='ground_access_columns only', goals=goals, retained_street_anchor=goals['street'],
                  expected_signs=[dict(pos=[x, y, z], facing=f, title=words[0]) for x, y, z, f, words in expected_signs],
                  source_authority=str(a.authority), source_native=str(a.native), native_math_samples='native-samples.json',
                  reference_centre=site['reference']['track_centre_xz'], reference_axis_degrees=site['axis_degrees'],
                  geographic_adaptation=True, native_axis_degrees=0, centre=[3126.5, Y, 799.5],
                  platform_length=48, physical_platform_bounds=[3101, Y, 790, 3151, Y, 797],
                  continuous_boarding_interval=[3102.5, 3150.5], boarding_edge_z=798,
                  vehicle='e44_mini_cab_3', route='HT', consist=dict(cars=2, native_car_length=9, native_total_length=18,
                       visible_car_length=9.25, visible_consist_span=18.25, metadata_width_not_used_for_clearance=True),
                  local_capacity_claim_only=True, planned_maximum_consist_length=18,
                  actual_visible_halfwidth=1.3125, doorway_trigger_halfwidth=1.5,
                  required_horizontal_margin=.15, required_longitudinal_margin=.15, required_vertical_margin=.03,
                  visible_closed_boarding_gap=.1875, clearance_after_horizontal_margin=.0375,
                  no_at_grade_passenger_crossing=True, street_route=route, ramp_centreline_grades=ramps,
                  footbridge=dict(deck_bounds=[3136, -73, 732, 3140, -73, 746], usable_width=3,
                                  abutment_rows=[734, 744], source_ground_y=-78, reserved_future_water_surface_y=-77,
                                  minimum_deck_underside_above_reserved_water=4, waterway_already_built=False,
                                  source_terrain_and_three_metre_bank_buffer_preserved=True),
                  step_free_claim='Minecraft no-jump half-slab access; no real wheelchair compliance claim',
                  physical_scope_complete=False, model_reconciliation_pending=True, through_service_complete=False,
                  native_registry_pending=True, production_replay_pending=True, world_written=False)
    dump(a.out / 'native-station-plan.json', native)
    dump(a.out / 'authoring-plan.json', dict(id=ID, name=NAME, origin=[3126,Y,799],rotation=0,
         reference_centre=site['reference']['track_centre_xz'], reference_axis_degrees=site['axis_degrees'],
         independent_layout_author='author_itabashi_station.py',street_anchor=goals['street']))
    dump(a.out / 'station-design.json', design)
    dump(a.out / 'manifest.json', dict(world=cap['world'], kind='measured-regional-station', bounds_xz=cap['bounds_xz'],
                                     regions=regions, cells=sum(q['cells'] for q in regions), station_design='station-design.json',
                                     native_station_pending=True, world_written=False))
    print('Prepared Itabashi:', sum(q['cells'] for q in regions), 'cells;', len(rows), 'public columns; candidate only', flush=True)


def verify(candidate, authority):
    e = Editor(candidate); d = json.loads((candidate / 'station-design.json').read_text('utf8'))
    m = json.loads((candidate / 'manifest.json').read_text('utf8')); bounds = d['parts'][0]['bounds']
    with np.load(authority / 'network.npz') as f:
        ax, az, _, _ = map(int, f['bounds']); oldwalk = f['walk']
    devices = {tuple(int(q[k]) for k in ('x', 'y', 'z')) for q in nbtlib.load(candidate / 'captured-devices.dat')['Devices']}
    errors = []; bad = []; changed = []; counts = collections.Counter()
    for file in (candidate / 'source').glob('*.npz'):
        rx, rz = map(int, file.stem.split('.')[1:]); r = e.region(rx * 512, rz * 512)
        for (cx, cz), before, after in zip(r['coords'], r['before'], r['after']):
            for iy, iz, ix in np.argwhere(before != after):
                x, y, z = int(cx) * 16 + int(ix), int(iy) - 128, int(cz) * 16 + int(iz)
                st = r['names'][int(before[iy, iz, ix])]; counts['cells'] += 1
                changed.append((x, y, z, r['names'][int(after[iy, iz, ix])]))
                if st.split('[')[0] not in ALLOWED:
                    counts['protected'] += 1; bad.append([x, y, z, st])
                if oldwalk[z - az, x - ax]: counts['old_public'] += 1
                if (x, y, z) in devices: counts['old_devices'] += 1
                if not all(bounds[i] <= (x, y, z)[i] <= bounds[i + 3] for i in range(3)): counts['outside'] += 1
    for name, message in [('protected', 'protected original block changed'), ('old_public', 'old public column changed'),
                          ('old_devices', 'old device changed'), ('outside', 'outside declared station volume')]:
        if counts[name]: errors.append(message)
    if counts['cells'] != m['cells']: errors.append('cell count mismatch')
    nodes, floor_failures = public_network(e, d['public_columns'])
    street = d['retained_street_anchor']; start = street[0], round(street[1] * 2), street[2]
    parents = reach(nodes, start); goals = []
    for name, q in d['goals'].items():
        p = q[0], round(q[1] * 2), q[2]; route = []
        while p in parents:
            route.append([p[0] + .5, p[1] / 2, p[2] + .5]); p = parents[p]
            if p is None: break
        route.reverse(); goals.append(dict(name=name, reachable=bool(route), route=route))
        if not route: errors.append('unreachable goal ' + name)
    if floor_failures: errors.append('public floor or headroom invalid')
    unreachable = [list(q) for q in nodes if q not in parents]
    if unreachable: errors.append('public surfaces disconnected')
    # Full-length platform aisle: independently derive all 49 rail-span edge
    # columns and require at least three continuous walkable columns behind it.
    edge = []
    for x in range(3102, 3151):
        width = 0
        for z in range(797, 789, -1):
            if (x, Y * 2 + 2, z) not in parents: break
            width += 1
        edge.append(dict(x=x, contiguous_aisle_width=width, visible_gap=799.5 - 798 - 1.3125))
    if min(q['contiguous_aisle_width'] for q in edge) < 3: errors.append('platform edge aisle is discontinuous')
    # Six-face support of every new solid, rooted in measured lower source.
    crop = [bounds[0] - 1, -86, bounds[2] - 1, bounds[3] + 1, bounds[4] + 1, bounds[5] + 1]
    data, palette = voxel_box(e, crop); solids = np.asarray([p.split('[')[0] not in OPEN for p in palette])[data]
    labels, count = label(solids); roots = set(map(int, np.unique(labels[0]))); floating = []
    for x, y, z, st in changed:
        if st.split('[')[0] in OPEN: continue
        if not all(crop[i] <= (x, y, z)[i] <= crop[i + 3] for i in range(3)): continue
        if int(labels[y - crop[1], z - crop[2], x - crop[0]]) not in roots: floating.append([x, y, z])
    if floating: errors.append('new solid component lacks ground support')
    sign_errors = []; tags = nbtlib.load(candidate / 'block-entities.dat')['Changes']
    expected = {tuple(q['pos']): q for q in d['expected_signs']}
    if len(tags) != len(expected): sign_errors.append('payload count')
    backing = {'north': (0, 1), 'south': (0, -1), 'east': (-1, 0), 'west': (1, 0)}
    for q in tags:
        if 'After' not in q: sign_errors.append('missing After payload'); continue
        t = q['After']; p = tuple(int(t[k]) for k in ('x', 'y', 'z'))
        if p not in expected or p in devices or 'Before' in q: sign_errors.append('unexpected sign location'); continue
        row = expected[p]; facing = row['facing']; dx, dz = backing[facing]
        st = e.state(*p)
        if 'wall_sign' not in st or 'facing=' + facing not in st: sign_errors.append('state mismatch')
        if e.state(p[0] + dx, p[1], p[2] + dz).split('[')[0] in OPEN: sign_errors.append('missing backing')
        if NAME not in str(t): sign_errors.append('station title missing')
    if sign_errors: errors.append('sign payload or backing invalid')
    proof = dict(errors=errors, cells=counts['cells'], protected_original_changes=counts['protected'],
                 old_public_changes=counts['old_public'], old_devices_changed=counts['old_devices'],
                 nodes=len(nodes), reachable_nodes=len(parents), unreachable=unreachable[:40],
                 floor_failures=floor_failures[:40], floating_new_solids=floating[:40], sign_errors=sign_errors,
                 goals=goals, full_length_edge=edge, minimum_boarding_aisle_width=min(q['contiguous_aisle_width'] for q in edge),
                 native_registry_pending=True, all_line_vehicle_sweep_complete=False, world_written=False)
    dump(candidate / 'offline-verification.json', proof)
    print('Itabashi structural checks:', len(errors), 'errors;', len(parents), '/', len(nodes), 'reachable', flush=True)
    if errors: raise ValueError(errors)
    return proof


if __name__ == '__main__':
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--verify', action='store_true')
    for key in ('source', 'authority', 'site', 'native', 'math', 'model', 'out'):
        p.add_argument('--' + key, type=Path)
    a = p.parse_args()
    if a.verify: verify(a.out, a.authority)
    else: author(a)
