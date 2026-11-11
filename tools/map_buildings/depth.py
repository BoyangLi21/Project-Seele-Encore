"""Per house: floor, roof, and the ground around it (ring 2..4 columns out), to tell half-buried from swallowed."""
import json, sys
from statistics import median
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from mca import REGION, World
from blocks import is_open, is_natural
from e5_plan import is_building, is_veg

HERE = Path(__file__).parent
w = World(REGION)
houses = json.load(open(HERE / 'houses.json', encoding='utf8'))


def surface(x, z, top=330, bottom=-128):
    y = top
    while y > bottom:
        s = w.get(x, y, z)
        if s is None:
            return None
        if not is_open(s) and not is_veg(s):
            return y, s
        y -= 1
    return None


for h in houses:
    bx0, bz0, bx1, bz1 = h['bbox']
    roof = None
    for x in range(bx0 - 1, bx1 + 2):
        for z in range(bz0 - 1, bz1 + 2):
            for y in range(h['ymax'] + 12, h['floor'], -1):
                if is_building(w.get(x, y, z)):
                    roof = y if roof is None else max(roof, y)
                    break
    ring, nat = [], 0
    for x in range(bx0 - 4, bx1 + 5):
        for z in range(bz0 - 4, bz1 + 5):
            d = max(bx0 - x, x - bx1, bz0 - z, z - bz1)
            if 2 <= d <= 4:
                s = surface(x, z, top=(roof or h['ymax']) + 30)
                if s:
                    ring.append(s[0])
                    nat += is_natural(s[1])
    g = median(ring) if ring else None
    h['roof'] = roof
    h['ground'] = g
    h['ground_natural'] = round(nat / max(len(ring), 1), 2)
    if g is None or roof is None:
        h['burial'] = 'unknown'
    elif g >= roof:
        h['burial'] = 'swallowed'
    elif g >= h['floor'] + 1:
        h['burial'] = 'half'
    else:
        h['burial'] = 'inside-only'
    print(h['id'], h['bbox'], 'floor', h['floor'], 'roof', roof, 'ground', g, 'nat', h['ground_natural'], h['burial'], 'fill', h['fill'], 'doors', len(h['doors']))
json.dump(houses, open(HERE / 'houses.json', 'w', encoding='utf8'), ensure_ascii=False, indent=0)
