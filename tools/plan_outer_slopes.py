"""Grade the artificial cliffs left at the edges of facility pads, as one cell patch.

A cliff is a step of four or more blocks between neighbouring columns of open
ground. The side next to a building, road, rail or water is the working side
and stays as built: a sunken pad has its hill cut back, a raised pad gets fill
at its foot. Every new surface is a cone of at most one block per block from
the cliff, bounded by cones from the columns that may not change, so grading
cannot make a new step against a road or a wall. A tree on a changed column goes
whole; the forest pass replants afterwards. The actual world is never opened.
"""
import argparse
from collections import deque
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

from plan_ashi_landscape_r54 import PLANTS, SOIL
from plan_station_access_corridor import CapturedSurface
from query_blocks import AIR

TOP, FILL = 'minecraft:grass_block[snowy=false]', 'minecraft:dirt'
EARTH = SOIL - {'minecraft:gravel', 'minecraft:sand', 'minecraft:mud', 'minecraft:clay'}
OPEN = AIR | PLANTS


def read(path):
    return json.loads(Path(path).read_text('utf8'))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=1), 'utf8')


def is_tree(name):
    return name.endswith(('_log', '_leaves', '_wood'))


def is_wet(name):
    return name in ('minecraft:water', 'minecraft:lava', 'minecraft:seagrass', 'minecraft:tall_seagrass', 'minecraft:kelp', 'minecraft:kelp_plant')


def columns(source_dir, bounds):
    """Per column: highest earth, and whether trees, water or anything built stand above it."""
    x0, z0, x1, z1 = bounds
    shape = (z1 - z0 + 1, x1 - x0 + 1)
    top = np.full(shape, -129, np.int16)
    tree, wet, built, known = (np.zeros(shape, bool) for _ in range(4))
    ys = np.arange(-128, 320, dtype=np.int16)[:, None, None]
    for path in sorted(Path(source_dir).glob('r.*.npz')):
        rx, rz = map(int, path.stem.split('.')[1:3])
        if rx * 512 > x1 or (rx + 1) * 512 <= x0 or rz * 512 > z1 or (rz + 1) * 512 <= z0:
            continue
        with np.load(path) as data:
            names = [str(s).split('[')[0] for s in data['palette']]
            coords, blocks = data['coordinates'], data['blocks']
        soil = np.array([n in SOIL for n in names])
        clear = np.array([n in OPEN for n in names])
        trees = np.array([is_tree(n) for n in names])
        water = np.array([is_wet(n) for n in names])
        other = ~(soil | clear | trees | water)
        for (cx, cz), b in zip(coords, blocks):
            ax, az = int(cx) * 16 - x0, int(cz) * 16 - z0
            if ax + 16 <= 0 or az + 16 <= 0 or ax >= shape[1] or az >= shape[0]:
                continue
            t = np.where(soil[b], ys, -129).max(0)
            def high(mask):
                return np.where(mask[b], ys, -129).max(0)
            sx, sz = max(0, -ax), max(0, -az)
            ex, ez = min(16, shape[1] - ax), min(16, shape[0] - az)
            area = np.s_[az + sz:az + ez, ax + sx:ax + ex]
            part = np.s_[sz:ez, sx:ex]
            top[area] = t[part]
            tree[area] = high(trees)[part] > t[part]
            wet[area] = high(water)[part] > t[part]
            built[area] = high(other)[part] > t[part]
            known[area] = True
    return top, tree, wet, built, known


def cone(seed, height, sign, reach, slope):
    """Chamfer cone from seed cells: rising (+1) or falling (-1) away from them at the given slope."""
    empty = sign * 9999.0
    value = np.where(seed, height.astype(np.float32), empty).astype(np.float32)
    for _ in range(reach):
        before = value
        for di, dj, w in ((0, 1, 1), (0, -1, 1), (1, 0, 1), (-1, 0, 1), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)):
            shifted = np.full_like(value, empty)
            si = np.s_[max(0, di):value.shape[0] + min(0, di)]
            ti = np.s_[max(0, -di):value.shape[0] + min(0, -di)]
            sj = np.s_[max(0, dj):value.shape[1] + min(0, dj)]
            tj = np.s_[max(0, -dj):value.shape[1] + min(0, -dj)]
            shifted[ti, tj] = value[si, sj] + sign * slope * w
            value = np.minimum(value, shifted) if sign > 0 else np.maximum(value, shifted)
        if np.array_equal(value, before):
            break
    return value


