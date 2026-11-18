"""Repaint the inside of EVA launch tunnels after the City exit's upper shaft (R64 launch tunnel pass).

The tunnel shape stays exactly as it is: no air is filled and no solid is cut, so the launch space, the code-drawn
guide rails and the hatches keep what they have. Only solid cells that face the tunnel air are repainted, by their
position in the tunnel's own frame (distance s along the centre line, u across, v down):

* floor faces nerv_shaft_panel, side walls and ceiling black_concrete (the City exit upper shaft's colours), or with
  --base keep the blue panel everywhere, so only lights, ribs, stray light bands and bare stone or dirt change;
* every 16 blocks of s a ring of lit nerv_strip_light: on an incline a strip up each side wall and one across the
  ceiling, in a vertical shaft two strips 8 high on each wall, as in the City exit;
* every 32 blocks of s a rib of nerv_machine_edge all round.

Never touched: guide rail anchor cells (their exact state is checked by the rail renderer), cells within 3 blocks of
a hatch seal (barrier) layer, and any block that is not plain wall material (launch armour, hatch covers, glass...).

    plan_launch_tunnel_skin.py --world W --leg unit2/exit3/upright_continuous [--leg ...] --out rows.json

Reads the centre curves from <world>/ROOT_RUNTIME_DIRECTORY.json and the anchors from
<world>/UPRIGHT_GUIDEWAY_SOURCE.json. Writes rows [x, y, z, before, after] for write_deep_cells.py.
"""
import argparse
import io
import json
import math
import mmap
import zlib
from collections import Counter
from pathlib import Path

import nbtlib
import numpy as np
from scipy.spatial import cKDTree

from plan_junction_signs import decode, state_name

REGION = 'dimensions/projectseele/geofront/region'
AIRISH = {'minecraft:air', 'minecraft:cave_air', 'minecraft:void_air', 'minecraft:light', 'minecraft:barrier'}
PAINTABLE = {'projectseele:nerv_shaft_panel', 'projectseele:nerv_machine_edge', 'minecraft:black_concrete',
             'minecraft:deepslate', 'minecraft:stone', 'minecraft:dirt', 'minecraft:grass_block', 'minecraft:coarse_dirt',
             'minecraft:gravel', 'minecraft:andesite', 'minecraft:tuff', 'minecraft:cobbled_deepslate',
             'projectseele:nerv_strip_light'}
FLOOR, WALL, LIGHT, RIB = ('projectseele:nerv_shaft_panel', 'minecraft:black_concrete',
                           'projectseele:nerv_strip_light[lit=true]', 'projectseele:nerv_machine_edge')
STEP = 0.25


def bezier(c, t):
    p = [np.asarray(q, float) for q in c]
    while len(p) > 1:
        p = [p[i] * (1 - t) + p[i + 1] * t for i in range(len(p) - 1)]
    return p[0]


