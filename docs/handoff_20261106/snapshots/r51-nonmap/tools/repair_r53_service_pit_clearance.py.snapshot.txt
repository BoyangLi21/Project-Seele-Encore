"""Repair authored R53 pit interference; preserve all devices and progress.

The original pit receipt grants removal ownership. The explicit replacement
lining stays inside that pit's construction envelope, connects to its existing
base and crossbeams, and is checked against complete current mechanism travel.
"""
from pathlib import Path
import argparse
import json
import numpy as np
import regional_voxels as vox
import survey_r52_original_complex as survey
from query_blocks import iter_block_entities
from prepare_continuous_upright_civil_r52 import cuboids


DIM = 'projectseele:geofront'
LO, HI = (-34, -1136, 307), (95, -1062, 350)
AIR = 'minecraft:air'
SHAFT = 'projectseele:nerv_shaft_panel'
STRUCT = 'projectseele:nerv_structural_panel'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--world', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    base = args.base.resolve()
    frozen = base / 'WORLD'
    survey.WORLD = frozen
    before, palette = survey.measure(LO, HI)
    ids = {state: i for i, state in enumerate(palette)}
    assert all(state in ids for state in (AIR, SHAFT, STRUCT))
    after = before.copy()
    shapes = json.loads((frozen/'native_collision_shapes.json').read_text('utf8'))
    solid_backing = {state for state in palette if shapes.get(state) == [[0.,0.,0.,1.,1.,1.]]}

    def index(pos):
        x, y, z = pos
        assert all(LO[i] <= pos[i] <= HI[i] for i in range(3)), pos
        return y-LO[1], z-LO[2], x-LO[0]

    receipt_path = base.parent / 'map_complete_20261013/complete_carrier_pits/three_supported_dry_carrier_pits/EXACT_BEFORE_AFTER.npz'
    receipt = np.load(receipt_path)
    assert tuple(receipt['origin']) == LO and receipt['after'].shape == before.shape
    old_names = receipt['palette'].tolist()
    conflicts = json.loads((base/'lead-pit-frozen-conflicts.json').read_text('utf8'))
    occupied = json.loads((base/'lead-pit-occupied.json').read_text('utf8'))
    removals = set()
    for unit in conflicts['units']:
        for hit in unit['hits']:
            pos = tuple(hit['position']); ix = index(pos)
            assert receipt['positive_edit_mask'][ix], ('Unowned removal', pos)
            assert palette[int(before[ix])] == old_names[int(receipt['after'][ix])] == hit['state']
            assert hit['state'] in (SHAFT, STRUCT)
            after[ix] = ids[AIR]; removals.add(pos)
    assert len(removals) == 1740

    # A continuous outer lining, connected to the original three-layer base.
    # Its top stays below the shutter/lower-frame workspace. The existing
    # front/rear crossbeams at -1071/-1070 retain their full outside row.
    additions = set()
    for cx in (72, 30, -12):
        for y in range(-1135, -1071):
            for x in range(cx-19, cx+20):
                for z in range(309, 348):
                    if x not in (cx-19, cx+19) and z not in (309, 347):
                        continue
                    if y == -1072 and z not in (309, 347):
                        continue  # Existing lower-frame lateral work band.
                    pos = x, y, z; ix = index(pos)
                    assert palette[int(before[ix])] == AIR or palette[int(before[ix])] in solid_backing, ('Unknown lining occupant', pos)
                    assert pos not in removals
                    if before[ix] == ids[AIR]:
                        after[ix] = ids[SHAFT]; additions.add(pos)
    changes = removals | additions

    peers = base/'pit-current-peers'
    contract = json.loads((peers/'CURRENT_FACTORY_CONTRACT.json').read_text('utf8'))
    for contact in contract['contacts']:
        p = contact['world']; pos = (int(np.floor(p[0])), int(np.floor(p[1]-1e-6)), int(np.floor(p[2])))
        assert pos not in changes, ('Protected bearing', contact)
    owner = json.loads((frozen/'ROOT_MECHANICAL_OWNER.json').read_text('utf8'))
    def protect(value):
        if isinstance(value, dict):
            for row in value.get('supports', []):
                assert tuple(row['position']) not in changes, ('Declared support', row['position'])
            for child in value.values(): protect(child)
        elif isinstance(value, list):
            for child in value: protect(child)
    protect(owner)
    for pos, _ in iter_block_entities(frozen, DIM, LO, HI):
        assert pos not in changes, ('Block entity protected', pos)

    for unit in occupied['units']:
        for row in unit['occupied_cells']:
            pos = tuple(row['position'])
            assert after[index(pos)] == ids[AIR], ('Lead stroke obstructed', pos)
    for name in ('LOWER_FULL_STROKE_CUBE_OCCUPANCY.json', 'HATCH_YAW0_FULL_STROKE_CUBE_OCCUPANCY.json'):
        for row in json.loads((peers/name).read_text('utf8')):
            x, y, z = row['canonical_cell']
            for cx in (72, 30, -12):
                assert (x+cx, y, z) not in additions, ('Lining enters mechanism sweep', name, (x+cx,y,z))
    for cx in (72, 30, -12):
        for y in range(-1135, -1071):
            for x in range(cx-19, cx+20):
                for z in range(309, 348):
                    if x in (cx-19, cx+19) or z in (309, 347):
                        if y == -1072 and z not in (309, 347):
                            continue
                        assert palette[int(after[index((x,y,z))])] in solid_backing, 'Open exterior lining'
        # Unbroken original base, outside beam row and eight hatch columns.
        for z in (309, 347):
            for x in range(cx-19, cx+20):
                assert after[index((x,-1071,z))] == ids[STRUCT]
        for x in range(cx-18, cx+19):
            for z in range(310,347):
                assert after[index((x,-1133,z))] == before[index((x,-1133,z))] != ids[AIR]

    world = args.world.resolve() if args.world else frozen
    if args.apply:
        assert args.world and world != frozen, 'Frozen R53 source must remain unchanged'
        assert (world/'level.dat').is_file()
        # Release ZIPs intentionally omit Minecraft's process-local lock file.
        if not (world/'session.lock').exists():
            with (world/'session.lock').open('xb') as lock:
                lock.write(bytes((0xe2, 0x98, 0x83)))
    vox.WORLD = world; vox.DIM = DIM; vox.OUT = base/'pit-repair'
    stage = world.name if args.apply else 'plan'
    assert not args.apply or not list((vox.OUT/stage).glob('applied_*')), 'Already applied'
    painter = vox.Painter(vertical_bounds=(-1344, 320))
    count = cuboids(painter, LO, before, after, palette, 'r53_declared_service_pit_lead_clearance_and_closed_lining')
    painter.meta.update(source='original R53 delivered save', purpose='repair three existing service pits',
                        original_pit_receipt=str(receipt_path), removal_count=len(removals),
                        lining_count=len(additions), original_bearings_preserved=True,
                        full_lead_lower_hatch_sweeps_checked=True, exterior_lining_closed=True,
                        dynamic_floor_and_all_entities_unchanged=True, visual_acceptance_pending=True)
    folder = painter.save_plan(stage)
    np.savez_compressed(folder/'EXACT_BEFORE_AFTER.npz', origin=LO, palette=palette, before=before, after=after, positive_edit_mask=before!=after)
    if args.apply:
        painter.apply(stage)
        survey.WORLD = world
        actual, names = survey.measure(LO, HI)
        for pos in changes:
            ix = index(pos)
            assert names[int(actual[ix])] == palette[int(after[ix])], ('Readback mismatch', pos)
    print(json.dumps(dict(world_written=args.apply, changed=count, removed=len(removals),
                          lining=len(additions), bearings_preserved=True, full_motion_checked=True)))


if __name__ == '__main__':
    main()
