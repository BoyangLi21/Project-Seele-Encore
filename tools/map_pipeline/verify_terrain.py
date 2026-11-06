"""Read prepared terrain back as voxels; check complete changed columns/edges."""
import argparse
import json
from pathlib import Path
import numpy as np
from author_hakone_lakefront import Editor
from map_pipeline.launch_earthworks import ground
from map_pipeline.launch_protection import load, check_candidate
from map_pipeline.verify_corridors import write_replay_expected
from plan_ashi_landscape_r54 import SOIL, PLANTS
from query_blocks import AIR


def verify(candidate, plan, world):
    guard = load(world)
    launch = check_candidate(guard, candidate)
    e = Editor(candidate)
    errors, rows = [], []
    for path in plan.glob('*.npz'):
        with np.load(path) as f:
            d = {k: f[k] for k in f.files}
        actual = ground(e, d['bounds'])
        active = d['active']; x, z, X, Z = map(int, d['bounds'])
        for iz, ix in np.argwhere(active):
            xx, zz = int(ix+x), int(iz+z)
            h, old = int(d['target'][iz, ix]), int(d['old'][iz, ix])
            if actual[iz, ix] != h:
                errors.append(['height', xx, zz, h, int(actual[iz, ix])])
            for y in range(max(-128, min(old, h)-2), h+1):
                if e.state(xx, y, zz).split('[')[0] not in SOIL:
                    errors.append(['support', xx, y, zz])
            # Natural skin completion may not bury or strand authored objects.
            for y in range(h+1, min(320, max(h+3, old+1)+1)):
                if e.state(xx, y, zz).split('[')[0] not in AIR | PLANTS:
                    errors.append(['object at changed surface', xx, y, zz])
        before = after = 0
        for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = np.roll(actual, (-dz, -dx), (0, 1))
            o = np.roll(d['old'], (-dz, -dx), (0, 1))
            valid = active & (n > -129)
            valid[[0, -1]] = False; valid[:, [0, -1]] = False
            was, now = abs(d['old']-o), abs(actual-n)
            before = max(before, int(was[valid].max(initial=0)))
            after = max(after, int(now[valid].max(initial=0)))
            bad = valid & (now > 2) & (now > was)
            if bad.any():
                iz, ix = np.argwhere(bad)[0]
                errors.append(['new terrace discontinuity', int(ix+x), int(iz+z), int(now[iz, ix])])
        if any(edge.any() for edge in (active[0], active[-1], active[:, 0], active[:, -1])):
            errors.append(['unknown exterior interface', path.name])
        rows.append(dict(id=path.stem, columns=int(active.sum()),
                         changed_interface_maximum_before=before,
                         changed_interface_maximum_after=after))
        e.regions.clear()
    report = dict(errors=errors, terrain=rows, launch_protection=launch,
                  actual_surface_matches_design=not errors, visual_verified=False)
    (candidate/'functional-check.json').write_text(json.dumps(report, indent=2), 'utf8')
    if errors:
        raise ValueError(('Terrain readback rejected', errors[:10]))
    write_replay_expected(candidate)
    print(json.dumps(report), flush=True)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(__doc__)
    for name in ('candidate', 'plan', 'world'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    verify(a.candidate, a.plan, a.world)