def monotone(surface, changed, seed, top, sign):
    """Walk changed columns outward from the seeds; sign=1 may only rise, sign=-1 may only fall."""
    order = ndimage.distance_transform_edt(~seed)
    out = surface.copy()
    ci, cj = np.nonzero(changed)
    for k in np.argsort(order[ci, cj], kind='stable'):
        i, j = int(ci[k]), int(cj[k])
        best = None
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                u, v = i + di, j + dj
                if not (di or dj) or not (0 <= u < out.shape[0] and 0 <= v < out.shape[1]) or order[u, v] >= order[i, j]:
                    continue
                # A cut follows the bench it grew from. A fill also sees the fixed columns
                # between it and its edge, which is what stops it behind a road margin.
                if sign > 0 and not (changed[u, v] or seed[u, v]):
                    continue
                best = out[u, v] if best is None else max(best, out[u, v])
        if best is None:
            continue
        out[i, j] = max(out[i, j], min(best, top[i, j])) if sign > 0 else min(out[i, j], max(best, top[i, j]))
    return out


def worthwhile(changed, before, after, mask, limit, columns_per_step):
    """Connected groups of changed columns that close enough scarps to justify themselves."""
    groups, count = ndimage.label(changed, structure=np.ones((3, 3), bool))
    if not count:
        return changed
    closed = np.zeros(count + 1)
    for u, v in ((np.s_[:, 1:], np.s_[:, :-1]), (np.s_[1:, :], np.s_[:-1, :])):
        pair = mask[u] & mask[v]
        was, now = np.abs(before[u] - before[v]) >= limit, np.abs(after[u] - after[v]) >= limit
        touched = np.maximum(groups[u], groups[v])
        closed += np.bincount(touched[pair & was & ~now], minlength=count + 1)
        closed -= np.bincount(touched[pair & ~was & now], minlength=count + 1)
    size = np.bincount(groups.ravel(), minlength=count + 1)
    keep = size <= columns_per_step * closed
    keep[0] = False
    return keep[groups]


def steps(height, mask, limit):
    count = 0
    for a, b in ((np.s_[:, 1:], np.s_[:, :-1]), (np.s_[1:, :], np.s_[:-1, :])):
        count += int(((np.abs(height[a].astype(int) - height[b].astype(int)) >= limit) & mask[a] & mask[b]).sum())
    return count


