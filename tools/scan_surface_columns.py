"""Read every finished chunk of the Hakone dimension and keep three heights per column.

ground: highest natural ground block (soil, rock, sand), ignoring plants, trees and buildings.
solid:  highest block that is neither air, water, a plant, a log nor leaves (buildings and roads count).
top:    highest non-air block of any kind.
One npz per region with 512x512 int16 heights (-32768 = no data) and uint16 palette ids.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import io
import json
import math
from pathlib import Path
import zlib

import nbtlib
import numpy as np

REGION = 'dimensions/projectseele/geofront/region'
AIR = {'minecraft:air', 'minecraft:cave_air', 'minecraft:void_air'}
GROUND = {'minecraft:' + s for s in (
    'stone', 'dirt', 'grass_block', 'coarse_dirt', 'gravel', 'sand', 'red_sand', 'sandstone', 'clay', 'andesite',
    'diorite', 'granite', 'deepslate', 'tuff', 'podzol', 'rooted_dirt', 'mud', 'mycelium', 'moss_block', 'calcite',
    'dirt_path', 'snow_block', 'packed_ice', 'cobbled_deepslate', 'terracotta', 'basalt', 'smooth_basalt', 'farmland')}
SOFT_WORDS = ('_leaves', '_log', '_wood', 'grass', 'fern', 'flower', 'bush', 'vine', 'sapling', 'kelp', 'seagrass',
              'lily', 'mushroom', 'dandelion', 'poppy', 'tulip', 'orchid', 'allium', 'bluet', 'daisy', 'cornflower',
              'rose', 'peony', 'lilac', 'sugar_cane', 'bamboo', 'snow', 'moss_carpet', 'azalea', 'dripleaf', 'roots',
              'propagule', 'pointed_dripstone', 'cocoa', 'berry', 'glow_lichen', 'hanging_roots', 'spore')
NONE = -32768


def bits_for(count):
    return max(4, math.ceil(math.log2(count)))


def section_ids(states):
    palette = [str(p['Name']) for p in states['palette']]
    data = states.get('data')
    if data is None or len(palette) == 1:
        return np.zeros(4096, np.int64), palette
    bits = bits_for(len(palette))
    per = 64 // bits
    words = np.array(data, dtype=np.int64).astype(np.uint64)
    at = np.arange(4096)
    return ((words[at // per] >> ((at % per) * bits).astype(np.uint64)) & np.uint64((1 << bits) - 1)).astype(np.int64), palette


def kind(name):
    """0 air, 1 water, 2 soft (plant, tree), 3 ground, 4 other solid."""
    if name in AIR:
        return 0
    if name in ('minecraft:water', 'minecraft:bubble_column', 'minecraft:lava'):
        return 1
    if name in GROUND:
        return 3
    if any(w in name for w in SOFT_WORDS):
        return 2
    return 4


def region(job):
    world, rx, rz = job
    path = Path(world) / REGION / f'r.{rx}.{rz}.mca'
    buf = path.read_bytes()
    palette, lookup = [], {}
    out = {k: np.full((512, 512), NONE, np.int16) for k in ('ground', 'solid', 'top', 'water')}
    ids = {k: np.zeros((512, 512), np.uint16) for k in ('ground', 'solid', 'top')}
    statuses = {}
    if len(buf) < 8192:
        return rx, rz, out, ids, palette, statuses
    for i in range(1024):
        loc, count = int.from_bytes(buf[4 * i:4 * i + 3], 'big'), buf[4 * i + 3]
        if not loc:
            continue
        length = int.from_bytes(buf[loc * 4096:loc * 4096 + 4], 'big')
        if buf[loc * 4096 + 4] != 2:
            continue
        root = nbtlib.File.parse(io.BytesIO(zlib.decompress(buf[loc * 4096 + 5:loc * 4096 + 4 + length])))
        status = str(root.get('Status', '')).removeprefix('minecraft:')
        lx, lz = i & 31, i >> 5
        statuses[f'{lx},{lz}'] = status
        if status != 'full':
            continue
        need = {k: np.ones(256, bool) for k in ('ground', 'solid', 'top', 'water')}
        res = {k: np.full(256, NONE, np.int32) for k in need}
        rid = {k: np.zeros(256, np.int32) for k in ('ground', 'solid', 'top')}
        sections = sorted((s for s in root['sections'] if 'block_states' in s), key=lambda s: -int(s['Y']))
        for s in sections:
            sy = int(s['Y'])
            sid, pal = section_ids(s['block_states'])
            kinds = np.array([kind(p) for p in pal], np.int8)
            if (kinds == 0).all():
                continue
            gid = []
            for p in pal:
                if p not in lookup:
                    lookup[p] = len(palette)
                    palette.append(p)
                gid.append(lookup[p])
            gid = np.array(gid, np.int32)
            k3 = kinds[sid].reshape(16, 256)          # [y, z*16+x]
            g3 = gid[sid].reshape(16, 256)
            for key, mask in (('top', k3 != 0), ('solid', k3 >= 3), ('ground', k3 == 3), ('water', k3 == 1)):
                if not need[key].any():
                    continue
                hit = mask & need[key][None, :]
                anyhit = hit.any(0)
                if not anyhit.any():
                    continue
                ly = 15 - np.argmax(hit[::-1], 0)
                cols = np.nonzero(anyhit)[0]
                res[key][cols] = sy * 16 + ly[cols]
                if key in rid:
                    rid[key][cols] = g3[ly[cols], cols]
                need[key][cols] = False
            if not need['ground'].any() and not need['solid'].any():
                break
        sl = (slice(lz * 16, lz * 16 + 16), slice(lx * 16, lx * 16 + 16))
        for key in out:
            out[key][sl] = res[key].reshape(16, 16)
        for key in ids:
            ids[key][sl] = rid[key].reshape(16, 16)
    return rx, rz, out, ids, palette, statuses


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--workers', type=int, default=24)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    jobs = []
    for f in sorted((a.world / REGION).glob('r.*.mca')):
        _, rx, rz, _ = f.name.split('.')
        if not (a.out / f'r.{rx}.{rz}.npz').exists():
            jobs.append((str(a.world), int(rx), int(rz)))
    done = 0
    with ProcessPoolExecutor(a.workers) as ex:
        for fut in as_completed([ex.submit(region, j) for j in jobs]):
            rx, rz, out, ids, palette, statuses = fut.result()
            np.savez_compressed(a.out / f'r.{rx}.{rz}.npz', palette=np.array(palette or ['minecraft:air']),
                                statuses=json.dumps(statuses), **out, **{k + '_id': v for k, v in ids.items()})
            done += 1
            if done % 20 == 0:
                print(done, '/', len(jobs), flush=True)
    print('done', len(jobs))


if __name__ == '__main__':
    main()
