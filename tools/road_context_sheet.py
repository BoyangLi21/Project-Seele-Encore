"""Contact sheet of wide top-down views (default 192 blocks square) around dead ends, one per end, with the end's
spur traced in yellow, for judging long spurs that a 48-block tile cannot show.
usage: road_context_sheet.py <capture> <network.npz> <skeleton.npy> <decisions.json> <out-prefix> id [id ...] [--size N]"""
import json
import sys

import numpy as np
from PIL import Image, ImageDraw

from plan_station_access_corridor import CapturedSurface
from road_region_top import render
from road_dead_ends_scan_pruned import crossing, bfs_spur


def main():
    a = sys.argv[1:]
    size = 192
    if '--size' in a:
        k = a.index('--size')
        size = int(a[k + 1])
        del a[k:k + 2]
    cap = CapturedSurface(a[0], partial=True)
    net = np.load(a[1])
    ax, az = map(int, net['bounds'][:2])
    sk = np.load(a[2]).astype(bool)
    cross = crossing(sk)
    ds = {d['id']: d for d in json.load(open(a[3], encoding='utf8'))}
    ids = [int(i) for i in a[5:]]
    T, per = 300, 4
    sheets = [ids[k:k + 12] for k in range(0, len(ids), 12)]
    for n, group in enumerate(sheets):
        sheet = Image.new('RGB', (T * per, T * ((len(group) + per - 1) // per)), (30, 30, 30))
        for k, i in enumerate(group):
            d = ds[i]
            h = size // 2
            x0, z0 = d['x'] - h, d['z'] - h
            img = render(cap, net, x0, z0, x0 + size - 1, z0 + size - 1, 2, ends=[dict(id=i, x=d['x'], z=d['z'])])
            dr = ImageDraw.Draw(img)
            # trace the spur
            best = None
            for r in range(6):
                for dz in range(-r, r + 1):
                    for dx in range(-r, r + 1):
                        iz, ix = d['z'] + dz - az, d['x'] + dx - ax
                        if best is None and 0 <= iz < sk.shape[0] and 0 <= ix < sk.shape[1] and sk[iz, ix]:
                            best = (iz, ix)
            if best:
                path, _ = bfs_spur(sk, cross, best, 4000)
                for pz, px in path:
                    wx, wz = px + ax - x0, pz + az - z0
                    if 0 <= wx < size and 0 <= wz < size:
                        dr.rectangle((wx * 2, wz * 2, wx * 2 + 1, wz * 2 + 1), fill=(255, 255, 0))
            img = img.resize((T, T))
            dr = ImageDraw.Draw(img)
            dr.rectangle((0, 0, T, 24), fill=(0, 0, 0))
            dr.text((2, 0), f"#{i} ({d['x']},{d['z']}) y{d['feet']:.0f} spur{d['spur']} {d['decision']}", fill=(255, 255, 255))
            dr.text((2, 11), d['rule_note'][:48], fill=(255, 255, 0))
            sheet.paste(img, ((k % per) * T, (k // per) * T))
            for key in list(cap.editor.regions):
                if abs(key[0] * 512 - d['x']) > 1024 or abs(key[1] * 512 - d['z']) > 1024:
                    del cap.editor.regions[key]
        sheet.save(f'{a[4]}-{n:02d}.png')
        print(f'{a[4]}-{n:02d}.png')


if __name__ == '__main__':
    main()
