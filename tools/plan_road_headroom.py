"""Open natural overhang above declared roads, from an installed public-route audit.

Only soil, rock and foliage are cut. Structures over a road stay and are listed as
height limits, because a low deck may be someone's floor. Output is a cell patch
for release_map_patch.py; the world is read through a fresh capture only.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np

from hakone_earthworks import road_blocks
from plan_ashi_landscape_r54 import PLANTS, SOIL
from plan_station_access_corridor import CapturedSurface
from query_blocks import AIR

CUTTABLE = SOIL | PLANTS | {'minecraft:stone', 'minecraft:andesite', 'minecraft:granite', 'minecraft:diorite'}
TREE = ('_leaves', '_log')
ROAD_CLEARANCE, WALK_CLEARANCE = 4, 2


def main(a):
    spec = json.loads(a.config.read_text('utf8'))
    audit = Path(spec['audit'])
    source = CapturedSurface(spec['source'], partial=True)
    with np.load(audit / 'actual-routes.npz') as f:
        x, z, grade, road, full, body = (f[k] for k in ('x', 'z', 'grade2', 'road', 'full', 'body_ok'))
    failed = np.flatnonzero(full & ~body)
    floors = road_blocks(grade[failed])[0]
    rows, limits, skipped = [], Counter(), Counter()
    for index, floor in zip(failed, floors):
        cx, cz = int(x[index]), int(z[index])
        reach = ROAD_CLEARANCE if road[index] else WALK_CLEARANCE
        try:
            cells = [(cx, int(floor) + height, cz) for height in range(1, reach + 1)]
            states = [source.state(*cell) for cell in cells]
        except ValueError:
            skipped['outside capture'] += 1
            continue
        names = [s.split('[')[0] for s in states]
        fixed = [n for n in names if n not in AIR and n not in CUTTABLE and not n.endswith(TREE)]
        if fixed:
            limits[fixed[0]] += 1
            continue
        if 'water' in source.state(cx, int(floor) + reach + 1, cz):
            skipped['water above'] += 1
            continue
        for cell, state, name in zip(cells, states, names):
            if name not in AIR:
                rows.append(dict(pos=list(cell), before=state, after='minecraft:air', purpose='road headroom'))
    errors = []
    report = dict(errors=errors, cells=len(rows), height_limited_columns=dict(limits), skipped=dict(skipped), world_written=False)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / 'headroom-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), 'utf8')
    (a.out / 'patch.json').write_text(json.dumps(dict(schema='map-cell-patch-v1', id=spec['id'], label=spec['label'], source=spec['source'], edits=rows,
        native_snapshot=spec['native_snapshot'], error_reports=[str(a.out / 'headroom-check.json')], views_reviewed_by_root=False,
        continuation_work=spec['continuation_work']), ensure_ascii=False, indent=1), 'utf8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    main(parser.parse_args())
