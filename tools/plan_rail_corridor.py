"""Regional rail line from one JSON plan: native service first, then its track bed.

`native` runs the MTR engine on a copied snapshot, so rails, the route, the depot
and a moving train are proved before any block exists. `edits` lays the bed under
the exact native samples and writes a cell patch for release_map_patch.py. Mapped
future water stays open under the deck; nothing here opens the actual world.
"""
import argparse
from collections import Counter
import gzip
import json
import math
import os
from pathlib import Path
import shutil
import subprocess

import numpy as np
import shapely
from scipy.ndimage import distance_transform_edt
from shapely.geometry import LineString, shape
from shapely.ops import unary_union

from native_transit_additions import inventory
from plan_ashi_landscape_r54 import PLANTS, SOIL
from plan_station_access_corridor import CapturedSurface
from prepare_station_set_native import classpath
from query_blocks import AIR
from verify_hakone_network_candidate import PAVEMENT

NATURAL = SOIL | PLANTS | AIR
BALLAST, HALF = 'minecraft:gravel', 'minecraft:andesite_slab[type=bottom,waterlogged=false]'
DECK = 'minecraft:stone_bricks'
BED_RADIUS, CLEAR_RADIUS, BODY_RADIUS, BODY_HEIGHT = 2.6, 3.1, 1.9, 4.3


def read(path):
    return json.loads(Path(path).read_text('utf8'))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=1), 'utf8')


def native(a):
    """Author on a copied snapshot; only brand-new members may leave staging."""
    spec = read(a.config)
    repo = Path(__file__).resolve().parents[1]
    work = repo / '.Codex' / ('rail-' + spec['id'])
    if work.exists():
        raise ValueError('Use a fresh native staging directory')
    (work / 'classes').mkdir(parents=True)
    staging, out = work / 'native', work / 'output'
    shutil.copytree(spec['native_snapshot'], staging)
    plan = {key: spec[key] for key in ('rails', 'stations', 'lines', 'warmup_seconds')}
    plan['commission_clock'] = True
    write(work / 'plan.json', plan)
    options = argparse.Namespace(work=work, mtr=a.mtr, java=a.java)
    subprocess.run([str(a.java / 'bin/javac.exe'), '-encoding', 'UTF-8', '-cp', classpath(options), '-d', str(work / 'classes'),
                    str(Path(__file__).with_name('java') / 'RegionalTransitAuthor.java')], check=True)
    subprocess.run([str(a.java / 'bin/java.exe'), '-cp', classpath(options), 'RegionalTransitAuthor', str(work / 'plan.json'),
                    str(staging), str(out), '--append'], check=True, cwd=work)
    before, after = inventory(Path(spec['native_snapshot'])), inventory(staging)
    # Staged trains keep moving, so sidings and the clock differ; neither is delivered.
    changed = sorted(k for k in before if k in after and after[k] != before[k]
                     and Path(k).parts[2] not in ('settings', 'sidings'))
    gone = sorted(set(before) - set(after))
    if changed or gone:
        raise ValueError(('Native authoring touched existing members', changed[:5], gone[:5]))
    additions = a.out / 'additions'
    for name in sorted(set(after) - set(before)):
        target = additions / 'mtr' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(staging / name, target)
    shutil.copy2(out / 'native_transit_receipt.json', a.out / 'native_transit_receipt.json')
    shutil.copy2(out / 'track_samples.json', a.out / 'track_samples.json')
    receipt = read(a.out / 'native_transit_receipt.json')
    print('Native commissioning', json.dumps(receipt['validation'], ensure_ascii=False), 'new members', len(set(after) - set(before)))


def water_mask(features, spec, cells, bounds):
    with gzip.open(features, 'rt', encoding='utf8') as stream:
        rows = json.load(stream)['features']
    clip = shapely.box(*bounds)
    shapes = []
    for q in rows:
        if q['properties'].get('source_layer') in ('WA', 'RvrCL', 'WStrL'):
            g = shape(q['geometry'])
            if g.intersects(clip):
                shapes.append(g if q['properties']['source_layer'] == 'WA' else g.buffer(1))
    reserve = unary_union(shapes).buffer(spec.get('water_margin', 1))
    shapely.prepare(reserve)
    return shapely.intersects(reserve, cells)


