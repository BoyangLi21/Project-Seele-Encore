"""A measured public field-test cabinet, separate from the command-room layout."""
from pathlib import Path
import argparse, copy, json
import nbtlib
import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / 'run/saves/SEELE_FIELD_R44_REVIEW'
OUT = ROOT / 'artifacts/rebuild_r44/city_coordination/field_equipment'


def cabinet_cells():
    cells = {(x, y, 572): 'projectseele:nerv_machine_panel'
             for x in range(-1075, -1072) for y in range(119, 122)}
    cells.update({
        (-1074, 120, 571): 'minecraft:stone_button[face=wall,facing=north,powered=false]',
        (-1075, 120, 571): 'projectseele:nerv_circuit_indicator[facing=north,lit=false]',
        (-1074, 121, 571): 'projectseele:nerv_direction_panel[facing=north,wayfinding=true]',
    })
    return cells


def main(apply=False):
    if apply:
        from release_combat_r36 import guard
        guard()
    OUT.mkdir(parents=True, exist_ok=True)
    measured = json.loads((ROOT / 'artifacts/rebuild_r44/facility_transit_r44/technical_centre_retest_site.json').read_text('utf8'))
    assert measured['unknown'] == []
    w = MeasuredWorld(WORLD)
    w.box((-1076, 118, 569), (-1072, 123, 574)); w.load()
    tags = dict(iter_block_entities(WORLD, v.DIM, (-1076, 118, 569), (-1072, 123, 574)))
    for x in range(-1075, -1072):
        assert w.block((x, 118, 572)).split('[')[0] != 'minecraft:air', ('Ungrounded cabinet', x)
        for z in (570, 571):
            for y in (119, 120):
                assert w.block((x, y, z)) == 'minecraft:air', ('Operator clearance', x, y, z)
    cells = cabinet_cells()
    v.WORLD = WORLD; v.OUT = OUT; painter = v.Painter()
    for q, state in cells.items():
        assert w.block(q) == 'minecraft:air' and q not in tags, ('Existing equipment or structure', q, w.block(q))
        painter.match((*q, *q), w.block(q), state, 'r44/city_coordination/field_test_cabinet')
    q = (-1074, 121, 571)
    painter.block_entities[q] = nbtlib.Compound(dict(
        id=nbtlib.String('projectseele:station_departure_board'),
        x=nbtlib.Int(q[0]), y=nbtlib.Int(q[1]), z=nbtlib.Int(q[2]),
        Station=nbtlib.String('馈线复测'), Route=nbtlib.String('地区技术中心'),
        Row0=nbtlib.String('先联络远山隔离备用馈线'),
        Row1=nbtlib.String('隔离灯亮后，按下方复测键'),
        Row2=nbtlib.String('留在台前，等读数稳定'), Wayfinding=nbtlib.Byte(1)))
    before = (WORLD / 'city_coordination_r44.json').read_bytes()
    config = json.loads(before)
    assert not config.get('passenger_access_certified', False), 'Do not replace already certified field equipment'
    config.update(visit=[-1074, 119, 570], field_button=[-1074, 120, 571],
                  field_indicator=[-1075, 120, 571], passenger_access_certified=False)
    painter.meta.update(scope='Measured south public station hall, grounded three-wide cabinet and exposed real button',
        reference='Project-original field instrument; TV grid mobilisation informs the procedure, no unseen TV drawing claimed',
        route_evidence=str(measured['station_id']),
        functional_scope='Actual local button and stable isolation samples, followed by posted engineer reconnection',
        release_gate='Passenger routes and real client button input remain unverified; certified flag stays false')
    painter.save_plan('technical_centre_field_cabinet')
    (OUT / 'config_before.json').write_bytes(before)
    (OUT / 'config_after.json').write_text(json.dumps(config, ensure_ascii=False, indent=2), 'utf8')
    if apply:
        painter.apply('technical_centre_field_cabinet')
        assert (WORLD / 'city_coordination_r44.json').read_bytes() == before
        (WORLD / 'city_coordination_r44.json').write_bytes((OUT / 'config_after.json').read_bytes())
    print('Measured field cabinet:', len(cells), 'blocks, one full-NBT panel; passenger certification remains locked', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--apply', action='store_true')
    main(parser.parse_args().apply)
