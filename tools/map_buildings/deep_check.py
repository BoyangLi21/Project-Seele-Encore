"""For the swallowed buildings: which of their blocks touch open sky, and the building block set itself."""
import json, sys
from collections import Counter, deque
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World
from blocks import is_open, is_natural, short
from e5_plan import is_building, is_veg

w = World(REGION)
B = json.load(open('E:/eva-map-buildings/deliver/e5-buildings.json', encoding='utf8'))
deep = [b for b in B if b['cls'] == 'deep' and b['area'].startswith('城北')]


def sky(x, y, z, up=48):
    for k in range(up):
        s = w.get(x, y + k, z)
        if not (is_open(s) or is_veg(s)):
            return False
    return True


def building_set(b):
    """Flood the building blocks from the seed box above the floor (6-neighbour), limited around it."""
    x0, z0, x1, z1 = b['bbox']
    F, roof = b['floor'], b['roof']
    lo, hi = F + 1, roof + 3
    seeds = [(x, y, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1) for y in range(lo, hi + 1) if is_building(w.get(x, y, z))]
    seen = set(seeds)
    q = deque(seeds)
    while q:
        x, y, z = q.popleft()
        for d in [(a, b, c) for a in (-1, 0, 1) for b in (-1, 0, 1) for c in (-1, 0, 1) if (a, b, c) != (0, 0, 0)]:
            # 26 neighbours: gutters and awnings touch the walls only along an edge
            n = (x + d[0], y + d[1], z + d[2])
            if n in seen or not (x0 - 8 <= n[0] <= x1 + 8 and z0 - 8 <= n[2] <= z1 + 8 and lo <= n[1] <= hi):
                continue
            if is_building(w.get(*n)):
                seen.add(n)
                q.append(n)
    return seen


if __name__ == '__main__':
    out = []
    for b in deep:
        cells = building_set(b)
        exposed = []
        for (x, y, z) in cells:
            for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, 0, 1), (0, 0, -1)):
                n = (x + d[0], y + d[1], z + d[2])
                if n in cells:
                    continue
                if is_open(w.get(*n)) and sky(*n):
                    exposed.append((x, y, z))
                    break
        xs = [c[0] for c in cells]; zs = [c[2] for c in cells]
        mats = Counter(short(w.get(*c)) for c in cells)
        bes = [c for c in cells if w.block_entity(*c)]
        b2 = dict(id=b['id'], bbox=[min(xs), min(zs), max(xs), max(zs)], floor=b['floor'], roof=b['roof'], cells=len(cells),
                  exposed=len(exposed), exposed_sample=exposed[:5], block_entities=len(bes), mats=dict(mats.most_common(6)))
        out.append(b2)
        print(b2['id'], b2['bbox'], 'blocks', len(cells), 'exposed', len(exposed), exposed[:3], 'BE', len(bes), list(mats.most_common(4)))
    json.dump(out, open('E:/eva-map-buildings/scan/deep_check.json', 'w', encoding='utf8'), ensure_ascii=False, indent=1)
