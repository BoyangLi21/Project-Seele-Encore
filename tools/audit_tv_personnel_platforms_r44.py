"""Actual 0.6 x 1.8m standing clearance over each whole sloped apron.

Deck tops come from actual slab collision boxes, not overall mesh width.
At every longitudinal sample the admissible centre intervals are solved
analytically against physical machinery/guard boxes. No candidate installation.
"""
from pathlib import Path
import argparse, hashlib, json
import numpy as np
from audit_tv_cage_space_r44 import motion

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/rebuild_r44/hangar_machinery'


def remaining(low, high, blocked):
    ranges = [(low, high)]
    for a, b in sorted(blocked):
        new = []
        for x, y in ranges:
            if a >= y or b <= x: new.append((x, y)); continue
            if a > x: new.append((x, min(a, y)))
            if b < y: new.append((max(b, x), y))
        ranges = new
    return [(a, b) for a, b in ranges if b - a > 1e-6]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--resource', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists(): raise ValueError('Fresh private measurement epoch required')
    d = json.loads(args.resource.read_text('utf8')); reports = []
    for variant in range(3):
        for side in (-1, 1):
            name = 'platform_2_r' if variant == 2 and side == 1 else 'platform_r' if side == 1 else 'platform_l'
            floor = np.array(d['collision_parts'][name])
            # Generated load slab has full apron X span and a <=.125m strip;
            # posts/handrails cannot be mistaken for the walking datum.
            floor = floor[(floor[:, 1, 0] - floor[:, 0, 0] > 3) & (floor[:, 1, 2] - floor[:, 0, 2] <= .126)]
            x0, x1 = float(floor[:, 0, 0].min()), float(floor[:, 1, 0].max())
            z0, z1 = float(floor[:, 0, 2].min()), float(floor[:, 1, 2].max())
            components = [c for c in d['components'] if c.get('variant', variant) == variant and not c['part'].startswith('thin_side_rails')]
            phases = []
            for opening in (0., 1.):
                boxes, owners = [], []
                for c in components:
                    moved = np.array(d['collision_parts'][c['part']]) + motion(c, opening)
                    # Whole deck plus standing headroom rejects distant wetwalls
                    # and equipment before any fine-box intersection work.
                    mask = (moved[:, 1, 0] > x0) & (moved[:, 0, 0] < x1) & (moved[:, 1, 2] > z0) & (moved[:, 0, 2] < z1)
                    boxes.extend(moved[mask]); owners.extend([c['part']] * int(mask.sum()))
                boxes = np.array(boxes); owners = np.array(owners)
                rows = []
                for z in np.arange(z0 + .3, z1 - .3 + 1e-8, .125):
                    support = floor[(floor[:, 1, 2] > z - .3) & (floor[:, 0, 2] < z + .3)]
                    feet = float(support[:, 1, 1].max())
                    obstacle = ((boxes[:, 1, 2] > z - .3) & (boxes[:, 0, 2] < z + .3)
                                & (boxes[:, 1, 1] > feet + 1e-6) & (boxes[:, 0, 1] < feet + 1.8))
                    selected = boxes[obstacle]
                    clear = remaining(x0 + .3, x1 - .3, [(b[0, 0] - .3, b[1, 0] + .3) for b in selected])
                    rows.append({'z_local': float(z), 'actual_highest_footprint_support_y': feet,
                                 'clear_centre_intervals': clear,
                                 'physical_clear_strip_widths_m': [b - a + .6 for a, b in clear],
                                 'maximum_clear_strip_m': max((b - a + .6 for a, b in clear), default=0.),
                                 'obstructing_parts': sorted(set(map(str, owners[obstacle])))})
                phases.append({'opening': opening, 'deck_rows': rows,
                               'minimum_whole_deck_clear_strip_m': min(r['maximum_clear_strip_m'] for r in rows),
                               'rows_below_1p5m_clear_strip': int(sum(r['maximum_clear_strip_m'] < 1.5 for r in rows)),
                               'rows_without_any_0p6x1p8_body': sum(not r['clear_centre_intervals'] for r in rows)})
            reports.append({'variant': variant, 'side': side, 'part': name,
                            'nominal_deck_width_m': x1 - x0, 'headroom_requirement_m': 1.8,
                            'human_width_m': .6, 'floor_longitudinal_bounds': [z0, z1], 'phases': phases,
                            'declared_crew_access': 'UNVERIFIED: retained two-lane crew feet48.96 is outboard at offsets18/19; no connected apron access bridge/stair is authored in v4.'})
    args.out.mkdir(parents=True)
    report = {'resource_sha256': hashlib.sha256(args.resource.read_bytes()).hexdigest(),
              'platforms': reports, 'longitudinal_sampling_m': .125,
              'method': 'Actual apron slab tops under full .6m footprint; exact X complements of all physical machinery and rail intersections over 1.8m headroom. Reported clear strip includes the body width; centre travel interval is separately recorded. No standing on top of a receiver/rail is substituted for deck access.',
              'scope': 'Current source cage physical geometry, secured closed/open states. Existing world block shapes, exact native body triangles, continuous moving-state occupancy and real full access routes remain additional checks.',
              'native_passed': False, 'whole_personnel_platform_passed': False, 'world_write_performed': False}
    (args.out / 'contract.json').write_text(json.dumps(report, indent=2), 'utf8')
    print(json.dumps([{'variant':r['variant'],'side':r['side'],'nominal':r['nominal_deck_width_m'],
                       'states':[{k:p[k] for k in ('opening','minimum_whole_deck_clear_strip_m','rows_below_1p5m_clear_strip','rows_without_any_0p6x1p8_body')} for p in r['phases']]} for r in reports]))


if __name__ == '__main__': main()
