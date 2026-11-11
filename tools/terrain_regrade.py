"""Regrade natural terrain in a stopped world copy and emit rows for write_deep_cells.py.

Only natural blocks change: soil, rock, plants, logs and leaves. Columns holding anything built
(roads, rails, buildings, tunnels, lifts) keep every block, and so do the columns around them.
The caller supplies the new ground height per column; this module turns it into cells:
lowered columns lose everything natural above the new ground and get grass over two dirt,
raised columns get dirt under grass, leaves cut off from every log are removed, and new
slopes are replanted with the forest tool's trees.
Rows: [x, y, z, before, after] with full block states, as write_deep_cells.py reads them.
"""
from concurrent.futures import ProcessPoolExecutor
import io
import json
import random
import zlib

import nbtlib
import numpy as np
from scipy import ndimage

from write_deep_cells import decode, REGION

AIR = {'minecraft:air', 'minecraft:cave_air', 'minecraft:void_air'}
GROUND = {'minecraft:' + s for s in (
    'stone', 'dirt', 'grass_block', 'coarse_dirt', 'gravel', 'sand', 'red_sand', 'sandstone', 'clay', 'andesite',
    'diorite', 'granite', 'deepslate', 'tuff', 'podzol', 'rooted_dirt', 'mud', 'mycelium', 'moss_block', 'calcite',
    'snow_block', 'cobbled_deepslate', 'terracotta', 'farmland')}
SOFT_WORDS = ('_leaves', '_log', '_wood', 'grass', 'fern', 'flower', 'bush', 'vine', 'sapling', 'seagrass',
              'mushroom', 'dandelion', 'poppy', 'tulip', 'orchid', 'allium', 'bluet', 'daisy', 'cornflower',
              'rose', 'peony', 'lilac', 'sugar_cane', 'bamboo', 'snow', 'moss_carpet', 'azalea', 'dripleaf', 'roots',
              'cocoa', 'berry', 'glow_lichen', 'spore')
GRASS = 'minecraft:grass_block[snowy=false]'
DIRT = 'minecraft:dirt'
AIR_STATE = 'minecraft:air'
# 0 air, 1 fluid, 2 plant or tree, 3 natural ground, 4 anything built
AIRK, FLUID, SOFT, SOIL, BUILT = range(5)


def kind(state):
    name = state.split('[')[0]
    if name in AIR:
        return AIRK
    if name in ('minecraft:water', 'minecraft:bubble_column', 'minecraft:lava') or 'waterlogged=true' in state:
        return FLUID
    if name in GROUND:
        return SOIL
    if name == 'minecraft:grass_block' or any(w in name for w in SOFT_WORDS):
        return SOFT if name != 'minecraft:grass_block' else SOIL
    return BUILT


def _region(job):
    world, rx, rz, chunks, y0, y1 = job
    buf = open(f'{world}/{REGION}/r.{rx}.{rz}.mca', 'rb').read()
    res = []
    for cx, cz in chunks:
        i = 4 * ((cx & 31) + (cz & 31) * 32)
        loc = int.from_bytes(buf[i:i + 3], 'big')
        if not loc:
            res.append((cx, cz, None, None, None))
            continue
        length = int.from_bytes(buf[loc * 4096:loc * 4096 + 4], 'big')
        root = nbtlib.File.parse(io.BytesIO(zlib.decompress(buf[loc * 4096 + 5:loc * 4096 + 4 + length])))
        if str(root.get('Status', '')).removeprefix('minecraft:') != 'full':
            res.append((cx, cz, None, None, None))
            continue
        lookup, arr, sections = {}, np.zeros((y1 - y0 + 1, 16, 16), np.int32), set()
        for s in root['sections']:
            sy = int(s['Y'])
            if 'block_states' not in s or sy * 16 + 15 < y0 or sy * 16 > y1:
                continue
            sections.add(sy)
            ids, pal = decode(s['block_states'])
            remap = np.array([lookup.setdefault(n, len(lookup)) for n in pal], np.int32)
            blk = remap[ids].reshape(16, 16, 16)
            lo, hi = max(y0, sy * 16), min(y1, sy * 16 + 15)
            arr[lo - y0:hi - y0 + 1] = blk[lo - sy * 16:hi - sy * 16 + 1]
        pal = [None] * len(lookup)
        for n, k in lookup.items():
            pal[k] = n
        entities = [(int(e['x']), int(e['y']), int(e['z'])) for e in root.get('block_entities', [])]
        res.append((cx, cz, arr, pal or [AIR_STATE], (sorted(sections), entities)))
    return res


