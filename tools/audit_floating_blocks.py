"""Find block groups connected to nothing, region by region, in a saved world.

Reads only. A group is floating when it touches neither the bottom of the world nor
a region edge or unfinished chunk, so a group cut by a region edge is left out rather
than guessed at. Groups are reported with their size, bounds and materials for review.
"""
import argparse
from collections import Counter
import json
from multiprocessing import Pool
from pathlib import Path
import re

import numpy as np
from scipy.ndimage import find_objects, label

from query_blocks import AIR, chunk_statuses, iter_selected_sections

DIM = 'projectseele:geofront'
Y0, HEIGHT, SECTIONS = -128, 448, range(-8, 20)
LOOSE = AIR | {'minecraft:water', 'minecraft:lava', 'minecraft:light', 'minecraft:bubble_column', 'minecraft:seagrass', 'minecraft:tall_seagrass',
               'minecraft:kelp', 'minecraft:kelp_plant', 'minecraft:grass', 'minecraft:tall_grass', 'minecraft:fern', 'minecraft:large_fern'}


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
        rows.append(dict(size=int(sizes[index]), bounds=[box[2].start + rx * 512, box[0].start + Y0, box[1].start + rz * 512, box[2].stop - 1 + rx * 512, box[0].stop - 1 + Y0, box[1].stop - 1 + rz * 512],
                         materials=materials.most_common(4)))
    return rows


def main(a):
    regions = sorted({tuple(map(int, re.match(r'r\.(-?\d+)\.(-?\d+)\.mca', p.name).groups())) for p in (a.world / 'dimensions/projectseele/geofront/region').glob('r.*.mca')})
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
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=3)
    main(parser.parse_args())
