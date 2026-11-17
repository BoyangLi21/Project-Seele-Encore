"""Change named fields of existing block entities (station boards, plaques) in a stopped world's region files.

Rows (JSON list): {"pos": [x, y, z], "id": "projectseele:station_departure_board",
                   "expect": {"Route": "old text"}, "set": {"Route": "new text"}}
Only string, integer and long fields that already exist can be set, with the same tag type. Every row is
checked first (block entity present, id and expected values match); nothing is written if one fails. Each
touched region is copied to <out> before writing, and every field is read back afterwards.
usage: patch_block_entity_fields.py --world <world> --rows <rows.json> --out <new-dir> [--dimension projectseele/geofront]"""
import argparse
import json
import shutil
from collections import defaultdict
from pathlib import Path

import nbtlib

from write_deep_cells import read_chunk, write_chunk


def find(root, x, y, z):
    for e in root.get('block_entities', []):
        if int(e['x']) == x and int(e['y']) == y and int(e['z']) == z:
            return e
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--world', type=Path, required=True)
    ap.add_argument('--rows', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--dimension', default='projectseele/geofront')
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    reg = a.world / 'dimensions' / a.dimension / 'region'
    rows = json.loads(a.rows.read_text('utf8'))
    by_region = defaultdict(list)
    for r in rows:
        x, y, z = r['pos']
        by_region[f'r.{x >> 9}.{z >> 9}.mca'].append(r)
    problems = []
    bufs = {}
    for name, rs in by_region.items():
        bufs[name] = bytearray((reg / name).read_bytes())
        for r in rs:
            x, y, z = r['pos']
            _, _, _, root = read_chunk(bufs[name], x >> 4, z >> 4)
            e = find(root, x, y, z)
            if e is None:
                problems.append(f'{r["pos"]}: no block entity')
                continue
            if str(e.get('id')) != r['id']:
                problems.append(f'{r["pos"]}: id {e.get("id")} is not {r["id"]}')
            for k, v in r.get('expect', {}).items():
                if k not in e or e[k].unpack() != v:
                    problems.append(f'{r["pos"]}: {k} is {e[k].unpack() if k in e else None!r}, expected {v!r}')
            for k in r['set']:
                if k not in e:
                    problems.append(f'{r["pos"]}: no field {k}')
    if problems:
        raise SystemExit('Preflight refused, nothing written:\n' + '\n'.join(problems[:20]))
    for name, rs in by_region.items():
        shutil.copy2(reg / name, a.out / name)
        chunks = defaultdict(list)
        for r in rs:
            chunks[(r['pos'][0] >> 4, r['pos'][2] >> 4)].append(r)
        for (cx, cz), crs in chunks.items():
            i, loc, count, root = read_chunk(bufs[name], cx, cz)
            for r in crs:
                e = find(root, *r['pos'])
                for k, v in r['set'].items():
                    e[k] = type(e[k])(v)
            write_chunk(bufs[name], i, loc, count, root)
        (reg / name).write_bytes(bufs[name])
    wrong = 0
    for name, rs in by_region.items():
        buf = bytearray((reg / name).read_bytes())
        for r in rs:
            _, _, _, root = read_chunk(buf, r['pos'][0] >> 4, r['pos'][2] >> 4)
            e = find(root, *r['pos'])
            wrong += any(e[k].unpack() != v for k, v in r['set'].items())
    (a.out / 'installation.json').write_text(json.dumps(dict(status='installed', entities=len(rows), regions=len(by_region), readback_wrong=wrong), indent=1), 'utf8')
    print(json.dumps(dict(entities=len(rows), regions=len(by_region), readback_wrong=wrong)))


if __name__ == '__main__':
    main()
