"""Write individual blocks directly into a stopped world's chunk sections, at any height.

The map patch pipeline covers y -128..319; the GeoFront cavern lies far below that. Each
touched region file is copied to the output folder first, each cell's prior state is
checked, and the rewritten chunks are compared with those copies: every planned cell must
hold its new state and no other block may differ.
Rows: [x, y, z, before, after] with block states written as name[prop=value,...], optionally a sixth item
giving the new block its block entity: {"id": "trafficcraft:colored_block_entity", "color": n} for road paint, or
{"id": "mtr:<block>", "snbt": "{...}"} for an MTR station fitting (PIDS boards, station name signs) with its data, or
{"id": "movingelevators:elevator_tile|button_tile|display_tile", "snbt": "{...}"} for a lift controller or cabin panel, or
{"id": "projectseele:nerv_staff_gate", "snbt": "{}"} for the lower half of a NERV staff gate lane.
"""
import argparse
from collections import Counter, defaultdict
import io
import json
import math
import os
from pathlib import Path
import shutil
import zlib

import nbtlib
import numpy as np

from install_r53_carrier_trays import stopped_world

REGION = 'dimensions/projectseele/geofront/region'
# R65 item 42: the old glass stair shaft (x -191..-175, z 81..97) and two floating slabs stand partly in city lift
# spaces (original96/66 lowered, raised and hatch; original96/2 raised). Inside those spaces these boxes may only be
# cleared, and only from these blocks (--item42-city-lift-obstructions).
CITY_LIFT_OBSTRUCTIONS = (((-179, -175), (-8, 85), (91, 97)), ((-162, -142), (82, 83), (80, 107)),
                          ((-144, -120), (83, 84), (129, 155)))
CITY_LIFT_OBSTRUCTION_BLOCKS = {'minecraft:' + n for n in ('light_gray_concrete', 'gray_stained_glass', 'polished_deepslate',
                                                          'iron_bars', 'smooth_stone', 'oak_stairs', 'stone_brick_stairs')}


def city_lift_obstruction(x, y, z):
    return any(xa <= x <= xb and ya <= y <= yb and za <= z <= zb for (xa, xb), (ya, yb), (za, zb) in CITY_LIFT_OBSTRUCTIONS)


# Moving Elevators block entity -> its block. A lift's controllers, in-cabin button and display carry their links here.
MOVING_ELEVATOR_ENTITIES = {'movingelevators:elevator_tile': 'movingelevators:elevator_block',
                            'movingelevators:button_tile': 'movingelevators:button_block',
                            'movingelevators:display_tile': 'movingelevators:display_block'}


def state_name(entry):
    name = str(entry['Name'])
    props = entry.get('Properties')
    if not props:
        return name
    return name + '[' + ','.join(f'{k}={props[k]}' for k in sorted(props)) + ']'


def state_entry(state):
    name, _, rest = state.partition('[')
    entry = nbtlib.Compound({'Name': nbtlib.String(name)})
    if rest:
        entry['Properties'] = nbtlib.Compound({k: nbtlib.String(v) for k, v in (p.split('=') for p in rest[:-1].split(','))})
    return entry


def bits_for(count):
    if count > 256:
        raise ValueError('Palette too large for a section palette')
    return max(4, math.ceil(math.log2(count)))


