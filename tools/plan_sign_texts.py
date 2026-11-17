"""Plan text edits for street signs and NERV signs and boards by the rules in sign_rules.py.

Reads the current text straight from the world (so "before" is exact) and writes an edit list for
write_block_texts.py.

    plan_sign_texts.py --world W --at x,y,z [x,y,z ...] --out EDITS.json     (chosen signs)
    plan_sign_texts.py --world W --signs signs.json --kinds sign --areas core odawara --out EDITS.json

Street signs (vanilla): Japanese only. Generator lines ("入口 / 出口", "人员通行", block numbers) go; a house or office
entrance gets a house or building name picked from its position. Front and back get the same text.
NERV room plates (Japanese / CATEGORY / NERV): the Chinese name goes on the empty fourth line.
NERV wayfinding boards: title = Japanese floor or guide name, second line = Chinese and English, each destination row
= arrow + Japanese + Chinese + English, one name per place. The arrows themselves are kept as they are; they get
redone from the rebuilt floor graph in a later batch.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from write_deep_cells import REGION, read_chunk, block_at
from write_block_texts import current
import sign_rules as R

NUMBER = re.compile(r'^[0-9]{1,3}-[0-9]{1,3}$')
PYRAMID = (-90, 150, -1100, -294, 207, 447)        # x0 x1 y0 y1 z0 z1, with the levels under the pyramid


def pick(options, x, z):
    return options[int(hashlib.md5(f'{x},{z}'.encode()).hexdigest(), 16) % len(options)]


def in_nerv(x, y, z):
    return PYRAMID[0] <= x <= PYRAMID[1] and PYRAMID[2] <= y <= PYRAMID[3] and PYRAMID[4] <= z <= PYRAMID[5]


def street_sign(lines, x, z):
    kept = [l for l in lines if l and l not in R.DROP_LINES and not NUMBER.match(l)]
    head = lines[0] if lines else ''
    if head == '办公楼入口':
        return [pick(R.OFFICE_JA, x, z), '', '', '']
    if head == '住宅入口' or (not kept and head):
        return [pick(R.APARTMENT_JA, x, z), '', '', '']
    out = [R.to_ja(l) for l in kept][:4]
    return (out + [''] * 4)[:4]


def nerv_line(line):
    """'↑ 东侧主电梯' -> '↑ A号エレベーター  A号电梯  Lift A'; unknown names get Japanese characters only."""
    m = re.match(r'^([←→↑↓●│]\s*)?(.*)$', line)
    arrow, name = (m.group(1) or ''), m.group(2).strip()
    names = R.place(name)
    if names:
        return f'{arrow}{names[0]}  {names[1]}  {names[2]}'
    return f'{arrow}{R.to_ja(name)}' if name else line


def nerv_plate(lines):
    """Room plate (Japanese / CATEGORY / NERV): the Chinese name goes on the free fourth line.
    Guide signs (arrows or Chinese phrases) are rewritten line by line from the phrase table."""
    lines = (list(lines) + [''] * 4)[:4]
    if tuple(lines) in R.NERV_GUIDE_SIGNS:
        return R.NERV_GUIDE_SIGNS[tuple(lines)]
    names = R.place(lines[0])
    if names:
        return [names[0], names[2].upper(), 'NERV', names[1]]
    if lines[2] == 'NERV' and not lines[3]:
        ja = R.to_ja(lines[0])
        zh = R.ja_to_zh(lines[0]) if ja == lines[0] else lines[0]
        return [ja, lines[1], 'NERV', zh]
    return [R.NERV_PHRASES.get(l, nerv_line(l) if l[:1] in '←→↑↓' else l) for l in lines]


def board(cur):
    station, route = cur['Station'], cur['Route']
    floor = R.FLOORS.get(station)
    guide = R.GUIDE_TITLE.get(route)
    after = {}
    if floor and guide:
        # the renderer shows Route on top and Station under it for wayfinding boards
        after['Route'] = floor[0]
        after['Station'] = f'{floor[1]} · {floor[2]}'
    for k in ('Row0', 'Row1', 'Row2'):
        if cur.get(k):
            after[k] = nerv_line(cur[k])
    return {k: v for k, v in after.items() if v != cur.get(k)}


def plan(world, positions):
    edits = []
    cache = {}
    for (x, y, z) in positions:
        rx, rz = x >> 9, z >> 9
        if (rx, rz) not in cache:
            cache[rx, rz] = (Path(world) / REGION / f'r.{rx}.{rz}.mca').read_bytes()
        root = read_chunk(cache[rx, rz], x >> 4, z >> 4)[3]
        ent = next((e for e in root.get('block_entities', []) if (int(e['x']), int(e['y']), int(e['z'])) == (x, y, z)), None)
        if ent is None:
            continue
        if str(ent['id']).endswith('sign'):
            cur = current(ent, 'sign')
            lines = cur['front']
            new = nerv_plate(lines) if in_nerv(x, y, z) else street_sign(lines, x, z)
            if new != lines or cur['back'] != new:
                edits.append(dict(pos=[x, y, z], type='sign', before=cur, after={'front': new, 'back': new}))
        elif str(ent['id']) == 'projectseele:station_departure_board' and int(ent.get('Wayfinding', 0)):
            cur = current(ent, 'board')
            after = board(cur) if in_nerv(x, y, z) else {}
            if after:
                edits.append(dict(pos=[x, y, z], type='board', before={k: cur[k] for k in after}, after=after))
    return edits


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world', type=Path, required=True)
    p.add_argument('--at', action='append', default=[], help='x,y,z (repeat; write --at=-1,2,3 for negative x)')
    p.add_argument('--signs', type=Path)
    p.add_argument('--kinds', nargs='*', default=['sign', 'wayfinding'])
    p.add_argument('--areas', nargs='*')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    positions = [tuple(map(int, s.split(','))) for s in a.at]
    if a.signs:
        for s in json.loads(a.signs.read_text('utf8')):
            if s['kind'] in a.kinds and (not a.areas or s['area'] in a.areas) and not s['empty']:
                positions.append((s['x'], s['y'], s['z']))
    edits = plan(a.world, positions)
    a.out.write_text(json.dumps(edits, ensure_ascii=False, indent=1), 'utf8')
    print(json.dumps(dict(positions=len(positions), edits=len(edits))))


if __name__ == '__main__':
    main()
