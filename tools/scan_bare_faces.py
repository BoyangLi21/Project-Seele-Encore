"""Find bare earth and rock faces on natural slopes from a scan mosaic (scan_mosaic.py output) and rank them by how
visible they are from roads and buildings.

A natural column (nothing built on it, ground block is soil or rock) shows a vertical face where its ground stands
above the highest solid block of a neighbour: drop = ground - min(neighbour solid). Faces are grouped by drop:
    stripe  drop 1     terrace stripe: the dirt side of a grass block
    bank    drop 2-3   earth bank: dirt below the grass top
    cliff   drop >= 4  wall too steep for soil
Bare tops (dirt, coarse dirt, gravel, stone showing on top on a slope) are counted too.

Areas are 64-block cells; each gets exposed face cells, a share of cliff, and a visibility weight from the distance to
the nearest built column (roads, buildings): 1 within 48 blocks, falling to 0.1 at 400.

    scan_bare_faces.py --mosaic DIR --out DIR
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

SOIL = ('grass_block', 'dirt', 'coarse_dirt', 'podzol', 'rooted_dirt', 'gravel', 'stone', 'andesite', 'diorite',
        'granite', 'tuff', 'moss_block', 'sand', 'clay', 'mud', 'deepslate', 'calcite', 'mycelium')
BARE = ('dirt', 'coarse_dirt', 'gravel', 'stone', 'rooted_dirt')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mosaic', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--cell', type=int, default=64)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    M = a.mosaic
    pal = np.load(M / 'palette.npy', allow_pickle=True)
    names = np.array([q.split('[')[0].split(':')[-1] for q in pal])
    ox, oz = (int(v) for v in np.load(M / 'origin.npy'))
    ground = np.load(M / 'ground.npy').astype(np.int32)
    solid = np.load(M / 'solid.npy').astype(np.int32)
    gname = names[np.load(M / 'ground_id.npy')]
    water = np.load(M / 'water.npy')
    have = ground > -30000
    natural = have & (solid <= ground) & np.isin(gname, SOIL)
    wet = water > -30000 if water.dtype != bool else water
    built = have & (solid > ground + 1)
    # a neighbour under water shows the face only down to the water surface; that part is a shore wall, kept apart
    surface = np.maximum(solid, ground)
    nsolid = np.where(have, np.where(wet, np.maximum(surface, water.astype(np.int32)), surface), 10000)
    low = np.full(ground.shape, 10000, np.int32)
    low_dry = np.full(ground.shape, 10000, np.int32)
    for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        n = np.roll(nsolid, (dz, dx), (0, 1))
        low = np.minimum(low, n)
        low_dry = np.minimum(low_dry, np.where(np.roll(wet, (dz, dx), (0, 1)), 10000, n))
    near_built = ndimage.binary_dilation(built, iterations=2)
    keep = natural & ~wet & ~near_built
    drop = np.where(keep, np.clip(ground - np.minimum(low, low_dry), 0, 64), 0)
    shore = np.where(keep & (low < low_dry), np.clip(ground - low, 0, 64), 0)
    del low, low_dry, nsolid
    gy, gx = np.gradient(ndimage.gaussian_filter(np.where(have, ground, 0).astype(float), 1.5))
    slope = np.hypot(gx, gy)
    bare_top = natural & np.isin(gname, BARE) & (slope > .6)
    # distance on a 4-block grid: the full map at block scale does not fit in memory beside other clients
    h4, w4 = ground.shape[0] // 4, ground.shape[1] // 4
    b4 = built[:h4 * 4, :w4 * 4].reshape(h4, 4, w4, 4).any((1, 3))
    d4 = ndimage.distance_transform_edt(~b4).astype(np.float32) * 4
    d_built = np.full(ground.shape, 4000, np.float32)
    d_built[:h4 * 4, :w4 * 4] = np.repeat(np.repeat(d4, 4, 0), 4, 1)
    del d4
    vis = np.clip(1 - (d_built - 48) / 352, .1, 1).astype(np.float32)
    del d_built
    stripe = drop == 1
    bank = (drop >= 2) & (drop <= 3)
    cliff = drop >= 4
    face_cells = np.where(drop >= 2, drop - 1, 0)        # cells under the top block
    c = a.cell
    H, W = ground.shape[0] // c, ground.shape[1] // c

    def pool(arr):
        return arr[:H * c, :W * c].reshape(H, c, W, c).sum((1, 3))
    faces = pool(face_cells.astype(np.int64))
    cl = pool(np.where(cliff, face_cells, 0).astype(np.int64))
    stripes = pool(stripe.astype(np.int64))
    bares = pool(bare_top.astype(np.int64))
    v = pool(vis) / (c * c)
    score = (faces + .3 * stripes + bares) * v
    order = np.argsort(score.ravel())[::-1]
    top = []
    for i in order[:60]:
        r, q = divmod(int(i), W)
        if score[r, q] <= 0:
            break
        top.append(dict(x=ox + q * c + c // 2, z=oz + r * c + c // 2, face_cells=int(faces[r, q]), cliff_cells=int(cl[r, q]),
                        stripes=int(stripes[r, q]), bare_tops=int(bares[r, q]), visibility=round(float(v[r, q]), 2), score=round(float(score[r, q]))))
    total = dict(columns_stripe=int(stripe.sum()), columns_bank=int(bank.sum()), columns_cliff=int(cliff.sum()),
                 face_cells=int(face_cells.sum()), cliff_cells=int(np.where(cliff, face_cells, 0).sum()), bare_tops=int(bare_top.sum()),
                 face_cells_visible=int((face_cells * (vis >= .5)).sum()), stripes_visible=int((stripe & (vis >= .5)).sum()),
                 shore_wall_columns=int((shore >= 3).sum()))
    (a.out / 'faces.json').write_text(json.dumps(dict(total=total, top=top), indent=1), 'utf8')
    np.savez_compressed(a.out / 'faces.npz', drop=drop.astype(np.int8), shore=shore.astype(np.int8), bare_top=bare_top, vis=vis.astype(np.float16), origin=np.array([ox, oz]))
    print(json.dumps(total))
    for t in top[:25]:
        print(t)


if __name__ == '__main__':
    main()