def bed_heights(ys):
    """Ballast top under a rail: full gravel near a whole block, a slab near a half."""
    rounded = np.rint(np.asarray(ys, float) * 2) / 2
    block = np.floor(rounded).astype(int) - 1
    return block, rounded % 1 == .5


def edits(a):
    spec = read(a.config)
    samples = [r for r in read(a.out / 'track_samples.json') if r['mode'] == 'TRAIN']
    # A diagonal line's bounding box holds ungenerated corners; state() refuses those columns.
    source = CapturedSurface(spec['source'], partial=True)
    points = np.array([p for r in samples for p in r['points']])
    lines = unary_union([LineString(np.array(r['points'])[:, [0, 2]]) for r in samples])
    sx, sz, sX, sZ = source.bounds
    x0, z0, x1, z1 = lines.buffer(16).bounds
    bx, bz, bX, bZ = max(sx, math.floor(x0)), max(sz, math.floor(z0)), min(sX, math.ceil(x1)), min(sZ, math.ceil(z1))
    zz, xx = np.mgrid[bz:bZ + 1, bx:bX + 1]
    cells = shapely.box(xx, zz, xx + 1, zz + 1)
    def near(radius):
        g = lines.buffer(radius, cap_style=2)
        shapely.prepare(g)
        return shapely.intersects(g, cells)
    bed, clear, body = near(BED_RADIUS), near(CLEAR_RADIUS), near(BODY_RADIUS)
    from scipy.spatial import cKDTree
    _, nearest = cKDTree(points[:, [0, 2]]).query(np.c_[xx.ravel() + .5, zz.ravel() + .5])
    block, half = bed_heights(points[nearest, 1])
    block, half = block.reshape(xx.shape), half.reshape(xx.shape)
    with np.load(Path(spec['authority']) / 'network.npz') as f:
        ax, az, _, _ = map(int, f['bounds'])
        area = np.s_[bz - az:bZ - az + 1, bx - ax:bX - ax + 1]
        public = (f['walk'] | f['road'])[area].copy()
    station = np.zeros(public.shape, bool)
    for a0, _, c0, a1, _, c1 in read(Path(spec['authority']) / 'station-volumes.json'):
        station[(xx >= a0) & (xx <= a1) & (zz >= c0) & (zz <= c1)] = True
    original = source.measured['top'][bz - sz:bZ - sz + 1, bx - sx:bX - sx + 1].astype(int)
    full = source.measured['full'][bz - sz:bZ - sz + 1, bx - sx:bX - sx + 1]
    water = water_mask(spec['features'], spec, cells, (bx, bz, bX, bZ))
    d, near_bed = distance_transform_edt(~bed, return_indices=True)
    top = (block + 0)[tuple(near_bed)]
    target = np.rint(np.clip(original, top - d, top + d)).astype(int)
    active = (target != original) & (d <= spec.get('earthwork_reach', 10)) & ~bed & ~water & ~public & full
    writes, purposes, skipped, blocked = {}, {}, Counter(), []
    def put(x, y, z, state, purpose):
        before = source.state(x, y, z)
        if before.split('[')[0] not in NATURAL:
            skipped[before.split('[')[0]] += 1
            return
        if before != state:
            writes[x, y, z] = state
            purposes[x, y, z] = purpose
    for iz, ix in np.argwhere(active):
        x, z, old, new = int(xx[iz, ix]), int(zz[iz, ix]), int(original[iz, ix]), int(target[iz, ix])
        for y in range(min(old, new) - 2, max(old, new) + 1):
            state = 'minecraft:air' if y > new else 'minecraft:grass_block[snowy=false]' if y == new else 'minecraft:dirt' if y >= new - 2 else 'minecraft:stone'
            put(x, y, z, state, 'embankment slope')
    for iz, ix in np.argwhere(bed):
        x, z, y = int(xx[iz, ix]), int(zz[iz, ix]), int(block[iz, ix])
        if public[iz, ix]:
            continue
        if not full[iz, ix]:
            blocked.append([x, y, z])
            continue
        if water[iz, ix]:
            put(x, y - 1, z, DECK, 'open deck over a mapped channel')
        else:
            for yy in range(min(int(original[iz, ix]) - 1, y - 1), y):
                put(x, yy, z, 'minecraft:stone', 'track bed fill')
        put(x, y, z, BALLAST, 'ballast')
        if half[iz, ix]:
            put(x, y + 1, z, HALF, 'ballast half step')
    for iz, ix in np.argwhere(clear):
        x, z = int(xx[iz, ix]), int(zz[iz, ix])
        if not full[iz, ix]:
            if body[iz, ix]:
                blocked.append([x, 0, z])
            continue
        base = int(block[iz, ix]) + (2 if half[iz, ix] else 1)
        for y in range(base, base + 6):
            before = source.state(x, y, z)
            if before.split('[')[0] in AIR or (x, y, z) in writes:
                continue
            if before.split('[')[0] in NATURAL:
                put(x, y, z, 'minecraft:air', 'track clearance')
            elif body[iz, ix] and not public[iz, ix] and not station[iz, ix]:
                blocked.append([x, y, z])
    def state(x, y, z):
        return writes.get((x, y, z), source.state(x, y, z))
    floating, solid_in_body = [], []
    for x, y, z in points[::2]:
        cx, cz = math.floor(x), math.floor(z)
        if not state(cx, math.floor(y + .01) - 1, cz).split('[')[0] not in AIR:
            floating.append([cx, math.floor(y), cz])
    # Platform edges sit inside this radius by design; the real model sweep owns stations.
    for iz, ix in np.argwhere(body & full & ~public & ~station):
        px, pz = int(xx[iz, ix]), int(zz[iz, ix])
        base = int(block[iz, ix]) + (2 if half[iz, ix] else 1)
        for y in range(base, base + math.ceil(BODY_HEIGHT)):
            if state(px, y, pz).split('[')[0] not in AIR and state(px, y, pz).split('[')[0] not in PLANTS:
                solid_in_body.append([px, y, pz, state(px, y, pz)[:40]])
    devices = {tuple(int(t[k]) for k in 'xyz') for t in source.devices}
    errors = []
    if blocked:
        errors.append(['Track meets a public or unknown column', blocked[:10]])
    if floating:
        errors.append(['Rail without bed', floating[:10]])
    if solid_in_body:
        errors.append(['Solid inside the train body', solid_in_body[:10]])
    if devices & set(writes):
        errors.append('Track edits an original device')
    rows = [dict(pos=list(p), before=source.state(*p), after=s, purpose=purposes[p]) for p, s in sorted(writes.items())]
    report = dict(errors=errors, cells=len(rows), purposes=dict(Counter(r['purpose'] for r in rows)), skipped_foreign=dict(skipped),
                  length=float(lines.length), open_deck_columns=int((bed & water).sum()), world_written=False, train_run_in_game=False)
    write(a.out / 'bed-check.json', report)
    additions = a.out / 'additions'
    write(a.out / 'patch.json', dict(schema='map-cell-patch-v1', id=spec['id'], label=spec['label'], source=spec['source'], edits=rows,
          native_snapshot=spec['native_snapshot'], native_additions=str(additions), error_reports=[str(a.out / 'bed-check.json')],
          views_reviewed_by_root=False, continuation_work=spec['continuation_work']))
    print(json.dumps({k: report[k] for k in ('cells', 'purposes', 'skipped_foreign', 'length', 'open_deck_columns')}, ensure_ascii=False))
    if errors:
        print(json.dumps(errors, ensure_ascii=False)[:1500])
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('native', 'edits'))
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--java', type=Path)
    parser.add_argument('--mtr', type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    globals()[args.mode](args)