class Box:
    """Full block states of x0..x1, y0..y1, z0..z1 (inclusive) as ids[y, z, x] and a palette."""

    def __init__(self, world, x0, x1, y0, y1, z0, z1, workers=6):
        self.origin = (x0, y0, z0)
        jobs = {}
        for cx in range(x0 >> 4, (x1 >> 4) + 1):
            for cz in range(z0 >> 4, (z1 >> 4) + 1):
                jobs.setdefault((cx >> 5, cz >> 5), []).append((cx, cz))
        self.ids = np.zeros((y1 - y0 + 1, z1 - z0 + 1, x1 - x0 + 1), np.uint16)
        self.loaded = np.zeros((z1 - z0 + 1, x1 - x0 + 1), bool)
        lookup = {AIR_STATE: 0}
        self.entities = set()
        with ProcessPoolExecutor(workers) as ex:
            for res in ex.map(_region, [(str(world), rx, rz, c, y0, y1) for (rx, rz), c in jobs.items()]):
                for cx, cz, arr, pal, extra in res:
                    if arr is None:
                        continue
                    remap = np.array([lookup.setdefault(n, len(lookup)) for n in pal], np.uint16)
                    gx, gz = cx * 16, cz * 16
                    ax0, ax1, az0, az1 = max(x0, gx), min(x1, gx + 15), max(z0, gz), min(z1, gz + 15)
                    self.ids[:, az0 - z0:az1 - z0 + 1, ax0 - x0:ax1 - x0 + 1] = remap[arr[:, az0 - gz:az1 - gz + 1, ax0 - gx:ax1 - gx + 1]]
                    self.loaded[az0 - z0:az1 - z0 + 1, ax0 - x0:ax1 - x0 + 1] = True
                    self.entities.update(extra[1])
        self.palette = [None] * len(lookup)
        for n, k in lookup.items():
            self.palette[k] = n
        self.lookup = lookup
        self.kinds = np.array([kind(p) for p in self.palette], np.int8)

    def state_id(self, state):
        if state not in self.lookup:
            self.lookup[state] = len(self.palette)
            self.palette.append(state)
            self.kinds = np.append(self.kinds, np.int8(kind(state)))
        return self.lookup[state]

    def kind_grid(self, ids=None):
        return self.kinds[self.ids if ids is None else ids]


def top_of(mask, y0):
    """Highest y where mask is set per column, or y0 - 1."""
    hit = mask.any(0)
    return np.where(hit, mask.shape[0] - 1 - np.argmax(mask[::-1], 0) + y0, y0 - 1)


def built_columns(box, above_y=None):
    """Columns holding a built block (or a fluid) anywhere in the box, or only above above_y."""
    k = box.kind_grid()
    built = (k == BUILT) | (k == FLUID)
    if above_y is not None:
        built[:above_y - box.origin[1] + 1] = False
    return built.any(0)


def softmin(a, b, k):
    m = np.minimum(a, b)
    return m - k * np.log(np.exp(-(a - m) / k) + np.exp(-(b - m) / k))


