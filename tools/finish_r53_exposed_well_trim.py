"""Unify original trim immediately outside the installed black well enclosure."""
from pathlib import Path
import argparse
import gzip
import json
from collections import Counter

from query_blocks import read_box, iter_block_entities
from finish_r53_shaft_core_and_emblem import protect_owner, install

DIM = 'projectseele:geofront'
BLACK = 'minecraft:black_concrete'
FINISHES = {
    'projectseele:nerv_structural_panel', 'projectseele:nerv_shaft_panel',
    'projectseele:nerv_machine_edge', 'projectseele:nerv_floor_panel',
    'projectseele:nerv_strip_light[lit=true]',
    'projectseele:nerv_strip_light[lit=false]',
}


def plan(world, original, out):
    protected = set()
    protect_owner(world, json.loads((world / 'ROOT_MECHANICAL_OWNER.json').read_text('utf8')), protected, set())
    candidates = {}
    for left, right in ((-29, 5), (13, 47), (55, 89)):
        lo, hi = (left - 1, -429, -55), (right + 1, 74, 6)
        cells = read_box(world, DIM, lo, hi)
        old = read_box(original, DIM, lo, hi)
        tags = dict(iter_block_entities(world, DIM, lo, hi))
        pairs = []
        for z in range(-54, 6):
            pairs += [((left - 1, z), (left, z)), ((right + 1, z), (right, z))]
        for x in range(left, right + 1):
            pairs += [((x, -55), (x, -54)), ((x, 6), (x, 5))]
        for y in range(-429, 75):
            for (x, z), (ix, iz) in pairs:
                p = x, y, z
                before = cells.get(p)
                if p in protected or p in tags or before not in FINISHES:
                    continue
                if old.get(p) != before or cells.get((ix, y, iz)) != BLACK:
                    continue
                candidates[p] = dict(pos=p, before=before, after=BLACK,
                    before_nbt=None, after_nbt=None,
                    reason='original_trim_outside_installed_black_well_wall')
    rows = list(candidates.values())
    out.mkdir(parents=True, exist_ok=True)
    (out / 'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows).encode(), mtime=0))
    report = dict(changed_cells=len(rows), materials=dict(Counter(r['before'] for r in rows)),
                  original_geometry_retained=True, devices_and_owned_cells_retained=True,
                  retained_lift_landing_below_y=-430)
    (out / 'PLAN.json').write_text(json.dumps(report, indent=2), 'utf8')
    print(json.dumps(report))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--world', type=Path, required=True)
    p.add_argument('--original', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--apply', action='store_true')
    a = p.parse_args()
    install(a.world, a.out) if a.apply else plan(a.world, a.original, a.out)
