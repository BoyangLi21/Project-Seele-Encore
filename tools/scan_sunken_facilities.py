"""Find built pads cut into a hill: flat built areas whose surroundings rise sheer above them.

From a scan mosaic (folder of .npy layers, see scan_surface_columns.py): connected areas of
at least --min columns whose highest solid block is built, of one height within two blocks
(aprons, platforms, plazas, sports grounds). For each, the natural ground two to six columns
outside is compared with the pad: a ring share well above the pad is a pad sunk into terrain,
the case of the NERV airport. Pads under soil (buried parts) are counted too when the ground
right over the pad edge stands above it.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

import scan_surface_columns as sc

X0, Z0 = -5120, -8704


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mosaic', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--min', type=int, default=600)
    p.add_argument('--tile', type=int, default=3072)
    a = p.parse_args()
    L = {k: np.load(a.mosaic / f'{k}.npy', mmap_mode='r') for k in ('ground', 'solid', 'solid_id', 'water')}
    pal = [str(s) for s in np.load(a.mosaic / 'palette.npy')]
    pk = np.array([sc.kind(s) for s in pal], np.int8)
    nz, nx = L['ground'].shape
    found = []
    pad = 256
    for tz in range(0, nz, a.tile):
        for tx in range(0, nx, a.tile):
            z0, z1, x0, x1 = max(0, tz - pad), min(nz, tz + a.tile + pad), max(0, tx - pad), min(nx, tx + a.tile + pad)
            g = np.array(L['ground'][z0:z1, x0:x1]).astype(np.int32)
            s = np.array(L['solid'][z0:z1, x0:x1]).astype(np.int32)
            if (g > -30000).sum() < 1000:
                continue
            built = (pk[np.array(L["solid_id"][z0:z1, x0:x1])] == 4) & (s >= g) & (s > -30000)
            lab, n = ndimage.label(built)
            if not n:
                continue
            for i, sl in enumerate(ndimage.find_objects(lab), 1):
                m = lab[sl] == i
                if m.sum() < a.min:
                    continue
                zz, xx = np.nonzero(m)
                cz, cx = int(np.median(zz)) + sl[0].start, int(np.median(xx)) + sl[1].start
                if not (tz <= cz + z0 < tz + a.tile and tx <= cx + x0 < tx + a.tile):
                    continue
                hs = s[sl][m]
                level = int(np.median(hs))
                flat = (np.abs(hs - level) <= 2).mean()
                if flat < .7:
                    continue
                e0 = max(0, sl[0].start - 8), max(0, sl[1].start - 8)
                e1 = min(g.shape[0], sl[0].stop + 8), min(g.shape[1], sl[1].stop + 8)
                big = np.zeros((e1[0] - e0[0], e1[1] - e0[1]), bool)
                big[sl[0].start - e0[0]:sl[0].stop - e0[0], sl[1].start - e0[1]:sl[1].stop - e0[1]] = m
                big = ndimage.binary_fill_holes(big)
                ring = ndimage.binary_dilation(big, iterations=6) & ~ndimage.binary_dilation(big, iterations=2)
                gr = g[e0[0]:e1[0], e0[1]:e1[1]][ring]
                br = built[e0[0]:e1[0], e0[1]:e1[1]][ring]
                nat = gr[(gr > -30000) & ~br]
                if len(nat) < 40:
                    continue
                above = nat - level
                share4 = float((above >= 4).mean())
                if share4 < .2:
                    continue
                found.append(dict(centre=[cx + x0 + X0, cz + z0 + Z0], x=[int(xx.min() + sl[1].start + x0 + X0), int(xx.max() + sl[1].start + x0 + X0)],
                                  z=[int(zz.min() + sl[0].start + z0 + Z0), int(zz.max() + sl[0].start + z0 + Z0)], columns=int(m.sum()), level=level,
                                  ring_share_4_above=round(share4, 2), ring_p90_above=int(np.percentile(above, 90)), ring_max_above=int(above.max()),
                                  score=round(float(m.sum()) ** .5 * share4 * max(0, np.percentile(above, 90)), 1)))
            print('tile', tx, tz, len(found), flush=True)
    found.sort(key=lambda f: -f['score'])
    a.out.write_text(json.dumps(found, indent=0), 'utf8')
    print(len(found))


if __name__ == '__main__':
    main()
