"""Rivers, streams and ponds as real water, from surveyed levels or surveyed outlines.

Designed rivers bring their own water level and bed per column. Every other surveyed water area
or centreline gets a shallow channel: its level is one block under its own ground and no higher
than the dry ground beside it. Under a road or a track the channel passes as a culvert below the
surface layer; under a building or a station it stops.

Water must never leave its channel. Before anything is written, every water cell needs water or a
solid block on each side and below. Where a channel steps down, the lower reach's banks must hold
the upper reach's level too, because the overflow runs across it. A column that cannot be held is
lowered, and dropped if lowering does not help. Nothing is written to the world here.
"""
import argparse
from collections import Counter
import gzip
import json
import math
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import shape

from plan_ashi_landscape_r54 import PLANTS, SOIL
from plan_rail_corridor import existing_track
from plan_station_access_corridor import CapturedSurface
from query_blocks import AIR

WATER = 'minecraft:water[level=0]'
RIVER_BED, STREAM_BED = 'minecraft:gravel', 'minecraft:dirt'
TREE = ('_leaves', '_log')
# GSI river centre lines: dry and underground reaches carry no open water.
DRY_CODES = {'5302', '5311', '5312', '5322'}
TRACK_REACH = 2.6


def read(path):
    return json.loads(Path(path).read_text('utf8'))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=1), 'utf8')


def natural(name):
    return name in SOIL or name in PLANTS or name in AIR or name.endswith(TREE) or name == 'minecraft:water'


def surveyed(spec, bx, bz, bX, bZ):
    """Columns under surveyed water areas and centre lines, with the line codes kept apart."""
    zz, xx = np.mgrid[bz:bZ + 1, bx:bX + 1]
    centres = shapely.points(xx.ravel() + .5, zz.ravel() + .5)
    cells = shapely.box(xx.ravel(), zz.ravel(), xx.ravel() + 1, zz.ravel() + 1)
    clip = shapely.box(bx, bz, bX + 1, bZ + 1)
    areas, lines = [], []
    with gzip.open(spec['features'], 'rt', encoding='utf8') as stream:
        for row in json.load(stream)['features']:
            p = row['properties']
            if p.get('source_layer') not in ('WA', 'RvrCL'):
                continue
            g = shape(row['geometry'])
            if not g.intersects(clip):
                continue
            if p['source_layer'] == 'WA':
                areas.append(g)
            elif str(p.get('vt_code')) not in DRY_CODES and not spec.get('areas_only'):
                # Upstream in the mountains only the surveyed river areas are built, not every gully.
                lines.append(g.buffer(spec.get('stream_half_width', .55), cap_style=2))
    area = np.zeros(xx.size, bool)
    stream = np.zeros(xx.size, bool)
    if areas:
        geom = shapely.union_all(areas)
        shapely.prepare(geom)
        area = shapely.contains(geom, centres)
    if lines:
        geom = shapely.union_all(lines)
        shapely.prepare(geom)
        stream = shapely.intersects(geom, cells) & ~area
    return area.reshape(xx.shape), stream.reshape(xx.shape)


