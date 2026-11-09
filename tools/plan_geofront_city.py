"""Voxel the hanging city of the GeoFront reference model under the real cavern ceiling.

Reads the saved world and the mesh parts exported from the model; writes rows for
write_deep_cells. Nothing is written to the world here. Cells stand only in empty air and
keep clear of launch volumes, tower travel, rails and anything already built in the cavern.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

import nbtlib
import numpy as np
from scipy.ndimage import binary_dilation, distance_transform_edt, label, uniform_filter

from map_pipeline.launch_protection import load as load_launch
from map_pipeline.native_rails import load_rails
from query_blocks import iter_selected_sections

SCALE = 0.5
DIM = 'projectseele:geofront'
Y0, Y1 = -320, 79
AIR = ('', 'minecraft:air', 'minecraft:cave_air', 'minecraft:void_air')
STATES = ('', 'minecraft:light_gray_concrete', 'minecraft:gray_concrete', 'minecraft:polished_andesite',
          'minecraft:light_blue_stained_glass')
GLASS = 4
FLOOR = 1
POST = 2
MIN_ROOF_Y = 0             # a lower "roof" is the underside of a retracted tower, not the dome
TIE_LIMIT = 30


def air_volume(world, x0, z0, x1, z1):
    """Which kind of air each cell of the box holds, 0 when it is a block. Index [y-Y0, z-z0, x-x0]."""
    shape = (Y1 - Y0 + 1, z1 - z0 + 1, x1 - x0 + 1)
    air = np.zeros(shape, np.uint8)
    selection = {(cx, cz): set(range(Y0 >> 4, (Y1 >> 4) + 1)) for cx in range(x0 >> 4, (x1 >> 4) + 1)
                 for cz in range(z0 >> 4, (z1 >> 4) + 1)}
    for cx, cz, sy, palette, ids in iter_selected_sections(world, DIM, selection, skip_unfinished=True):
        code = np.array([AIR.index(s) if s in AIR else 0 for s in (p.split('[')[0] for p in palette)], np.uint8)
        block = code[ids].reshape(16, 16, 16)
        base = sy * 16
        ya, yb = max(base, Y0), min(base + 16, Y1 + 1)
        ax, az = cx * 16 - x0, cz * 16 - z0
        xa, xb, za, zb = max(ax, 0), min(ax + 16, shape[2]), max(az, 0), min(az + 16, shape[1])
        if ya < yb and xa < xb and za < zb:
            air[ya - Y0:yb - Y0, za:zb, xa:xb] = block[ya - base:yb - base, za - az:zb - az, xa - ax:xb - ax]
    return air


def ceiling_field(open_air):
    """The block level just above the highest tall run of air in each column; -9999 where there is none."""
    solid = ~open_air
    roof = np.full(open_air.shape[1:], -9999, np.int32)
    run = np.zeros(open_air.shape[1:], np.int32)
    for level in range(open_air.shape[0] - 1):
        run = np.where(open_air[level], run + 1, 0)
        roof[(run >= 24) & solid[level + 1]] = level + 1 + Y0
    return roof


def smooth_roof(roof):
    """The dome's own surface: tower undersides dropped, gaps filled from the nearest measured column."""
    good = roof >= MIN_ROOF_Y
    nearest = distance_transform_edt(~good, return_distances=False, return_indices=True)
    return uniform_filter(roof[tuple(nearest)].astype(float), size=31)


def model_part(parts, rows, material_prefix):
    tris, kinds = [], []
    for i, row in enumerate(rows):
        wanted = [n for n, m in enumerate(row['mats']) if m.startswith(material_prefix)]
        if not wanted:
            continue
        v, f, m = parts[f'{i}_v'], parts[f'{i}_f'], parts[f'{i}_m']
        keep = np.isin(m, wanted)
        tris.append(v[f[keep]])
        kinds.append(m[keep])
    return np.concatenate(tris), np.concatenate(kinds)


def sample(tri, step):
    a, b, c = tri
    n = int(max(np.linalg.norm(b - a), np.linalg.norm(c - a), np.linalg.norm(c - b)) / step) + 2
    us, vs = np.meshgrid(np.linspace(0, 1, n), np.linspace(0, 1, n))
    keep = us + vs <= 1
    return a + np.outer(us[keep], b - a) + np.outer(vs[keep], c - a)