def author(a):
    spec = read(a.config)
    source = CapturedSurface(spec['source'], partial=True)
    x0, z0, x1, z1 = spec['bounds']
    top, tree, wet, built, known = columns(Path(spec['source']) / 'source', spec['bounds'])
    sx, sz = source.bounds[:2]
    protected = source.measured['protected'][z0 - sz:z1 - sz + 1, x0 - sx:x1 - sx + 1]
    net = np.load(spec['network'])
    nx, nz = int(net['bounds'][0]), int(net['bounds'][1])
    public = np.zeros_like(known)
    px0, pz0 = max(x0, nx), max(z0, nz)
    px1, pz1 = min(x1, int(net['bounds'][2])), min(z1, int(net['bounds'][3]))
    public[pz0 - z0:pz1 - z0 + 1, px0 - x0:px1 - x0 + 1] = (net['road'] | net['walk'])[pz0 - nz:pz1 - nz + 1, px0 - nx:px1 - nx + 1]
    rails = np.zeros_like(known)
    for r in read(spec['rails']):
        for x, _, z in r['points']:
            i, j = int(z) - z0, int(x) - x0
            if 0 <= i < rails.shape[0] and 0 <= j < rails.shape[1]:
                rails[i, j] = True
    open_ground = known & (top > -129) & ~built & ~wet
    working = built | wet | public | rails | protected
    distance = ndimage.distance_transform_edt(~working)
    keep_off = ndimage.binary_dilation(public, iterations=spec.get('public_margin', 3)) | ndimage.binary_dilation(rails, iterations=spec.get('rail_margin', 4)) \
        | ndimage.binary_dilation(built | protected, iterations=1) | ndimage.binary_dilation(wet, iterations=1)
    movable = open_ground & ~keep_off
    limit, near, slope = spec.get('cliff', 4), spec.get('protect', 6), spec.get('slope', 1.0)
    cliff = np.zeros_like(known)
    cut_seed, fill_seed = np.zeros_like(known), np.zeros_like(known)
    for u, v in ((np.s_[:, 1:], np.s_[:, :-1]), (np.s_[1:, :], np.s_[:-1, :])):
        jump = top[u].astype(int) - top[v].astype(int)
        hit = open_ground[u] & open_ground[v] & (np.abs(jump) >= limit)
        for hi_, lo_, s in ((u, v, 1), (v, u, -1)):
            pair = hit & (jump * s > 0)
            # The side nearer to a building, road, rail or water is the anchor and the other side
            # changes: a low side beside the works has its hill cut back, a high side beside
            # them (an embankment or raised pad) gets fill at its foot.
            anchored_low = (distance[lo_] <= distance[hi_]) & ((distance[lo_] <= near) | ~movable[lo_])
            cuts = pair & movable[hi_] & anchored_low
            fills = pair & movable[lo_] & ~anchored_low
            cut_seed[lo_] |= cuts
            fill_seed[hi_] |= fills
            cliff[hi_] |= cuts | fills
            cliff[lo_] |= cuts | fills
    fixed = known & (top > -129) & ~movable
    reach = spec.get('reach', 40)
    cut_cone, fill_cone = cone(cut_seed, top, 1, reach, slope), cone(fill_seed, top, -1, spec.get('fill_reach', 24), slope)
    below_fixed, above_fixed = cone(fixed, top, -1, reach, slope), cone(fixed, top, 1, reach, slope)
    lower = np.ceil(np.maximum(cut_cone, below_fixed) - 1e-6).astype(int)
    raised = np.floor(np.minimum(fill_cone, above_fixed) + 1e-6).astype(int)
    cut = np.where(movable, np.clip(top - lower, 0, spec.get('max_cut', 40)), 0)
    cut[cut_cone > 9000] = 0
    # Where a cone from a fixed rim meets the cone from the pit the cut dips again on its way
    # out. Walking outward from the pit the surface may only rise, up to the original ground.
    if cut.any():
        cut = top - monotone(top - cut, cut > 0, cut_seed, top, 1)
    fill = np.where(movable, np.clip(raised - top, 0, spec.get('max_fill', 24)), 0)
    fill[(fill_cone < -9000) | (cut > 0)] = 0
    # The same rule falling away from a raised edge. Fill cut off from its edge by a fixed ring
    # (a road or building margin) would otherwise stand as a mound on flat ground.
    if fill.any():
        fill = monotone(top + fill, fill > 0, fill_seed, top, -1) - top
        fill = np.where(worthwhile(fill > 0, top, top + fill, open_ground, limit, spec.get('fill_columns_per_step', 12)), fill, 0)
    changed = (cut > 0) | (fill > 0)
    rows, skipped = {}, {}

    def put(cell, before, state, purpose):
        rows[cell] = dict(pos=list(cell), before=before, after=state, purpose=purpose)

    seen = set()

    def clear_tree(start):
        queue = deque([start])
        while queue:
            cell = queue.popleft()
            if cell in seen:
                continue
            seen.add(cell)
            try:
                state = source.state(*cell)
            except ValueError:
                continue
            if not is_tree(state.split('[')[0]):
                continue
            put(cell, state, 'minecraft:air', 'tree on graded ground')
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        queue.append((cell[0] + dx, cell[1] + dy, cell[2] + dz))

    for i, j in zip(*np.nonzero(changed)):
        x, z, t = int(j + x0), int(i + z0), int(top[i, j])
        ground = source.state(x, t, z)
        if ground.split('[')[0] not in EARTH:
            skipped[ground.split('[')[0]] = skipped.get(ground.split('[')[0], 0) + 1
            cut[i, j], fill[i, j] = 0, 0
            continue
        if tree[i, j]:
            for y in range(t + 1, t + 40):
                if is_tree(source.state(x, y, z).split('[')[0]):
                    clear_tree((x, y, z))
        if fill[i, j]:
            f = int(fill[i, j])
            if ground != FILL:
                put((x, t, z), ground, FILL, 'slope body')
            for y in range(t + 1, t + f + 1):
                put((x, y, z), source.state(x, y, z), TOP if y == t + f else FILL, 'slope surface' if y == t + f else 'slope body')
        else:
            c = int(cut[i, j])
            for y in range(t - c + 1, t + 1):
                put((x, y, z), source.state(x, y, z), 'minecraft:air', 'slope cut')
            face = source.state(x, t - c, z)
            if face != TOP:
                put((x, t - c, z), face, TOP, 'slope surface')
        for y in range(t + 1, t + 3):
            state = source.state(x, y, z)
            if state.split('[')[0] in PLANTS and (x, y, z) not in rows and y > t + int(fill[i, j]):
                put((x, y, z), state, 'minecraft:air', 'slope clearance')
    after = top + fill - cut
    measure = known & (top > -129) & ~built & ~wet
    report = dict(errors=[], bounds=spec['bounds'], cliff_columns=int(cliff.sum()), cut_columns=int((cut > 0).sum()), fill_columns=int((fill > 0).sum()),
                  cells=len(rows), steps_before=steps(top, measure, limit), steps_after=steps(after, measure, limit), skipped=skipped,
                  max_cut=int(cut.max()), max_fill=int(fill.max()), tree_cells=sum(1 for r in rows.values() if r['purpose'].startswith('tree')), world_written=False)
    a.out.mkdir(parents=True, exist_ok=True)
    write(a.out / 'slope-check.json', report)
    np.savez_compressed(a.out / 'slope-map.npz', bounds=spec['bounds'], top=top, after=after, cliff=cliff, cut=cut.astype(np.int16), fill=fill.astype(np.int16), built=built, wet=wet, working=working)
    write(a.out / 'patch.json', dict(schema='map-cell-patch-v1', id=spec['id'], label=spec['label'], source=spec['source'], edits=[rows[c] for c in sorted(rows)],
                                     native_snapshot=spec['native_snapshot'], error_reports=[str((a.out / 'slope-check.json').resolve())], views_reviewed_by_root=False,
                                     continuation_work=spec['continuation_work']))
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('author',))
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    globals()[args.mode](args)