def edits(a):
    spec = read(a.config)
    source = CapturedSurface(spec['source'], partial=True)
    sx, sz, sX, sZ = source.bounds
    bx, bz, bX, bZ = spec.get('bounds', [sx, sz, sX, sZ])
    bx, bz, bX, bZ = max(bx, sx + 1), max(bz, sz + 1), min(bX, sX - 1), min(bZ, sZ - 1)
    shape_ = (bZ - bz + 1, bX - bx + 1)
    area = np.s_[bz - sz:bZ - sz + 1, bx - sx:bX - sx + 1]
    ground = source.measured['top'][area].astype(int)
    highest = source.measured['highest'][area].astype(int)
    full = source.measured['full'][area].copy()

    level = np.full(shape_, -32768, int)
    bed = np.full(shape_, -32768, int)
    designed = np.zeros(shape_, bool)
    for path in spec.get('profiles', ()):
        with np.load(Path(path) / 'river-profile.npz') as p:
            px, pz, _, _ = map(int, p['bounds'])
            sl = np.s_[bz - pz:bZ - pz + 1, bx - px:bX - px + 1]
            wet = p['wet'][sl]
            level[wet] = p['level'][sl][wet]
            bed[wet] = p['bed'][sl][wet]
            designed |= wet
    river, stream = surveyed(spec, bx, bz, bX, bZ)
    river &= ~designed
    stream &= ~designed & ~river
    wet = designed | river | stream

    with np.load(Path(spec['authority']) / 'network.npz') as f:
        ax, az, _, _ = map(int, f['bounds'])
        public = (f['walk'] | f['road'])[bz - az:bZ - az + 1, bx - ax:bX - ax + 1]
    station = np.zeros(shape_, bool)
    zz, xx = np.mgrid[bz:bZ + 1, bx:bX + 1]
    for a0, _, c0, a1, _, c1 in read(Path(spec['authority']) / 'station-volumes.json'):
        station[(xx >= a0) & (xx <= a1) & (zz >= c0) & (zz <= c1)] = True
    tracks, track_heights = existing_track(spec['native_snapshot'], shapely.box(bx - 3, bz - 3, bX + 4, bZ + 4))
    near_track = np.zeros(shape_, bool)
    if tracks is not None:
        gap, _ = tracks.query(np.c_[xx.ravel() + .5, zz.ravel() + .5])
        near_track = (gap < TRACK_REACH).reshape(shape_)

    # A structure stands in a column when something solid rises above its soil.
    built = (highest > ground) & full
    for iz, ix in np.argwhere(built & wet):
        x, z = int(xx[iz, ix]), int(zz[iz, ix])
        if all(natural(source.state(x, y, z).split('[')[0]) for y in range(ground[iz, ix] + 1, highest[iz, ix] + 1)):
            built[iz, ix] = False
    # A column holding any water above its ground is a water body already: a ship or a pier
    # over the sea must not turn it into a channel to be cut.
    standing = np.zeros(shape_, bool)
    standing_top = np.full(shape_, -32768, int)
    for iz, ix in np.argwhere((highest > ground) & full):
        x, z = int(xx[iz, ix]), int(zz[iz, ix])
        for y in range(int(ground[iz, ix]) + 1, int(highest[iz, ix]) + 1):
            if 'water' in source.state(x, y, z):
                standing[iz, ix] = True
                standing_top[iz, ix] = y
    built &= ~standing
    # Only designed rivers and streams pass under a surface; a surveyed water area under paving
    # is land on purpose, such as a quay, and stays land.
    culvert = (designed | stream) & (public | near_track) & full & ~standing
    # A column with no soil found (all built, or bare void) has no ground to cut a channel into.
    blocked = wet & ~standing & ((built & ~culvert) | station | ~full | (ground < -120) | (river & (public | near_track)))
    wet &= ~blocked
    wet |= standing
    # A culvert keeps the surface block and the one under it as its deck.
    deck = np.where(culvert, highest - 1, 32767)

    shallow = (river | stream) & wet
    depth = np.where(river, spec.get('river_depth', 2), 1)
    neighbours = ((1, 0), (-1, 0), (0, 1), (0, -1))
    dry_min = np.full(shape_, 32767, int)
    for dz, dx in neighbours:
        shifted = np.full(shape_, 32767, int)
        # A neighbour without captured soil gives no bank height; holds() still checks it.
        src = np.where(wet | ~full | (ground < -120), 32767, ground)
        ys, xs = slice(max(dz, 0), shape_[0] + min(dz, 0)), slice(max(dx, 0), shape_[1] + min(dx, 0))
        yd, xd = slice(max(-dz, 0), shape_[0] + min(-dz, 0)), slice(max(-dx, 0), shape_[1] + min(-dx, 0))
        shifted[yd, xd] = src[ys, xs]
        dry_min = np.minimum(dry_min, shifted)
    level = np.where(shallow, np.minimum(ground - 1, dry_min), level)
    level = np.where(culvert, np.minimum(level, deck - 1), level)
    bed = np.where(shallow | (culvert & ~designed), level - depth, bed)
    # Designed water sits on low ground with a raised bank; this pass only cuts, so a level
    # above the ground beside it comes down to that ground.
    level = np.where(designed, np.minimum(level, np.maximum(dry_min, bed + 1)), level)
    level = np.where(standing, standing_top, level)
    bed = np.where(standing, ground, bed)
    # Air under the surface means a hull, a deck or a cave, not soil to cut into: a ship's
    # stone deck would otherwise flood its hold.
    hollow = np.zeros(shape_, bool)
    for iz, ix in np.argwhere(wet & ~standing):
        x, z = int(xx[iz, ix]), int(zz[iz, ix])
        if any(source.state(x, y, z).split('[')[0] in AIR
               for y in range(int(bed[iz, ix]), min(int(level[iz, ix]), int(ground[iz, ix]) - 1) + 1)):
            hollow[iz, ix] = True
    wet &= ~hollow

    def holds(iz, ix, height):
        """Solid at `height` in a dry column, or water at least that high in a wet one."""
        if not (0 <= iz < shape_[0] and 0 <= ix < shape_[1]):
            return False
        if wet[iz, ix]:
            return level[iz, ix] >= height
        if not full[iz, ix]:
            return False
        if ground[iz, ix] >= height and not hollow[iz, ix]:
            return True
        name = source.state(int(xx[iz, ix]), height, int(zz[iz, ix])).split('[')[0]
        # Water already there joins this water; anything else must be a solid block.
        return name not in AIR and name not in PLANTS

    dropped = Counter()
    for _ in range(spec.get('lowering_passes', 4)):
        changed = 0
        for iz, ix in np.argwhere(wet & ~standing):
            L = level[iz, ix]
            if L <= bed[iz, ix]:
                wet[iz, ix] = False
                dropped['no depth'] += 1
                changed += 1
                continue
            ok = True
            for dz, dx in neighbours:
                n = (iz + dz, ix + dx)
                if not (0 <= n[0] < shape_[0] and 0 <= n[1] < shape_[1]):
                    ok = False
                    break
                if wet[n]:
                    if level[n] < L - 1:
                        ok = False
                        break
                    if level[n] < L:
                        # Overflow crosses the lower column; its dry sides must stand that high.
                        for ez, ex in neighbours:
                            m = (n[0] + ez, n[1] + ex)
                            if m == (iz, ix):
                                continue
                            inside = 0 <= m[0] < shape_[0] and 0 <= m[1] < shape_[1]
                            if not inside or (not wet[m] and not holds(*m, L)):
                                ok = False
                elif not holds(*n, L):
                    ok = False
                if not ok:
                    break
            if not ok:
                level[iz, ix] -= 1
                changed += 1
        if not changed:
            break
    for iz, ix in np.argwhere(wet & ~standing):
        if level[iz, ix] <= bed[iz, ix]:
            wet[iz, ix] = False
            dropped['lowered to its bed'] += 1
    keep_out = [tuple(b) for b in spec.get('keep_out', ())]

    rows, skipped = {}, Counter()

    def put(x, y, z, state, purpose):
        before = source.state(x, y, z)
        if before == state:
            return
        name = before.split('[')[0]
        if not natural(name):
            skipped[name] += 1
            return
        rows[x, y, z] = dict(pos=[x, y, z], before=before, after=state, purpose=purpose)

    for iz, ix in np.argwhere(wet & ~standing):
        x, z, L, b = int(xx[iz, ix]), int(zz[iz, ix]), int(level[iz, ix]), int(bed[iz, ix])
        if any(k[0] <= x <= k[2] and k[1] <= z <= k[3] for k in keep_out):
            continue
        top = int(deck[iz, ix]) - 1 if culvert[iz, ix] else max(int(highest[iz, ix]), L)
        put(x, b, z, RIVER_BED if (designed[iz, ix] or river[iz, ix]) else STREAM_BED, 'channel bed')
        for y in range(b + 1, L + 1):
            put(x, y, z, WATER, 'culvert water' if culvert[iz, ix] else 'water')
        for y in range(L + 1, top + 1):
            name = source.state(x, y, z).split('[')[0]
            if name not in AIR and 'water' not in name:
                put(x, y, z, 'minecraft:air', 'channel cut')
    report = dict(errors=[], cells=len(rows), purposes=dict(Counter(r['purpose'] for r in rows.values())),
                  wet_columns=int(wet.sum()), standing_columns=int(standing.sum()), designed_columns=int((wet & designed).sum()), river_columns=int((wet & river).sum()),
                  stream_columns=int((wet & stream).sum()), culvert_columns=int((wet & culvert).sum()),
                  blocked_columns=int(blocked.sum()), hollow_columns=int(hollow.sum()), dropped=dict(dropped), skipped_built=dict(skipped.most_common(12)),
                  world_written=False)
    a.out.mkdir(parents=True, exist_ok=True)
    write(a.out / 'water-check.json', report)
    write(a.out / 'patch.json', dict(schema='map-cell-patch-v1', id=spec['id'], label=spec['label'], source=spec['source'],
          edits=[rows[k] for k in sorted(rows)], native_snapshot=spec['native_snapshot'], error_reports=[str(a.out / 'water-check.json')],
          views_reviewed_by_root=False, continuation_work=spec['continuation_work']))
    print(json.dumps({k: report[k] for k in ('cells', 'purposes', 'wet_columns', 'standing_columns', 'designed_columns', 'river_columns', 'stream_columns',
                                              'culvert_columns', 'blocked_columns', 'hollow_columns', 'dropped')}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('edits',))
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    globals()[args.mode](args)
