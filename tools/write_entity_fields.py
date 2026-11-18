"""Change saved fields of named entities in a stopped world, nothing else.

Edits: JSON list of
    {"dimension": "dimensions/projectseele/geofront", "id": "projectseele:lilith",
     "tag": "projectseele.terminal_dogma_lilith", "pos": [x, y, z],
     "before": {"ContainmentScale": 1.65}, "after": {"ContainmentScale": 1.95}}
The entity is found by id, tag and position (within 0.5 block); there must be exactly one. Every field in "before"
must hold that value, or nothing is written. Values are written with the type the field already has (Float, Byte,
Int, Double, String). Each touched entity region file is copied to --out first; after writing, the entities are
read back: the edited fields hold "after", and every other entity and field in the touched chunks is unchanged.

    write_entity_fields.py --world W --edits EDITS.json --out DIR
"""
import argparse
import json
import os
import shutil
from pathlib import Path

import nbtlib

from install_r53_carrier_trays import stopped_world
from write_deep_cells import read_chunk, write_chunk


def find(root, edit):
    hits = []
    for e in root.get('Entities', []):
        if str(e.get('id')) != edit['id'] or edit['tag'] not in [str(t) for t in e.get('Tags', [])]:
            continue
        pos = [float(v) for v in e['Pos']]
        if all(abs(a - b) <= 0.5 for a, b in zip(pos, edit['pos'])):
            hits.append(e)
    return hits


def typed(old, value):
    for kind in (nbtlib.Float, nbtlib.Double, nbtlib.Byte, nbtlib.Short, nbtlib.Int, nbtlib.Long, nbtlib.String):
        if isinstance(old, kind):
            return kind(value)
    raise SystemExit(f'unsupported field type {type(old).__name__}')


def same(a, b):
    return abs(float(a) - float(b)) < 1e-4 if isinstance(b, (int, float)) and not isinstance(b, bool) else str(a) == str(b)


def locate(world, edit):
    x, z = int(edit['pos'][0]) >> 4, int(edit['pos'][2]) >> 4
    path = Path(world) / edit['dimension'] / 'entities' / f'r.{x >> 5}.{z >> 5}.mca'
    return path, x, z


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--world', type=Path, required=True)
    ap.add_argument('--edits', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    edits = json.loads(a.edits.read_text('utf8'))
    problems = []
    for e in edits:
        path, cx, cz = locate(a.world, e)
        hits = find(read_chunk(path.read_bytes(), cx, cz)[3], e)
        if len(hits) != 1:
            problems.append(f"{e['id']} at {e['pos']}: {len(hits)} matching entities")
            continue
        for k, v in e['before'].items():
            if k not in hits[0] or not same(hits[0][k], v):
                problems.append(f"{e['id']} {k} is {hits[0].get(k)}, expected {v}")
    if problems:
        raise SystemExit('Preflight refused, nothing written:\n' + '\n'.join(problems))
    a.out.mkdir(parents=True, exist_ok=False)
    touched = {}
    with stopped_world(a.world):
        for e in edits:
            path, cx, cz = locate(a.world, e)
            if path not in touched:
                shutil.copy2(path, a.out / path.name)
                touched[path] = bytearray(path.read_bytes())
            buf = touched[path]
            i, loc, count, root = read_chunk(buf, cx, cz)
            ent = find(root, e)[0]
            for k, v in e['after'].items():
                ent[k] = typed(ent[k], v)
            write_chunk(buf, i, loc, count, root)
        for path, buf in touched.items():
            swap = path.with_name(path.name + '.swap')
            swap.write_bytes(buf)
            os.replace(swap, path)
    wrong = collateral = 0
    for e in edits:
        path, cx, cz = locate(a.world, e)
        new, old = read_chunk(path.read_bytes(), cx, cz)[3], read_chunk((a.out / path.name).read_bytes(), cx, cz)[3]
        ent = find(new, e)
        if len(ent) != 1 or not all(same(ent[0][k], v) for k, v in e['after'].items()):
            wrong += 1
            continue
        before = find(old, e)[0]
        for k in set(ent[0]) | set(before):
            if k not in e['after'] and ent[0].get(k) != before.get(k):
                collateral += 1
        others_new = [x for x in new.get('Entities', []) if x is not ent[0]]
        others_old = [x for x in old.get('Entities', []) if x is not before]
        if others_new != others_old:
            collateral += 1
    if wrong or collateral:
        raise SystemExit(f'Readback: {wrong} edits wrong, {collateral} other changes')
    print(json.dumps(dict(edits=len(edits), files=len(touched), readback_wrong=0, collateral=0)))


if __name__ == '__main__':
    main()
