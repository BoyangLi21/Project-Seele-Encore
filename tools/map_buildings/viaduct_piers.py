"""Viaducts: find spans longer than MAXSPAN without a pier along each MTR rail and plan 2x2 piers.

A rail sample is free when its column hangs at least MINGAP over the ground under the deck
(float.npy underside with that gap). Runs of free samples longer than MAXSPAN get piers every
STEP blocks; a pier is a 2x2 column of the viaduct's own pier block (the commonest block found
standing under its deck) from the ground up to the deck. Water and plants may be replaced, nothing else.
"""
import glob, json, math, sys
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World, WORLD
from blocks import is_open, is_natural, short
from rails import path
from stations import unpack
from e5_plan import is_building

MINGAP, MAXSPAN, STEP = 6, 32, 18
HERE = Path(__file__).parent


def main(plates_file, out):
    w = World(REGION)
    A = np.load(HERE / 'float.npy')
    plates = [p for p in json.load(open(plates_file, encoding='utf8')) if p['kind'] == 'viaduct']
    rails = [unpack(open(f, 'rb').read())[0] for f in glob.glob(WORLD + '/mtr/projectseele/geofront/rails/*/*')]
    rows, report = {}, []
    for p in plates:
        x0, y0, z0, x1, y1, z1 = p['bbox']
        m = (A[:, 0] >= x0) & (A[:, 0] <= x1) & (A[:, 2] >= z0) & (A[:, 2] <= z1) & (A[:, 1] >= y0) & (A[:, 1] <= y1)
        under = {}
        for x, y, z, gap, gr, gy in A[m].tolist():
            if (x, z) not in under or y < under[x, z][0]:
                under[x, z] = (y, gap)
        # pier block: what the viaduct's existing piers are made of (vertical runs of one man-made
        # block just under the deck level); the deck's own block only when no pier is found
        skip = ('slab', 'stairs', 'wall', 'fence', 'pane', 'rail', 'bars', 'light', 'edge', 'glass', 'leaves', 'log')
        piers = Counter()
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                if (x, z) in under:
                    continue
                for y in range(y0 - 2, y0 - 10, -1):
                    s = w.get(x, y, z)
                    if s and not is_open(s) and not is_natural(s) and not any(k in s for k in skip) \
                            and w.get(x, y - 1, z) == s and w.get(x, y - 2, z) == s and w.get(x, y - 3, z) == s:
                        piers[s] += 1
                        break
        deck = Counter(w.get(x, y, z) for (x, z), (y, g) in list(under.items())[:400])
        block = next((b for b, _ in piers.most_common() + deck.most_common() if b and not any(k in b for k in skip)),
                     'minecraft:light_gray_concrete')

        def supported(c, ry):
            """A deck column near c that does not hang over open space: a pier, or ground close under it."""
            for dx in range(-6, 7):
                for dz in range(-6, 7):
                    n = (c[0] + dx, c[1] + dz)
                    if n in under:
                        if under[n][1] < MINGAP and abs(under[n][0] - ry) <= 6:
                            return True
                        continue
                    for yy in range(int(ry) - 1, int(ry) - 4, -1):
                        if is_building(w.get(n[0], yy, n[1])):
                            # deck here, and not listed as hanging: it reaches down to something
                            return True
            return False
        spans, added = [], 0
        for d in rails:
            pts = [(int(math.floor(x)), int(math.floor(z)), ry) for x, z, ry in path(d) if x0 <= x <= x1 + 1 and z0 <= z <= z1 + 1]
            if len(pts) < 2:
                continue
            seq = []
            for x, z, ry in pts:
                hit = [under[c] for c in ((x, z), (x + 1, z), (x, z + 1), (x - 1, z), (x, z - 1)) if c in under and abs(under[c][0] - ry) <= 6]
                seq.append(((x, z), bool(hit) and not supported((x, z), ry)))
            run = []
            for c, free in seq + [((0, 0), False)]:
                if free:
                    if not run or run[-1] != c:
                        run.append(c)
                    continue
                L = len(run)
                if L > MAXSPAN * 1.5:      # samples are ~1.5 per block
                    spans.append(L / 1.5)
                    n = int(L / 1.5 // STEP)
                    for k in range(1, n + 1):
                        cx, cz = run[int(k * len(run) / (n + 1))]
                        for px, pz in ((cx, cz), (cx + 1, cz), (cx, cz + 1), (cx + 1, cz + 1)):
                            if (px, pz) not in under:
                                continue
                            u, gap = under[px, pz]
                            y = u - 1
                            col = []
                            while y > u - 80:
                                s = w.get(px, y, pz)
                                if s is None or not (is_open(s) or 'water' in s):
                                    break
                                col.append((y, s))
                                y -= 1
                            if not col or not (is_natural(w.get(px, y, pz)) or is_building(w.get(px, y, pz))):
                                continue
                            for yy, s in col:
                                rows[px, yy, pz] = [px, yy, pz, s, block]
                        added += 1
                run = []
        report.append(dict(bbox=p['bbox'], station=p['station'], long_spans=len(spans), longest=round(max(spans, default=0)),
                           piers_added=added, pier_block=short(block)))
        print(p['bbox'][:3], p['station'], 'long spans', len(spans), 'longest', round(max(spans, default=0)), 'piers', added, short(block))
    Path(out).mkdir(parents=True, exist_ok=True)
    R = [r for r in rows.values() if not w.block_entity(*r[:3])]
    (Path(out) / 'rows.json').write_text(json.dumps(R), 'utf8')
    (Path(out) / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), 'utf8')
    print('cells', len(R), 'piers', sum(r['piers_added'] for r in report))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
