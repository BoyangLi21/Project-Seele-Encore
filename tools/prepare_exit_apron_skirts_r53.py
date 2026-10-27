"""Plan the three declared GeoFront hatch-to-apron joints; never write a world."""
import argparse
import gzip
import json
from collections import defaultdict
from pathlib import Path

from query_blocks import read_box, iter_block_entities

DIM = 'projectseele:geofront'
TARGET = 'projectseele:nerv_exit_apron_skirt_r53'
BOUNDS = [0, 12, 10.4, 16, 16, 16]


def packed(point):
    x, y, z = point
    value = ((x & 0x3ffffff) << 38) | ((z & 0x3ffffff) << 12) | (y & 0xfff)
    return value - (1 << 64) if value >= 1 << 63 else value


def generation_candidates(world, output, rows):
    """Extend only the selected world's existing complete chunk recipes."""
    import nbtlib
    data = world / 'dimensions/projectseele/geofront/data'
    topologies = list(data.glob('projectseele_city_rigid_topology_r45_*.dat'))
    assert len(topologies) == 1, 'One installed topology owner required'
    topology = nbtlib.load(topologies[0])['data']
    assert str(topology['Stage']) == 'INSTALLED'
    recipe = (data / str(topology['GenerationFolder']) / 'chunks').resolve()
    assert recipe.is_relative_to(data.resolve()), 'Recipe must remain inside its owning dimension'
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['pos'][0] // 16, row['pos'][2] // 16].append(row)
    updates = []
    for (x, z), batch in grouped.items():
        original = recipe / f'{x}_{z}.dat'
        doc = nbtlib.load(original)
        assert int(doc['Version']) == 1 and doc['WorldUUID'] == topology['WorldUUID']
        old_cells = {int(cell['Pos']) for cell in doc['Static']}
        wanted = {packed(row['pos']) for row in batch}
        assert not wanted.intersection(old_cells), 'Do not silently overwrite a registered generator owner'
        assert not wanted.intersection(int(cell['Pos']) for cell in doc.get('Ground', []))
        relative = original.relative_to(world.resolve())
        forward, inverse = output / 'generation/forward' / relative, output / 'generation/inverse' / relative
        forward.parent.mkdir(parents=True, exist_ok=True)
        inverse.parent.mkdir(parents=True, exist_ok=True)
        inverse.write_bytes(original.read_bytes())
        palette = doc['Palette']
        state = nbtlib.Compound({'Name': nbtlib.String(TARGET)})
        index = next((i for i, value in enumerate(palette) if value == state), len(palette))
        if index == len(palette):
            palette.append(state)
        for row in batch:
            doc['Static'].append(nbtlib.Compound({'Pos': nbtlib.Long(packed(row['pos'])),
                                                  'StateId': nbtlib.Int(index)}))
        doc.save(forward, gzipped=True)
        installed = nbtlib.load(forward)
        assert len(installed['Static']) == len(old_cells) + len(batch)
        assert {int(cell['Pos']) for cell in installed['Static']} == old_cells | wanted
        updates.append(dict(target_world_relative=relative.as_posix(), added_static_cells=len(batch),
                            original_entries_modified=0, inverse_preserves_original_file=True))
    (output / 'GENERATION_UPDATES.json').write_text(json.dumps(dict(
        runtime='GeoFrontBoundedChunkGenerator.applyBiomeDecoration -> CityRigidGenerationR45.apply',
        scope='Newly generated chunks only; existing FULL chunks use EXACT_DELTA',
        added_static_cells=sum(row['added_static_cells'] for row in updates), files=updates), indent=2), 'utf8')


def read_table(world, reference):
    data = (world / reference['cells_file']).read_bytes()
    return json.loads(gzip.decompress(data) if reference['cells_file'].endswith('.gz') else data)


def positions(value):
    if isinstance(value, dict):
        point = value.get('position')
        if isinstance(point, list) and len(point) == 3:
            yield tuple(point)
        for child in value.values():
            yield from positions(child)
    elif isinstance(value, list):
        for child in value:
            yield from positions(child)


def plan(world, output):
    owner = json.loads((world / 'ROOT_MECHANICAL_OWNER.json').read_text('utf8'))
    gates = {g['resource']: g for g in owner['gates']}
    rows, ports = [], []
    for lane, centre in enumerate((-11.5, 30.5, 72.5)):
        gate_id = f'bank_1_surface_lane_{lane}'
        gate = gates[gate_id]
        assert gate['frame'] == dict(position=[centre, -466.98, 124.5], quaternion=[0, 0, 0, 1])
        spec = gate['silo_hatch']
        assert spec['opening_x'] == spec['opening_z'] == 31
        assert spec['separation_sign'] == 1 and spec['upright_guide_ports']
        left, right = int(centre - 15.5), int(centre + 15.5) - 1
        lo, hi = (left, -467, 141), (right, -467, 142)
        cells = read_box(world, DIM, lo, hi)
        assert not list(iter_block_entities(world, DIM, lo, hi)), 'Device at fixed joint'
        protected = set(positions(gate['supports']))
        reference = gate['collision_steps']
        protected.update(positions(read_table(world, reference) if isinstance(reference, dict) else reference))
        for x in range(left, right + 1):
            point = (x, -467, 141)
            assert point not in protected, ('Owned gate cell', point)
            assert cells.get(point) == 'minecraft:air', ('Changed joint', point, cells.get(point))
            assert cells.get((x, -467, 142)) == 'projectseele:nerv_shaft_panel', ('Changed apron', x)
            rows.append(dict(pos=list(point), before=cells[point], after=TARGET,
                             before_nbt=None, after_nbt=None,
                             reason=f'{gate_id}/fixed_south_apron_joint'))
        ports.append(dict(gate=gate_id, variant=gate['variant'],
                          port=f"unit{gate['variant']}/exit1/port",
                          cell_bounds=[list(lo), [right, -467, 141]],
                          fixed_join_world_z=[141.65, 142],
                          opening_width_m=31, retained_inner_seam_world_z=[141, 141.05]))
    assert len(rows) == 93 and len({tuple(r['pos']) for r in rows}) == 93
    output.mkdir(parents=True, exist_ok=True)
    inverse = [dict(r, before=r['after'], after=r['before'], reason='restore/' + r['reason']) for r in rows]
    for name, values in [('EXACT_DELTA.json.gz', rows), ('INVERSE_DELTA.json.gz', inverse)]:
        (output / name).write_bytes(gzip.compress(json.dumps(values, separators=(',', ':')).encode(), mtime=0))
    report = dict(world=str(world.resolve()), dimension=DIM, installed=False, changed_cells=93,
                  source_ownership='prepare_complete_ascent_civil.new_geofront_apron',
                  apron_bounds=[[-31, -469, 100], [91, -467, 148]], ports=ports,
                  block_model_and_voxel_bounds_16=BOUNDS,
                  thickness_m=.25, preserved='gate proxies, supports, frame, moving panels, trees, entities, progress')
    (output / 'PLAN.json').write_text(json.dumps(report, indent=2), 'utf8')
    generation_candidates(world, output, rows)
    print(json.dumps(dict(changed_cells=93, ports=[p['gate'] for p in ports], installed=False)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('world', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    plan(args.world, args.output)
