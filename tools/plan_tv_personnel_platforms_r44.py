"""Private whole six-side personnel layout on declared existing hangar corridors.

Authored world cells are measured before states. It is not applicable until
the paired support geometry, exact boundary/gate policy and full native routes
are validated together. This script never invokes a world writer.
"""
from pathlib import Path
import argparse, hashlib, json, math
from measure_world_r40 import MeasuredWorld

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/rebuild_r44/hangar_machinery'


def deck(profile, level, facing='south'):
    return f'projectseele:tv_personnel_deck_r44[facing={facing},level={level},profile={profile}]'


def main(out):
    out = Path(out)
    if out.exists(): raise ValueError('Fresh private layout epoch required')
    cells, areas, gates, routes = {}, [], [], []
    def floor(q, state, variant, side, role):
        assert q not in cells or cells[q]['after'] == state
        cells[q] = {'position': q, 'after': state, 'variant': variant, 'side': side, 'role': role}
    for variant, cx in enumerate((-12, 30, 72)):
        for side in (-1, 1):
            if variant == 2 and side == 1:
                # The whole original east arrival cell domain ends at z=-247,
                # not -248: inclusive block coordinates have a full extent.
                # These two stair rows begin beyond that retained boundary.
                for step, x in enumerate((88, 87)):
                    low = -394 + .75 * step; y = math.floor(low); level = round((low - y) * 4)
                    for z in (-246, -245): floor((x, y, z), deck('stair', level, 'west'), variant, side, '02_right_supported_entry_stair')
                for z in (-246, -245):
                    floor((86, -393, z), deck('ramp', 2, 'west'), variant, side, '02_right_safe_footprint_transfer')
                    floor((85, -393, z), deck('ramp', 3, 'west'), variant, side, '02_right_safe_footprint_transfer')
                    for x in (83, 84): floor((x, -393, z), deck('flat', 3), variant, side, '02_right_full_width_turn_landing')
                for z in range(-256, -246):
                    for x in (83, 84): floor((x, -393, z), deck('flat', 3), variant, side, '02_right_low_operator_workdeck')
                gate = {'variant': variant, 'side': side, 'facing': 'west', 'lower_positions': [[89, -394, -246], [89, -394, -245]],
                        'public_approach': [90.5, -394, -245.0], 'native_type_proposal': 'projectseele:city_personnel_door',
                        'requires_pair_use_and_no_entry_while_moving_and_occupied_leaf_refusal': True}
                path = [[90.5, -394, -245.0], [89.5, -394, -245.0], [88.5, -393.25, -245.0],
                        [87.5, -392.5, -245.0], [86.5, -392.25, -245.0], [85.5, -392, -245.0],
                        [83.5, -392, -245.0], [84, -392, -247.5], [84, -392, -255.5]]
                areas.append({'variant': variant, 'side': side, 'nominal_personnel_width_m': 2., 'floor_y': -392.,
                              'floor_roles': ['02_right_supported_entry_stair', '02_right_safe_footprint_transfer', '02_right_full_width_turn_landing', '02_right_low_operator_workdeck'],
                              'source_support_revision_required': 'Complete fixed_support_2_r front column/cap to localz=-3.0, supported on retained lower side girder; longitudinal start behind whole stair. Reconnect apron underside with real diagonal bearing. No original east lift cell or aperture changed.'})
            else:
                xs = (cx + 15, cx + 16) if side == 1 else (cx - 16, cx - 15)
                for z in range(-263, -260):
                    for x in xs: floor((x, -395, z), deck('flat', 3), variant, side, 'supported_front_access_bridge')
                for z in range(-260, -246):
                    low = -394 + (z + 260) * .25; y = math.floor(low); level = round((low - y) * 4)
                    for x in xs: floor((x, y, z), deck('ramp', level), variant, side, 'outer_operator_service_lane')
                gate = {'variant': variant, 'side': side, 'facing': 'south', 'lower_positions': [[x, -394, -264] for x in xs],
                        'public_approach': [sum(xs) / 2 + .5, -394, -265.5], 'native_type_proposal': 'projectseele:city_personnel_door',
                        'requires_pair_use_and_no_entry_while_moving_and_occupied_leaf_refusal': True}
                mx = sum(xs) / 2 + .5
                path = [[mx, -394, -265.5], [mx, -394, -264.5], [mx, -394, -263.5]]
                path += [[mx, -394, z + .5] for z in (-263, -262, -261)]
                path += [[mx, -394 + (z + 261) * .25, z + .5] for z in range(-260, -247)]
                areas.append({'variant': variant, 'side': side, 'nominal_personnel_width_m': 2.,
                              'mechanical_apron_width_m': 5.3, 'full_assembly_width_m': 7.6,
                              'role': 'Separate grating service lane for receiver/frontbeam and apron-front inspection; original side patrol/upper observation roles remain distinct.'})
            gates.append(gate)
            routes.append({'id': f'tv_operator/{variant}/{side}/entry', 'waypoints_for_native_refinement': path,
                           'expected_y_is_not_a_teleport_or_native_proof': True})
            routes.append({'id': f'tv_operator/{variant}/{side}/return', 'waypoints_for_native_refinement': list(reversed(path)),
                           'expected_y_is_not_a_teleport_or_native_proof': True})
    w = MeasuredWorld(ROOT / 'run/saves/SEELE_FIELD_R44_REVIEW')
    for q in cells: w.around(q, 1)
    for gate in gates:
        for q in gate['lower_positions']: w.around(q, 2)
    w.load()
    for q, item in cells.items():
        item['before'] = w.block(q)
        if item['before'] is None: raise ValueError(('Unknown source cell', q))
        # Cells, not a broad empty-room assumption, define the full preserved
        # arrival domain. Stair profiles extending to neighbour y are separately
        # required in physical-world clearance validation.
        if 85 <= q[0] <= 98 and -399 <= q[1] <= -390 and -264 <= q[2] <= -248:
            raise ValueError(('Personnel layout entered original02 arrival owner', q))
    for gate in gates:
        gate['before_lower'] = [w.block(q) for q in gate['lower_positions']]
        gate['before_upper'] = [w.block([q[0], q[1] + 1, q[2]]) for q in gate['lower_positions']]
    out.mkdir(parents=True)
    report = {'floor_cells': list(cells.values()), 'operator_areas': areas, 'entry_gate_pairs': gates,
              'complete_entry_and_return_cases': routes,
              'native_deck_union_proof': str(BASE / 'tv_personnel_deck_native_v1/native_union_readback/result.json'),
              'floor_cells_count': len(cells), 'world_write_performed': False, 'apply_allowed': False,
              'required_remaining': ['Fine guards with exact fractional floor datum and real pair-gate policy',
                                     'Fixed full02 support revision + its actual body/plug/crane/world/crew clearance',
                                     'Actual native cell and neighbour fullfootprint/headroom over all six complete decks',
                                     'Three lateral walking lines, real entry and return from original public corridors',
                                     'Entire operator-area occupant admission for prepare and machinery motion; source maintenance parity'],
              'no_visual_only_narrowing': True, 'native_personnel_passed': False, 'art_passed': False}
    (out / 'layout.json').write_text(json.dumps(report, indent=2), 'utf8')
    print(json.dumps({'fixed_deck_cells': len(cells), 'entry_pairs': len(gates), 'full_return_routes': len(routes),
                      'non_air_floor_sources': [q for q in report['floor_cells'] if q['before'] not in ('minecraft:air', 'minecraft:cave_air', 'minecraft:void_air')][:8], 'apply_allowed': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); main(args.out)
