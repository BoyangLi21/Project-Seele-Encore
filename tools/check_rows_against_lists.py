"""Check a write list against other sessions' lists that are still waiting to be written: same cells, and
planted columns within --near blocks of a column where their list puts something built.

    check_rows_against_lists.py WORLD ROWS.json [--near 3] [--lists GLOB ...] [--days 4]
"""
import argparse
import glob
import json
import os
import time

from plan_forest_transitions import still_pending

NATURAL = ('air', 'grass', 'fern', 'dirt', 'stone', 'leaves', 'log', 'podzol', 'gravel', 'sand', 'flower', 'tulip', 'poppy',
           'dandelion', 'bush', 'water', 'snow', 'moss', 'vine')
DEFAULT = ['F:/eva/.claude/map-roads-work/plans/**/*.json', 'E:/eva-map-buildings/plans/**/*.json',
           'E:/eva-map-edges/**/rows*.json', 'F:/eva/.claude/map-work/**/rows*.json']


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('world')
    p.add_argument('rows', nargs='+')
    p.add_argument('--near', type=int, default=3)
    p.add_argument('--lists', nargs='*', default=DEFAULT)
    p.add_argument('--days', type=float, default=4)
    a = p.parse_args()
    mine = []
    for f in a.rows:
        mine += json.load(open(f))
    cells = {tuple(r[:3]) for r in mine}
    cols = {(r[0], r[2]) for r in mine}
    xs = [c[0] for c in cols]
    zs = [c[1] for c in cols]
    bx0, bx1, bz0, bz1 = min(xs) - a.near, max(xs) + a.near, min(zs) - a.near, max(zs) + a.near
    own = {os.path.normcase(os.path.abspath(f)) for f in a.rows}
    report = []
    for pat in a.lists:
        for f in glob.glob(pat, recursive=True):
            if os.path.normcase(os.path.abspath(f)) in own or os.path.getsize(f) > 400e6 or time.time() - os.path.getmtime(f) > a.days * 86400:
                continue
            try:
                rows = json.load(open(f))
            except Exception:
                continue
            if not isinstance(rows, list) or not rows or not isinstance(rows[0], list) or len(rows[0]) < 5:
                continue
            inbox = [r for r in rows if isinstance(r[0], int) and len(r) >= 5 and isinstance(r[4], str) and bx0 <= r[0] <= bx1 and bz0 <= r[2] <= bz1]
            if not inbox:
                continue
            pending = still_pending(rows, a.world)
            same = sum(1 for r in inbox if tuple(r[:3]) in cells)
            built = {(r[0], r[2]) for r in inbox if not any(w in r[4].split('[')[0].split(':')[-1] for w in NATURAL)}
            near = 0
            for (x, z) in built:
                if any((x + dx, z + dz) in cols for dx in range(-a.near, a.near + 1) for dz in range(-a.near, a.near + 1)):
                    near += 1
            if same or (pending and near):
                report.append(dict(list=f, pending=pending, rows=len(rows), same_cells=same, built_columns_near=near))
    print(json.dumps(dict(my_cells=len(cells), my_columns=len(cols), flagged=report), indent=1))


if __name__ == '__main__':
    main()