def tower_floors(world, shape, x0, z0):
    """Per column, the lowest level any tower reaches, with a three-block clearance all round."""
    floors = np.full(shape, 9999, np.int32)
    path = next(Path(world, 'dimensions/projectseele/geofront/data').glob('projectseele_city_rigid_topology_r45_*.dat'))
    for tower in nbtlib.load(path)['data']['Towers']:
        centre = int(tower['Centre'])
        x = centre >> 38
        z = (centre >> 12) & 0x3FFFFFF
        z = z - (1 << 26) if z >= (1 << 25) else z
        box = tower['Footprint']
        floors[max(z + int(box['MinZ']) - 3 - z0, 0):max(z + int(box['MaxZ']) + 4 - z0, 0),
               max(x + int(box['MinX']) - 3 - x0, 0):max(x + int(box['MaxX']) + 4 - x0, 0)] = int(tower['RetractedBaseY']) - 3
    return floors


def rail_mask(snapshot, shape, x0, z0, x1, z1):
    near = np.zeros(shape, bool)
    for rail in load_rails(snapshot):
        p, q = np.array(rail['a'], float), np.array(rail['b'], float)
        line = (p + np.outer(np.linspace(0, 1, max(2, int(np.linalg.norm(q - p)) + 1)), q - p)).astype(int)
        inside = (line[:, 0] >= x0) & (line[:, 0] <= x1) & (line[:, 2] >= z0) & (line[:, 2] <= z1) & (line[:, 1] >= Y0) & (line[:, 1] <= Y1)
        hits = line[inside]
        near[hits[:, 1] - Y0, hits[:, 2] - z0, hits[:, 0] - x0] = True
    return binary_dilation(near, iterations=6) if near.any() else near


def launch_mask(guard, shape, x0, z0):
    mask = np.zeros(shape, bool)
    for cx, cz in {key for key in guard.by_chunk}:
        ax, az = cx * 16 - x0, cz * 16 - z0
        xa, xb, za, zb = max(ax, 0), min(ax + 16, shape[2]), max(az, 0), min(az + 16, shape[1])
        if xa < xb and za < zb:
            part = guard.chunk_mask(cx, cz, y0=Y0, height=shape[0])
            mask[:, za:zb, xa:xb] |= part[:, za - az:zb - az, xa - ax:xb - ax]
    return mask


def voxels(tris, kinds, cx, cz, top, x0, z0, nz, nx):
    """Model surface points as world cells: columns follow the real ceiling, depth follows the model."""
    mx, my, radius, height, base = 88.0, -13.0, 3197.0, 1260.0, -156.0     # dome axis, measured
    px, py = 23.0, -29.0                                                   # pyramid, placed on the HQ
    columns, levels, codes = [], [], []
    for tri, kind in zip(tris, kinds):
        points = sample(tri, 1.2)
        normal = np.cross(tri[1] - tri[0], tri[2] - tri[0])
        flat = abs(normal[2]) > 0.7 * (np.linalg.norm(normal) + 1e-9)
        # Model +Y is north and Minecraft +Z is south: negating keeps the layout unmirrored.
        ix = np.floor(cx + (points[:, 0] - px) * SCALE).astype(int) - x0
        iz = np.floor(cz - (points[:, 1] - py) * SCALE).astype(int) - z0
        keep = (ix >= 0) & (ix < nx) & (iz >= 0) & (iz < nz)
        ix, iz, points = ix[keep], iz[keep], points[keep]
        ratio = np.minimum(1.0, np.hypot(points[:, 0] - mx, points[:, 1] - my) / radius)
        surface = base + height * np.sqrt(1 - ratio * ratio)
        y = np.floor(top[iz, ix] - (surface - points[:, 2]) * SCALE).astype(int)
        if flat:
            code = np.full(len(y), FLOOR)
        else:
            window = np.isin(y % 4, (1, 2)) & ((ix + iz) % 4 != 0)
            code = np.where(window, GLASS, int(kind) % 3 + 1)
        columns.append(iz * nx + ix)
        levels.append(y)
        codes.append(code)
    return np.concatenate(columns), np.concatenate(levels), np.concatenate(codes)


