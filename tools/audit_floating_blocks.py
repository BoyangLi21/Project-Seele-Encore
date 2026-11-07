"""Find block groups connected to nothing, region by region, in a saved world.

Reads only. A group is floating when it touches neither the bottom of the world nor
a region edge or unfinished chunk, so a group cut by a region edge is left out rather
than guessed at. Groups are reported with their size, bounds and materials for review.
Soil and plant groups carry their cells: built ones may be meant to hang, these never are.
"""
import argparse
from collections import Counter
import json
from multiprocessing import Pool
from pathlib import Path
import re

import numpy as np
from scipy.ndimage import find_objects, label

from plan_ashi_landscape_r54 import PLANTS, SOIL
from query_blocks import AIR, chunk_statuses, iter_selected_sections

DIM = 'projectseele:geofront'
Y0, HEIGHT, SECTIONS, SURFACE = -128, 448, range(-8, 20), -100
LOOSE = AIR | {'minecraft:water', 'minecraft:lava', 'minecraft:light', 'minecraft:bubble_column', 'minecraft:seagrass', 'minecraft:tall_seagrass',
               'minecraft:kelp', 'minecraft:kelp_plant', 'minecraft:grass', 'minecraft:tall_grass', 'minecraft:fern', 'minecraft:large_fern'}


def natural(name):
    return name in SOIL or name in PLANTS or name.endswith(('_leaves', '_log')) or name == 'minecraft:stone'


def scan(job):
    world, rx, rz = job
    wanted = [(rx * 32 + i, rz * 32 + j) for i in range(32) for j in range(32)]
    status = chunk_statuses(Path(world), DIM, wanted)
    full = [c for c in wanted if status.get(c) == 'full']
    if not full:
        return []
    solid = np.zeros((HEIGHT, 512, 512), bool)
    names = np.empty((HEIGHT, 512, 512), np.int16)
    palette_index, palette_names = {}, []
    selected = {c: set(SECTIONS) for c in full}
    for cx, cz, sy, palette, ids in iter_selected_sections(Path(world), DIM, selected, skip_unfinished=True):
        bare = [s.split('[')[0] for s in palette]
        codes = np.array([palette_index.setdefault(b, len(palette_index)) for b in bare], np.int16)
        hard = np.array([b not in LOOSE for b in bare])
        ids = np.asarray(ids).reshape(16, 16, 16)
        y = (sy * 16 - Y0)
        if 0 <= y <= HEIGHT - 16:
            solid[y:y + 16, (cz - rz * 32) * 16:(cz - rz * 32) * 16 + 16, (cx - rx * 32) * 16:(cx - rx * 32) * 16 + 16] = hard[ids]
            names[y:y + 16, (cz - rz * 32) * 16:(cz - rz * 32) * 16 + 16, (cx - rx * 32) * 16:(cx - rx * 32) * 16 + 16] = codes[ids]
    palette_names = sorted(palette_index, key=palette_index.get)
    labels, count = label(solid, np.ones((3, 3, 3), int))
    if not count:
        return []
    anchored = np.zeros(count + 1, bool)
    anchored[np.unique(labels[:2])] = True
    known = np.zeros((512, 512), bool)
    for cx, cz in full:
        known[(cz - rz * 32) * 16:(cz - rz * 32) * 16 + 16, (cx - rx * 32) * 16:(cx - rx * 32) * 16 + 16] = True
    edge = ~known
    edge[0, :] = edge[-1, :] = edge[:, 0] = edge[:, -1] = True
    from scipy.ndimage import binary_dilation
    border = binary_dilation(edge)
    anchored[np.unique(labels[:, border])] = True
    anchored[0] = True
    sizes = np.bincount(labels.ravel(), minlength=count + 1)
    rows = []
    for index, box in enumerate(find_objects(labels), 1):
        if box is None or anchored[index]:
            continue
        mask = labels[box] == index
        materials = Counter(palette_names[i] for i in names[box][mask].tolist())
        row = dict(size=int(sizes[index]), bounds=[box[2].start + rx * 512, box[0].start + Y0, box[1].start + rz * 512, box[2].stop - 1 + rx * 512, box[0].stop - 1 + Y0, box[1].stop - 1 + rz * 512],
                   materials=materials.most_common(4))
        if box[0].stop + Y0 >= SURFACE and all(natural(name) for name in materials):
            cells = np.argwhere(mask) + [box[0].start, box[1].start, box[2].start]
            row['cells'] = [[int(x) + rx * 512, int(y) + Y0, int(z) + rz * 512] for y, z, x in cells.tolist()]
        rows.append(row)
    return rows


def clear(a):
    """Cell patch removing the reported soil and plant groups that lie inside one capture."""
    from plan_station_access_corridor import CapturedSurface
    spec = json.loads(a.clear.read_text('utf8'))
    source = CapturedSurface(spec['source'], partial=True)
    x0, z0, x1, z1 = source.bounds
    rows, groups = [], 0
    for group in json.loads(Path(spec['report']).read_text('utf8'))['rows']:
        cells = group.get('cells', ())
        if not cells or min(c[0] for c in cells) < x0 or max(c[0] for c in cells) > x1 or min(c[2] for c in cells) < z0 or max(c[2] for c in cells) > z1:
            continue
        if group['bounds'][0] in spec.get('keep_x', ()):
            continue
        groups += 1
        rows += [dict(pos=c, before=source.state(*c), after='minecraft:air', purpose='floating natural block') for c in cells if source.state(*c).split('[')[0] not in AIR]
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / 'floating-check.json').write_text(json.dumps(dict(errors=[], groups=groups, cells=len(rows)), ensure_ascii=False), 'utf8')
    (a.out / 'patch.json').write_text(json.dumps(dict(schema='map-cell-patch-v1', id=spec['id'], label=spec['label'], source=spec['source'], edits=rows, native_snapshot=spec['native_snapshot'],
        error_reports=[str(a.out / 'floating-check.json')], views_reviewed_by_root=False, continuation_work=spec['continuation_work']), ensure_ascii=False, indent=1), 'utf8')
    print('groups', groups, 'cells', len(rows))


def main(a):
    if a.clear:
        return clear(a)
    regions = sorted({tuple(map(int, re.match(r'r\.(-?\d+)\.(-?\d+)\.mca', p.name).groups())) for p in (a.world / 'dimensions/projectseele/geofront/region').glob('r.*.mca')})
    if a.only:
        regions = sorted({(r['bounds'][0] >> 9, r['bounds'][2] >> 9) for r in json.loads(a.only.read_text('utf8'))['rows'] if a.deep or r['bounds'][4] >= 40 or r['bounds'][0] >= 1200} & set(regions))
    print('regions', len(regions), flush=True)
    rows = []
    with Pool(a.workers) as pool:
        for i, part in enumerate(pool.imap_unordered(scan, [(str(a.world), x, z) for x, z in regions]), 1):
            rows += part
            print('region', i, '/', len(regions), 'floating', len(rows), flush=True)
    rows.sort(key=lambda r: -r['size'])
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / 'floating.json').write_text(json.dumps(dict(world=str(a.world), regions=len(regions), groups=len(rows), blocks=sum(r['size'] for r in rows), rows=rows), ensure_ascii=False), 'utf8')
    print('groups', len(rows), 'blocks', sum(r['size'] for r in rows))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--only', type=Path, help='Rescan just the regions of an earlier report')
    parser.add_argument('--clear', type=Path, help='Config for a cell patch that removes reported natural groups')
    parser.add_argument('--deep', action='store_true', help='With --only, include underground groups')
    main(parser.parse_args())
