"""Carry TrafficCraft lane markings down to a lowered road deck.

A ramp planned by plan_road_tunnel_finish.py clears the old deck and lays plain asphalt lower down, so the
paint (asphalt_pattern_N / asphalt_slope_pattern_N plus its colored_block_entity) would be lost. For every
column where the list lays a new TrafficCraft deck and the old top paving block was a pattern block, the new
top block takes the same pattern number, facing and colour (slope or full block as the new deck needs).
The colours are read from the block entities of a read-only copy of the world's region files.
usage: carry_ramp_markings.py <rows.json> <region-dir> <out-rows.json> <delta-rows.json>
  out-rows: the full list with the new tops painted (rows get the sixth item the writer takes)
  delta:    only the repainting, as rows from the plain new deck, for a copy the plain list was written to"""
import io
import json
import re
import sys
import zlib
from collections import defaultdict

import nbtlib

rows = json.load(open(sys.argv[1], encoding='utf8'))
regdir = sys.argv[2]


def chunk(buf, cx, cz):
    i = 4 * ((cx & 31) + (cz & 31) * 32)
    loc = int.from_bytes(buf[i:i + 3], 'big')
    if not loc:
        return None
    n = int.from_bytes(buf[loc * 4096:loc * 4096 + 4], 'big')
    return nbtlib.File.parse(io.BytesIO(zlib.decompress(bytes(buf[loc * 4096 + 5:loc * 4096 + 4 + n]))))


colours, bufs, seen = {}, {}, set()


def colour(x, y, z):
    cx, cz = x >> 4, z >> 4
    if (cx, cz) not in seen:
        seen.add((cx, cz))
        rf = f'{regdir}/r.{cx >> 5}.{cz >> 5}.mca'
        if rf not in bufs:
            bufs[rf] = open(rf, 'rb').read()
        root = chunk(bufs[rf], cx, cz)
        for e in root.get('block_entities', []):
            if str(e.get('id')) == 'trafficcraft:colored_block_entity':
                colours[int(e['x']), int(e['y']), int(e['z'])] = int(e['color'])
    return colours.get((x, y, z))


def props(s):
    m = re.search(r'\[(.*)\]', s)
    return dict(kv.split('=') for kv in m.group(1).split(',')) if m else {}


cols = defaultdict(list)
for i, r in enumerate(rows):
    cols[r[0], r[2]].append(i)
out_rows = [list(r) for r in rows]
delta, carried, lost = [], 0, []
for (x, z), idx in cols.items():
    olds = [i for i in idx if rows[i][3].startswith('trafficcraft:')]
    news = [i for i in idx if rows[i][4].startswith('trafficcraft:')]
    if not olds:
        continue
    top_old = max(olds, key=lambda i: rows[i][1])
    s_old = rows[top_old][3]
    m = re.match(r'trafficcraft:asphalt(?:_slope)?_pattern_(\d+)', s_old)
    if not m:
        continue
    if not news:
        lost.append(rows[top_old][:4])
        continue
    top_new = max(news, key=lambda i: rows[i][1])
    s_new = rows[top_new][4]
    c = colour(*rows[top_old][:3])
    if c is None or not s_new.startswith('trafficcraft:asphalt'):
        lost.append(rows[top_old][:4])
        continue
    p = {'facing': props(s_old).get('facing', 'north')}
    if 'slope' in s_new:
        p.update(layers=props(s_new)['layers'], waterlogged='false')
        name = f'trafficcraft:asphalt_slope_pattern_{m.group(1)}'
    else:
        name = f'trafficcraft:asphalt_pattern_{m.group(1)}'
    state = name + '[' + ','.join(f'{k}={p[k]}' for k in sorted(p)) + ']'
    ent = {'id': 'trafficcraft:colored_block_entity', 'color': c}
    out_rows[top_new] = rows[top_new][:4] + [state, ent]
    delta.append([rows[top_new][0], rows[top_new][1], rows[top_new][2], s_new, state, ent])
    carried += 1
json.dump(out_rows, open(sys.argv[3], 'w', encoding='utf8'))
json.dump(delta, open(sys.argv[4], 'w', encoding='utf8'))
print(json.dumps({'carried': carried, 'not_carried': len(lost), 'examples_not_carried': lost[:5]}))