def plan(a):
    parts = np.load(a.parts)
    rows = json.loads(Path(str(a.parts) + '.json').read_text('utf8'))
    tris, kinds = model_part(parts, rows, 'Ed_penjats')
    cx, cz = a.centre
    span = int(1100 * SCALE) + 40
    x0, z0, x1, z1 = cx - span, cz - span, cx + span, cz + span
    air = air_volume(a.world, x0, z0, x1, z1)
    shape = air.shape
    open_air = air > 0
    roof = ceiling_field(open_air)
    top = smooth_roof(roof)
    good = roof >= MIN_ROOF_Y
    print('model triangles', len(tris), 'dome columns', int(good.sum()), 'of', good.size, 'roof', int(roof[good].min()), int(roof[good].max()), flush=True)

    levels_above = np.arange(shape[0])[:, None, None] + Y0
    built = binary_dilation(~open_air & (levels_above < top[None, :, :] - 3), iterations=3)
    floors = tower_floors(a.world, shape[1:], x0, z0)
    tower = levels_above >= floors[None, :, :]
    rails = rail_mask(a.native, shape, x0, z0, x1, z1)
    launch = launch_mask(load_launch(a.world), shape, x0, z0)
    # A column whose rock stands well above the dome is an opening (a shaft), not ceiling.
    above = levels_above >= top[None, :, :] + 2
    blocked = {'not air': ~open_air, 'above the dome': above, 'built nearby': built, 'tower travel': tower, 'rail': rails, 'launch volume': launch}
    print('masks ready', {k: int(v.sum()) for k, v in blocked.items()}, flush=True)

    columns, levels, codes = voxels(tris, kinds, cx, cz, top, x0, z0, shape[1], shape[2])
    skipped = Counter()
    inside = (levels >= Y0) & (levels <= Y1)
    skipped['outside band'] = int((~inside).sum())
    grid = np.zeros(shape, np.uint8)
    iz, ix = columns[inside] // shape[2], columns[inside] % shape[2]
    grid[levels[inside] - Y0, iz, ix] = codes[inside]
    print('voxels', int((grid > 0).sum()), flush=True)
    allowed = np.ones(shape, bool)
    for name, mask in blocked.items():
        skipped[name] = int(((grid > 0) & allowed & mask).sum())
        allowed &= ~mask
    grid[~allowed] = 0

    # Tie each column to the rock, then drop whatever still does not reach it.
    highest = shape[0] - 1 - np.argmax(grid[::-1] > 0, axis=0)
    posts = 0
    for jz, jx in zip(*np.nonzero((grid > 0).any(axis=0))):
        low, ceiling = highest[jz, jx] + 1, roof[jz, jx] - Y0
        if roof[jz, jx] < MIN_ROOF_Y or abs(roof[jz, jx] - top[jz, jx]) > 6 or ceiling - low > TIE_LIMIT or ceiling > shape[0]:
            continue
        free = allowed[low:ceiling, jz, jx]
        grid[low:ceiling, jz, jx][free] = POST
        posts += int(free.sum())
    labels, count = label(grid > 0, structure=np.ones((3, 3, 3), bool))
    touching = np.zeros_like(open_air)
    touching[:-1] = (grid[:-1] > 0) & ~open_air[1:]
    joined = np.zeros(count + 1, bool)
    joined[labels[touching]] = True
    joined[0] = False
    loose = (labels > 0) & ~joined[labels]
    skipped['not attached to the rock'] = int(loose.sum())
    grid[loose] = 0

    ys, zs, xs = np.nonzero(grid)
    tally = Counter(STATES[c] for c in grid[ys, zs, xs].tolist())
    output = [[int(x) + x0, int(y) + Y0, int(z) + z0, AIR[air[y, z, x]], STATES[grid[y, z, x]]] for y, z, x in zip(ys, zs, xs)]
    report = dict(cells=len(output), roof_ties=posts, loose_pieces_removed=count - int(joined.sum()),
                  attached_pieces=int(joined.sum()), skipped=dict(skipped), materials=dict(tally), centre=[cx, cz],
                  bounds=[int(xs.min()) + x0, int(ys.min()) + Y0, int(zs.min()) + z0, int(xs.max()) + x0, int(ys.max()) + Y0, int(zs.max()) + z0],
                  world_written=False)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(output), 'utf8')
    Path(str(a.out) + '.report.json').write_text(json.dumps(report, indent=1), 'utf8')
    print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--parts', type=Path, required=True)
    parser.add_argument('--native', type=Path, required=True)
    parser.add_argument('--centre', type=int, nargs=2, required=True, metavar=('X', 'Z'))
    parser.add_argument('--out', type=Path, required=True)
    plan(parser.parse_args())
