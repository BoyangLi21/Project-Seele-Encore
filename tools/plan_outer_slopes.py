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

from map_pipeline.launch_protection import load as load_launch_protection
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


def in_launch_volume(guard, cell):
    return any(b[0] <= cell[0] <= b[3] and b[1] <= cell[1] <= b[4] and b[2] <= cell[2] <= b[5] for _, b in guard.by_chunk.get((cell[0] >> 4, cell[2] >> 4), ()))


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


def declared(spec, bounds):
    """Registered road and walk columns, and rail columns, inside bounds."""
    x0, z0, x1, z1 = bounds
    shape = (z1 - z0 + 1, x1 - x0 + 1)
    net = np.load(spec['network'])
    nx, nz = int(net['bounds'][0]), int(net['bounds'][1])
    public = np.zeros(shape, bool)
    px0, pz0 = max(x0, nx), max(z0, nz)
    px1, pz1 = min(x1, int(net['bounds'][2])), min(z1, int(net['bounds'][3]))
    if px0 <= px1 and pz0 <= pz1:
        public[pz0 - z0:pz1 - z0 + 1, px0 - x0:px1 - x0 + 1] = (net['road'] | net['walk'])[pz0 - nz:pz1 - nz + 1, px0 - nx:px1 - nx + 1]
    rails = np.zeros(shape, bool)
    for r in read(spec['rails']):
        for x, _, z in r['points']:
            i, j = int(z) - z0, int(x) - x0
            if 0 <= i < shape[0] and 0 <= j < shape[1]:
                rails[i, j] = True
    return public, rails


def author(a):
    spec = read(a.config)
    if a.source:
        spec['source'] = a.source
    source = CapturedSurface(spec['source'], partial=True)
    x0, z0, x1, z1 = spec['bounds']
    top, tree, wet, built, known = columns(Path(spec['source']) / 'source', spec['bounds'])
    sx, sz = source.bounds[:2]
    protected = source.measured['protected'][z0 - sz:z1 - sz + 1, x0 - sx:x1 - sx + 1]
    public, rails = declared(spec, spec['bounds'])
    open_ground = known & (top > -129) & ~built & ~wet
    working = built | wet | public | rails | protected
    distance = ndimage.distance_transform_edt(~working)
    keep_off = ndimage.binary_dilation(public, iterations=spec.get('public_margin', 3)) | ndimage.binary_dilation(rails, iterations=spec.get('rail_margin', 4)) \
        | ndimage.binary_dilation(built | protected, iterations=1) | ndimage.binary_dilation(wet, iterations=1)
    movable = open_ground & ~keep_off
    # Ground left as it is on purpose, as [x0, z0, x1, z1]; its edge anchors the slopes around it.
    for ex0, ez0, ex1, ez1 in spec.get('exclude', ()):
        movable[max(0, ez0 - z0):max(0, ez1 - z0 + 1), max(0, ex0 - x0):max(0, ex1 - x0 + 1)] = False
    # The EVA launch volumes are finite in height, so a column is held only where one of them
    # overlaps the range this column could be dug, filled or cleared of a tree.
    guard = load_launch_protection(spec['launch_world'])
    reach_up = np.where(tree, 40, spec.get('max_fill', 24) + 2)
    lowest, highest = top - spec.get('max_cut', 40) - 1, top + reach_up
    launch_held = np.zeros_like(known)
    for _, (bx, by, bz, BX, BY, BZ) in guard.boxes:
        area = np.s_[max(bz, z0) - z0:max(min(BZ, z1) - z0 + 1, 0), max(bx, x0) - x0:max(min(BX, x1) - x0 + 1, 0)]
        launch_held[area] |= (lowest[area] <= BY) & (highest[area] >= by)
    movable &= ~launch_held
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
            if cell in seen or in_launch_volume(guard, cell):
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

    # Region by region: each decoded region takes about 450 MB and the capture reader keeps them.
    region = None
    for i, j in sorted(zip(*np.nonzero(changed)), key=lambda c: ((int(c[1]) + x0) >> 9, (int(c[0]) + z0) >> 9)):
        x, z, t = int(j + x0), int(i + z0), int(top[i, j])
        if (x >> 9, z >> 9) != region:
            source.editor.regions.clear()
            region = x >> 9, z >> 9
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
            # Stop above anything that is not earth: buried road pieces and brickwork stay whole.
            c = 0
            while c < int(cut[i, j]) and source.state(x, t - c - 1, z).split('[')[0] in EARTH:
                c += 1
            cut[i, j] = c
            if not c:
                continue
            for y in range(t - c + 1, t + 1):
                put((x, y, z), source.state(x, y, z), 'minecraft:air', 'slope cut')
            face = source.state(x, t - c, z)
            if face != TOP:
                put((x, t - c, z), face, TOP, 'slope surface')
        for y in range(t + 1, t + 3):
            state = source.state(x, y, z)
            if state.split('[')[0] in PLANTS and (x, y, z) not in rows and y > t + int(fill[i, j]):
                put((x, y, z), state, 'minecraft:air', 'slope clearance')
    guard.assert_positions(list(rows))
    after = top + fill - cut
    measure = known & (top > -129) & ~built & ~wet
    report = dict(errors=[], bounds=spec['bounds'], cliff_columns=int(cliff.sum()), cut_columns=int((cut > 0).sum()), fill_columns=int((fill > 0).sum()),
                  cells=len(rows), steps_before=steps(top, measure, limit), steps_after=steps(after, measure, limit), skipped=skipped,
                  launch_held_columns=int((launch_held & open_ground).sum()), max_cut=int(cut.max()), max_fill=int(fill.max()), tree_cells=sum(1 for r in rows.values() if r['purpose'].startswith('tree')), world_written=False)
    a.out.mkdir(parents=True, exist_ok=True)
    write(a.out / 'slope-check.json', report)
    np.savez_compressed(a.out / 'slope-map.npz', bounds=spec['bounds'], top=top, after=after, cliff=cliff, cut=cut.astype(np.int16), fill=fill.astype(np.int16), built=built, wet=wet, working=working)
    # One patch per X strip when the config lists them; each is installed as its own batch.
    for strip in spec.get('strips', [dict(id=spec['id'], label=spec['label'], x=[-10**6, 10**6], name='patch', continuation_work=spec['continuation_work'])]):
        edits = [rows[c] for c in sorted(rows) if strip['x'][0] <= c[0] < strip['x'][1]]
        write(a.out / f"{strip.get('name', strip['id'])}.json", dict(schema='map-cell-patch-v1', id=strip['id'], label=strip['label'], source=spec['source'], edits=edits,
                                                                     native_snapshot=spec['native_snapshot'], error_reports=[str((a.out / 'slope-check.json').resolve())], views_reviewed_by_root=False,
                                                                     continuation_work=strip['continuation_work']))
        report.setdefault('strip_cells', {})[strip['id']] = len(edits)
    print(json.dumps(report, ensure_ascii=False))


