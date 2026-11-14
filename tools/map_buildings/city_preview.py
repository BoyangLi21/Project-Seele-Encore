"""Isometric preview of planned rows, to review designs before a client run.

city_preview.py <out.png> <x0,z0,x1,z1|-> <scale> <rows.json[::dy]> ...

Draws every planned non-air block (the rows' new state) as a shaded cube seen from the south-east,
with block colours approximated from the block name. Only the planned cells are drawn.
"""
import json, sys
from PIL import Image, ImageDraw

COLOURS = (
    ('froglight', (250, 220, 150)), ('shroomlight', (240, 160, 80)), ('sea_lantern', (200, 230, 225)), ('lantern', (240, 200, 120)),
    ('light_blue_stained_glass', (150, 190, 225)), ('gray_stained_glass', (90, 100, 110)), ('white_stained_glass', (225, 235, 240)),
    ('light_gray_stained_glass', (175, 180, 185)), ('glass', (185, 215, 230)),
    ('white_concrete', (225, 228, 228)), ('smooth_quartz', (235, 230, 225)), ('light_gray_concrete', (150, 150, 145)),
    ('gray_concrete', (85, 88, 92)), ('black_concrete', (25, 27, 32)), ('green_concrete', (75, 110, 40)), ('red_concrete', (160, 40, 35)),
    ('white_terracotta', (210, 180, 160)), ('red_terracotta', (145, 65, 50)), ('orange_terracotta', (165, 85, 40)),
    ('yellow_terracotta', (185, 135, 40)), ('cyan_terracotta', (90, 95, 95)), ('light_blue_terracotta', (115, 110, 140)),
    ('lime_terracotta', (105, 120, 55)), ('pink_terracotta', (160, 80, 80)), ('blue_terracotta', (75, 60, 90)),
    ('green_terracotta', (75, 85, 45)), ('brown_terracotta', (80, 55, 40)),
    ('smooth_sandstone', (220, 205, 160)), ('polished_andesite', (135, 135, 135)), ('andesite', (130, 130, 130)),
    ('smooth_stone', (160, 160, 160)), ('stone_bricks', (120, 120, 120)), ('gravel', (130, 125, 120)),
    ('deepslate', (60, 60, 65)), ('basalt', (80, 80, 85)), ('spruce', (110, 80, 50)), ('dark_oak', (65, 45, 25)),
    ('cherry_leaves', (235, 170, 200)), ('leaves', (70, 120, 50)), ('_log', (100, 80, 60)), ('grass_block', (95, 145, 65)),
    ('azalea', (80, 130, 60)), ('lightning_rod', (190, 110, 80)),
)


def colour(s):
    for k, c in COLOURS:
        if k in s:
            return c
    return (180, 120, 180)


def main(rows_files, out, box=None, scale=3):
    vox = {}
    for spec in rows_files:            # rows.json[:dy] - dy lifts a tower list from its parked depth
        f, _, dy = spec.partition('::')
        dy = int(dy or 0)
        for x, y, z, old, new in json.load(open(f, encoding='utf8')):
            if box and not (box[0] <= x <= box[2] and box[1] <= z <= box[3]):
                continue
            if 'air' not in new:
                vox[x, y + dy, z] = new
    if not vox:
        raise SystemExit('nothing to draw')
    s = scale
    # isometric: screen u = (x - z) * s, v = (x + z) * s/2 - y * s
    us = [(x - z) * s for x, y, z in vox]
    vs = [(x + z) * s / 2 - y * s for x, y, z in vox]
    u0, v0 = min(us) - 2 * s, min(vs) - 2 * s
    W, H = int(max(us) - u0 + 3 * s), int(max(vs) - v0 + 3 * s)
    img = Image.new('RGB', (W, H), (205, 220, 235))
    d = ImageDraw.Draw(img)
    for (x, y, z) in sorted(vox, key=lambda p: (p[0] + p[2], p[1])):
        c = colour(vox[x, y, z])
        u, v = (x - z) * s - u0, (x + z) * s / 2 - y * s - v0
        top = [(u, v - s / 2), (u + s, v), (u, v + s / 2), (u - s, v)]
        left = [(u - s, v), (u, v + s / 2), (u, v + 1.5 * s), (u - s, v + s)]
        right = [(u, v + s / 2), (u + s, v), (u + s, v + s), (u, v + 1.5 * s)]
        d.polygon(top, fill=c)
        d.polygon(left, fill=tuple(int(k * 0.78) for k in c))
        d.polygon(right, fill=tuple(int(k * 0.62) for k in c))
    img.save(out)
    print(out, img.size, len(vox))


if __name__ == '__main__':
    box = [int(v) for v in sys.argv[2].split(',')] if sys.argv[2] != '-' else None
    main(sys.argv[4:], sys.argv[1], box, int(sys.argv[3]))
