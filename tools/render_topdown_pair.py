"""Top-down before/after of boxes straight from two copies of the world: colour of the top non-air block
with hillshade, side by side, one row per box.

    render_topdown_pair.py BEFORE AFTER OUT.png SCALE BOXES.json   (BOXES: [[label, x0, x1, z0, z1], ...])
"""
import json
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import terrain_regrade as tr

TABLE = [('water', (48, 90, 200)), ('grass_block', (96, 150, 60)), ('spruce_leaves', (35, 80, 45)), ('dark_oak_leaves', (35, 85, 30)),
         ('birch_leaves', (100, 140, 60)), ('leaves', (50, 110, 40)), ('log', (90, 70, 40)), ('podzol', (110, 85, 50)), ('dirt', (130, 95, 60)),
         ('sand', (220, 210, 160)), ('gravel', (140, 135, 130)), ('stone', (125, 125, 125)), ('asphalt', (45, 45, 48)), ('concrete', (170, 170, 165)),
         ('glass', (170, 210, 230)), ('snow', (250, 250, 250)), ('planks', (150, 110, 70)), ('tall_grass', (110, 170, 70)), ('grass', (110, 170, 70)),
         ('fern', (80, 140, 60)), ('brick', (150, 80, 60)), ('terracotta', (160, 100, 70))]


def colour(name):
    n = name.split('[')[0].split(':')[-1]
    for key, c in TABLE:
        if key in n:
            return c
    return (180, 140, 160)


def top_rgb(world, x0, x1, z0, z1, y0=-64, y1=260):
    b = tr.Box(world, x0, x1, y0, y1, z0, z1)
    k = b.kind_grid()
    n = k.shape[0]
    solid = k != tr.AIRK
    top = n - 1 - np.argmax(solid[::-1], 0)
    ids = np.take_along_axis(b.ids, top[None], 0)[0]
    lut = np.array([colour(p) for p in b.palette], np.float32)
    rgb = lut[ids]
    h = top.astype(float)
    shade = np.clip(1 + (-np.gradient(h, axis=1) - np.gradient(h, axis=0)) * .18, .45, 1.5)
    rgb = np.clip(rgb * shade[..., None], 0, 255).astype(np.uint8)
    rgb[~solid.any(0)] = (255, 0, 255)
    return Image.fromarray(rgb)


def main():
    before, after, out, scale = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
    boxes = json.load(open(sys.argv[5], encoding='utf8'))
    font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 16)
    rows = []
    for lab, x0, x1, z0, z1 in boxes:
        a, b = top_rgb(before, x0, x1, z0, z1), top_rgb(after, x0, x1, z0, z1)
        size = (int(a.width * scale), int(a.height * scale))
        a, b = a.resize(size, Image.NEAREST), b.resize(size, Image.NEAREST)
        im = Image.new('RGB', (2 * size[0] + 8, size[1] + 26), (14, 14, 14))
        im.paste(a, (0, 26))
        im.paste(b, (size[0] + 8, 26))
        d = ImageDraw.Draw(im)
        d.text((6, 3), f'改前 {lab}', fill='white', font=font)
        d.text((size[0] + 14, 3), '改后', fill='white', font=font)
        rows.append(im)
    w = max(r.width for r in rows)
    sheet = Image.new('RGB', (w, sum(r.height for r in rows)), (14, 14, 14))
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height
    sheet.save(out)
    print(out, sheet.size)


if __name__ == '__main__':
    main()
