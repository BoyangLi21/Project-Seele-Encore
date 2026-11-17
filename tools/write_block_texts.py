"""Rewrite the text of existing signs and station boards in a stopped world, nothing else.

Edits: JSON list of
    {"pos": [x, y, z], "type": "sign",  "before": {"front": [4 lines], "back": [4 lines]},
                                        "after":  {"front": [...], "back": [...], "color": "black", "glow": false}}
    {"pos": [x, y, z], "type": "board", "before": {"Station": "...", "Route": "...", "Row0": "...", "Row1": "...", "Row2": "..."},
                                        "after":  {same keys, any subset}}
    (boards may also carry "MapRows": [strings], the stop list of a station line diagram)
Every edit is checked before anything is written: the block entity is there, of the right kind, and its current text
equals "before" exactly. Each touched region file is copied to --out first. After writing, every chunk is read back:
the edited entities must hold "after", every other block entity and every block state must be unchanged.

    write_block_texts.py --world W --edits EDITS.json --out DIR
"""
import argparse
import json
import os
import shutil
from collections import defaultdict
from pathlib import Path

import nbtlib

from install_r53_carrier_trays import stopped_world
from write_deep_cells import REGION, read_chunk, write_chunk, sign_text

BOARD_KEYS = ('Station', 'Route', 'Row0', 'Row1', 'Row2')
LIST_KEYS = ('MapRows',)        # station line diagrams keep their stops and footers in a string list


def sign_lines(side):
    return [json.loads(str(m)).get('text', '') if str(m).startswith('{') else str(m) for m in side['messages']]


def current(entity, kind):
    if kind == 'sign':
        return {'front': sign_lines(entity['front_text']), 'back': sign_lines(entity['back_text'])}
    got = {k: str(entity.get(k, '')) for k in BOARD_KEYS}
    for k in LIST_KEYS:
        if k in entity:
            got[k] = [str(v) for v in entity[k]]
    return got


def apply_edit(entity, edit):
    after = edit['after']
    if edit['type'] == 'sign':
        for side in ('front', 'back'):
            if side in after:
                text = entity[f'{side}_text']
                text['messages'] = sign_text(after[side])
                if 'color' in after:
                    text['color'] = nbtlib.String(after['color'])
                if 'glow' in after:
                    text['has_glowing_text'] = nbtlib.Byte(1 if after['glow'] else 0)
        entity['is_waxed'] = nbtlib.Byte(1)
    else:
        for k in BOARD_KEYS:
            if k in after:
                entity[k] = nbtlib.String(after[k])
        for k in LIST_KEYS:
            if k in after:
                if k not in entity:
                    raise SystemExit(f"{edit['pos']}: has no {k} to rewrite")
                entity[k] = nbtlib.List[nbtlib.String]([nbtlib.String(v) for v in after[k]])


def matches(entity, edit, key):
    got = current(entity, edit['type'])
    want = edit[key]
    if edit['type'] == 'sign':
        return all(got[s] == (list(want[s]) + [''] * 4)[:4] for s in ('front', 'back') if s in want)
    return all(got.get(k) == want[k] for k in want if k in BOARD_KEYS + LIST_KEYS)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world', type=Path, required=True)
    p.add_argument('--edits', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    edits = json.loads(a.edits.read_text('utf8'))
    grouped = defaultdict(lambda: defaultdict(list))
    for e in edits:
        x, y, z = e['pos']
        grouped[x >> 9, z >> 9][x >> 4, z >> 4].append(e)
    folder = a.world / REGION
    problems = []
    for (rx, rz), chunks in grouped.items():
        buf = (folder / f'r.{rx}.{rz}.mca').read_bytes()
        for (cx, cz), es in chunks.items():
            ents = {(int(t['x']), int(t['y']), int(t['z'])): t for t in read_chunk(buf, cx, cz)[3].get('block_entities', [])}
            for e in es:
                t = ents.get(tuple(e['pos']))
                if t is None:
                    problems.append(f"{e['pos']}: no block entity")
                elif (e['type'] == 'sign') != str(t['id']).endswith('sign'):
                    problems.append(f"{e['pos']}: holds {t['id']}, not a {e['type']}")
                elif not matches(t, e, 'before'):
                    problems.append(f"{e['pos']}: text is {json.dumps(current(t, e['type']), ensure_ascii=False)}")
    if problems:
        raise SystemExit(f'Preflight refused {len(problems)} edits, nothing written:\n' + '\n'.join(problems[:20]))
    a.out.mkdir(parents=True, exist_ok=False)
    with stopped_world(a.world):
        for (rx, rz), chunks in sorted(grouped.items()):
            path = folder / f'r.{rx}.{rz}.mca'
            shutil.copy2(path, a.out / path.name)
            buf = bytearray(path.read_bytes())
            for (cx, cz), es in chunks.items():
                i, loc, count, root = read_chunk(buf, cx, cz)
                ents = {(int(t['x']), int(t['y']), int(t['z'])): t for t in root.get('block_entities', [])}
                for e in es:
                    apply_edit(ents[tuple(e['pos'])], e)
                write_chunk(buf, i, loc, count, root)
            swap = path.with_name(path.name + '.swap')
            swap.write_bytes(buf)
            os.replace(swap, path)
    wrong = collateral = 0
    for (rx, rz), chunks in grouped.items():
        name = f'r.{rx}.{rz}.mca'
        new, old = (folder / name).read_bytes(), (a.out / name).read_bytes()
        for (cx, cz), es in chunks.items():
            nr, orr = read_chunk(new, cx, cz)[3], read_chunk(old, cx, cz)[3]
            if [s.get('block_states') for s in nr['sections']] != [s.get('block_states') for s in orr['sections']]:
                collateral += 1
            ne = {(int(t['x']), int(t['y']), int(t['z'])): t for t in nr.get('block_entities', [])}
            oe = {(int(t['x']), int(t['y']), int(t['z'])): t for t in orr.get('block_entities', [])}
            edited = {tuple(e['pos']): e for e in es}
            for pos in set(ne) | set(oe):
                if pos in edited:
                    e = edited[pos]
                    want = {**e['before'], **{k: v for k, v in e['after'].items() if k not in ('color', 'glow')}}
                    if pos not in ne or not matches(ne[pos], {'type': e['type'], 'w': want}, 'w'):
                        wrong += 1
                elif ne.get(pos) != oe.get(pos):
                    collateral += 1
    if wrong or collateral:
        raise SystemExit(f'Readback: {wrong} edits wrong, {collateral} other changes')
    (a.out / 'installation.json').write_text(json.dumps(dict(status='installed', edits=len(edits), readback_wrong=0, collateral=0)), 'utf8')
    print(json.dumps(dict(edits=len(edits), regions=len(grouped), readback_wrong=0, collateral=0)))


if __name__ == '__main__':
    main()
