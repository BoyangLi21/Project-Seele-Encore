"""E6 rows: close the air gaps beside (and above) doors with the wall block next to each gap.

Each gap column beside a door is filled at door height 0..2 where the cell is air and open on
both faces of the wall; the fill copies the wall block two cells from the door at the same
height (the frame the gap interrupts). Output rows [x, y, z, before, after] for write_deep_cells.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World, AIR
from blocks import FACING, props, is_open, is_door, short

recs = json.load(open(Path(__file__).parent / 'doors.json'))
w = World(REGION)
rows, items = [], []
for r in recs:
    if not r['gaps']:
        continue
    x, y, z = r['pos']
    nx, nz = FACING[r['facing']]
    ax, az = -nz, nx
    cells = []
    for gp in r['gaps']:
        s = gp['side']
        if s == 0:
            cx, cy, cz = gp['cell']
            fill = gp['outer']
            cells.append((cx, cy, cz, w.get(cx, cy, cz), fill))
            continue
        if gp['dy'] != 0:
            continue
        for dy in (0, 1, 2):
            cx, cy, cz = x + ax * s, y + dy, z + az * s
            c = w.get(cx, cy, cz)
            if c not in AIR:
                continue
            if not (is_open(w.get(cx + nx, cy, cz + nz)) and is_open(w.get(cx - nx, cy, cz - nz))):
                continue
            fill = w.get(x + ax * s * 2, cy, z + az * s * 2)
            if fill is None or is_open(fill) or is_door(fill):
                fill = w.get(cx, y + 3, cz) if dy == 2 else None
            if fill is None or is_open(fill):
                raise SystemExit(f'no wall block to copy at {cx},{cy},{cz}')
            cells.append((cx, cy, cz, c, fill))
    for c in cells:
        if w.block_entity(c[0], c[1], c[2]):
            raise SystemExit(f'block entity at {c[:3]}')
    # a double door is listed once per leaf; keep each cell once
    new = [c for c in cells if [c[0], c[1], c[2]] not in [rw[:3] for rw in rows]]
    rows += [list(c) for c in new]
    if new:
        items.append(dict(door=r['pos'], type=r['door'], facing=r['facing'], cells=[list(c[:3]) for c in new],
                          fills=sorted({short(c[4]) for c in new})))
out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
(out / 'rows.json').write_text(json.dumps(rows), 'utf8')
(out / 'items.json').write_text(json.dumps(items, ensure_ascii=False, indent=1), 'utf8')
print(len(items), 'doors', len(rows), 'cells')
for it in items:
    print(it['door'], it['type'], it['facing'], len(it['cells']), it['fills'])