def decode(states):
    """Section block ids as a flat array of 4096, and the palette as state strings."""
    palette = [state_name(p) for p in states['palette']]
    data = states.get('data')
    if data is None or len(palette) == 1:
        return np.zeros(4096, np.int64), palette
    bits = bits_for(len(palette))
    per = 64 // bits
    words = np.array(data, dtype=np.int64).astype(np.uint64)
    at = np.arange(4096)
    return ((words[at // per] >> ((at % per) * bits).astype(np.uint64)) & np.uint64((1 << bits) - 1)).astype(np.int64), palette


def encode(states, ids, palette):
    used, packed = np.unique(ids, return_inverse=True)
    names = [palette[i] for i in used.tolist()]
    states['palette'] = nbtlib.List[nbtlib.Compound]([state_entry(s) for s in names])
    if len(names) == 1:
        if 'data' in states:
            del states['data']
        return
    bits = bits_for(len(names))
    per = 64 // bits
    at = np.arange(4096)
    words = np.zeros(math.ceil(4096 / per), np.uint64)
    np.bitwise_or.at(words, at // per, packed.astype(np.uint64) << ((at % per) * bits).astype(np.uint64))
    states['data'] = nbtlib.LongArray(words.astype(np.int64))


def read_chunk(buf, cx, cz):
    i = 4 * ((cx & 31) + (cz & 31) * 32)
    loc, count = int.from_bytes(buf[i:i + 3], 'big'), buf[i + 3]
    if not loc:
        raise ValueError(f'Chunk {cx},{cz} is not generated')
    length = int.from_bytes(buf[loc * 4096:loc * 4096 + 4], 'big')
    if buf[loc * 4096 + 4] != 2:
        raise ValueError(f'Chunk {cx},{cz} is not zlib compressed')
    return i, loc, count, nbtlib.File.parse(io.BytesIO(zlib.decompress(bytes(buf[loc * 4096 + 5:loc * 4096 + 4 + length]))))


def write_chunk(buf, i, loc, count, root):
    raw = io.BytesIO()
    root.write(raw)
    data = zlib.compress(raw.getvalue())
    payload = (len(data) + 1).to_bytes(4, 'big') + b'\x02' + data
    payload += bytes(-len(payload) % 4096)
    need = len(payload) // 4096
    if need <= count:
        buf[loc * 4096:(loc + count) * 4096] = payload + bytes((count - need) * 4096)
    else:
        if len(buf) % 4096:
            buf.extend(bytes(-len(buf) % 4096))
        loc = len(buf) // 4096
        buf.extend(payload)
    buf[i:i + 3] = loc.to_bytes(3, 'big')
    buf[i + 3] = need


def clear_light(root):
    """Drop every stored light value so the game, with Starlight, relights the chunk when it loads."""
    for holder in (root, *root['sections']):
        for key in [k for k in holder if k in ('SkyLight', 'BlockLight') or k.startswith('starlight.')]:
            del holder[key]
    root['isLightOn'] = nbtlib.Byte(0)


def split_rows(rows, folder, limit=300000):
    """Write rows as batch-NNN.json files of at most limit cells, whole chunks at a time, by region."""
    chunks = defaultdict(list)
    for row in rows:
        chunks[row[0] >> 4, row[2] >> 4].append(row)
    batches, current = [], []
    for key in sorted(chunks, key=lambda c: (c[0] >> 5, c[1] >> 5, c)):
        if current and len(current) + len(chunks[key]) > limit:
            batches.append(current)
            current = []
        current += chunks[key]
    if current:
        batches.append(current)
    for number, batch in enumerate(batches):
        (Path(folder) / f'batch-{number:03d}.json').write_text(json.dumps(batch), 'utf8')
    return [len(batch) for batch in batches]


def sign_text(lines):
    """Four sign lines as the 1.20 text component strings."""
    lines = list(lines) + [''] * (4 - len(lines))
    if len(lines) != 4:
        raise ValueError('A sign side holds four lines')
    return nbtlib.List[nbtlib.String]([nbtlib.String(json.dumps({'text': t}, ensure_ascii=False)) for t in lines])


def sign_entity(sign, state):
    x, y, z = sign['pos']
    side = lambda key: nbtlib.Compound({'messages': sign_text(sign.get(key, [])), 'color': nbtlib.String(sign.get('color', 'black')),
                                        'has_glowing_text': nbtlib.Byte(1 if sign.get('glow') else 0)})
    return nbtlib.Compound({'id': nbtlib.String('minecraft:hanging_sign' if 'hanging_sign' in state else 'minecraft:sign'),
                            'x': nbtlib.Int(x), 'y': nbtlib.Int(y), 'z': nbtlib.Int(z), 'keepPacked': nbtlib.Byte(0),
                            'is_waxed': nbtlib.Byte(1), 'front_text': side('front'), 'back_text': side('back')})


def campfire_entity(x, y, z):
    """An empty lit campfire's block entity; without it the client never runs the campfire's particle tick, so no smoke."""
    zero = nbtlib.IntArray([0, 0, 0, 0])
    return nbtlib.Compound({'id': nbtlib.String('minecraft:campfire'), 'x': nbtlib.Int(x), 'y': nbtlib.Int(y), 'z': nbtlib.Int(z),
                            'keepPacked': nbtlib.Byte(0), 'Items': nbtlib.List[nbtlib.Compound](), 'CookingTimes': zero,
                            'CookingTotalTimes': nbtlib.IntArray([0, 0, 0, 0])})


def block_at(root, x, y, z):
    for s in root['sections']:
        if int(s['Y']) == y >> 4 and 'block_states' in s:
            ids, palette = decode(s['block_states'])
            return palette[ids[((y & 15) << 8) | ((z & 15) << 4) | (x & 15)]]
    return 'minecraft:air'


def preflight(folder, grouped, allow_block_entities):
    """Check every row before anything is written: prior state, and no block entity under a row unless allowed."""
    problems = []
    for (rx, rz), chunks in sorted(grouped.items()):
        buf = (folder / f'r.{rx}.{rz}.mca').read_bytes()
        for (cx, cz), cells in chunks.items():
            root = read_chunk(buf, cx, cz)[3]
            entities = {(int(e['x']), int(e['y']), int(e['z'])): str(e['id']) for e in root.get('block_entities', [])}
            decoded = {}
            for s in root['sections']:
                if 'block_states' in s:
                    decoded[int(s['Y'])] = decode(s['block_states'])
            for x, y, z, before, _ in cells:
                if y >> 4 not in decoded:
                    problems.append(f'{x},{y},{z}: section {y >> 4} missing')
                    continue
                ids, palette = decoded[y >> 4]
                state = palette[ids[((y & 15) << 8) | ((z & 15) << 4) | (x & 15)]]
                if state != before:
                    problems.append(f'{x},{y},{z} is {state}, expected {before}')
                if (x, y, z) in entities and not allow_block_entities:
                    problems.append(f'{x},{y},{z} holds a {entities[x, y, z]} block entity')
    if problems:
        raise SystemExit(f'Preflight refused {len(problems)} rows, nothing written:\n' + '\n'.join(problems[:20]))


# Project block entities a row may give (the block's own state machine, no data needed): the NERV staff gate's lower
# half ticks its lane from its block entity, so a gate written without one would never open.
PROJECT_ENTITIES = {'projectseele:nerv_staff_gate'}


def apply(a):
    rows = json.loads(a.rows.read_text('utf8'))
    # A row may carry a sixth item, the block entity to give the new block: TrafficCraft paint or an MTR fitting.
    given = {(r[0], r[1], r[2]): r[5] for r in rows if len(r) > 5 and r[5]}
    for pos, e in given.items():
        if e.get('id') == 'trafficcraft:colored_block_entity':
            continue
        eid = str(e.get('id', ''))
        if not ((eid.startswith('mtr:') or eid in MOVING_ELEVATOR_ENTITIES or eid in PROJECT_ENTITIES) and isinstance(e.get('snbt'), str)):
            raise SystemExit(f'{pos}: only trafficcraft:colored_block_entity, an mtr: entity, a Moving Elevators entity or '
                             f'{sorted(PROJECT_ENTITIES)} with snbt can be given, not {e.get("id")}')
        row = next(r for r in rows if (r[0], r[1], r[2]) == pos)
        if row[4].split('[')[0] != MOVING_ELEVATOR_ENTITIES.get(eid, eid):
            raise SystemExit(f'{pos}: entity {e["id"]} given for block {row[4]}')
        nbtlib.parse_nbt(e['snbt'])                     # refuse a malformed entity before anything is touched
    rows = [r[:5] for r in rows]
    signs = json.loads(a.signs.read_text('utf8')) if a.signs else []
    # A cell listed twice passes the preflight (both rows match the old world) and then fails halfway through the
    # write, after some region files were already replaced. Refuse it before anything is touched.
    for label, cells in (('rows', [(x, y, z) for x, y, z, _, _ in rows]), ('signs', [tuple(s['pos']) for s in signs])):
        repeated = sorted(pos for pos, n in Counter(cells).items() if n > 1)
        if repeated:
            raise SystemExit(f'{len(repeated)} cells appear more than once in the {label}, nothing written: '
                             + ', '.join(map(str, repeated[:20])))
    grouped = defaultdict(lambda: defaultdict(list))
    for x, y, z, before, after in rows:
        grouped[x >> 9, z >> 9][x >> 4, z >> 4].append((x, y, z, before, after))
    sign_chunks = defaultdict(list)
    for sign in signs:
        x, y, z = sign['pos']
        sign_chunks[x >> 4, z >> 4].append(sign)
        grouped[x >> 9, z >> 9][x >> 4, z >> 4]       # the chunk is visited even without block rows
    positions = [(x, y, z) for x, y, z, _, _ in rows] + [tuple(sign['pos']) for sign in signs]
    if not a.allow_city_lift:
        # The city lift compares its hatch cover and needs its travel space empty: refuse before any change.
        from map_pipeline.city_protection import load as city_protection
        city = city_protection(a.world)
        checked = positions
        if a.item42_city_lift_obstructions:
            # The old glass stair shaft and two floating slabs in city lift spaces: only their cells, only cleared.
            inside = city.inside(positions)
            for x, y, z, before, after in rows:
                if (x, y, z) not in inside:
                    continue
                if not city_lift_obstruction(x, y, z) or before.split('[')[0] not in CITY_LIFT_OBSTRUCTION_BLOCKS or after != 'minecraft:air':
                    raise SystemExit(f'{(x, y, z)}: inside the city lift space and not an old shaft or scrap cell cleared to air ({before} -> {after})')
            if any(tuple(sign['pos']) in inside for sign in signs):
                raise SystemExit('a sign inside the city lift space')
            checked = [p for p in positions if p not in inside]
        city.assert_positions(checked)
    if not a.allow_lift_shaft:
        # A buried shaft is how a lift stops reaching a floor; doors and controllers count too.
        from map_pipeline.lift_protection import load as lift_protection
        lift_protection(a.world).assert_positions(positions)
    from map_pipeline.launch_protection import load as launch_protection
    launch = launch_protection(a.world, allow_air_shaft=a.allow_air_shaft)
    if a.allow_launch_repaint:
        # Launch tunnel walls lie inside the launch space volumes. A repaint may change their colour only: wall block
        # to wall block, never air, a hatch seal or a guide rail anchor (whose exact state the rail renderer checks).
        from plan_launch_tunnel_skin import anchors as rail_anchors, PAINTABLE
        inside = launch.inside(positions)
        anchor_cells = rail_anchors(a.world)
        allowed = PAINTABLE | {'projectseele:nerv_strip_light', 'projectseele:nerv_machine_edge'}
        for x, y, z, before, after in rows:
            if (x, y, z) not in inside:
                continue
            if (x, y, z) in anchor_cells:
                raise SystemExit(f'{(x, y, z)}: guide rail anchor in the launch space, never repainted')
            if before.split('[')[0] not in allowed or after.split('[')[0] not in allowed:
                raise SystemExit(f'{(x, y, z)}: launch space repaint must stay wall block to wall block ({before} -> {after})')
        positions = [p for p in positions if p not in inside]
    if getattr(a, 'bank2_exterior', False):
        from plan_r64_silo_exterior import on_facade, BLACK
        from query_blocks import AIR
        if signs or given or any(before not in AIR or after != BLACK or not on_facade(x,y,z)
                                 for x,y,z,before,after in rows):
            raise ValueError('This operation only adds exterior black cladding on the surveyed launch bank')
        # The broad 32-block route reservations include the outside of the
        # solid casing. All rows above are strictly on its four outside faces.
        positions = []
    if getattr(a, 'dogma_hall_doorway', False):
        # The one approved opening in the hangar hall (inside the launch reservation): only cells of the declared
        # doorway, only opened, never a mechanical cell. Every other row is checked as usual below.
        from plan_r66_dogma_doorway import in_doorway
        from query_blocks import AIR
        mechanical = {tuple(box[:3]) for name, box in launch.boxes if name == 'mechanical-cell'}
        inside = launch.inside(positions)
        for x, y, z, before, after in rows:
            if (x, y, z) not in inside:
                continue
            if not in_doorway(x, y, z) or after not in AIR or before in AIR or (x, y, z) in mechanical:
                raise SystemExit(f'{(x, y, z)}: inside the launch reservation and not an opening of the declared hall doorway ({before} -> {after})')
        positions = [p for p in positions if p not in inside]
    launch.assert_positions(positions)
    folder = a.world / REGION
    if given:
        # Rows that bring their own paint replace marked blocks; any other replaced block entity goes with its block.
        a.allow_block_entities = True
    preflight(folder, grouped, a.allow_block_entities)
    a.out.mkdir(parents=True, exist_ok=False)
    changed = 0
    dropped = set()
    written_entities = 0
    with stopped_world(a.world):
        for (rx, rz), chunks in sorted(grouped.items()):
            path = folder / f'r.{rx}.{rz}.mca'
            shutil.copy2(path, a.out / path.name)
            buf = bytearray(path.read_bytes())
            for (cx, cz), cells in chunks.items():
                i, loc, count, root = read_chunk(buf, cx, cz)
                sections = {int(s['Y']): s for s in root['sections']}
                by_section = defaultdict(list)
                for cell in cells:
                    by_section[cell[1] >> 4].append(cell)
                for sy, part in by_section.items():
                    if sy not in sections:
                        raise ValueError(f'Section {sy} missing in chunk {cx},{cz}')
                    if 'block_states' not in sections[sy]:
                        raise ValueError(f'Section {sy} in chunk {cx},{cz} holds no blocks')
                    states = sections[sy]['block_states']
                    ids, palette = decode(states)
                    index = {s: n for n, s in enumerate(palette)}
                    for x, y, z, before, after in part:
                        at = ((y & 15) << 8) | ((z & 15) << 4) | (x & 15)
                        if palette[ids[at]] != before:
                            raise ValueError(f'{x},{y},{z} is {palette[ids[at]]}, expected {before}')
                        if after not in index:
                            index[after] = len(palette)
                            palette.append(after)
                        ids[at] = index[after]
                        changed += 1
                    encode(states, ids, palette)
                if a.allow_block_entities:
                    # a replaced block takes its block entity with it (chest, sign, machine data)
                    gone = {(x, y, z) for x, y, z, before, after in cells if before.split('[')[0] != after.split('[')[0]}
                    entities = root.get('block_entities')
                    for e in list(entities or ()):
                        pos = (int(e['x']), int(e['y']), int(e['z']))
                        if pos in gone:
                            entities.remove(e)
                            dropped.add(pos)
                mine = [(x, y, z) for x, y, z, _, _ in cells if (x, y, z) in given]
                if mine:
                    entities = root.get('block_entities')
                    if entities is None or not len(entities):
                        root['block_entities'] = entities = nbtlib.List[nbtlib.Compound]()
                    for e in list(entities):
                        if (int(e['x']), int(e['y']), int(e['z'])) in given:
                            entities.remove(e)
                    for (x, y, z) in mine:
                        e = given[x, y, z]
                        if 'snbt' in e:
                            entity = nbtlib.parse_nbt(e['snbt'])
                            entity.update({'id': nbtlib.String(e['id']), 'x': nbtlib.Int(x), 'y': nbtlib.Int(y), 'z': nbtlib.Int(z),
                                           'keepPacked': nbtlib.Byte(0)})
                        else:
                            entity = nbtlib.Compound({'id': nbtlib.String(e['id']), 'x': nbtlib.Int(x), 'y': nbtlib.Int(y), 'z': nbtlib.Int(z),
                                                      'color': nbtlib.Int(int(e['color'])), 'keepPacked': nbtlib.Byte(0)})
                        entities.append(entity)
                        written_entities += 1
                for sign in sign_chunks.get((cx, cz), ()):
                    x, y, z = sign['pos']
                    state = block_at(root, x, y, z)
                    if not state.split('[')[0].endswith('sign'):
                        raise ValueError(f'{x},{y},{z} is {state}, not a sign')
                    entities = root.get('block_entities')
                    if entities is None or not len(entities):
                        # An empty list is saved with an End element type and refuses compounds.
                        root['block_entities'] = entities = nbtlib.List[nbtlib.Compound]()
                    for e in list(entities):
                        if (int(e['x']), int(e['y']), int(e['z'])) == (x, y, z):
                            if not str(e['id']).endswith('sign'):
                                raise ValueError(f'{x},{y},{z} holds a {e["id"]} block entity')
                            entities.remove(e)
                    entities.append(sign_entity(sign, state))
                if a.campfire_entities:
                    for x, y, z, _, after in cells:
                        if not after.split('[')[0].endswith('campfire'):
                            continue
                        entities = root.get('block_entities')
                        if entities is None or not len(entities):
                            root['block_entities'] = entities = nbtlib.List[nbtlib.Compound]()
                        for e in list(entities):
                            if (int(e['x']), int(e['y']), int(e['z'])) == (x, y, z):
                                entities.remove(e)
                        entities.append(campfire_entity(x, y, z))
                clear_light(root)
                if a.refresh_heightmaps and 'Heightmaps' in root:
                    # The game rebuilds missing heightmaps on load; stale ones keep rain and spawning at the old ground.
                    del root['Heightmaps']
                write_chunk(buf, i, loc, count, root)
            swap = path.with_name(path.name + '.swap')
            swap.write_bytes(buf)
            os.replace(swap, path)
        wrong = collateral = 0
        for (rx, rz), chunks in grouped.items():
            name = f'r.{rx}.{rz}.mca'
            buf = (folder / name).read_bytes()
            old = (a.out / name).read_bytes()
            for (cx, cz), cells in chunks.items():
                new_sections = {int(s['Y']): s for s in read_chunk(buf, cx, cz)[3]['sections']}
                old_sections = {int(s['Y']): s for s in read_chunk(old, cx, cz)[3]['sections']}
                planned = defaultdict(dict)
                for x, y, z, _, after in cells:
                    planned[y >> 4][((y & 15) << 8) | ((z & 15) << 4) | (x & 15)] = after
                new_entities = {(int(e['x']), int(e['y']), int(e['z'])): e for e in read_chunk(buf, cx, cz)[3].get('block_entities', [])}
                old_entities = {(int(e['x']), int(e['y']), int(e['z'])): e for e in read_chunk(old, cx, cz)[3].get('block_entities', [])}
                wanted = {tuple(sign['pos']): sign for sign in sign_chunks.get((cx, cz), ())}
                fires = {(x, y, z) for x, y, z, _, after in cells if a.campfire_entities and after.split('[')[0].endswith('campfire')}
                for pos in set(new_entities) | set(old_entities):
                    if pos in fires:
                        e = new_entities.get(pos)
                        if e is None or str(e['id']) != 'minecraft:campfire':
                            wrong += 1
                    elif pos in wanted:
                        e = new_entities.get(pos)
                        if e is None or [json.loads(str(m))['text'] for m in e['front_text']['messages']] != (list(wanted[pos].get('front', [])) + [''] * 4)[:4]:
                            wrong += 1
                    elif pos in given:
                        e = new_entities.get(pos)
                        if e is None or str(e['id']) != given[pos]['id']:
                            wrong += 1
                        elif 'snbt' in given[pos]:
                            # every field given must read back as given
                            if any(e.get(k) != v for k, v in nbtlib.parse_nbt(given[pos]['snbt']).items()):
                                wrong += 1
                        elif int(e['color']) != int(given[pos]['color']):
                            wrong += 1
                    elif pos in dropped:
                        if pos in new_entities:
                            wrong += 1
                    elif new_entities.get(pos) != old_entities.get(pos):
                        collateral += 1
                if set(new_sections) != set(old_sections):
                    raise SystemExit(f'Chunk {cx},{cz} changed its section list')
                for sy, section in new_sections.items():
                    if sy not in planned:
                        if section.get('block_states') != old_sections[sy].get('block_states'):
                            collateral += 4096
                        continue
                    new_ids, new_palette = decode(section['block_states'])
                    old_ids, old_palette = decode(old_sections[sy]['block_states'])
                    new_names = np.array(new_palette, dtype=object)[new_ids]
                    old_names = np.array(old_palette, dtype=object)[old_ids]
                    moved = set(np.nonzero(new_names != old_names)[0].tolist())
                    collateral += len(moved - set(planned[sy]))
                    wrong += sum(new_names[at] != after for at, after in planned[sy].items())
    if wrong or collateral:
        raise SystemExit(f'Readback: {wrong} of {changed} cells wrong, {collateral} cells changed outside the plan')
    (a.out / 'installation.json').write_text(json.dumps(dict(status='installed', cells=changed, signs=len(signs), dropped_block_entities=len(dropped), written_block_entities=written_entities, regions=len(grouped), readback_wrong=0, collateral=0), indent=1), 'utf8')
    print(json.dumps(dict(cells=changed, signs=len(signs), regions=len(grouped), readback_wrong=0, collateral=0, dropped_block_entities=len(dropped),
                          written_block_entities=written_entities)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--rows', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--allow-city-lift', action='store_true', help='only to restore the hatch cover of the city lift itself')
    parser.add_argument('--signs', type=Path, help='JSON list of {pos, front, back, color, glow}: writes only those sign block entities')
    parser.add_argument('--allow-lift-shaft', action='store_true', help='only to clear the travel space of a lift itself')
    parser.add_argument('--allow-air-shaft', action='store_true',
                        help='only to clear the travel space of the remote air shaft itself or to rebuild its surface door')
    parser.add_argument('--allow-block-entities', action='store_true',
                        help='let rows replace blocks that carry a block entity (chests, signs, machines) and drop that entity; off by default')
    parser.add_argument('--campfire-entities', action='store_true', help='give every campfire a row places its (empty) block entity, so it smokes')
    parser.add_argument('--allow-launch-repaint', action='store_true',
                        help='launch tunnel walls: rows inside the launch space may only turn one wall block into another (no air, seals or rail anchors)')
    parser.add_argument('--bank2-exterior', action='store_true', help='install the measured exterior cladding of the second launch bank')
    parser.add_argument('--dogma-hall-doorway', action='store_true',
                        help='open the declared EVA doorway to the Central Dogma shaft in the hangar hall (plan_r66_dogma_doorway); nothing else in the launch reservation')
    parser.add_argument('--item42-city-lift-obstructions', action='store_true',
                        help='clear the old glass stair shaft and two floating slabs where they stand in city lift spaces (listed boxes, listed blocks, to air only); every other cell of a city lift space is still refused')
    parser.add_argument('--refresh-heightmaps', action='store_true', help='drop the stored heightmaps of touched chunks, for terrain cut or raised')
    apply(parser.parse_args())
