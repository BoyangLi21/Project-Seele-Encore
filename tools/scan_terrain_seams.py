"""Find terrain seams in a scan mosaic made by scan_surface_columns.py.

Three kinds, each away from anything built and from water:
height  a jump in natural ground between neighbouring columns that the slope on either side does
        not explain, joined into lines; straight long lines are seams between terrain passes,
        ragged short ones are real cliffs.
surface a straight boundary where the ground block changes kind (grass, rock, gravel, sand).
trees   a straight line with forest on one side and bare ground on the other.
Writes seams.json (raw, by score), seams-classified.json (classified, merged) and per-tile mask npz files.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

X0, Z0 = -5120, -8704
OX, OZ = X0, Z0          # origin of the tile being analysed
ROCK = ('stone', 'andesite', 'diorite', 'granite', 'deepslate', 'tuff', 'calcite', 'basalt', 'terracotta')


def material_class(name):
    n = name.split(':')[-1]
    if n in ('grass_block', 'dirt', 'coarse_dirt', 'podzol', 'rooted_dirt', 'mycelium', 'moss_block', 'farmland', 'mud'):
        return 1
    if any(r in n for r in ROCK):
        return 2
    if n == 'gravel':
        return 3
    if 'sand' in n:
        return 4
    return 0


def natural_mask(d, pal_kind):
    g, s, w = d['ground'], d['solid'], d['water']
    valid = g > -30000
    built = (pal_kind[d['solid_id']] == 4) & (s > g)
    nat = valid & ~built & (w < g)
    # keep two columns clear of anything built or wet, and of unscanned chunks
    return ndimage.binary_erosion(nat, iterations=3, border_value=0)


def describe(lab, idx, extra):
    out = []
    objs = ndimage.find_objects(lab)
    for k, sl in enumerate(objs, 1):
        if sl is None:
            continue
        sub = lab[sl] == k
        zz, xx = np.nonzero(sub)
        n = len(zz)
        if n < extra['min_cells']:
            continue
        zz = zz + sl[0].start
        xx = xx + sl[1].start
        pts = np.stack([xx, zz], 1).astype(float)
        c = pts - pts.mean(0)
        ev, evec = np.linalg.eigh(c.T @ c / n)
        length = 4 * np.sqrt(max(ev[1], 1e-9)) * 1.0 + 1
        width = 4 * np.sqrt(max(ev[0], 1e-9)) + 1
        vals = extra['value'][zz, xx]
        out.append(dict(cells=int(n), x=[int(xx.min() + OX), int(xx.max() + OX)], z=[int(zz.min() + OZ), int(zz.max() + OZ)],
                        centre=[int(np.median(xx) + OX), int(np.median(zz) + OZ)], length=round(float(length), 1),
                        straightness=round(float(length / width), 1),
                        direction=round(float(np.degrees(np.arctan2(evec[1, 1], evec[0, 1])) % 180), 1),
                        mean=round(float(np.abs(vals).mean()), 2), max=int(np.abs(vals).max()),
                        axis_aligned=bool(min(abs(np.degrees(np.arctan2(evec[1, 1], evec[0, 1])) % 90 - a) for a in (0, 90)) < 4),
                        chunk_line=chunk_alignment(xx + OX, zz + OZ, evec[:, 1])))
    return out


def chain(segments, gap=48):
    """Join axis segments lying on one line (within a column) with gaps up to gap into one entry."""
    groups = {}
    for s in segments:
        along_x = s['direction'] < 45 or s['direction'] > 135
        const = (s['z'][0] + s['z'][1]) // 2 if along_x else (s['x'][0] + s['x'][1]) // 2
        groups.setdefault((along_x, const), []).append(s)
    keys = sorted(groups)
    merged, used = [], set()
    for key in keys:
        if key in used:
            continue
        pool = []
        for d in (-1, 0, 1):
            k = (key[0], key[1] + d)
            if k in groups and k not in used:
                pool += groups[k]
                used.add(k)
        along_x = key[0]
        pool.sort(key=lambda s: s['x'][0] if along_x else s['z'][0])
        run = [pool[0]]
        for s in pool[1:]:
            end = max(r['x'][1] if along_x else r['z'][1] for r in run)
            start = s['x'][0] if along_x else s['z'][0]
            if start - end <= gap:
                run.append(s)
            else:
                merged.append(join(run))
                run = [s]
        merged.append(join(run))
    return merged


def join(run):
    if len(run) == 1:
        return run[0]
    out = dict(run[0])
    out['x'] = [min(r['x'][0] for r in run), max(r['x'][1] for r in run)]
    out['z'] = [min(r['z'][0] for r in run), max(r['z'][1] for r in run)]
    out['centre'] = [(out['x'][0] + out['x'][1]) // 2, (out['z'][0] + out['z'][1]) // 2]
    out['cells'] = sum(r['cells'] for r in run)
    out['pieces'] = len(run)
    out['span'] = max(out['x'][1] - out['x'][0], out['z'][1] - out['z'][0]) + 1
    out['length'] = round(sum(r['length'] for r in run), 1)
    out['mean'] = round(sum(r['mean'] * r['cells'] for r in run) / out['cells'], 2)
    out['max'] = max(r['max'] for r in run)
    out['score'] = round(sum(r['score'] for r in run), 1)
    return out


def chunk_alignment(x, z, v):
    """Share of the line lying on a chunk boundary (a column at 15/0 of a chunk), for axis lines."""
    if abs(v[0]) > abs(v[1]):          # runs along x: test z
        r = np.mod(z, 16)
    else:
        r = np.mod(x, 16)
    return round(float(np.isin(r, (0, 15)).mean()), 2)


def analyse(d, pal, pal_kind, mask_path):
    nat = natural_mask(d, pal_kind)
    g = d['ground'].astype(np.int32)
    results = {}

    # height: residual of each neighbour step against the steps two columns either side
    resid = np.zeros(g.shape, np.int32)
    for axis in (0, 1):
        st = np.diff(g, axis=axis)
        pad = [(0, 0), (0, 0)]
        pad[axis] = (3, 3)
        sp = np.pad(st, pad, mode='edge')
        sl = lambda o: sp[tuple(slice(3 + o, 3 + o + st.shape[axis]) if ax == axis else slice(None) for ax in range(2))]
        trend = np.median(np.stack([sl(-2), sl(-1), sl(1), sl(2)]), 0)
        r = (st - np.round(trend)).astype(np.int32)
        both = nat[tuple(slice(0, -1) if ax == axis else slice(None) for ax in range(2))] & nat[tuple(slice(1, None) if ax == axis else slice(None) for ax in range(2))]
        r[~both] = 0
        full = np.zeros(g.shape, np.int32)
        full[tuple(slice(0, -1) if ax == axis else slice(None) for ax in range(2))] = r
        resid = np.where(np.abs(full) > np.abs(resid), full, resid)
    strong = np.abs(resid) >= 3
    lab, n = ndimage.label(ndimage.binary_dilation(strong, iterations=1) & nat, structure=np.ones((3, 3)))
    lab = np.where(strong, lab, 0)
    height = describe(lab, None, dict(min_cells=16, value=resid))
    for s in height:
        s['kind'] = 'height'
        s['score'] = round(s['length'] * s['mean'] * min(1.0, s['straightness'] / 8), 1)
    results['height'] = height

    # surface: straight material boundaries
    mclass = np.array([material_class(s) for s in pal], np.int8)[d['ground_id']]
    mclass[~nat] = 0
    edge = np.zeros(g.shape, bool)
    edge[:, :-1] |= (mclass[:, :-1] != mclass[:, 1:]) & (mclass[:, :-1] > 0) & (mclass[:, 1:] > 0)
    edge[:-1] |= (mclass[:-1] != mclass[1:]) & (mclass[:-1] > 0) & (mclass[1:] > 0)
    lab, n = ndimage.label(edge, structure=np.ones((3, 3)))
    surf = [s for s in describe(lab, None, dict(min_cells=24, value=edge.astype(np.int32))) if s['straightness'] >= 12]
    for s in surf:
        s['kind'] = 'surface'
        s['score'] = round(s['length'] * min(1.0, s['straightness'] / 20) * 0.5, 1)
    results['surface'] = surf

    # trees: axis lines with forest on one side, bare ground on the other
    tree = np.isin(pal_kind[d['top_id']], (2,)) & (d['top'] > d['ground'] + 2)
    strip = 6
    lines = []
    for axis in (0, 1):
        t = tree.astype(np.float32)
        nn = nat.astype(np.float32)
        # mean over strip columns before and after each boundary, then along 16 cells of the line
        ct = ndimage.uniform_filter1d(t, strip, axis=axis, mode='constant')
        cn = ndimage.uniform_filter1d(nn, strip, axis=axis, mode='constant')
        # centred window [i-3, i+2] for 6: shift so one ends at i and the other starts at i+1
        before, after = np.roll(ct, 2, axis), np.roll(ct, -4, axis)
        nb, na = np.roll(cn, 2, axis), np.roll(cn, -4, axis)
        along = 1 - axis
        seg = 16
        kb = ndimage.uniform_filter1d(before, seg, axis=along)
        ka = ndimage.uniform_filter1d(after, seg, axis=along)
        ok = ndimage.minimum_filter1d(np.minimum(nb, na), seg, axis=along) > .99
        cut = ok & (((kb > .45) & (ka < .04)) | ((ka > .45) & (kb < .04)))
        lab, n = ndimage.label(cut, structure=np.array([[0, 1, 0], [0, 1, 0], [0, 1, 0]]) if axis == 1 else np.array([[0, 0, 0], [1, 1, 1], [0, 0, 0]]))
        for s in describe(lab, None, dict(min_cells=24, value=cut.astype(np.int32))):
            s['kind'] = 'trees'
            s['score'] = round(s['length'] * 0.4, 1)
            lines.append(s)
    results['trees'] = lines

    # steps: small but steady offsets across a straight axis line, the mark of two terrain passes
    # meeting; a ramp of a few columns between them still shows, real slopes average out.
    gf = g.astype(np.float32)
    steps = []
    resid_line = np.zeros(g.shape, np.float32)
    for axis in (0, 1):
        c3 = ndimage.uniform_filter1d(gf, 3, axis=axis)
        r = (np.roll(c3, -2, axis) - np.roll(c3, 1, axis)) - (np.roll(c3, -5, axis) - np.roll(c3, 4, axis)) / 3
        okn = ndimage.minimum_filter1d(nat.astype(np.uint8), 13, axis=axis) > 0
        r[~okn] = 0
        along = 1 - axis
        seg = 32
        mean = ndimage.uniform_filter1d(r, seg, axis=along)
        agree = ndimage.uniform_filter1d(((np.sign(r) == np.sign(mean)) & (np.abs(r) >= .67)).astype(np.float32), seg, axis=along)
        full = ndimage.minimum_filter1d(okn.astype(np.uint8), seg, axis=along) > 0
        hit = full & (np.abs(mean) >= 1.5) & (agree >= .7)
        resid_line = np.where(hit & (np.abs(mean) > np.abs(resid_line)), mean, resid_line)
        lab, n = ndimage.label(hit, structure=np.array([[0, 1, 0], [0, 1, 0], [0, 1, 0]]) if axis == 1 else np.array([[0, 0, 0], [1, 1, 1], [0, 0, 0]]))
        for s in describe(lab, None, dict(min_cells=24, value=mean)):
            s['kind'] = 'step'
            s['score'] = round(s['length'] * s['mean'] * .8, 1)
            steps.append(s)
    results['step'] = steps
    np.savez_compressed(mask_path, origin=np.array([OX, OZ]), resid=resid.astype(np.int8), nat=nat, edge=edge, tree=tree, step=np.round(resid_line * 4).astype(np.int8))
    return results


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mosaic', type=Path, required=True, help='folder of .npy layers from the scan mosaic')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--bounds', type=int, nargs=4, help='x0 z0 x1 z1 to limit the scan')
    p.add_argument('--tile', type=int, default=2048)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / 'tiles').mkdir(exist_ok=True)
    layers = {k: np.load(a.mosaic / f'{k}.npy', mmap_mode='r') for k in ('ground', 'solid', 'top', 'water', 'ground_id', 'solid_id', 'top_id')}
    pal = [str(s) for s in np.load(a.mosaic / 'palette.npy')]
    import scan_surface_columns as sc
    pal_kind = np.array([sc.kind(s) for s in pal], np.int8)
    nz, nx = layers['ground'].shape
    bx0, bz0, bx1, bz1 = a.bounds if a.bounds else (X0, Z0, X0 + nx, Z0 + nz)
    results = {'height': [], 'surface': [], 'trees': [], 'step': []}
    pad = 64
    global OX, OZ
    for tz in range(bz0, bz1, a.tile):
        for tx in range(bx0, bx1, a.tile):
            z0, z1 = max(Z0, tz - pad), min(Z0 + nz, min(bz1, tz + a.tile) + pad)
            x0, x1 = max(X0, tx - pad), min(X0 + nx, min(bx1, tx + a.tile) + pad)
            d = {k: np.array(v[z0 - Z0:z1 - Z0, x0 - X0:x1 - X0]) for k, v in layers.items()}
            if (d['ground'] > -30000).sum() < 1000:
                continue
            OX, OZ = x0, z0
            part = analyse(d, pal, pal_kind, a.out / 'tiles' / f'{x0}_{z0}.npz')
            core = lambda s: tx <= s['centre'][0] < tx + a.tile and tz <= s['centre'][1] < tz + a.tile
            for k, v in part.items():
                results[k] += [s for s in v if core(s)]
            print('tile', tx, tz, {k: len(v) for k, v in results.items()}, flush=True)
    results['trees'] = chain(results['trees'])
    results['step'] = chain(results['step'])
    height, surf, lines = results['height'], results['surface'], results['trees']
    allr = sorted(height + surf + lines + results['step'], key=lambda s: -s['score'])
    for i, s in enumerate(allr, 1):
        s['id'] = i
    (a.out / 'seams.json').write_text(json.dumps(dict(counts={k: len(v) for k, v in results.items()}, seams=allr), indent=0), 'utf8')
    classify(allr, layers, pal, pal_kind)
    kept = dedupe(allr)
    from collections import Counter
    counts = Counter(f"{q['class']}/{q.get('severity', '-')}" for q in kept)
    (a.out / 'seams-classified.json').write_text(json.dumps(dict(counts=counts, seams=kept), ensure_ascii=False, indent=0), 'utf8')
    print(json.dumps({k: len(v) for k, v in results.items()}), json.dumps(counts))


def area(q):
    x, z = q['centre']
    if x > 1700 and z < -1500:
        return 'NE corridor'
    return 'Odawara plain' if x > 2400 else 'Hakone'


def classify(seams, layers, pal, pal_kind):
    """class: map-edge (unscanned chunks within 48), rail-bed (gravel ballast alongside), facility-cut
    (built within 6), ragged-cliff (crooked single piece), else seam with severity S1-S3."""
    g, s, sid, w, gid = (layers[k] for k in ('ground', 'solid', 'solid_id', 'water', 'ground_id'))
    gravel = [i for i, p in enumerate(pal) if p.endswith(':gravel')]
    for q in seams:
        x0, x1 = q['x']
        z0, z1 = q['z']
        near = (slice(max(0, z0 - 48 - Z0), z1 + 49 - Z0), slice(max(0, x0 - 48 - X0), x1 + 49 - X0))
        band = (slice(max(0, z0 - 6 - Z0), z1 + 7 - Z0), slice(max(0, x0 - 6 - X0), x1 + 7 - X0))
        nodata = float((np.array(g[near]) < -30000).mean())
        gb, sb = np.array(g[band]), np.array(s[band])
        built = float(((pal_kind[np.array(sid[band])] == 4) & (sb > gb)).mean())
        q['gravel_share'] = round(float(np.isin(np.array(gid[band]), gravel).mean()), 3)
        q['built_share'] = round(built, 3)
        q['water_share'] = round(float((np.array(w[band]) >= gb).mean()), 3)
        q['area'] = area(q)
        terrain = q['kind'] in ('height', 'step')
        if nodata > 0:
            q['class'] = 'map-edge'
        elif q['gravel_share'] > .12:
            q['class'] = 'rail-bed'
        elif terrain and built > .02:
            q['class'] = 'facility-cut'
        elif terrain and q['straightness'] < 6 and q.get('pieces', 1) == 1:
            q['class'] = 'ragged-cliff'
        else:
            q['class'] = 'seam'
            big = terrain and (q['mean'] >= 5 or q['length'] >= 100) or q['kind'] == 'trees' and q['length'] >= 100
            q['severity'] = 'S3' if q['area'] == 'NE corridor' else 'S1' if big else 'S2'


def dedupe(seams, margin=4):
    """A cliff and a step found on the same line are one seam; the stronger keeps the others' ids as aliases."""
    family = lambda q: 'terrain' if q['kind'] in ('height', 'step') else q['kind']
    kept = []
    for q in sorted(seams, key=lambda q: -q['score']):
        host = next((k for k in kept if family(k) == family(q) and k['class'] == q['class']
                     and k['x'][0] - margin <= q['x'][1] and q['x'][0] - margin <= k['x'][1]
                     and k['z'][0] - margin <= q['z'][1] and q['z'][0] - margin <= k['z'][1]), None)
        if host:
            host.setdefault('aliases', []).append(q['id'])
            host['x'] = [min(host['x'][0], q['x'][0]), max(host['x'][1], q['x'][1])]
            host['z'] = [min(host['z'][0], q['z'][0]), max(host['z'][1], q['z'][1])]
        else:
            kept.append(q)
    return kept


if __name__ == '__main__':
    main()
