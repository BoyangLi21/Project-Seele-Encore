"""Remove chosen floating pieces: every block of each piece becomes air.

float_fix.py <pieces.json> <out dir>

pieces.json is a list of float_blocks.py pieces (each with 'at' and 'bbox'). Each piece is found
again in the world (BUILDINGS_WORLD) by flooding face-touching solid blocks from 'at' inside its
box, so the rows hold what is really there now. A piece that has grown a support since the scan
(the flood leaves its box or reaches the ground) is skipped and reported. Blocks with a block
entity are never planned.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World
from float_blocks import is_solid

AIR = 'minecraft:air'


def main(pieces_file, out):
    w = World(REGION)
    rows, skipped = [], []
    for p in json.load(open(pieces_file)):
        x0, y0, z0, x1, y1, z1 = p['bbox']
        start = tuple(p['at'])
        if not is_solid(w.get(*start) or AIR):
            skipped.append([p['at'], 'gone'])
            continue
        seen, q, ok = {start}, [start], True
        while q and ok:
            c = q.pop()
            for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                n = (c[0] + d[0], c[1] + d[1], c[2] + d[2])
                if n in seen or not is_solid(w.get(*n) or AIR):
                    continue
                if not (x0 <= n[0] <= x1 and y0 <= n[1] <= y1 and z0 <= n[2] <= z1):
                    ok = False      # it touches something outside its old box now: not floating any more
                    break
                seen.add(n)
                q.append(n)
        if not ok or len(seen) != p['size']:
            skipped.append([p['at'], f'changed ({len(seen)} of {p["size"]})'])
            continue
        if any(w.block_entity(*c) for c in seen):
            skipped.append([p['at'], 'block entity'])
            continue
        rows += [[*c, w.get(*c), AIR] for c in sorted(seen)]
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / 'rows.json').write_text(json.dumps(rows), 'utf8')
    (Path(out) / 'skipped.json').write_text(json.dumps(skipped), 'utf8')
    print('rows', len(rows), 'skipped', len(skipped))


if __name__ == '__main__':
    main(*sys.argv[1:])
