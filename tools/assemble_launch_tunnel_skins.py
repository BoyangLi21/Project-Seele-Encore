"""Assemble nine plan_launch_tunnel_skin results into disjoint, protected exit manifests."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3

import numpy as np
from scipy.spatial import cKDTree
from plan_launch_tunnel_skin import centre_samples, anchors, PAINTABLE, WALL, FLOOR, LIGHT, RIB


def protected_positions(value):
    if isinstance(value, dict):
        p = value.get('position')
        if isinstance(p, list) and len(p) == 3 and all(isinstance(n, int) for n in p):
            yield tuple(p)
        for child in value.values():
            yield from protected_positions(child)
    elif isinstance(value, list):
        for child in value:
            yield from protected_positions(child)


def guarded_frame(samples, points, mask, start):
    s, pos, direction, u, v, _ = samples
    segment = s < 180 if start else pos[:, 1] >= -470
    if not segment.any():
        return
    s, pos, u, v = (a[segment] for a in (s, pos, u, v))
    near = np.flatnonzero(np.all((points >= pos.min(0) - 75) & (points <= pos.max(0) + 75), axis=1))
    if not len(near):
        return
    dist, idx = cKDTree(pos).query(points[near])
    delta = points[near] - pos[idx]
    lu = np.einsum('ij,ij->i', delta, u[idx])
    lv = np.einsum('ij,ij->i', delta, v[idx])
    within = (dist <= 75) & (abs(lu) <= 28) & (lv >= -66) & (lv <= 15)
    within &= (s[idx] < 90) if start else (points[near, 1] >= -394)
    mask[near[within]] = True


def write_manifest(folder, name, rows):
    path = folder / (name + '.json')
    count = 0
    digest = hashlib.md5()
    with path.open('xb') as f:
        def emit(data):
            digest.update(data)
            f.write(data)
        emit(b'[')
        for x, y, z, old, new in rows:
            if count:
                emit(b',\n')
            emit(json.dumps([x, y, z, old, new], separators=(',', ':')).encode())
            count += 1
        emit(b']\n')
    return dict(path=path.name, rows=count, md5=digest.hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('world', 'inputs', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    directory = json.loads((args.world / 'ROOT_RUNTIME_DIRECTORY.json').read_bytes())
    tracks = {l['id']: centre_samples(l['centre_curve']) for l in directory['legs']
              if l['id'].endswith('/upright_continuous')}
    if len(tracks) != 9:
        raise ValueError(f'Expected nine tunnel tracks, found {len(tracks)}')
    owner = json.loads((args.world / 'ROOT_MECHANICAL_OWNER.json').read_bytes())
    fixed = set(protected_positions(owner)) | anchors(args.world)
    hatches = json.loads((args.world / 'launch_hatch_layers_r54.json').read_bytes())
    seals = set(protected_positions(hatches))
    for gate in owner['gates']:
        seals.update(protected_positions(gate.get('collision_steps', [])))
    seal_tree = cKDTree(list(seals))
    db = sqlite3.connect(args.out / 'ownership.sqlite')
    db.execute('CREATE TABLE cells (x INTEGER,y INTEGER,z INTEGER,old TEXT,new TEXT, lane TEXT, conflict INTEGER DEFAULT 0, PRIMARY KEY(x,y,z)) WITHOUT ROWID')
    insert = '''INSERT INTO cells (x,y,z,old,new,lane) VALUES (?,?,?,?,?,?)
                ON CONFLICT(x,y,z) DO UPDATE SET conflict = conflict OR old != excluded.old OR new != excluded.new'''
    index = dict(parameters=dict(base='black', bands='plan', straight=10, skip_start=90, light_every=16),
                 lanes={}, exits={})
    for name, samples in sorted(tracks.items(), key=lambda item: (item[0].split('/')[1], item[0])):
        unit, exit_name, _ = name.split('/')
        lane = unit + '-' + exit_name
        source = args.inputs / (lane + '.json')
        rows = json.loads(source.read_bytes())
        points = np.array([r[:3] for r in rows], dtype=float)
        close_to_gate = seal_tree.query(points, p=1, distance_upper_bound=3.01)[0] <= 3
        points += .5
        reserved = np.zeros(len(points), dtype=bool)
        for other, frame in tracks.items():
            guarded_frame(frame, points, reserved, True)
            if '/exit2/' in other:
                guarded_frame(frame, points, reserved, False)
        reasons = Counter()
        def filtered():
            for protected, seal, (x, y, z, old, new) in zip(reserved, close_to_gate, rows):
                if old.split('[')[0] not in PAINTABLE or new not in (WALL, FLOOR, LIGHT, RIB) or old == new:
                    raise ValueError((lane, x, y, z, old, new))
                if protected or seal or (x, y, z) in fixed:
                    reasons['protected'] += 1
                    continue
                yield x, y, z, old, new, lane
        with db:
            db.executemany(insert, filtered())
        index['lanes'][lane] = dict(input_rows=len(rows), filtered=dict(reasons))
    index['shared_material_conflicts_held'] = db.execute('SELECT count(*) FROM cells WHERE conflict').fetchone()[0]
    cols = 'SELECT x,y,z,old,new FROM cells WHERE NOT conflict AND '
    for lane, entry in index['lanes'].items():
        entry.update(write_manifest(args.out, lane, db.execute(cols + 'lane=? ORDER BY x,y,z', (lane,))))
    for exit_num in (1, 2, 3):
        name = f'exit{exit_num}'
        index['exits'][name] = write_manifest(args.out, name, db.execute(cols + 'lane LIKE ? ORDER BY x,y,z', ('%-' + name,)))
    db.close()
    (args.out / 'index.json').write_text(json.dumps(index, indent=2), 'utf8')
    print(json.dumps(index['exits']), flush=True)


if __name__ == '__main__':
    main()
