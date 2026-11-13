"""Drop planted trees and shrubs that would touch a protected volume (city lift, lift shaft, EVA launch space),
the same guards write_deep_cells.py refuses on. A row inside a guard takes out the whole tree it belongs
to: every planted cell joined to it (26-neighbours, through planted rows only).

Also, with --pending, trees that share a cell with another session's list still waiting to be written, or come
within --near blocks of a column where such a list builds something.

    filter_protected_rows.py WORLD ROWS.json OUT.json [--pending] [--near 3]
"""
import json
import sys
from collections import defaultdict, deque

import numpy as np


def guards(world):
    from map_pipeline.city_protection import load as city
    from map_pipeline.lift_protection import load as lift
    from map_pipeline.launch_protection import load as launch
    return [('city', city(world)), ('lift', lift(world)), ('launch', launch(world))]


def hits(guard, rows):
    by = defaultdict(list)
    for i, r in enumerate(rows):
        by[r[0] // 16, r[2] // 16].append(i)
    out = set()
    for key, idx in by.items():
        boxes = guard.by_chunk.get(key, ())
        if not boxes:
            continue
        p = np.array([rows[i][:3] for i in idx])
        for _, b in boxes:
            inside = np.all((p >= b[:3]) & (p <= b[3:]), axis=1)
            out.update(idx[j] for j in np.nonzero(inside)[0])
    return out


def pending_hits(world, rows, near):
    import glob, os, time
    from check_rows_against_lists import DEFAULT, NATURAL
    from plan_forest_transitions import still_pending
    cells = {tuple(r[:3]): i for i, r in enumerate(rows)}
    cols = {}
    for i, r in enumerate(rows):
        cols.setdefault((r[0], r[2]), []).append(i)
    xs = [c[0] for c in cols]
    zs = [c[1] for c in cols]
    bx0, bx1, bz0, bz1 = min(xs) - near, max(xs) + near, min(zs) - near, max(zs) + near
    out, per = set(), {}
    for pat in DEFAULT:
        for f in glob.glob(pat, recursive=True):
            if os.path.getsize(f) > 400e6 or time.time() - os.path.getmtime(f) > 4 * 86400:
                continue
            try:
                other = json.load(open(f))
            except Exception:
                continue
            if not isinstance(other, list) or not other or not isinstance(other[0], list) or len(other[0]) < 5:
                continue
            inbox = [r for r in other if isinstance(r[0], int) and len(r) >= 5 and isinstance(r[4], str) and bx0 <= r[0] <= bx1 and bz0 <= r[2] <= bz1]
            if not inbox or not still_pending(other, world):
                continue
            hit = {cells[tuple(r[:3])] for r in inbox if tuple(r[:3]) in cells}
            for r in inbox:
                if any(w in r[4].split('[')[0].split(':')[-1] for w in NATURAL):
                    continue
                for dx in range(-near, near + 1):
                    for dz in range(-near, near + 1):
                        hit.update(cols.get((r[0] + dx, r[2] + dz), ()))
            if hit:
                per[f] = len(hit)
                out |= hit
    return out, per


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('world')
    p.add_argument('src')
    p.add_argument('dst')
    p.add_argument('--pending', action='store_true')
    p.add_argument('--near', type=int, default=3)
    a = p.parse_args()
    world, src, dst = a.world, a.src, a.dst
    rows = json.load(open(src))
    pos = {tuple(r[:3]): i for i, r in enumerate(rows)}
    bad, per = set(), {}
    for name, g in guards(world):
        h = hits(g, rows)
        per[name] = len(h)
        bad |= h
    if a.pending:
        h, lists = pending_hits(world, rows, a.near)
        per['pending_lists'] = lists
        bad |= h
    drop = set(bad)
    queue = deque(bad)
    while queue:
        x, y, z = rows[queue.popleft()][:3]
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    j = pos.get((x + dx, y + dy, z + dz))
                    if j is not None and j not in drop:
                        drop.add(j)
                        queue.append(j)
    kept = [r for i, r in enumerate(rows) if i not in drop]
    json.dump(kept, open(dst, 'w'))
    print(json.dumps(dict(rows=len(rows), inside_guards=per, dropped=len(drop), kept=len(kept))))


if __name__ == '__main__':
    main()
