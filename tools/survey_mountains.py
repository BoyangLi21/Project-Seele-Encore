"""Survey the Hakone hills for M6 round 2 from a scan mosaic: where conifer plantations, pampas grassland, road cut
protection, bamboo, terraced paddies and reed beds would go, ranked by how visible each place is from roads, railways
and the city.

    plantation   forest on mid-slopes (not ridge, not valley bottom: |TPI| < 5 on a 25-block scale), slope 0.25-1.6;
                 reports the current conifer share, since the hills are mostly mixed now
    pampas       open natural grass on gentle slopes (0.03-0.45), at least 8 blocks from anything built
    road_cut     natural columns 1-3 blocks from a road standing 3 or more blocks above it (cut faces along roads)
    bamboo       natural slopes 8-40 blocks behind village houses outside the city zones
    terraces     open grass slopes 0.12-0.5 within 60 blocks of village houses outside the city zones
    reeds        shallow water (at most a block deep) next to natural land
    bare_rock    large open patches of stone, gravel, andesite or tuff on the hills (candidate volcanic ground)

Visibility: 1 within 48 blocks of a road, railway or city zone, falling to 0.1 at 400. Areas are 128-block cells.

    survey_mountains.py --mosaic DIR --world W --out DIR [--area x0 x1 z0 z1]
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

NATURAL = ('grass_block', 'dirt', 'coarse_dirt', 'podzol', 'rooted_dirt', 'gravel', 'stone', 'andesite', 'diorite',
           'granite', 'tuff', 'moss_block', 'sand', 'clay', 'mud', 'calcite', 'mycelium')
ROCK = ('stone', 'gravel', 'andesite', 'tuff', 'cobblestone', 'diorite', 'granite')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mosaic', type=Path, required=True)
    p.add_argument('--world', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--area', type=int, nargs=4, default=[-4000, 3000, -3000, 2600])
    p.add_argument('--cell', type=int, default=128)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    M = a.mosaic
    ox, oz = (int(v) for v in np.load(M / 'origin.npy'))
    x0, x1, z0, z1 = a.area
    sl = (slice(z0 - oz, z1 - oz), slice(x0 - ox, x1 - ox))
    pal = np.load(M / 'palette.npy', allow_pickle=True)
    names = np.array([q.split('[')[0] for q in pal])
    short = np.array([n.split(':')[-1] for n in names])
    ground = np.array(np.load(M / 'ground.npy', mmap_mode='r')[sl]).astype(np.float32)
    solid = np.array(np.load(M / 'solid.npy', mmap_mode='r')[sl]).astype(np.float32)
    water = np.array(np.load(M / 'water.npy', mmap_mode='r')[sl]).astype(np.float32)
    top_id = np.array(np.load(M / 'top_id.npy', mmap_mode='r')[sl])
    solid_id = np.array(np.load(M / 'solid_id.npy', mmap_mode='r')[sl])
    ground_id = np.array(np.load(M / 'ground_id.npy', mmap_mode='r')[sl])
    have = ground > -30000
    wet = water > -30000
    tname = short[top_id]
    gname = short[ground_id]
    sname = names[solid_id]
    canopy = np.char.endswith(tname, '_leaves')
    conifer = tname == 'spruce_leaves'
    natural = have & (solid <= ground) & np.isin(gname, NATURAL)
    built = have & (solid > ground + 1)
    road = have & ~wet & (np.char.startswith(sname, 'trafficcraft:') | np.char.find(sname, 'asphalt') >= 0)
    rail = have & (np.char.startswith(sname, 'mtr:') | np.char.find(sname, 'rail') >= 0)
    zones = json.loads((a.world / 'regional_plan.json').read_text('utf8'))['zones']
    city = np.zeros(ground.shape, bool)
    for zn in zones:
        if zn.get('kind') in ('district', 'airport', 'gateway'):
            bx0, bx1, bz0, bz1 = zn['bounds']
            city[max(bz0 - z0, 0):max(bz1 - z0, 0), max(bx0 - x0, 0):max(bx1 - x0, 0)] = True
    viewers = road | rail | city
    # distance on a 4-block grid keeps memory in bounds
    h4, w4 = ground.shape[0] // 4, ground.shape[1] // 4
    v4 = viewers[:h4 * 4, :w4 * 4].reshape(h4, 4, w4, 4).any((1, 3))
    d4 = ndimage.distance_transform_edt(~v4).astype(np.float32) * 4
    vis = np.full(ground.shape, .1, np.float32)
    vis[:h4 * 4, :w4 * 4] = np.clip(1 - (np.repeat(np.repeat(d4, 4, 0), 4, 1) - 48) / 352, .1, 1)
    del d4
    g0 = np.where(have, ground, np.nanmean(np.where(have, ground, np.nan)))
    tpi = g0 - ndimage.gaussian_filter(g0, 25)
    gy, gx = np.gradient(ndimage.gaussian_filter(g0, 2))
    slope = np.hypot(gx, gy)
    del gy, gx
    near_built = ndimage.binary_dilation(built, iterations=8)
    houses = have & (solid > ground + 3) & ~city
    hl, hn = ndimage.label(ndimage.binary_dilation(houses, iterations=2))
    hsize = ndimage.sum(houses, hl, range(1, hn + 1)) if hn else np.array([])
    village = np.isin(hl, 1 + np.nonzero((hsize >= 20) & (hsize <= 4000))[0]) & houses if hn else houses
    d_village = ndimage.distance_transform_edt(~village) if village.any() else np.full(ground.shape, 1e4)
    layers = {}
    layers['plantation'] = canopy & natural.__or__(canopy) & (np.abs(tpi) < 5) & (slope > .25) & (slope < 1.6) & ~city & ~near_built
    # Sengokuhara is the caldera floor round Tokyo-3: uplands near the city, not the coastal plain
    d_city = ndimage.distance_transform_edt(~city[::4, ::4]).repeat(4, 0).repeat(4, 1)[:ground.shape[0], :ground.shape[1]] * 4 if city.any() else np.full(ground.shape, 1e4)
    upland = ground >= 70
    layers['pampas'] = upland & (d_city <= 2500) & natural & ~canopy & np.isin(tname, ['grass_block', 'grass', 'tall_grass', 'fern']) & (slope > .03) & (slope < .45) & ~near_built & ~wet & ~city
    d_road, (riz, rix) = ndimage.distance_transform_edt(~road, return_indices=True)
    road_level = solid[riz, rix]
    cut_h = np.where(natural & (d_road >= 1) & (d_road <= 3), ground - road_level, 0)
    layers['road_cut'] = cut_h >= 3
    layers['bamboo'] = (ground >= 30) & natural & (d_village >= 8) & (d_village <= 40) & (slope > .15) & (slope < 1.2) & ~wet
    layers['terraces'] = (ground >= 30) & natural & ~canopy & (d_village <= 60) & (slope > .12) & (slope < .5) & ~wet & ~near_built
    shallow = wet & (water - ground <= 1)
    shore = shallow & ndimage.binary_dilation(natural & ~wet, iterations=1)
    layers['reeds_lake'] = shore & (ground >= 40)
    layers['reeds_river'] = shore & (ground < 40)
    rock_top = natural & ~canopy & np.isin(tname, ROCK) & (ground > 90)
    rl, rn = ndimage.label(rock_top)
    rsize = ndimage.sum(rock_top, rl, range(1, rn + 1)) if rn else np.array([])
    layers['bare_rock'] = np.isin(rl, 1 + np.nonzero(rsize >= 600)[0]) if rn else rock_top
    c = a.cell
    H, W = ground.shape[0] // c, ground.shape[1] // c

    def pool(arr):
        return arr[:H * c, :W * c].reshape(H, c, W, c).sum((1, 3))
    vpool = pool(vis) / (c * c)
    cpool = pool(canopy.astype(np.int32))
    conpool = pool(conifer.astype(np.int32))
    res = {}
    for name, m in layers.items():
        amt = pool(m.astype(np.int32))
        score = amt * vpool
        order = np.argsort(score.ravel())[::-1]
        top = []
        for i in order[:12]:
            r, q = divmod(int(i), W)
            if score[r, q] <= 0:
                break
            e = dict(x=x0 + q * c + c // 2, z=z0 + r * c + c // 2, columns=int(amt[r, q]), visibility=round(float(vpool[r, q]), 2),
                     ground=int(np.median(ground[r * c:(r + 1) * c, q * c:(q + 1) * c])))
            if name == 'plantation':
                e['conifer_share_now'] = round(float(conpool[r, q] / max(cpool[r, q], 1)), 2)
            if name == 'road_cut':
                e['face_cells'] = int(np.where(m, cut_h, 0)[r * c:(r + 1) * c, q * c:(q + 1) * c].sum())
            top.append(e)
        res[name] = dict(total_columns=int(m.sum()), visible_columns=int((m & (vis >= .5)).sum()), top=top)
    res['forest'] = dict(canopy_columns=int(canopy.sum()), conifer_share=round(float(conifer.sum() / max(canopy.sum(), 1)), 3))
    res['villages'] = dict(clusters=int(len(np.unique(hl[village])) - (0 in np.unique(hl[village]))) if hn else 0)
    (a.out / 'survey.json').write_text(json.dumps(res, indent=1), 'utf8')
    np.savez_compressed(a.out / 'survey.npz', origin=np.array([x0, z0]), **{k: v for k, v in layers.items()}, vis=vis.astype(np.float16))
    # overview on a 5-block grid in 8-bit: hillshade with the categories
    from PIL import Image
    f = 5
    gd = g0[::f, ::f]
    gy, gx = np.gradient(gd)
    shade = np.clip(.8 - .4 * (gx + gy), .4, 1.2)
    img = np.zeros(gd.shape + (3,), np.uint8)
    img[...] = (110, 150, 80)
    img[canopy[::f, ::f]] = (45, 100, 45)
    img[(canopy & conifer)[::f, ::f]] = (30, 70, 40)
    img[wet[::f, ::f]] = (60, 100, 200)
    img[built[::f, ::f]] = (150, 150, 150)
    img = (img * shade[..., None]).clip(0, 255).astype(np.uint8)
    colours = dict(plantation=(20, 40, 20), pampas=(230, 210, 120), road_cut=(255, 60, 60), bamboo=(120, 220, 80), terraces=(255, 160, 40),
                   reeds_lake=(200, 255, 200), reeds_river=(160, 230, 160), bare_rock=(255, 255, 255))
    for k, col in colours.items():
        m = (layers[k] & (vis >= .3))
        m = ndimage.maximum_filter(m, f)[::f, ::f] if k in ('road_cut', 'reeds_lake', 'reeds_river', 'bare_rock') else m[::f, ::f]
        img[m] = col if k != 'plantation' else (img[m] // 2 + np.array(col, np.uint8) // 2)
    Image.fromarray(img).save(a.out / 'overview.png')
    print(json.dumps({k: (v['total_columns'], v['visible_columns']) if 'top' in v else v for k, v in res.items()}))


if __name__ == '__main__':
    main()
