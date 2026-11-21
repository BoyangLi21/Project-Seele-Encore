"""Retire the complete exposed east pier row of the relocated original incline.

Original generator ownership, frozen R53 detection, exact source-state equality,
and absence of external authored contacts are all required. The ground plane,
retained laboratory, all devices, and current mechanical supports are protected.
"""
from pathlib import Path
import argparse
import json
import math
import numpy as np
import regional_voxels as vox
import survey_r52_original_complex as survey
from query_blocks import iter_block_entities
from survey_facility_target import role_of
from plan_factory_r20 import guide_y
from prepare_continuous_upright_civil_r52 import cuboids


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', required=True, type=Path)
    p.add_argument('--world', type=Path)
    p.add_argument('--apply', action='store_true')
    args = p.parse_args(); frozen = args.base/'WORLD'
    target = args.world if args.world else frozen
    assert not args.apply or args.world and target.resolve() != frozen.resolve()
    survey.WORLD = frozen
    lo, hi = (92, -468, -194), (96, -417, -69)
    before, palette = survey.measure(lo, hi)
    old = np.load(args.base.parent/'map_complete_20261013/survey/original_hangar_transfer_launch.npz')
    old_cells, old_names, origin = old['states'], old['palette'], old['origin']
    mask = np.zeros(before.shape, bool); piers = []
    for z0 in range(-192, -53, 20):
        cells = []
        for z in (z0, z0+1):
            # The migration retired y >= grade-6. The generator owned the
            # support down to -467; keep that ground-level contact cell.
            for y in range(-466, math.floor(guide_y(z))-6):
                pos = (94, y, z); ix, iy, iz = np.asarray(pos)-lo
                ox, oy, oz = np.asarray(pos)-origin
                state = palette[int(before[iy, iz, ix])]
                assert state == str(old_names[old_cells[oy, oz, ox]])
                assert state == 'projectseele:nerv_structural_panel', (pos, state)
                mask[iy, iz, ix] = True; cells.append(pos)
        assert cells
        piers.append(dict(z=z0, removed=len(cells), bottom=-466,
                          top=max(q[1] for q in cells)))
    changed = {tuple(map(int, q[[2,0,1]]+lo)) for q in np.argwhere(mask)}
    assert (94, -432, -91) in changed
    for x,y,z in changed:
        for dx,dy,dz in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
            q = (x+dx,y+dy,z+dz)
            if q in changed or q[1] == -467: continue
            ix,iy,iz = np.asarray(q)-lo
            assert role_of(palette[int(before[iy,iz,ix])]) in ('air','natural'), ('Retained contact',q)
    assert not any(tuple(pos) in changed for pos,tag in iter_block_entities(frozen,survey.DIM,lo,hi))
    def protect(value):
        if isinstance(value, dict):
            for row in value.get('supports', []): assert tuple(row['position']) not in changed
            for v in value.values(): protect(v)
        elif isinstance(value, list):
            for v in value: protect(v)
    protect(json.loads((frozen/'ROOT_MECHANICAL_OWNER.json').read_text('utf8')))
    after = before.copy(); after[mask] = palette.index('minecraft:air')
    vox.WORLD = target; vox.DIM = survey.DIM; vox.OUT = args.base/'retired-piers-repair'
    stage = target.name if args.apply else 'plan'
    assert not args.apply or not list((vox.OUT/stage).glob('applied_*'))
    painter = vox.Painter(vertical_bounds=(-1344,320))
    cuboids(painter,lo,before,after,palette,'original_incline_east_piers')
    painter.meta.update(source='Frozen original R53 detected complete obsolete pier row',
        original_generator='plan_factory_r20.py: x=94, (z+212)%20 in (0,1)',
        preserved_ground_y=-467, preserved_devices_and_progress=True, piers=piers,
        visual_acceptance_pending=True)
    folder = painter.save_plan(stage)
    np.savez_compressed(folder/'EXACT_BEFORE_AFTER.npz',origin=lo,palette=palette,
                        before=before,after=after,positive_edit_mask=mask)
    if args.apply:
        painter.apply(stage); survey.WORLD = target
        actual, names = survey.measure(lo,hi)
        lookup = {s:i for i,s in enumerate(palette)}
        remap = np.asarray([lookup.get(s,65535) for s in names],np.uint16)
        assert np.array_equal(remap[actual],after)
    print(json.dumps(dict(world_written=args.apply,complete_piers=len(piers),
                          removed=int(mask.sum()),ground_devices_progress_preserved=True)))


if __name__ == '__main__': main()
