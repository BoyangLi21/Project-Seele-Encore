"""Reface only measured TV dome cover and the declared remote airshaft casing."""
from pathlib import Path
from collections import Counter
import argparse
import json
import math
import numpy as np
import regional_voxels as vox
from query_blocks import iter_selected_sections
from prepare_continuous_upright_civil_r52 import cuboids

PANEL = 'projectseele:nerv_structural_panel'
JOINT = 'minecraft:black_concrete'


def roof(x, z):
    radius = np.hypot(x - 30, z - 296)
    t = np.minimum(1, np.maximum(0, (radius - 600) / 1200))
    return np.where(radius <= 600, 24,
                    -478 + np.floor(502 * np.sqrt(np.maximum(0, 1 - t*t)))).astype(int)


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument('world', type=Path)
    ap.add_argument('output', type=Path)
    ap.add_argument('--chunks', type=Path, help='Restrict to a previously measured chunk list')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    vox.WORLD, vox.OUT, vox.DIM = args.world, args.output, 'projectseele:geofront'
    painter = vox.Painter(vertical_bounds=(-1344, 320))
    selected, grids = {}, {}
    local_z, local_x = np.indices((16, 16))
    for cx in range(-111, 115):
        for cz in range(-95, 132):
            x, z = local_x + cx*16, local_z + cz*16
            active = np.hypot(x-30, z-296) < 1780
            if not active.any():
                continue
            h = roof(x, z)
            selected[cx, cz] = set(range(int(h[active].min()+1)//16,
                                          int(h[active].max()+3)//16+1))
            grids[cx, cz] = (h, active, ((x-30)%64 == 0) | ((z-296)%64 == 0))
    # Exterior faces only. The south aperture, collision proxies, door frame,
    # internal ribs and aircraft clear volume are not in this mask.
    faces = [(-1205,-475,-805,-1205,24,-636),
             (-1036,-475,-805,-1036,24,-636),
             (-1204,-475,-805,-1037,24,-805),
             (-1204,-289,-636,-1037,24,-636)]
    for x,y,z,X,Y,Z in faces:
        for cx in range(x//16, X//16+1):
            for cz in range(z//16, Z//16+1):
                selected.setdefault((cx,cz), set()).update(range(y//16,Y//16+1))
    if args.chunks:
        measured = json.loads(args.chunks.read_text('utf8'))
        allowed = set(map(tuple, measured['targets'] if isinstance(measured, dict) else measured))
        selected = {p: sections for p, sections in selected.items() if p in allowed}
    counts = Counter()
    for cx,cz,sy,palette,indices in iter_selected_sections(
            args.world, vox.DIM, selected, skip_unfinished=True):
        names = list(palette)
        for s in (PANEL, JOINT):
            if s not in names: names.append(s)
        before = indices.reshape(16,16,16)
        after = before.copy()
        yy = np.arange(sy*16,sy*16+16)[:,None,None]
        xx,zz = local_x[None,:,:]+cx*16,local_z[None,:,:]+cz*16
        if (cx,cz) in grids:
            h,active,joints = grids[cx,cz]
            owned = active[None,:,:] & (yy > h) & (yy <= h+3)
            owned &= np.asarray([s == 'minecraft:stone' for s in names])[before]
            after[owned] = np.broadcast_to(np.where(joints,names.index(JOINT),names.index(PANEL)),before.shape)[owned]
            counts['roof_cells'] += int(owned.sum())
        for x,y,z,X,Y,Z in faces:
            owned = (xx>=x)&(xx<=X)&(yy>=y)&(yy<=Y)&(zz>=z)&(zz<=Z)
            owned &= np.asarray([s == 'projectseele:nerv_shaft_panel' for s in names])[before]
            horizontal = zz+805 if x == X else xx+1205
            joints = ((yy+475)%32 == 0) | (horizontal%32 == 0)
            after[owned] = np.broadcast_to(np.where(joints,names.index(JOINT),names.index(PANEL)),before.shape)[owned]
            counts['shaft_cells'] += int(owned.sum())
        if np.any(before != after):
            cuboids(painter,(cx*16,sy*16,cz*16),before,after,names,'measured_tv_cover_and_airshaft_exterior')
            counts['sections'] += 1
            if counts['sections'] % 3000 == 0: print(dict(counts),flush=True)
    painter.meta.update(purpose='User-requested GeoFront armor surface',
        geometry='TvWorldPreviewTerrain.roof; original 3 outer cover cells only',
        preserved='All non-stone dome cells, air, authored devices, flight aperture and runtime doors',
        measured=dict(counts))
    painter.save_plan('cavern_armor')
    print(dict(counts),flush=True)
    if args.apply:
        painter.apply('cavern_armor')


if __name__ == '__main__':
    main()
