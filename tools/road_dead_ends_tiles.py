"""Top-down block-colour tiles around each dead end (48x48 blocks), declared road edges in red, walk in blue, end in yellow.
usage: road_dead_ends_tiles.py <capture> <network.npz> <classified.json> <outdir> [--level] [ids...]
--level: slice at each end's walking height instead of the top surface (dark = wall at head height, white = open drop)."""
import colorsys
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from plan_station_access_corridor import CapturedSurface

cap = CapturedSurface(sys.argv[1], partial=True)
net = np.load(sys.argv[2])
ends = json.load(open(sys.argv[3], encoding='utf8'))['ends']
out = Path(sys.argv[4])
out.mkdir(parents=True, exist_ok=True)
LEVEL = '--level' in sys.argv
pick = set(int(a) for a in sys.argv[5:] if a != '--level')
ax, az = map(int, net['bounds'][:2])
cx, cz = map(int, cap.bounds[:2])
hi = cap.measured['highest']
FIX = {'grass_block': (90, 160, 60), 'dirt': (130, 95, 60), 'stone': (125, 125, 125), 'water': (50, 90, 200), 'sand': (220, 210, 150),
       'oak_leaves': (40, 110, 40), 'spruce_leaves': (40, 90, 50), 'birch_leaves': (80, 130, 60), 'gravel': (140, 135, 130),
       'asphalt': (45, 45, 50), 'concrete': (190, 190, 185), 'smooth_stone': (165, 165, 165), 'smooth_stone_slab': (175, 175, 175)}
AIR = ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air')


def colour(n):
    short = n.split(':')[-1]
    for k, v in FIX.items():
        if short == k or (k in ('asphalt', 'concrete') and short.startswith(k) and n.startswith('trafficcraft:')):
            return v
    if 'leaves' in short:
        return (50, 110, 50)
    h = int(hashlib.md5(short.encode()).hexdigest()[:4], 16) / 65535
    r, g, b = colorsys.hsv_to_rgb(h, .45, .85)
    return int(r * 255), int(g * 255), int(b * 255)


R, P = 24, 4
tiles = []
for e in ends:
    if pick and e['id'] not in pick:
        continue
    x0, z0 = e['x'] - R, e['z'] - R
    img = np.zeros((2 * R, 2 * R, 3), np.uint8)
    for j in range(2 * R):
        for i in range(2 * R):
            x, z = x0 + i, z0 + j
            try:
                if LEVEL:
                    # Slice at the end's height: the floor block if the walking space is open, the wall block if not.
                    y = int(np.floor(e['feet']))
                    s = cap.state(x, y, z)
                    if s.split('[')[0] in AIR or 'layers=' in s:
                        y -= 1
                        s = cap.state(x, y, z)
                        if s.split('[')[0] in AIR:
                            img[j, i] = (255, 255, 255)
                            continue
                    else:
                        s = cap.state(x, y + 1, z) if cap.state(x, y + 1, z).split('[')[0] not in AIR else s
                        img[j, i] = np.array(colour(s.split('[')[0])) * .35
                        continue
                    img[j, i] = colour(s.split('[')[0])
                    continue
                y = int(hi[z - cz, x - cx])
                s = cap.state(x, y, z)
                while s.split('[')[0] in AIR and y > -64:
                    y -= 1
                    s = cap.state(x, y, z)
                c = np.array(colour(s.split('[')[0]), float)
                # Shade by height relative to the end.
                c = np.clip(c * (1 + (y - e['feet']) * .015), 0, 255)
                img[j, i] = c
            except (ValueError, IndexError):
                img[j, i] = (255, 0, 255)
    im = Image.fromarray(img).resize((2 * R * P, 2 * R * P), Image.NEAREST)
    d = ImageDraw.Draw(im)
    road, walk = net['road'], net['walk']
    for j in range(2 * R):
        for i in range(2 * R):
            x, z = x0 + i, z0 + j
            iz, ix = z - az, x - ax
            if not (0 <= iz < road.shape[0] and 0 <= ix < road.shape[1]):
                continue
            if road[iz, ix] or walk[iz, ix]:
                col = (255, 40, 40) if road[iz, ix] else (60, 160, 255)
                for di, dj, edge in ((1, 0, (P - 1, 0, P - 1, P - 1)), (-1, 0, (0, 0, 0, P - 1)), (0, 1, (0, P - 1, P - 1, P - 1)), (0, -1, (0, 0, P - 1, 0))):
                    nz, nx = iz + dj, ix + di
                    other = 0 <= nz < road.shape[0] and 0 <= nx < road.shape[1] and (road[nz, nx] if road[iz, ix] else (walk[nz, nx] or road[nz, nx]))
                    if not other:
                        d.line((i * P + edge[0], j * P + edge[1], i * P + edge[2], j * P + edge[3]), fill=col)
    d.ellipse((R * P - 6, R * P - 6, R * P + 6, R * P + 6), outline=(255, 255, 0), width=2)
    label = f"#{e['id']} ({e['x']},{e['z']}) y{e['feet']:g} {e.get('kind', e.get('cls'))}" + (' slice' if LEVEL else '')
    d.rectangle((0, 0, im.width, 22), fill=(0, 0, 0))
    d.text((2, 0), label, fill=(255, 255, 255))
    d.text((2, 11), ','.join(e.get('why', []))[:46] + f" spur{e['spur']}", fill=(255, 255, 0))
    tiles.append(im)
W, H = 6, 4
for s in range(0, len(tiles), W * H):
    sheet = Image.new('RGB', (W * (2 * R * P + 4), H * (2 * R * P + 4)), (30, 30, 30))
    for k, t in enumerate(tiles[s:s + W * H]):
        sheet.paste(t, ((k % W) * (t.width + 4), (k // W) * (t.height + 4)))
    sheet.save(out / f'sheet-{s // (W * H):02d}.png')
print(len(tiles), 'tiles')
