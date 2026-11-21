"""Install the non-block parts of a map patch into a stopped world: nested block-entity fields, world-root JSON
fields and whole data files (chunk regeneration recipes), each checked against its expected old value first.

Package (JSON):
  {"entities": [{"pos": [x, y, z], "id": "movingelevators:elevator_tile", "path": ["data", "name"],
                 "expect": "old", "set": "new"}],
   "json": [{"file": "personnel_lifts_r52.json", "path": ["lifts", 0, "floors", 0, "label"],
             "expect": "old", "set": "new"}],
   "files": [{"file": "dimensions/.../surface/1_15.dat", "expect_sha256": "...", "source": "recipes/1_15.dat",
              "sha256": "..."}]}
"source" paths are relative to the package file. Nothing is written unless every expected value and hash matches.
Every touched file is copied to <out> first; everything is read back afterwards (installation.json).
usage: install_world_extras.py --world <world> --package <package.json> --out <new-dir> [--dimension projectseele/geofront]"""
import argparse
import hashlib
import json
import os
import shutil
from collections import defaultdict
from pathlib import Path

import nbtlib

from install_r53_carrier_trays import stopped_world
from write_deep_cells import read_chunk, write_chunk


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dig(node, path):
    for k in path[:-1]:
        node = node[k]
    return node, path[-1]


def find(root, x, y, z):
    return next((e for e in root.get('block_entities', []) if (int(e['x']), int(e['y']), int(e['z'])) == (x, y, z)), None)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--world', type=Path, required=True)
    ap.add_argument('--package', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--dimension', default='projectseele/geofront')
    a = ap.parse_args()
    pkg = json.loads(a.package.read_text('utf8'))
    base = a.package.parent
    reg = a.world / 'dimensions' / a.dimension / 'region'
    problems = []
    bufs, by_region = {}, defaultdict(list)
    for r in pkg.get('entities', []):
        x, y, z = r['pos']
        by_region[f'r.{x >> 9}.{z >> 9}.mca'].append(r)
    for name, rs in by_region.items():
        bufs[name] = bytearray((reg / name).read_bytes())
        for r in rs:
            e = find(read_chunk(bufs[name], r['pos'][0] >> 4, r['pos'][2] >> 4)[3], *r['pos'])
            if e is None or str(e.get('id')) != r['id']:
                problems.append(f"{r['pos']}: no {r['id']}")
                continue
            try:
                node, k = dig(e, r['path'])
                if node[k].unpack() != r['expect']:
                    problems.append(f"{r['pos']} {r['path']}: {node[k].unpack()!r}, expected {r['expect']!r}")
            except (KeyError, IndexError):
                problems.append(f"{r['pos']}: no field {r['path']}")
    docs = {}
    for r in pkg.get('json', []):
        f = a.world / r['file']
        docs.setdefault(r['file'], json.loads(f.read_text('utf8')))
        try:
            node, k = dig(docs[r['file']], r['path'])
            if node[k] != r['expect']:
                problems.append(f"{r['file']} {r['path']}: {node[k]!r}, expected {r['expect']!r}")
        except (KeyError, IndexError):
            problems.append(f"{r['file']}: no field {r['path']}")
    for r in pkg.get('files', []):
        f = a.world / r['file']
        have = sha(f) if f.exists() else None
        if have != r['expect_sha256']:
            problems.append(f"{r['file']}: sha256 {have}, expected {r['expect_sha256']}")
        if sha(base / r['source']) != r['sha256']:
            problems.append(f"{r['source']}: package file does not match its sha256")
    if problems:
        raise SystemExit('Preflight refused, nothing written:\n' + '\n'.join(problems[:30]))
    a.out.mkdir(parents=True, exist_ok=False)
    with stopped_world(a.world):
        for name, rs in by_region.items():
            (a.out / 'region').mkdir(exist_ok=True)
            shutil.copy2(reg / name, a.out / 'region' / name)
            chunks = defaultdict(list)
            for r in rs:
                chunks[r['pos'][0] >> 4, r['pos'][2] >> 4].append(r)
            for (cx, cz), crs in chunks.items():
                i, loc, count, root = read_chunk(bufs[name], cx, cz)
                for r in crs:
                    node, k = dig(find(root, *r['pos']), r['path'])
                    node[k] = type(node[k])(r['set'])
                write_chunk(bufs[name], i, loc, count, root)
            tmp = (reg / name).with_suffix('.extras-new')
            tmp.write_bytes(bufs[name])
            os.replace(tmp, reg / name)
        for file, doc in docs.items():
            f = a.world / file
            (a.out / 'json').mkdir(exist_ok=True)
            shutil.copy2(f, a.out / 'json' / f.name)
            for r in pkg['json']:
                if r['file'] == file:
                    node, k = dig(doc, r['path'])
                    node[k] = r['set']
            tmp = f.with_suffix('.extras-new')
            # the world's JSON files are compact UTF-8; keep that so an unchanged field stays byte for byte
            tmp.write_text(json.dumps(doc, ensure_ascii=False, separators=(',', ':')), 'utf8')
            os.replace(tmp, f)
        for r in pkg.get('files', []):
            f = a.world / r['file']
            dest = a.out / 'files' / r['file']
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
            tmp = f.with_suffix('.extras-new')
            shutil.copy2(base / r['source'], tmp)
            os.replace(tmp, f)
    wrong = []
    for name, rs in by_region.items():
        buf = bytearray((reg / name).read_bytes())
        for r in rs:
            node, k = dig(find(read_chunk(buf, r['pos'][0] >> 4, r['pos'][2] >> 4)[3], *r['pos']), r['path'])
            if node[k].unpack() != r['set']:
                wrong.append(r['pos'])
    for r in pkg.get('json', []):
        node, k = dig(json.loads((a.world / r['file']).read_text('utf8')), r['path'])
        if node[k] != r['set']:
            wrong.append(r['file'])
    for r in pkg.get('files', []):
        if sha(a.world / r['file']) != r['sha256']:
            wrong.append(r['file'])
    result = dict(status='installed', entities=len(pkg.get('entities', [])), json_fields=len(pkg.get('json', [])),
                  files=len(pkg.get('files', [])), readback_wrong=wrong)
    (a.out / 'installation.json').write_text(json.dumps(result, ensure_ascii=False, indent=1), 'utf8')
    print(json.dumps(result, ensure_ascii=False))
    if wrong:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
