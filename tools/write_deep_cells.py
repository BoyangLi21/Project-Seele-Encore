"""Write individual blocks directly into a stopped world's chunk sections, at any height.

The map patch pipeline covers y -128..319; the GeoFront cavern lies far below that. Each
touched region file is copied to the output folder first, each cell's prior state is
checked, and the rewritten chunks are compared with those copies: every planned cell must
hold its new state and no other block may differ.
Rows: [x, y, z, before, after] with block states written as name[prop=value,...].
"""
import argparse
from collections import defaultdict
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


def block_at(root, x, y, z):
    for s in root['sections']:
        if int(s['Y']) == y >> 4 and 'block_states' in s:
            ids, palette = decode(s['block_states'])
            return palette[ids[((y & 15) << 8) | ((z & 15) << 4) | (x & 15)]]
    return 'minecraft:air'


def apply(a):
    rows = json.loads(a.rows.read_text('utf8'))
    signs = json.loads(a.signs.read_text('utf8')) if a.signs else []
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
        city_protection(a.world).assert_positions(positions)
    if not a.allow_lift_shaft:
        # A buried shaft is how a lift stops reaching a floor; doors and controllers count too.
        from map_pipeline.lift_protection import load as lift_protection
        lift_protection(a.world).assert_positions(positions)
    from map_pipeline.launch_protection import load as launch_protection
    launch_protection(a.world).assert_positions(positions)
    a.out.mkdir(parents=True, exist_ok=False)
    folder = a.world / REGION
    changed = 0
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
                for sign in sign_chunks.get((cx, cz), ()):
                    x, y, z = sign['pos']
                    state = block_at(root, x, y, z)
                    if not state.split('[')[0].endswith('sign'):
                        raise ValueError(f'{x},{y},{z} is {state}, not a sign')
                    entities = root.setdefault('block_entities', nbtlib.List[nbtlib.Compound]())
                    for e in list(entities):
                        if (int(e['x']), int(e['y']), int(e['z'])) == (x, y, z):
                            if not str(e['id']).endswith('sign'):
                                raise ValueError(f'{x},{y},{z} holds a {e["id"]} block entity')
                            entities.remove(e)
                    entities.append(sign_entity(sign, state))
                clear_light(root)
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
                for pos in set(new_entities) | set(old_entities):
                    if pos in wanted:
                        e = new_entities.get(pos)
                        if e is None or [json.loads(str(m))['text'] for m in e['front_text']['messages']] != (list(wanted[pos].get('front', [])) + [''] * 4)[:4]:
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
    (a.out / 'installation.json').write_text(json.dumps(dict(status='installed', cells=changed, signs=len(signs), regions=len(grouped), readback_wrong=0, collateral=0), indent=1), 'utf8')
    print(json.dumps(dict(cells=changed, signs=len(signs), regions=len(grouped), readback_wrong=0, collateral=0)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--rows', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--allow-city-lift', action='store_true', help='only to restore the hatch cover of the city lift itself')
    parser.add_argument('--signs', type=Path, help='JSON list of {pos, front, back, color, glow}: writes only those sign block entities')
    parser.add_argument('--allow-lift-shaft', action='store_true', help='only to clear the travel space of a lift itself')
    apply(parser.parse_args())
