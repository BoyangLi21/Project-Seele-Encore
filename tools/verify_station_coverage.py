"""Read-only inventory of explicitly marked deck surfaces in station snapshots.

Uses the existing strict walker. It never opens a world or treats unmarked air
as a missing floor. Marked-surface coverage is not whole-platform coverage:
the latter also requires an authoritative public-footprint declaration.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np
from audit_hakone_station_walks import Walker
from review_underground_station_evidence import strict_walk


MARKED = {'mtr:platform', 'projectseele:station_tactile_warning'}


def run(args):
    args.out.mkdir(parents=True, exist_ok=True)
    review = json.loads((args.review / 'review.json').read_text('utf8'))
    shapes = json.loads(Path(review['shape_export']).read_text('utf8'))
    walker = Walker(Path(review['source']), shapes)
    rows = []
    for file in sorted(args.review.glob('native-*.json')):
        station = json.loads(file.read_text('utf8'))
        bounds = station['bounds']
        arr, palette = walker.reader.box(bounds)
        levels = {p['position1']['y'] for p in station['platforms']}
        inspected = []
        for code, state in enumerate(palette):
            if state.split('[')[0] not in MARKED:
                continue
            for iy, iz, ix in np.argwhere(arr == code):
                x, y, z = int(ix)+bounds[0], int(iy)+bounds[1], int(iz)+bounds[2]
                if y not in levels:
                    continue
                feet = [x+.5, y+1, z+.5]
                # A zero-length strict sweep checks real support and headroom;
                # it does not infer any connection from an arbitrary start.
                proof = strict_walk(walker, [feet, feet])
                blocking_state = proof.get('state', '')
                if proof['kind'] == 'strict_static_clear':
                    classification = 'clear_marked_surface'
                elif proof['kind'] == 'body_obstruction' and blocking_state.startswith('mtr:apg_glass['):
                    classification = 'fixed_platform_screen_footprint_not_a_walk_lane'
                else:
                    classification = 'unresolved_marked_surface'
                heights, unknown = walker.floors(*feet)
                inspected.append(dict(pos=[x,y,z], state=state, result=proof,
                                      classification=classification,
                                      exact_support_present=any(abs(h-feet[1])<.0001 for h in heights),
                                      unknown_support_queries=len(unknown)))
        counts = Counter(r['result']['kind'] for r in inspected)
        classes = Counter(r['classification'] for r in inspected)
        issues = [r for r in inspected if r['classification'] == 'unresolved_marked_surface' or not r['exact_support_present']]
        fixtures = [r for r in inspected if r['classification'] == 'fixed_platform_screen_footprint_not_a_walk_lane']
        row = dict(site=file.stem, name=station['name'], marked_surface_cells=len(inspected),
                   counts=dict(counts), classifications=dict(classes), issues=issues,
                   fixed_screen_footprint_cells=len(fixtures),
                   marked_support_cells_passed=sum(r['exact_support_present'] for r in inspected),
                   marked_surface_support_and_headroom_complete=bool(inspected) and not issues,
                   full_platform_width_proven=False,
                   full_platform_width_missing='Explicit full passenger-floor footprint, including gaps, furniture exclusions and edges; marks alone do not define the full deck.',
                   retained_path_evidence=str(file), source_bounds=bounds,
                   static_paths_not_repeated=True, world_opened=False, world_written=False)
        (args.out / (file.stem+'.json')).write_text(json.dumps(row,ensure_ascii=False,indent=2),'utf8')
        rows.append({k:v for k,v in row.items() if k != 'issues'})
        print(station['name'],len(inspected),dict(classes),flush=True)
    result = dict(stations=rows, marked_surface_cells=sum(r['marked_surface_cells'] for r in rows),
                  world_opened=False, world_written=False, runtime_accepted=False,
                  method='Every explicitly marked platform/tactile cell at native platform levels; existing Walker collision shapes and strict support/headroom probe. This adds surface coverage only; no gate is opened.',
                  collision_shape_scope='Retained offline export; runtime confirmation remains stage 3.',
                  authoritative_full_footprint_required=True)
    (args.out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--review',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    run(parser.parse_args())
