"""Put the plain back into the surveyed height field where the remote air shaft's pit was dug into it.

On 1 November the field lost its ground around the shaft, and terrain written from it since has stood the shaft in a
pit. Where the present field lies two blocks or more under an earlier one, in the area connected to the shaft, the
earlier ground returns: level with the door layer on the door's own pad, and blended into the earlier relief over 64
blocks around it. The block rows that fill the same pit in a saved world use the same rule, so the field and the
world agree afterwards. Water levels are left alone; there is no water here in either field.

    git show da6910f7:src/main/resources/data/projectseele/worldgen/hakone_surface.bin.gz > before.bin.gz
    python tools/restore_air_shaft_ground.py --before before.bin.gz [--door-layer 26] [--resource <field>]

Running it again changes nothing: with the ground back, only the pad is still found, and it is already level.
"""
import argparse
import gzip
import hashlib
import json
import struct
from pathlib import Path

import numpy as np
from scipy.ndimage import label

RESOURCE = Path(__file__).resolve().parents[1] / 'src/main/resources/data/projectseele/worldgen/hakone_surface.bin.gz'
MAGIC = 0x484B3535
CENTRE = (-1120, -720)                  # x, z of the shaft
PAD = (-1226, -1014, -807, -634)        # x0, x1, z0, z1: the door with its two panel pockets, kept level
BOX = (-1440, -800, -1040, -400)        # x0, x1, z0, z1: the pit and its slopes lie well inside
BLEND = 64.0                            # blocks over which the level pad passes into the earlier relief
LOWERED = 2.0                           # a column counts as dug out from this difference on


def read(path):
    raw = gzip.decompress(Path(path).read_bytes())
    magic, x, z, step, width, depth = struct.unpack('>6i', raw[:24])
    if magic != MAGIC or len(raw) != 24 + 4 * width * depth:
        raise SystemExit(f'{path} is not a surface field')
    return (x, z, step, width, depth), np.frombuffer(raw, '>i2', width * depth, 24).reshape(depth, width), raw


def sample(header, heights, xs, zs):
    """Ground at block columns, interpolated between the field's nodes as HakoneSurfaceField does."""
    x, z, step, width, depth = header
    fx = np.clip((xs - x) / step, 0, width - 1)
    fz = np.clip((zs - z) / step, 0, depth - 1)
    ix = np.minimum(fx.astype(int), width - 2)
    iz = np.minimum(fz.astype(int), depth - 2)
    dx, dz = fx - ix, fz - iz
    h = lambda j, i: heights[j, i] / 16.0
    return (h(iz, ix) * (1 - dx) + h(iz, ix + 1) * dx) * (1 - dz) + (h(iz + 1, ix) * (1 - dx) + h(iz + 1, ix + 1) * dx) * dz


def plan(before, now, layer):
    """For the block columns of BOX as [z, x]: the ground wanted, and the columns it applies to."""
    xs = np.arange(BOX[0], BOX[1] + 1)[None, :]
    zs = np.arange(BOX[2], BOX[3] + 1)[:, None]
    outside = np.maximum(np.maximum(PAD[0] - xs, xs - PAD[1]), np.maximum(PAD[2] - zs, zs - PAD[3])).astype(float)
    weight = np.clip(outside / BLEND, 0, 1)
    weight = weight * weight * (3 - 2 * weight)
    lowered = (before - now >= LOWERED) | (outside <= 0)
    # Only what is joined to the shaft: other places where the two fields differ are other work.
    parts, _ = label(lowered)
    dug = parts == parts[CENTRE[1] - BOX[2], CENTRE[0] - BOX[0]]
    if dug[0].any() or dug[-1].any() or dug[:, 0].any() or dug[:, -1].any():
        raise SystemExit('The lowered ground reaches the edge of the work box; nothing changed')
    return layer * (1 - weight) + before * weight, dug


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--before', type=Path, required=True, help='the field as it was before the pit, e.g. from commit da6910f7')
    parser.add_argument('--resource', type=Path, default=RESOURCE)
    parser.add_argument('--door-layer', type=int, default=26, help='y of the top ground block on the pad')
    a = parser.parse_args()
    header, heights, raw = read(a.resource)
    old_header, old_heights, _ = read(a.before)
    x, z, step, width, depth = header
    xs = np.arange(BOX[0], BOX[1] + 1)[None, :].astype(float)
    zs = np.arange(BOX[2], BOX[3] + 1)[:, None].astype(float)
    wanted, dug = plan(sample(old_header, old_heights, xs, zs), sample(header, heights, xs, zs), a.door_layer)

    # The field's own nodes inside the box.
    ix = np.arange(-(-(BOX[0] - x) // step), (BOX[1] - x) // step + 1)
    iz = np.arange(-(-(BOX[2] - z) // step), (BOX[3] - z) // step + 1)
    if ix[0] < 0 or iz[0] < 0 or ix[-1] >= width or iz[-1] >= depth:
        raise SystemExit('The field does not cover the shaft')
    columns = np.ix_(z + step * iz - BOX[2], x + step * ix - BOX[0])
    nodes = np.ix_(iz, ix)
    new = heights.copy()
    part = new[nodes]
    part[dug[columns]] = np.rint(wanted[columns][dug[columns]] * 16).astype('>i2')
    new[nodes] = part
    changed = new != heights
    summary = {'resource': str(a.resource), 'door_layer': a.door_layer, 'nodes_in_dug_area': int(dug[columns].sum()),
               'nodes_changed': int(changed.sum())}
    if not changed.any():
        print(json.dumps(dict(summary, result='nothing changed')))
        return
    rows, cols = np.nonzero(changed)
    rise = (new.astype(float) - heights)[changed] / 16
    summary.update(x=[int(x + step * cols.min()), int(x + step * cols.max())], z=[int(z + step * rows.min()), int(z + step * rows.max())],
                   raised=int((rise > 0).sum()), lowered=int((rise < 0).sum()), largest_rise=round(float(rise.max()), 2),
                   largest_cut=round(float(-rise.min()), 2), sha256_before=hashlib.sha256(a.resource.read_bytes()).hexdigest())
    payload = raw[:24] + new.tobytes() + raw[24 + 2 * width * depth:]
    packed = gzip.compress(payload, compresslevel=6, mtime=0)
    a.resource.write_bytes(packed)
    print(json.dumps(dict(summary, sha256_after=hashlib.sha256(packed).hexdigest())))


if __name__ == '__main__':
    main()
