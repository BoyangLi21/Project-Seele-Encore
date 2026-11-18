"""R64 dead-end rule (owner, 2026-11-18): every road end joins another road or leads to a place.

Reads road_dead_ends_classify output and re-judges each end:
  keep    - map edge; a station or a door at the end; a roof over the end (it runs into a building or a tunnel);
            a wide paved end with a door within DOOR_R; a footway that, within FOOT_STEPS, reaches a door, a
            station or road DETACH blocks or more away from the end (the footway itself joins the network).
  height  - road continues within 4 blocks ahead at a different walking height (1.5 blocks or more): the network
            did not join it; needs a ramp or is reported as a network-only gap.
  speck   - a piece of fewer than SPECK declared cells: a few stray paving blocks, not a road; listed, not changed.
  keep (place) - the end runs onto a paved area of PLACE cells or more at its own height (plaza, car park, forecourt)
            or up to a building wall.
  A step of more than CROSS blocks is a road passing over or under, not a missed ramp: judged like any other end.
  dead    - everything else: unexplained ends, footways that lead nowhere, turning circles with nothing beside them,
            water-only ends (a river bank is not a pier).
usage: classify_deadends_r64.py <capture> <network.npz> <classified.json> <out.json>
"""
import json
import sys
from collections import Counter, deque

import numpy as np

from plan_station_access_corridor import CapturedSurface

DOOR_R, FOOT_STEPS, DETACH = 16, 80, 12
SPECK, PLACE, CROSS = 40, 100, 10
BARRIER = ('fence', '_wall', 'bars', 'pane', 'chain', 'rail', 'guard', 'barrier', 'cone', 'post')
NATURAL = ('grass_block', 'dirt', 'coarse_dirt', 'stone', 'gravel', 'sand', 'podzol', 'andesite', 'granite', 'diorite',
           'moss_block', 'rooted_dirt', 'water', 'snow', 'snow_block', 'clay', 'mud', 'deepslate', 'tuff', 'calcite', 'red_sand')
AIR = ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air')


def name(s):
    return s.split('[')[0]