def centre_samples(curve):
    raw = []
    for seg in curve['segments']:
        c = seg['controls']
        n = max(8, int(sum(np.linalg.norm(np.subtract(c[i + 1], c[i])) for i in range(len(c) - 1)) * 4))
        raw += [bezier(c, i / n) for i in range(n + 1)]
    raw = np.array(raw)
    seg = np.linalg.norm(np.diff(raw, axis=0), axis=1)
    cum = np.r_[0, np.cumsum(seg)]
    s = np.arange(0, cum[-1], STEP)
    pos = np.stack([np.interp(s, cum, raw[:, k]) for k in range(3)], 1)
    d = np.gradient(pos, axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    vertical = np.abs(d[:, 1]) > 0.97
    u = np.stack([d[:, 2], np.zeros(len(d)), -d[:, 0]], 1)
    u[vertical] = (1, 0, 0)
    u /= np.linalg.norm(u, axis=1, keepdims=True)
    v = np.cross(u, d)
    v[v[:, 1] > 0] *= -1
    v[vertical] = (0, 0, 1)
    return s, pos, d, u, v, vertical


def anchors(world):
    with open(Path(world) / 'UPRIGHT_GUIDEWAY_SOURCE.json', 'rb') as f:
        m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        i = m.find(b'"anchors"')
        j = m.find(b'[', i)
        arr, _ = json.JSONDecoder().raw_decode(m[j:].decode('utf8'))
    return {tuple(a['at']) for a in arr}


def read_box(world, x0, x1, y0, y1, z0, z1):
    """Block state ids[y, z, x] (uint16) and their palette for an inclusive box."""
    ids = np.zeros((y1 - y0 + 1, z1 - z0 + 1, x1 - x0 + 1), np.uint16)
    lookup = {'minecraft:air': 0}
    for rx in range(x0 >> 9, (x1 >> 9) + 1):
        for rz in range(z0 >> 9, (z1 >> 9) + 1):
            p = Path(world) / REGION / f'r.{rx}.{rz}.mca'
            if not p.exists():
                continue
            buf = p.read_bytes()
            for cx in range(max(x0 >> 4, rx * 32), min(x1 >> 4, rx * 32 + 31) + 1):
                for cz in range(max(z0 >> 4, rz * 32), min(z1 >> 4, rz * 32 + 31) + 1):
                    i = 4 * ((cx & 31) + (cz & 31) * 32)
                    loc = int.from_bytes(buf[i:i + 3], 'big')
                    if not loc:
                        continue
                    n = int.from_bytes(buf[loc * 4096:loc * 4096 + 4], 'big')
                    root = nbtlib.File.parse(io.BytesIO(zlib.decompress(buf[loc * 4096 + 5:loc * 4096 + 4 + n])))
                    gx, gz = cx * 16, cz * 16
                    ax0, ax1, az0, az1 = max(x0, gx), min(x1, gx + 15), max(z0, gz), min(z1, gz + 15)
                    for sec in root['sections']:
                        if 'block_states' not in sec:
                            continue
                        sy = int(sec['Y']) * 16
                        if sy + 15 < y0 or sy > y1:
                            continue
                        idx, pal = decode(sec['block_states'])
                        remap = np.array([lookup.setdefault(state_name(e), len(lookup)) for e in pal], np.uint16)
                        cube = remap[idx].reshape(16, 16, 16)
                        ay0, ay1 = max(y0, sy), min(y1, sy + 15)
                        ids[ay0 - y0:ay1 - y0 + 1, az0 - z0:az1 - z0 + 1, ax0 - x0:ax1 - x0 + 1] = \
                            cube[ay0 - sy:ay1 - sy + 1, az0 - gz:az1 - gz + 1, ax0 - gx:ax1 - gx + 1]
    pal = [None] * len(lookup)
    for k, v in lookup.items():
        pal[v] = k
    return ids, pal


def material(s, lu, lv, kind, vertical, base='black'):
    # bands two blocks thick: on a wall that steps diagonally in plan, a one-block band misses every other row
    if 8 <= s % 32 < 10:
        return RIB
    if base == 'keep':
        wall = floor = FLOOR                        # keep the dark blue panel; only lights, ribs and stray faces change
    else:
        wall, floor = WALL, FLOOR
    if vertical:
        if s % 16 < 8 and abs(abs(lu if kind == 'z' else lv) - 9.5) < 1.0:
            return LIGHT
        return wall
    if s % 16 < 2 and ((kind == 'side' and -30 <= lv <= -6) or (kind == 'ceiling' and abs(lu) <= 6)):
        return LIGHT
    return floor if kind == 'floor' else wall


def plan_leg(world, curve, keep, piece=32, reach=70, umax=28, vmin=-66, vmax=15, guard=3, base='black', skip_start=0):
    s, pos, d, u, v, vertical = centre_samples(curve)
    tree = cKDTree(pos)
    rows, why = {}, Counter()
    for s0 in np.arange(0, s[-1], piece):
        m = (s >= s0 - 2) & (s < s0 + piece + 2)
        lo = np.floor(pos[m].min(0) - reach).astype(int)
        hi = np.ceil(pos[m].max(0) + reach).astype(int)
        ids, pal = read_box(world, lo[0], hi[0], lo[1], hi[1], lo[2], hi[2])
        names = np.array([p.split('[')[0] for p in pal])
        air = np.isin(names, list(AIRISH))[ids]
        barrier = (names == 'minecraft:barrier')[ids]
        near_air = np.zeros_like(air)
        for ax in range(3):
            for sh in (1, -1):
                near_air |= np.roll(air, sh, axis=ax)
        cand = ~air & near_air
        if barrier.any():
            from scipy import ndimage
            cand &= ~ndimage.binary_dilation(barrier, iterations=guard)
        cy, cz, cx = np.nonzero(cand)
        if not len(cx):
            continue
        wx, wy, wz = cx + lo[0], cy + lo[1], cz + lo[2]
        pts = np.stack([wx + .5, wy + .5, wz + .5], 1)
        dist, k = tree.query(pts)
        inside = (s[k] >= s0) & (s[k] < s0 + piece) & (s[k] >= skip_start)
        r = pts - pos[k]
        lu, lv = np.einsum('ij,ij->i', r, u[k]), np.einsum('ij,ij->i', r, v[k])
        inside &= (np.abs(lu) <= umax) & (lv >= vmin) & (lv <= vmax)
        for i in np.nonzero(inside)[0]:
            x, y, z = int(wx[i]), int(wy[i]), int(wz[i])
            old = pal[ids[cy[i], cz[i], cx[i]]]
            if (x, y, z) in keep:
                why['anchor kept'] += 1
                continue
            if old.split('[')[0] not in PAINTABLE:
                why['not wall material'] += 1
                continue
            # the face looks towards its air neighbours; its kind follows that direction in the tunnel frame
            nvec = np.zeros(3)
            for ax, unit in ((2, (1, 0, 0)), (0, (0, 1, 0)), (1, (0, 0, 1))):
                for sh in (1, -1):
                    j = [cy[i], cz[i], cx[i]]
                    j[ax] += sh
                    if 0 <= j[ax] < ids.shape[ax] and air[tuple(j)]:
                        nvec -= np.array(unit) * sh        # from the solid towards the air
            kk = k[i]
            if vertical[kk]:
                kind = 'z' if abs(nvec[2]) >= abs(nvec[0]) else 'x'
            else:
                nv, nu = -nvec @ v[kk], -nvec @ u[kk]       # outward: air to solid
                kind = 'floor' if nv > max(abs(nu), 0.3) else 'ceiling' if -nv > max(abs(nu), 0.3) else 'side'
            new = material(s[kk], lu[i], lv[i], kind, vertical[kk], base)
            if new == old or (x, y, z) in rows:
                continue
            rows[(x, y, z)] = [x, y, z, old, new]
            why[new.split('[')[0].split(':')[1]] += 1
    return list(rows.values()), why


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--world', type=Path, required=True)
    ap.add_argument('--leg', action='append', required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--base', choices=['black', 'keep'], default='black',
                    help='black: side walls and ceiling black concrete; keep: keep the blue panel, change only lights, ribs and stray faces')
    ap.add_argument('--skip-start', type=float, default=90,
                    help='leave the first blocks of each leg alone: the bank chamber and its first hatch, dressed in light panels')
    ap.add_argument('--s-range', type=float, nargs=2, help='only this stretch of each leg (testing)')
    a = ap.parse_args()
    directory = json.loads((a.world / 'ROOT_RUNTIME_DIRECTORY.json').read_text('utf8'))
    legs = {lg['id']: lg for lg in directory['legs']}
    keep = anchors(a.world)
    rows, total = {}, Counter()
    for name in a.leg:
        curve = legs[name]['centre_curve']
        if a.s_range:
            # trim by rebuilding a curve from the sampled stretch
            s, pos, *_ = centre_samples(curve)
            sel = pos[(s >= a.s_range[0]) & (s <= a.s_range[1])]
            curve = {'segments': [{'controls': [list(sel[i]), list(sel[i + 1])]} for i in range(0, len(sel) - 1, 8)]}
        r, why = plan_leg(a.world, curve, keep, base=a.base, skip_start=0 if a.s_range else a.skip_start)
        for row in r:
            rows.setdefault(tuple(row[:3]), row)
        total += why
        print(name, len(r), dict(why), flush=True)
    a.out.write_text(json.dumps(list(rows.values())), 'utf8')
    print(json.dumps({'rows': len(rows), 'why': dict(total)}))


if __name__ == '__main__':
    main()
