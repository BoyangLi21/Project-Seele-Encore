"""Author one reversible Unit01 equipment-tray candidate; never write a world.

The footprint belongs to the declared original carrier, not to inferred air.
Install only with a short bay actuator and an explicit station-marker adapter.
"""
import argparse
import json
import zipfile
from collections import Counter
from pathlib import Path

from query_blocks import iter_block_entities, read_box


def rail(name, xmin, xmax):
    # Closed steel section rests on the native tray floor. Top face matches
    # the complete source deck's four existing bottom bearing facets.
    p = [(x, y, z) for z in (-15.5, 24.5) for y in (-5, -4.0078125) for x in (xmin, xmax)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1),
             (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    rgb = []
    for a, b, c, d in faces:
        for i in (a, b, c, a, c, d):
            rgb.extend((*p[i], .30, .36, .40))
    return dict(name=name, triangles_rgb=rgb)


def prepare(world, output, variant=1):
    owner = json.loads((world / 'ROOT_MECHANICAL_OWNER.json').read_text('utf8'))
    unit = next(u for u in owner['units'] if u['variant'] == variant)
    dx = unit['bay_frame']['position'][0] - 30.5
    assert dx == int(dx) and unit['bay_frame']['position'][1:] == [-1062, 328.5]
    dx = int(dx)
    assert unit['bay_frame']['quaternion'] == [0, 1, 0, 0]
    with zipfile.ZipFile(world.parents[1] / 'mods/projectseele-0.1.0-all.jar') as jar:
        carrier = json.loads(jar.read('assets/projectseele/mesh/carrier_mk2_r53.json'))
    assert carrier['source_triangles'] == 8727
    assert carrier['fitting']['source_faces_removed'] == 0
    # Every part's Y motion is affine on each side of RISE_END. Retraction
    # changes X/Z only, so the endpoint minimum bounds the entire 1m stroke.
    lowest_stroke = min(min(v[1::8]) - (0 if n == 'deck' or n.startswith('toe_') else 1)
                       for n, v in carrier['parts'].items()) - 1062
    assert lowest_stroke > -1067 + .99
    dimension = 'projectseele:geofront'
    lo, hi = (11 + dx, -1068, 304), (49 + dx, -1061, 344)
    old = {(x - dx, y, z): state for (x, y, z), state in read_box(world, dimension, lo, hi).items()}
    block_entities = {(x - dx, y, z): entry for (x, y, z), entry in iter_block_entities(world, dimension, lo, hi)}
    changes = {}

    def put(pos, state, purpose):
        pos = tuple(pos)
        assert pos in old, ('Unmeasured cell', pos)
        assert pos not in block_entities, ('Preserve block entity', pos)
        if old[pos] != state:
            actual = (pos[0] + dx, pos[1], pos[2])
            assert actual not in changes, ('Conflicting edit', actual)
            changes[actual] = dict(pos=list(actual), before=old[pos], after=state,
                                before_nbt=None, after_nbt=None, purpose=purpose)

    # Existing equipment floor is lowered only inside the source deck band.
    # Both outer floor strips and all four original gantry supports survive.
    allowed_floor = {'minecraft:iron_block', 'minecraft:light_gray_concrete',
                     'minecraft:lodestone', 'projectseele:nerv_floor_panel',
                     'projectseele:nerv_machine_panel', 'projectseele:nerv_machine_edge',
                     'minecraft:polished_basalt', 'minecraft:polished_blackstone', 'minecraft:sea_lantern',
                     'minecraft:oxidized_cut_copper', 'minecraft:air'}
    for x in range(17, 44):
        for z in range(304, 344):
            for y in range(-1067, -1062):
                at = (x, y, z)
                assert old[at] in allowed_floor, ('Unexpected device material', at, old[at])
                put(at, 'minecraft:air', 'complete_deck_clearance')
            bottom = ('minecraft:lodestone' if (x, z) == (30, 328)
                      else 'minecraft:sea_lantern' if any(old[x, y, z] == 'minecraft:sea_lantern'
                                                         for y in range(-1067, -1062))
                      else old[x, -1063, z] if old[x, -1063, z] in {'minecraft:oxidized_cut_copper',
                          'minecraft:polished_blackstone', 'projectseele:nerv_machine_edge'}
                      else 'projectseele:nerv_structural_panel')
            put((x, -1068, z), bottom, 'closed_tray_bottom')

    # The five-metre side plates hang from the retained floor bands. This is
    # a closed tray, not an unsupported sheet over the retired service pit.
    for x in (16, 44):
        for z in range(304, 345):
            assert old[x, -1063, z] != 'minecraft:air', ('Missing retained rim', x, z)
            for y in range(-1068, -1063):
                assert old[x, y, z] == 'minecraft:air', ('Do not replace hidden structure', x, y, z)
                put((x, y, z), 'projectseele:nerv_structural_panel', 'rim_attached_tray_side')
            guard_state = ('projectseele:nerv_edge_rail[east=' + str(x == 16).lower()
                    + ',north=false,south=false,west=' + str(x == 44).lower() + ']')
            assert old[x, -1062, z] in {'minecraft:air', 'projectseele:lcl[level=0]'}
            put((x, -1062, z), guard_state, 'personnel_edge_guard')
    for x in range(17, 44):
        assert old[x, -1063, 344] != 'minecraft:air'
        for y in range(-1068, -1063):
            assert old[x, y, 344] == 'minecraft:air'
            put((x, y, 344), 'projectseele:nerv_structural_panel', 'rear_tray_closure')
        assert old[x, -1062, 344] in {'minecraft:air', 'projectseele:lcl[level=0]'}
        put((x, -1062, 344),
            'projectseele:nerv_edge_rail[east=false,north=true,south=false,west=false]',
            'rear_personnel_edge_guard')
    assert old[30, -1063, 328] == 'minecraft:lodestone'
    for cell in unit['gantry']['supports']:
        pos = tuple(cell['position'])
        assert pos not in changes and old[pos[0] - dx, pos[1], pos[2]] == cell['state']
    assert all(tuple(c['position']) not in changes for c in unit['carrier_support'])
    forward = [changes[p] for p in sorted(changes)]
    inverse = [dict(pos=c['pos'], before=c['after'], after=c['before'],
                    before_nbt=c['after_nbt'], after_nbt=c['before_nbt']) for c in forward]
    output.mkdir(parents=True, exist_ok=True)
    for name, value in [('forwardPatch.json', forward), ('inversePatch.json', inverse),
                        ('positiveEditMask.json', [c['pos'] for c in forward])]:
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), 'utf8')
    plan = dict(schema='projectseele.r53.unit01-shallow-tray.candidate.v1',
                world=str(world.resolve()), dimension=dimension, world_written=False,
                ready_to_install=False, declared_leg=f'unit{variant}/original_incline',
                eva=unit['eva'], bay_frame=unit['bay_frame'],
                marker=dict(old=[30 + dx, -1063, 328], proposed=[30 + dx, -1068, 328],
                            payload_root_unchanged=unit['bay_frame']['position']),
                scope='Bay and current 7.2m cancel-return segment only; north continues into existing incline device space.',
                minimum_full_stroke_source_y=lowest_stroke, tray_top_y=-1067,
                full_stroke_vertical_clearance_m=lowest_stroke + 1067,
                body_stroke_m=1, payload_elevation_m=0, source_faces_removed=0,
                preserved_gantry_supports=unit['gantry']['supports'],
                preserved_personnel_bands=[[11 + dx, 15 + dx], [45 + dx, 49 + dx]],
                edits=len(forward), purposes=dict(Counter(c['purpose'] for c in forward)),
                install_together=['Explicit physical marker versus payload datum binding; no legacy bed+1 height reuse',
                                  'Keep exact selected edge-guard cells out of LCL fill/drain writes; preserve other fluid/task state',
                                  'Source-bound 1m bay actuator, finite foot bearings and full-source sweep admission',
                                  'Visible parked carrier; power only after rise completes',
                                  'Native deck/gantry/rail clearance and side-path review'],
                untouched=['EVA/player/task/traffic NBT', 'Retired 64m service pit',
                           'Original controller root, route clock, upper boarding bridge',
                           'Remaining 207m transfer route'])
    (output / 'construction.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), 'utf8')
    print(json.dumps(dict(candidate=str(output), edits=len(forward), world_written=False,
                         purposes=plan['purposes']), ensure_ascii=False))
    runtime = dict(variant=variant, eva=unit['eva'], root=unit['bay_frame']['position'],
                   logical_bed=[30 + dx, -1063, 328], physical_marker=[30 + dx, -1068, 328],
                   cells=[dict(pos=c['pos'], state=c['after']) for c in forward]
                         + [dict(pos=c['position'], state=c['state']) for c in unit['gantry']['supports']],
                   rails=[rail('left', 8.6, 9.2), rail('right', -10.1, -9.5)])
    (output / 'runtime-bay.json').write_text(json.dumps(runtime, separators=(',', ':')), 'utf8')
    return runtime


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--all-bays', action='store_true')
    args = parser.parse_args()
    if args.all_bays:
        bays = [prepare(args.world, args.output / f'unit{v}', v) for v in range(3)]
        target = args.output / 'assets/projectseele/facility/r53_carrier_bay_trays.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(dict(schema='projectseele.r53.carrier-bay-trays.v1', bays=bays), separators=(',', ':')), 'utf8')
    else:
        prepare(args.world, args.output)
