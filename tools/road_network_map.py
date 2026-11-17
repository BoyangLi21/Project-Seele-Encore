"""Network overview image: road (dark), walk (light), dead ends coloured by class, labelled with their index.
usage: road_network_map.py <network.npz> <ends.json> <out.png> [scale] [x0 z0 x1 z1]"""
import json
import sys

import numpy as np
from PIL import Image, ImageDraw

net = np.load(sys.argv[1])
ends = json.load(open(sys.argv[2], encoding='utf8'))['ends']
ax, az = map(int, net['bounds'][:2])
s = float(sys.argv[4]) if len(sys.argv) > 4 else 0.25
road, walk = net['road'], net['walk']
if len(sys.argv) > 8:
    x0, z0, x1, z1 = map(int, sys.argv[5:9])
else:
    x0, z0, x1, z1 = ax, az, ax + road.shape[1], az + road.shape[0]
r = road[z0 - az:z1 - az, x0 - ax:x1 - ax]
w = walk[z0 - az:z1 - az, x0 - ax:x1 - ax]
img = np.full(r.shape + (3,), 255, np.uint8)
img[w] = (170, 200, 255)
img[r] = (40, 40, 40)
im = Image.fromarray(img)
# Downscale with max pooling so thin roads survive.
k = max(1, int(round(1 / s)))
if k > 1:
    h, wd = (img.shape[0] // k) * k, (img.shape[1] // k) * k
    pooled = img[:h, :wd].reshape(h // k, k, wd // k, k, 3).min((1, 3))
    im = Image.fromarray(pooled)
    sc = 1 / k
else:
    sc = s
    im = im.resize((int(img.shape[1] * s), int(img.shape[0] * s)), Image.NEAREST)
d = ImageDraw.Draw(im)
COL = {'fix': (230, 0, 0), 'remove': (230, 0, 0), 'connect': (230, 0, 0), None: (230, 0, 0)}
for i, e in enumerate(ends):
    if not (x0 <= e['x'] < x1 and z0 <= e['z'] < z1):
        continue
    px, pz = (e['x'] - x0) * sc, (e['z'] - z0) * sc
    c = tuple(e.get('colour', COL.get(e.get('fix'), (230, 0, 0))))
    rr = 4 if sc < 1 else 6
    d.ellipse((px - rr, pz - rr, px + rr, pz + rr), outline=c, width=2)
    d.text((px + rr + 1, pz - rr), str(e.get('id', i)), fill=c)
im.save(sys.argv[3])
print(im.size)
