"""Door triggers for the Hakone ropeway stations, as a cell patch.

A ngong_ping_360 cabin hangs five blocks under its cable, so its doorways sit at
the station floor. MTR opens a doorway only beside a platform block, and the
ropeway stations had none: every floor block one and two cells either side of a
platform rail becomes mtr:platform, flush with the floor. Cells without floor
(the open cabin entries at platform ends) are skipped and reported. Proved in
the isolated client: cabins slowed to 3-4 km/h are boarded from the door side.
"""
import argparse
import json
from pathlib import Path

from plan_station_access_corridor import CapturedSurface

TRIGGER = 'mtr:platform[door_type=none,facing=north,side=0]'
FLOOR = {'minecraft:smooth_stone', 'minecraft:smooth_stone_slab', 'minecraft:stone_bricks', 'minecraft:polished_andesite',
         'minecraft:gray_concrete', 'minecraft:light_gray_concrete', 'minecraft:yellow_concrete', 'minecraft:white_concrete'}


def author(a):
    spec = json.loads(Path(a.config).read_text('utf8'))
    source = CapturedSurface(spec['source'], partial=True)
    edits, report = [], []
    for name, (x0, x1, z, rail_y) in spec['platforms'].items():
        y = rail_y - spec.get('floor_below_cable', 6)
        missing = []
        for x in range(min(x0, x1), max(x0, x1) + 1):
            sides = {-1: 0, 1: 0}
            for dz in (-2, -1, 1, 2):
                state = source.state(x, y, z + dz)
                if state.split('[')[0] in FLOOR:
                    edits.append(dict(pos=[x, y, z + dz], before=state, after=TRIGGER, purpose='ropeway door trigger'))
                    sides[1 if dz > 0 else -1] += 1
            if not all(sides.values()):
                missing.append([x, sides[-1], sides[1]])
        report.append(dict(platform=name, floor_y=y, columns_without_floor=missing))
    a.out.mkdir(parents=True, exist_ok=True)
    check = dict(errors=[], cells=len(edits), platforms=report, world_written=False)
    (a.out / 'door-check.json').write_text(json.dumps(check, ensure_ascii=False, indent=1), 'utf8')
    patch = dict(schema='map-cell-patch-v1', id=spec['id'], label=spec['label'], source=spec['source'], edits=edits,
                 native_snapshot=spec['native_snapshot'], error_reports=[str((a.out / 'door-check.json').resolve())], views_reviewed_by_root=False,
                 continuation_work=spec['continuation_work'])
    if spec.get('native_additions'):
        patch['native_additions'] = spec['native_additions']
    (a.out / 'patch.json').write_text(json.dumps(patch, ensure_ascii=False, indent=1), 'utf8')
    print(json.dumps(dict(cells=len(edits), platforms=[(r['platform'], len(r['columns_without_floor'])) for r in report]), ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('author',))
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    globals()[args.mode](args)
