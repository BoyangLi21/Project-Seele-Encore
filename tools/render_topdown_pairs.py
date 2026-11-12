"""Top-down before/after crops around listed sites, from two world captures, for review sheets.

Each column is coloured by its highest block (TrafficCraft asphalt dark, concrete light, paint yellow,
old paving grey, plants green, water blue, soil brown, everything else tan) and shaded by height; columns
whose highest block or its height changed have the edge of their region dotted red on the after crop.
sites.json: [{"label", "x", "z"}, ...]. Sheets hold PER_SHEET sites, three pairs to a row.
usage: render_topdown_pairs.py <before-capture> <after-capture> <sites.json> <out-prefix> [radius] [per-sheet]"""
import json
import sys

import numpy as np
from PIL import Image, ImageDraw

from plan_station_access_corridor import CapturedSurface

BEFORE, AFTER = sys.argv[1], sys.argv[2]
sites = json.load(open(sys.argv[3], encoding='utf8'))
PREFIX = sys.argv[4]
R = int(sys.argv[5]) if len(sys.argv) > 5 else 40
PER_SHEET = int(sys.argv[6]) if len(sys.argv) > 6 else 18
try:
    from PIL import ImageFont
    FONT = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 13)
except OSError:
    FONT = None
SCALE = 3 if R <= 60 else 1   # large areas at one pixel per block, without the change outline
from verify_hakone_network_candidate import PAVEMENT as OLD_PAVING


def colour(state):
    n = state.split('[')[0]
    if n.startswith('trafficcraft:asphalt_pattern') or 'colored' in n:
        return (220, 200, 60)
    if n.startswith('trafficcraft:asphalt'):
        return (55, 55, 60)
    if n.startswith('trafficcraft:'):
        return (190, 190, 185)
    if n in OLD_PAVING:
        return (120, 120, 125)
    if 'water' in n:
        return (50, 90, 200)
    if n.endswith(('leaves', 'grass', 'fern', 'sapling', 'bush')) or n == 'minecraft:grass_block' or 'moss' in n:
        return (70, 140, 60)
    if n.endswith(('dirt', 'podzol', 'mud', 'gravel', 'sand', 'clay')) or 'dirt' in n:
        return (130, 95, 60)
    if n.endswith(('stone', 'andesite', 'granite', 'diorite', 'deepslate', 'tuff')):
        return (140, 140, 140)
    if n.endswith('_log'):
        return (100, 70, 40)
    return (200, 170, 130)


def crop(cap, x0, z0):
    a, b, A, B = cap.bounds
    H, top = cap.measured['highest'], cap.measured['top']
    W = 2 * R + 1
    names = np.empty((W, W), object)
    hts = np.full((W, W), np.nan)
    for j in range(W):
        for i in range(W):
            x, z = x0 - R + i, z0 - R + j
            if not (a <= x <= A and b <= z <= B) or not cap.measured['full'][z - b, x - a]:
                names[j, i] = ''
                continue
            y = int(H[z - b, x - a])
            names[j, i] = cap.state(x, y, z)
            hts[j, i] = y
    return names, hts


def picture(names, hts, changed=None):
    W = names.shape[0]
    rgb = np.zeros((W, W, 3), float)
    for j in range(W):
        for i in range(W):
            rgb[j, i] = colour(names[j, i]) if names[j, i] else (0, 0, 0)
    # Hillshade from the north-west.
    h = np.nan_to_num(hts, nan=np.nanmean(hts) if np.isfinite(hts).any() else 0)
    gz, gx = np.gradient(h)
    shade = np.clip(1 - .12 * (gx + gz), .55, 1.35)
    rgb = np.clip(rgb * shade[..., None], 0, 255).astype(np.uint8)
    im = Image.fromarray(rgb).resize((W * SCALE, W * SCALE), Image.NEAREST)
    if changed is not None and SCALE > 1:
        d = ImageDraw.Draw(im)
        # Outline the edge of each changed region only, so the new surface stays visible.
        p = np.pad(changed, 1)
        edge = changed & ~(p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:])
        for j, i in zip(*np.nonzero(edge)):
            d.rectangle([i * SCALE + 1, j * SCALE + 1, i * SCALE + 1, j * SCALE + 1], fill=(230, 30, 30))
    d = ImageDraw.Draw(im)
    c = R * SCALE + SCALE // 2
    d.ellipse([c - 4, c - 4, c + 4, c + 4], outline=(255, 0, 255))
    return im


tile = (2 * R + 1) * SCALE
for s0 in range(0, len(sites), PER_SHEET):
    chunk = sites[s0:s0 + PER_SHEET]
    before, after = CapturedSurface(BEFORE, partial=True), CapturedSurface(AFTER, partial=True)
    rows = (len(chunk) + 2) // 3
    sheet = Image.new('RGB', (3 * (2 * tile + 18), rows * (tile + 22)), (30, 30, 30))
    for k, s in enumerate(chunk):
        nb, hb = crop(before, s['x'], s['z'])
        na, ha = crop(after, s['x'], s['z'])
        changed = (nb != na) | ~np.isclose(np.nan_to_num(hb), np.nan_to_num(ha))
        px, py = (k % 3) * (2 * tile + 18), (k // 3) * (tile + 22)
        sheet.paste(picture(nb, hb), (px, py + 18))
        sheet.paste(picture(na, ha, changed), (px + tile + 4, py + 18))
        ImageDraw.Draw(sheet).text((px + 2, py + 3), f"{s['label']}  ({s['x']},{s['z']})  before | after, red = changed", fill=(255, 255, 0), font=FONT)
    out = f'{PREFIX}-{s0 // PER_SHEET}.png'
    sheet.save(out)
    print(out, len(chunk))