def apply_heights(box, ground, target, frozen, rng_seed=7, steep_rock=2.5, plant=None, plant_keepout=None, chance=None, cover=True):
    """Rewrite box.ids so each unfrozen column's natural ground top sits at target. Returns new ids."""
    y0 = box.origin[1]
    ids = box.ids.copy()
    k = box.kind_grid()
    air, grass, dirt = box.state_id(AIR_STATE), box.state_id(GRASS), box.state_id(DIRT)
    target = np.round(target).astype(int)
    change = (target != ground) & ~frozen & box.loaded
    gy, gx = np.gradient(target.astype(float))
    slope = np.hypot(gx, gy)
    zz, xx = np.nonzero(change)
    for z, x in zip(zz.tolist(), xx.tolist()):
        old, new = int(ground[z, x]), int(target[z, x])
        col = ids[:, z, x]
        kc = k[:, z, x]
        if new < old:
            above = np.arange(new + 1 - y0, ids.shape[0])
            natural = (kc[above] == SOIL) | (kc[above] == SOFT)
            col[above[natural]] = air
            top_name = box.palette[box.ids[new - y0, z, x]].split('[')[0]
            soft_top = top_name in ('minecraft:dirt', 'minecraft:grass_block', 'minecraft:coarse_dirt', 'minecraft:podzol')
            # grass grows on any slope; only a cliff steeper than steep_rock shows its rock
            if kc[new - y0] == SOIL and (slope[z, x] < steep_rock or soft_top):
                col[new - y0] = grass
                for d in (1, 2):
                    if kc[new - d - y0] == SOIL:
                        col[new - d - y0] = dirt
        else:
            top = old
            for y in range(old + 1, new + 1):
                if kc[y - y0] not in (AIRK, SOFT):
                    break
                col[y - y0] = dirt
                top = y
            if top > old:
                col[top - y0] = grass
                if kc[old - y0] == SOIL and box.palette[box.ids[old - y0, z, x]].startswith('minecraft:grass_block'):
                    col[old - y0] = dirt
                # plants that stood on the old ground would float or sit inside the fill
                for y in range(top + 1, min(top + 3, ids.shape[0] + y0)):
                    name = box.palette[box.ids[y - y0, z, x]].split('[')[0]
                    if kc[y - y0] == SOFT and not name.endswith(('_log', '_leaves')):
                        col[y - y0] = air
    orphan_leaves(box, ids, change)
    if plant is not None:
        replant(box, ids, target, plant & change, plant_keepout, random.Random(rng_seed), chance=chance)
    if cover:
        ground_cover(box, ids, change, np.random.default_rng(rng_seed))
    return ids, change


def orphan_leaves(box, ids, change, reach=5):
    """Leaves near changed columns with no log within reach blocks (taxicab, as the game counts) go."""
    names = box.palette
    is_log = np.array([n.split('[')[0].endswith(('_log', '_wood')) for n in names])
    is_leaf = np.array([n.split('[')[0].endswith('_leaves') for n in names])
    near = ndimage.binary_dilation(change, iterations=reach + 3)
    zz, xx = np.nonzero(near)
    if not len(zz):
        return
    z0, z1, x0, x1 = zz.min(), zz.max() + 1, xx.min(), xx.max() + 1
    sub = ids[:, z0:z1, x0:x1]
    logs = is_log[sub]
    dist = ndimage.distance_transform_cdt(~logs, metric='taxicab')
    orphan = is_leaf[sub] & (dist > reach) & near[None, z0:z1, x0:x1]
    sub[orphan] = box.state_id(AIR_STATE)


