"""Top-down block-colour view of a region with the declared road (red) and walk (blue) edges, 1 block = P pixels.
Optional rows files overlay the changed columns (cut: orange, new paving: cyan).
usage: road_region_top.py <capture> <network.npz> <out.png> x0 z0 x1 z1 [P] [--rows rows.json ...] [--ends ends.json]"""
import colorsys
import hashlib
import json
import sys

import numpy as np
from PIL import Image, ImageDraw

from plan_station_access_corridor import CapturedSurface

FIX = {'grass_block': (90, 160, 60), 'dirt': (130, 95, 60), 'stone': (125, 125, 125), 'water': (50, 90, 200), 'sand': (220, 210, 150),
       'oak_leaves': (40, 110, 40), 'spruce_leaves': (40, 90, 50), 'birch_leaves': (80, 130, 60), 'gravel': (140, 135, 130),
       'asphalt': (45, 45, 50), 'concrete': (190, 190, 185), 'smooth_stone': (165, 165, 165), 'smooth_stone_slab': (175, 175, 175),
       'light_gray_concrete': (175, 175, 170), 'gray_concrete': (110, 110, 112)}
AIR = ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air')


def colour(n):
    short = n.split(':')[-1]
    if short in FIX:
        return FIX[short]
    if 'asphalt' in short or short.startswith('road'):
        return (45, 45, 50)
    h = int(hashlib.md5(short.encode()).hexdigest()[:4], 16) / 65535
    r, g, b = colorsys.hsv_to_rgb(h, .45, .85)
    return int(r * 255), int(g * 255), int(b * 255)


def render(cap, net, x0, z0, x1, z1, P=3, rows=(), ends=()):
    ax, az = map(int, net['bounds'][:2])
    road, walk = net['road'], net['walk']
    cx, cz = map(int, cap.bounds[:2])
    hi = cap.measured['highest']
    W, H = x1 - x0 + 1, z1 - z0 + 1
    img = np.zeros((H, W, 3), np.uint8)
    for z in range(z0, z1 + 1):
        for x in range(x0, x1 + 1):
            try:
                y = int(hi[z - cz, x - cx])
            except IndexError:
                continue
            for yy in range(y, y - 6, -1):
                try:
                    s = cap.state(x, yy, z)
                except ValueError:
                    break
                n = s.split('[')[0]
                if n not in AIR and not n.endswith(('grass', 'fern', 'flower', 'torch')):
                    img[z - z0, x - x0] = colour(n)
                    break
    big = Image.fromarray(img).resize((W * P, H * P), Image.NEAREST)
    d = ImageDraw.Draw(big)

    def at(a, x, z):
        iz, ix = z - az, x - ax
        return 0 <= iz < a.shape[0] and 0 <= ix < a.shape[1] and a[iz, ix]

    for z in range(z0, z1 + 1):
        for x in range(x0, x1 + 1):
            for a, col in ((road, (255, 40, 40)), (walk, (60, 160, 255))):
                if at(a, x, z) and not all(at(a, x + dx, z + dz) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    i, j = (x - x0) * P, (z - z0) * P
                    d.rectangle((i, j, i + P - 1, j + P - 1), outline=col)
                    break
    for path, col in rows:
        cols = {(r[0], r[2]) for r in json.load(open(path, encoding='utf8'))}
        for x, z in cols:
            if x0 <= x <= x1 and z0 <= z <= z1:
                i, j = (x - x0) * P, (z - z0) * P
                d.rectangle((i, j, i + P - 1, j + P - 1), fill=col)
    for e in ends:
        i, j = (e['x'] - x0) * P, (e['z'] - z0) * P
        if 0 <= i < W * P and 0 <= j < H * P:
            d.ellipse((i - 5, j - 5, i + 5, j + 5), outline=(255, 255, 0), width=2)
            d.text((i + 6, j - 6), str(e['id']), fill=(255, 255, 0))
    for k in range(0, W, 16):
        if (x0 + k) % 16 == 0:
            d.text((k * P + 1, 1), str(x0 + k), fill=(255, 255, 255))
    for k in range(0, H, 16):
        if (z0 + k) % 16 == 0:
            d.text((1, k * P + 1), str(z0 + k), fill=(255, 255, 255))
    return big


def main():
    a = sys.argv[1:]
    rows, ends = [], []
    cols = [(255, 150, 0), (0, 230, 230), (255, 0, 255)]
    while '--rows' in a:
        k = a.index('--rows')
        rows.append((a[k + 1], cols[len(rows) % 3]))
        del a[k:k + 2]
    if '--ends' in a:
        k = a.index('--ends')
        ends = json.load(open(a[k + 1], encoding='utf8'))['ends']
        del a[k:k + 2]
    cap = CapturedSurface(a[0], partial=True)
    net = np.load(a[1])
    x0, z0, x1, z1 = map(int, a[3:7])
    P = int(a[7]) if len(a) > 7 else 3
    render(cap, net, x0, z0, x1, z1, P, rows, ends).save(a[2])


if __name__ == '__main__':
    main()