def compare_captures(before_dir, after_dir, expected):
    """Every cell that differs between two captures, and how the patch cells ended up."""
    wanted = {}
    for cell in expected:
        wanted.setdefault((cell[0] >> 4, cell[2] >> 4), []).append(cell)
    changed, not_applied, stale, uncovered = set(), [], [], set(wanted)
    for path in sorted(Path(after_dir).glob('r.*.npz')):
        other = Path(before_dir) / path.name
        if not other.exists():
            continue
        with np.load(path) as data:
            after_names, after_coords, after_blocks = [str(n) for n in data['palette']], data['coordinates'], data['blocks']
        with np.load(other) as data:
            before_names, before_coords, before_blocks = [str(n) for n in data['palette']], data['coordinates'], data['blocks']
        union = {name: i for i, name in enumerate(sorted(set(after_names) | set(before_names)))}
        after_ids = np.array([union[n] for n in after_names])
        before_ids = np.array([union[n] for n in before_names])
        index = {(int(c[0]), int(c[1])): i for i, c in enumerate(before_coords)}
        for i, (cx, cz) in enumerate(after_coords.tolist()):
            j = index.get((cx, cz))
            if j is None:
                continue
            uncovered.discard((cx, cz))
            now, then = after_ids[after_blocks[i]], before_ids[before_blocks[j]]
            for y, z, x in zip(*np.nonzero(now != then)):
                changed.add((cx * 16 + int(x), int(y) - 128, cz * 16 + int(z)))
            for cell in wanted.get((cx, cz), ()):
                y, z, x = cell[1] + 128, cell[2] & 15, cell[0] & 15
                if after_names[after_blocks[i, y, z, x]] != expected[cell]['after']:
                    not_applied.append(cell)
                if before_names[before_blocks[j, y, z, x]] != expected[cell]['before']:
                    stale.append(cell)
    return changed, not_applied, stale, uncovered


def verify(a):
    """After install, from captures of the batch's area taken just before and just after it."""
    spec, patch = read(a.config), read(a.patch)
    expected = {tuple(e['pos']): e for e in patch['edits']}
    changed, not_applied, stale, uncovered = compare_captures(a.before / 'source', a.after / 'source', expected)
    cells = set(expected) | changed
    bounds = [min(c[0] for c in cells), min(c[2] for c in cells), max(c[0] for c in cells), max(c[2] for c in cells)]
    x0, z0 = bounds[:2]
    top, _, wet, built, known = columns(a.before / 'source', bounds)
    top_after, _, _, _, known_after = columns(a.after / 'source', bounds)
    public, rails = declared(spec, bounds)
    groups = dict(road=public, rail=rails, building=built, water=wet)
    touched = {name: sorted({(c[0], c[2]) for c in changed if mask[c[2] - z0, c[0] - x0]}) for name, mask in groups.items()}
    measure = known & known_after & (top > -129) & ~built & ~wet
    limit = spec.get('cliff', 4)
    cliffs_before, cliffs_after = steps(top, measure, limit), steps(top_after, measure, limit)
    unexpected = sorted(changed - set(expected))
    errors = []
    for name, found in (('patch cells not at their after state', not_applied), ('patch cells whose before state did not match', stale),
                        ('cells changed outside the patch', unexpected), ('chunks of the patch missing from the captures', sorted(uncovered))):
        if found:
            errors.append(f'{len(found)} {name}, first {found[:5]}')
    for name, found in touched.items():
        if found:
            errors.append(f'{len(found)} {name} columns changed, first {found[:5]}')
    if cliffs_after >= cliffs_before:
        errors.append(f'cliffs did not fall: {cliffs_before} before, {cliffs_after} after')
    report = dict(id=patch['id'], errors=errors, area=bounds, patch_cells=len(expected), cells_changed=len(changed), cliffs_before=cliffs_before, cliffs_after=cliffs_after,
                  columns_changed={name: len(found) for name, found in touched.items()}, world_written=False)
    a.out.mkdir(parents=True, exist_ok=True)
    write(a.out / f"verify-{patch['id']}.json", report)
    print(json.dumps(report, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('author', 'verify'))
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--source', help='Capture to plan from, in place of the one in the config')
    parser.add_argument('--patch', type=Path, help='verify: the patch that was installed')
    parser.add_argument('--before', type=Path, help='verify: capture of the area just before the install')
    parser.add_argument('--after', type=Path, help='verify: capture of the area just after the install')
    args = parser.parse_args()
    globals()[args.mode](args)
