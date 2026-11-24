"""Bring chunk regeneration recipes (city_rigid_generation_r45/surface) in line with a cell list.

Only cells a recipe already covers are changed, to the row's after-state; a covered cell whose recipe state differs
from the row's before-state is refused. Spans are split only where a changed cell falls; the order of all other
spans is kept. Writes the patched recipe files to <out>/recipes and <out>/extras.json for install_world_extras.py
(each file with the expected old sha256 and the new one).
usage: patch_surface_recipes.py --world <world> --rows <rows.json> --out <new-dir>"""
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import nbtlib

from write_deep_cells import state_entry, state_name

SURFACE = 'dimensions/projectseele/geofront/data/city_rigid_generation_r45/surface'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--world', type=Path, required=True)
    ap.add_argument('--rows', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    rows = json.loads(a.rows.read_text('utf8'))
    by = defaultdict(dict)
    for x, y, z, before, after, *_ in rows:
        by[x >> 4, z >> 4][x, y, z] = (before, after)
    (a.out / 'recipes').mkdir(parents=True, exist_ok=False)
    files, report, problems = [], [], []
    for (cx, cz), cells in sorted(by.items()):
        src = a.world / SURFACE / f'{cx}_{cz}.dat'
        if not src.exists():
            report.append(dict(chunk=[cx, cz], recipe=False))
            continue
        tag = nbtlib.load(src)
        palette = tag['Palette']
        codes = {state_name(v): i for i, v in enumerate(palette)}

        def index(state):
            if state not in codes:
                codes[state] = len(palette)
                palette.append(state_entry(state))
            return codes[state]

        changed = defaultdict(dict)
        spans = []
        for old in tag['Spans']:
            x, z, lo, hi, code = map(int, old)
            hits = sorted(y for (cx_, y, cz_) in cells if cx_ == x and cz_ == z and lo <= y <= hi)
            if not hits:
                spans.append(old)
                continue
            have = state_name(palette[code])
            start = lo
            for y in hits:
                before, after = cells[x, y, z]
                if have.split('[')[0] != before.split('[')[0]:
                    problems.append(f'{x},{y},{z}: recipe has {have}, row expects {before}')
                if start < y:
                    spans.append(nbtlib.IntArray([x, z, start, y - 1, code]))
                spans.append(nbtlib.IntArray([x, z, y, y, index(after)]))
                changed[x, z][y] = after
                start = y + 1
            if start <= hi:
                spans.append(nbtlib.IntArray([x, z, start, hi, code]))
        n = sum(len(v) for v in changed.values())
        report.append(dict(chunk=[cx, cz], recipe=True, cells_covered=n, cells_in_rows=len(cells)))
        if not n:
            continue
        tag['Spans'] = nbtlib.List[nbtlib.IntArray](spans)
        dest = a.out / 'recipes' / f'{cx}_{cz}.dat'
        tag.save(dest)
        # read back what was written
        back = nbtlib.load(dest)
        pal = [state_name(v) for v in back['Palette']]
        found = {}
        for sp in back['Spans']:
            x, z, lo, hi, i = map(int, sp)
            for y, after in changed.get((x, z), {}).items():
                if lo <= y <= hi:
                    found[x, y, z] = pal[i]
        if any(found.get((x, y, z)) != after for (x, z), ys in changed.items() for y, after in ys.items()):
            problems.append(f'{cx}_{cz}: readback differs')
        files.append(dict(file=f'{SURFACE}/{cx}_{cz}.dat', expect_sha256=sha(src), source=f'recipes/{cx}_{cz}.dat', sha256=sha(dest)))
    if problems:
        raise SystemExit('Refused:\n' + '\n'.join(problems[:20]))
    (a.out / 'extras.json').write_text(json.dumps(dict(files=files), indent=1), 'utf8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
