"""Repair measured truncation of legacy exterior waters at the Hakone blend.

The native world uses Y62 water. Existing wet columns retain that basin; only
its clipped surface is restored. Dry exposed banks rise to a finite crest and
meet untouched soil without crossing the surveyed core. No underground void
or facility is owned.
"""
import argparse, json, os
from pathlib import Path
import numpy as np
from scipy.ndimage import binary_dilation, distance_transform_edt
from author_hakone_lakefront import Editor
from map_pipeline.launch_protection import load, check_candidate
from plan_ashi_landscape_r54 import SOIL, PLANTS
from query_blocks import AIR

CORE = (-1982, -1548, 4386, 3720)
HALO = 256


def tile(survey, rx, rz):
    x, z = rx * 512 - HALO, rz * 512 - HALO
    size = 512 + 2 * HALO
    h = np.full((size, size), -129, np.int16)
    water = np.full(h.shape, -32768, np.int16)
    known = np.zeros(h.shape, bool)
    foreign = np.zeros(h.shape, bool)
    for nx in range(rx - 1, rx + 2):
        for nz in range(rz - 1, rz + 2):
            path = survey / f'r.{nx}.{nz}.npz'
            if not path.exists(): continue
            with np.load(path) as f:
                l, t = max(x, nx * 512), max(z, nz * 512)
                r, b = min(x + size, nx * 512 + 512), min(z + size, nz * 512 + 512)
                dst = np.s_[t-z:b-z, l-x:r-x]
                src = np.s_[t-nz*512:b-nz*512, l-nx*512:r-nx*512]
                h[dst], water[dst] = f['ground'][src], f['water'][src]
                known[dst], foreign[dst] = f['full'][src], f['foreign'][src]
    zz, xx = np.mgrid[z:z+size, x:x+size]
    outer = (xx < CORE[0]) | (xx > CORE[2]) | (zz < CORE[1]) | (zz > CORE[3])
    wet = known & outer & (water >= 44) & (water <= 62)
    seed = binary_dilation(wet) & known & outer & ~wet & (h < 62)
    if seed.any():
        distance = distance_transform_edt(~seed)
        target = np.maximum(h, np.ceil(63 - distance * .6).astype(np.int16))
        core_distance = np.maximum.reduce([CORE[0]-xx,xx-CORE[2],CORE[1]-zz,zz-CORE[3],np.zeros(h.shape,int)])
        feather = np.clip(core_distance/96,0,1)
        feather = feather*feather*(3-2*feather)
        target = np.rint(h+(target-h)*feather).astype(np.int16)
    else: target = h.copy()
    active = known & outer & ~wet & (target > h)
    target[~active] = h[~active]
    crop = np.s_[HALO:HALO+512, HALO:HALO+512]
    return {k: v[crop].copy() for k, v in dict(old=h, target=target, active=active,
        water=water, wet=wet, seed=seed, full=known, foreign=foreign).items()}


def prepare(a):
    a.out.mkdir(parents=True, exist_ok=False)
    for sub in ('source', 'delta', 'earthworks'): (a.out / sub).mkdir()
    for f in (a.source / 'source').glob('*.npz'): os.link(f, a.out / 'source' / f.name)
    e = Editor(a.out)
    guard = load(a.world)
    errors, summaries = [], []
    retained_cells = []
    yy = np.arange(-128, 320)[:, None, None]
    for file in sorted(a.survey.glob('r.*.npz')):
        rx, rz = map(int, file.stem.split('.')[1:])
        d = tile(a.survey, rx, rz)
        water_fix = d['wet'] & (d['water'] < 62)
        if not (d['active'].any() or water_fix.any()): continue
        r = e.region(rx*512, rz*512)
        states = ['minecraft:stone', 'minecraft:dirt', 'minecraft:grass_block[snowy=false]', 'minecraft:water[level=0]']
        for s in states:
            if s not in r['ids']: r['ids'][s] = len(r['names']); r['names'].append(s)
        stone, dirt, grass, water = (r['ids'][s] for s in states)
        natural = np.array([s.split('[')[0] in SOIL | PLANTS | AIR | {'minecraft:water'} for s in r['names']])
        empty = np.array([s.split('[')[0] in PLANTS | AIR | {'minecraft:water'} for s in r['names']])
        # R02 estate road piers and S2 rail foundations stay exact. Their
        # commissioned deck/track is Y70 or higher; the bank crest is <=63.
        retained = np.array([s.split('[')[0] in {'minecraft:polished_basalt','minecraft:light_gray_concrete',
            'minecraft:stone_bricks','minecraft:mossy_stone_bricks'} for s in r['names']])
        for q, v in zip(r['coords'], r['after']):
            cx, cz = map(int, q)
            area = np.s_[cz%32*16:cz%32*16+16, cx%32*16:cx%32*16+16]
            active, old, top = d['active'][area], d['old'][area], d['target'][area]
            restore = water_fix[area]
            if not (active.any() or restore.any()): continue
            # Only the measured exterior band. No new solid below its soil.
            band = active & (yy >= old-2) & (yy <= top)
            water_band = restore & (yy > d['water'][area]) & (yy <= 62)
            proposed = np.broadcast_to(np.where(yy == top, grass, np.where(yy >= top-3, dirt, stone)), v.shape)
            changed = (band & (v != proposed)) | (water_band & (v != water))
            blocked = changed & (guard.chunk_mask(cx,cz) | ~(natural[v] | retained[v]))
            # Raising a water surface may only replace exterior vegetation/air.
            blocked |= water_band & ~(empty[v] | retained[v])
            if blocked.any():
                for iy, iz, ix in np.argwhere(blocked)[:12]:
                    errors.append([cx*16+int(ix),int(iy)-128,cz*16+int(iz),r['names'][int(v[iy,iz,ix])]])
                continue
            keep = changed & retained[v]
            for iy, iz, ix in np.argwhere(keep):
                retained_cells.append([cx*16+int(ix),int(iy)-128,cz*16+int(iz),r['names'][int(v[iy,iz,ix])]])
            fill = band & natural[v]
            v[fill] = proposed[fill]
            v[water_band & empty[v]] = water
        e.save(); e.regions.clear()
        d['bounds'] = np.array([rx*512,rz*512,rx*512+511,rz*512+511])
        np.savez_compressed(a.out/'earthworks'/file.name, **d)
        summaries.append(dict(region=[rx,rz],bank_columns=int(d['active'].sum()),
            truncated_water_columns=int(water_fix.sum()),exposed_bank_seeds=int(d['seed'].sum())))
        print('Prepared legacy water banks',rx,rz,summaries[-1],flush=True)
    rows=e.save()
    (a.out/'manifest.json').write_text(json.dumps(dict(world=str(a.world),regions=rows,
        cells=sum(r['cells']for r in rows),world_written=False,legacy_water_banks=summaries),indent=2),'utf8')
    (a.out/'functional-check.json').write_text(json.dumps(dict(errors=errors,
        visual_verified=False,progress_records_written=False),indent=2),'utf8')
    (a.out/'retained-foundations.json').write_text(json.dumps(retained_cells,indent=2),'utf8')
    (a.out/'launch-protection.json').write_text(json.dumps(check_candidate(guard,a.out),indent=2),'utf8')
    if errors: raise ValueError(f'Bank candidate intersects retained cells: {errors[:12]}')
    print('Prepared',sum(r['cells']for r in rows),'cells; no world writes',flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser(__doc__)
    for key in ('source','survey','world','out'):p.add_argument('--'+key,type=Path,required=True)
    prepare(p.parse_args())