def replant(box, ids, target, where, keepout, rng, chance=None):
    """Plant the forest tool's conifers (every 5) and broadleaf (every 7) on grass in where; chance thins them per column."""
    from plan_forest import conifer, broadleaf, attached
    y0 = box.origin[1]
    k = box.kinds
    grass = box.state_id(GRASS)
    taken = np.zeros(where.shape, bool)
    chances = chance if isinstance(chance, tuple) else (chance, chance)
    for (step, maker), chance in zip(((5, lambda: conifer(rng, (11, 15), 'spruce', 'spruce') if rng.random() < .6 else conifer(rng, (10, 13), 'spruce', 'dark_oak')),
                        (7, lambda: broadleaf(rng, (('oak', 'oak'), ('oak', 'oak'), ('birch', 'birch'), ('dark_oak', 'dark_oak'))))), chances):
        for iz in range(0, where.shape[0], step):
            for ix in range(0, where.shape[1], step):
                jz, jx = iz + rng.randint(0, step - 1), ix + rng.randint(0, step - 1)
                if not (0 <= jz < where.shape[0] and 0 <= jx < where.shape[1]) or not where[jz, jx] or taken[jz, jx]:
                    continue
                if chance is not None and rng.random() > chance[jz, jx]:
                    continue
                y = int(target[jz, jx])
                if ids[y - y0, jz, jx] != grass:
                    continue
                cells, ok = [], True
                for dx, dy, dz, state in maker():
                    z, x, yy = jz + dz, jx + dx, y + dy
                    if not (0 <= z < where.shape[0] and 0 <= x < where.shape[1] and 0 <= yy - y0 < ids.shape[0]) or keepout[z, x]:
                        ok = False
                        break
                    if box.kinds[ids[yy - y0, z, x]] in (AIRK, SOFT) and not box.palette[ids[yy - y0, z, x]].split('[')[0].endswith(('_log', '_leaves')):
                        cells.append((x, yy, z, state))
                    elif dx == 0 and dz == 0:
                        ok = False
                        break
                if not ok or len(cells) < 4 or not any(c[0] == jx and c[2] == jz for c in cells):
                    continue
                for x, yy, z, state in attached(cells, jx, jz):
                    ids[yy - y0, z, x] = box.state_id(state)
                taken[max(0, jz - 2):jz + 3, max(0, jx - 2):jx + 3] = True


def rows_between(box, new_ids):
    x0, y0, z0 = box.origin
    diff = np.nonzero(new_ids != box.ids)
    rows = []
    for y, z, x in zip(*diff):
        pos = (int(x) + x0, int(y) + y0, int(z) + z0)
        if pos in box.entities:
            raise ValueError(f'{pos} holds a block entity')
        rows.append([pos[0], pos[1], pos[2], box.palette[box.ids[y, z, x]], box.palette[new_ids[y, z, x]]])
    return rows


def save(path, **arrays):
    np.savez_compressed(path, **arrays)


def write_rows(path, rows):
    with open(path, 'w', encoding='utf8') as f:
        json.dump(rows, f)


def local_tree_chances(box, radius=15, counts=None):
    """Per-column planting chances (conifer grid of 5, broadleaf grid of 7) that reproduce the trunk
    density and conifer share standing around each column now. counts limits which columns are
    sampled (leave out pavement, which would read as clearing)."""
    names = np.array([q.split('[')[0] for q in box.palette]).astype(str)
    y0 = box.origin[1]
    k = box.kind_grid()
    ground = top_of(k == SOIL, y0)
    above = np.clip(ground + 1 - y0, 0, box.ids.shape[0] - 1)
    base = names[np.take_along_axis(box.ids, above[None], 0)[0]]
    trunk = np.char.endswith(base, '_log')
    conifer = trunk & (base == 'minecraft:spruce_log')
    size = 2 * radius + 1
    weight = np.ones(trunk.shape) if counts is None else counts.astype(float)
    n = np.maximum(ndimage.uniform_filter(weight, size), 1e-6)
    d = ndimage.uniform_filter(trunk * weight, size) / n
    share = ndimage.uniform_filter(conifer * weight, size) / n / np.maximum(d, 1e-6)
    return np.clip(25 * d * share, 0, .9), np.clip(49 * d * (1 - share), 0, .9)


def ground_cover(box, ids, where, rng, grass=.3, fern=.06):
    """Short grass and ferns on bare grass blocks in where, so a fresh cut does not read as raw steps."""
    y0 = box.origin[1]
    k = box.kinds
    grass_id = box.state_id(GRASS)
    air = box.state_id(AIR_STATE)
    plants = [box.state_id('minecraft:grass'), box.state_id('minecraft:fern')]
    top = top_of(k[ids] == SOIL, y0)
    roll = rng.random(where.shape)
    for z, x in zip(*np.nonzero(where & (roll < grass + fern))):
        y = int(top[z, x]) - y0
        if y + 1 < ids.shape[0] and ids[y, z, x] == grass_id and ids[y + 1, z, x] == air:
            ids[y + 1, z, x] = plants[0] if roll[z, x] < grass else plants[1]
