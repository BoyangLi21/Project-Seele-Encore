"""Canon recolour of the M5 infill blocks (lots): same buildings, the pale Tokyo-3 palette.

  python canon_recolour.py <out dir> <M5 lot rows.json>...

For every cell an M5 lot list placed, if the world (BUILDINGS_WORLD) still holds that block and the block is in the
map below, the cell turns to its canon colour. Street level and below (sidewalks, paving) stay as they are, and so do
the two schools and the shrine (its torii stays red). Only full blocks are mapped, so no block properties change.
"""
import json, sys
from collections import Counter
from pathlib import Path
from mca import REGION, World

Y = 80
MAP = {'smooth_sandstone': 'smooth_quartz', 'white_terracotta': 'white_concrete', 'dark_oak_planks': 'gray_concrete',
       'black_concrete': 'gray_concrete', 'gray_stained_glass': 'light_gray_stained_glass', 'andesite': 'light_gray_concrete',
       'polished_andesite': 'light_gray_concrete', 'polished_basalt': 'light_gray_concrete', 'deepslate_tiles': 'gray_concrete',
       'red_terracotta': 'light_gray_concrete', 'brown_terracotta': 'gray_concrete', 'green_terracotta': 'cyan_terracotta',
       'yellow_terracotta': 'white_concrete', 'pink_terracotta': 'white_concrete', 'lime_terracotta': 'light_blue_terracotta',
       'orange_terracotta': 'light_gray_concrete', 'blue_terracotta': 'light_blue_terracotta', 'green_concrete': 'cyan_terracotta',
       'red_concrete': 'light_gray_concrete'}
KEEP_LOTS = [(-210, 180), (270, 420), (270, 380)]          # schools and the shrine
HALF = 16


def kept(x, z):
    return any(abs(x - cx) <= HALF and abs(z - cz) <= HALF for cx, cz in KEEP_LOTS)


def main(out, files):
    w = World(REGION)
    rows, stats, seen = [], Counter(), set()
    for f in files:
        for x, y, z, _, after in json.load(open(f)):
            if (x, y, z) in seen or y <= Y or kept(x, z) or '[' in after:
                continue
            seen.add((x, y, z))
            name = after.split(':', 1)[1]
            if name not in MAP:
                continue
            cur = w.get(x, y, z)
            if cur != after:
                stats['changed since M5'] += 1
                continue
            rows.append([x, y, z, cur, 'minecraft:' + MAP[name]])
            stats[name + '->' + MAP[name]] += 1
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / 'rows.json').write_text(json.dumps(rows), 'utf8')
    (Path(out) / 'report.json').write_text(json.dumps(dict(rows=len(rows), stats=stats), indent=1), 'utf8')
    print(len(rows), stats.most_common(12))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