def main():
    cap = CapturedSurface(sys.argv[1], partial=True)
    net = np.load(sys.argv[2])
    ends = json.load(open(sys.argv[3], encoding='utf8'))['ends']
    ax, az = map(int, net['bounds'][:2])
    road, walk, g2 = net['road'], net['walk'], net['grade2']
    H, W = road.shape
    foot = walk & ~road

    def state(x, y, z):
        try:
            return name(cap.state(x, y, z))
        except ValueError:
            return 'outside'

    def doors_near(x, z, feet, r):
        n = 0
        for dx in range(-r, r + 1, 1):
            for dz in range(-r, r + 1, 1):
                if dx * dx + dz * dz > r * r:
                    continue
                for y in (int(feet), int(feet) + 1):
                    s = state(x + dx, y, z + dz)
                    if s.endswith('door') and 'trapdoor' not in s:
                        n += 1
        return n

    def footway_reach(x, z, feet):
        """Footway cells reachable from the end: does the footway lead to a door, a station or other road?"""
        start = [(z + dz - az, x + dx - ax) for dx in range(-3, 4) for dz in range(-3, 4)
                 if 0 <= z + dz - az < H and 0 <= x + dx - ax < W and foot[z + dz - az, x + dx - ax]]
        seen, q = set(start), deque((p, 0) for p in start)
        while q:
            (iz, ix), d = q.popleft()
            wx, wz = ix + ax, iz + az
            if (wx - x) ** 2 + (wz - z) ** 2 >= DETACH ** 2:
                for jz in range(iz - 1, iz + 2):
                    for jx in range(ix - 1, ix + 2):
                        if 0 <= jz < H and 0 <= jx < W and road[jz, jx]:
                            return 'road'
            if d % 6 == 0:
                f = g2[iz, ix] / 2 + 1
                for dx in (-2, 0, 2):
                    for dz in (-2, 0, 2):
                        for y in (int(f), int(f) + 1):
                            s = state(wx + dx, y, wz + dz)
                            if s.endswith('door') and 'trapdoor' not in s:
                                return 'door'
                            if s.startswith('mtr:'):
                                return 'station'
            if d >= FOOT_STEPS:
                continue
            for jz, jx in ((iz + 1, ix), (iz - 1, ix), (iz, ix + 1), (iz, ix - 1)):
                if 0 <= jz < H and 0 <= jx < W and foot[jz, jx] and (jz, jx) not in seen:
                    seen.add((jz, jx))
                    q.append(((jz, jx), d + 1))
        return None

    hi = cap.measured['highest']
    cx, cz = map(int, cap.bounds[:2])

    def surface(x, z):
        try:
            y = int(hi[z - cz, x - cx])
        except IndexError:
            return None, None
        for yy in range(y, y - 6, -1):
            n = state(x, yy, z)
            short = n.split(':')[-1]
            if n in AIR or short.endswith(('grass', 'fern', 'flower', 'torch', 'carpet', 'button', 'sign', 'lantern')):
                continue
            return yy, n
        return None, None

    def man_made(n):
        short = n.split(':')[-1]
        return not (n == 'outside' or n in AIR or short in NATURAL or short.endswith(('_leaves', '_log', '_wood', 'sapling'))
                    or n.startswith('trafficcraft:'))

    def viaduct(x, y, z):
        """A rail embankment or viaduct (ballast or track on top), not a building."""
        return any(state(x, yy, z).startswith('mtr:') or 'rail' in state(x, yy, z) or state(x, yy, z) == 'minecraft:gravel'
                   for yy in range(y - 1, y + 3))

    def place_ahead(x, z, feet, d):
        """A paved area (plaza, car park, forecourt) or a building wall in front of the end."""
        R = 14
        ox, oz = x + d[0] * 6, z + d[1] * 6
        grid = np.zeros((2 * R + 1, 2 * R + 1), bool)
        wall = 0
        for j in range(2 * R + 1):
            for i in range(2 * R + 1):
                wx, wz = int(round(ox)) + i - R, int(round(oz)) + j - R
                iz, ix = wz - az, wx - ax
                if 0 <= iz < H and 0 <= ix < W and road[iz, ix]:
                    continue
                if (wx - x) * d[0] + (wz - z) * d[1] < 0:
                    continue
                y, n = surface(wx, wz)
                if y is None:
                    continue
                if feet - 3 <= y <= feet and man_made(n):
                    grid[j, i] = True
                elif y >= feet + 1 and man_made(n) and (wx - x) ** 2 + (wz - z) ** 2 <= 16 and not viaduct(wx, y, wz)                         and all(man_made(state(wx, h, wz)) and not any(k in state(wx, h, wz) for k in BARRIER)
                                for h in (int(feet), int(feet) + 1)):
                    wall += 1
        if wall >= 3:
            return f'runs up to a building wall ({wall} columns)'
        from scipy import ndimage
        lab, _ = ndimage.label(grid)
        best = 0
        for k in range(1, 6):
            px, pz = int(round(x + d[0] * k)) - int(round(ox)) + R, int(round(z + d[1] * k)) - int(round(oz)) + R
            for jj in range(pz - 1, pz + 2):
                for ii in range(px - 1, px + 2):
                    if 0 <= jj <= 2 * R and 0 <= ii <= 2 * R and lab[jj, ii]:
                        best = max(best, int((lab == lab[jj, ii]).sum()))
        return f'runs onto a paved area of {best} cells' if best >= PLACE else None

    out = []
    # Region by region, dropping the cached capture regions of earlier ones: each holds two copies of up to 224 MiB.
    for e in sorted(ends, key=lambda e: (e['x'] // 512, e['z'] // 512)):
        x, z, feet = e['x'], e['z'], e['feet']
        if len(cap.editor.regions) > 4:
            near = {((x + dx) // 512, (z + dz) // 512) for dx in (-64, 0, 64) for dz in (-64, 0, 64)}
            for k in [k for k in cap.editor.regions if k not in near]:
                del cap.editor.regions[k]
        why = list(e['why'])
        rule, note = 'dead', ''
        bx, bz = e['back']
        d = np.array([x - bx, z - bz], float)
        d = d / (np.linalg.norm(d) or 1)
        own = int(g2[z - az, x - ax])
        ahead = [(int(round(x + d[0] * k)), int(round(z + d[1] * k))) for k in range(1, 5)]
        step = next((abs(int(g2[pz - az, px - ax]) - own) for px, pz in ahead
                     if 0 <= pz - az < H and 0 <= px - ax < W and road[pz - az, px - ax]
                     and 3 <= abs(int(g2[pz - az, px - ax]) - own) <= 2 * CROSS), None)
        if e.get('comp_cells', SPECK) < SPECK:
            rule, note = 'speck', f"piece of {e['comp_cells']} cells"
        elif e['cls'] == 'boundary':
            rule, note = 'keep', 'map edge'
        elif any(w.startswith(('station', 'door', 'covered')) for w in why):
            rule, note = 'keep', ', '.join(w for w in why if w.startswith(('station', 'door', 'covered')))
        elif step is not None:
            rule, note = 'height', f'road ahead {step / 2:.1f} blocks higher or lower'
        else:
            if any(w.startswith('wide') for w in why):
                n = doors_near(x, z, feet, DOOR_R)
                if n:
                    rule, note = 'keep', f'turning circle with {n} door cells within {DOOR_R}'
                else:
                    note = 'turning circle with nothing beside it'
            if rule == 'dead' and any(w.startswith('continues') for w in why):
                reach = footway_reach(x, z, feet)
                if reach:
                    rule, note = 'keep', f'footway reaches a {reach}'
                else:
                    note = 'footway leads nowhere'
            if rule == 'dead':
                p = place_ahead(x, z, feet, d)
                if p:
                    rule, note = 'keep', p
            if rule == 'dead' and not note:
                note = 'water only' if any(w.startswith('water') for w in why) else 'nothing at the end'
        out.append(dict(e, rule=rule, rule_note=note))
    out.sort(key=lambda r: r['id'])
    json.dump(dict(ends=out), open(sys.argv[4], 'w', encoding='utf8'), ensure_ascii=False, indent=0)
    print(json.dumps(dict(Counter(r['rule'] for r in out)), ensure_ascii=False))
    print(json.dumps(dict(Counter(r['rule_note'].split(' with ')[0] for r in out)), ensure_ascii=False))


if __name__ == '__main__':
    main()
