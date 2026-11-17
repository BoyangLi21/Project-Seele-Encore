"""Vertical section along each dead end's road: 30 blocks back along the spur to 20 ahead, 8 below to 16 above the end.
Colours by block; declared road cells marked under the section in red, walk in blue; the end column in yellow.
usage: road_dead_ends_sections.py <capture> <network.npz> <ends.json with x,z,feet,back,id,kind> <outdir> [ids...]"""
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
ends = json.load(open(sys.argv[3], encoding='utf8'))
ends = ends['ends'] if isinstance(ends, dict) else ends
out = Path(sys.argv[4])
out.mkdir(parents=True, exist_ok=True)
pick = set(map(int, sys.argv[5:]))
ax, az = map(int, net['bounds'][:2])
AIR = ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air')
FIX = {'grass_block': (90, 160, 60), 'dirt': (130, 95, 60), 'stone': (125, 125, 125), 'water': (50, 90, 200), 'sand': (220, 210, 150)}


def colour(st):
    n = st.split('[')[0]
    short = n.split(':')[-1]
    if n in AIR:
        return (235, 245, 255)
    if n.startswith('trafficcraft:'):
        return (40, 40, 45) if 'asphalt' in short else (200, 200, 195)
    if short in FIX:
        return FIX[short]
    if 'leaves' in short:
        return (50, 120, 50)
    h = int(hashlib.md5(short.encode()).hexdigest()[:4], 16) / 65535
    r, g, b = colorsys.hsv_to_rgb(h, .45, .85)
    return int(r * 255), int(g * 255), int(b * 255)


BACK, AHEAD, BELOW, ABOVE, P = 30, 20, 8, 16, 6
tiles = []
for e in ends:
    if pick and e['id'] not in pick:
        continue
    d = np.array([e['x'] - e['back'][0], e['z'] - e['back'][1]], float)
    d = d / (np.linalg.norm(d) or 1)
    f = int(np.floor(e['feet']))
    W, H = BACK + AHEAD + 1, BELOW + ABOVE + 3
    img = np.zeros((H, W, 3), np.uint8)
    for i, t in enumerate(range(-BACK, AHEAD + 1)):
        x, z = int(round(e['x'] + d[0] * t)), int(round(e['z'] + d[1] * t))
        for j, y in enumerate(range(f + ABOVE, f - BELOW - 1, -1)):
            try:
                img[j, i] = colour(cap.state(x, y, z))
            except ValueError:
                img[j, i] = (255, 0, 255)
        iz, ix = z - az, x - ax
        r = 0 <= iz < net['road'].shape[0] and 0 <= ix < net['road'].shape[1]
        img[H - 2, i] = (230, 30, 30) if r and net['road'][iz, ix] else (60, 150, 255) if r and net['walk'][iz, ix] else (30, 30, 30)
        img[H - 1, i] = (30, 30, 30)
    im = Image.fromarray(img).resize((W * P, H * P), Image.NEAREST)
    dr = ImageDraw.Draw(im)
    dr.rectangle((BACK * P, 0, BACK * P + P - 1, (H - 2) * P), outline=(255, 220, 0))
    yy = (ABOVE + (f - e['feet']) + 1) * P
    dr.line((0, (ABOVE + 1) * P, W * P, (ABOVE + 1) * P), fill=(255, 220, 0))
    dr.rectangle((0, 0, W * P, 11), fill=(0, 0, 0))
    dr.text((2, 0), f"#{e['id']} ({e['x']},{e['z']}) feet y{e['feet']:g} {e.get('kind', e.get('cls', ''))}  back<-  ->ahead", fill=(255, 255, 255))
    tiles.append(im)
C, R = 3, 6
for s in range(0, len(tiles), C * R):
    sheet = Image.new('RGB', (C * (tiles[0].width + 4), R * (tiles[0].height + 4)), (20, 20, 20))
    for k, t in enumerate(tiles[s:s + C * R]):
        sheet.paste(t, ((k % C) * (t.width + 4), (k // C) * (t.height + 4)))
    sheet.save(out / f'sections-{s // (C * R):02d}.png')
print(len(tiles), 'sections')
