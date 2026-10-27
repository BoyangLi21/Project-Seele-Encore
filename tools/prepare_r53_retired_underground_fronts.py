"""Retire the exact R48 horizontal-door proxies superseded by claimed R52 routes.

Read the installed receipt and actual blocks; produce a reversible candidate only.
The original apron, shaft walls, actors, current gates and progress are untouched.
"""
import argparse
import gzip
import json
import shutil
from collections import Counter
from pathlib import Path

from query_blocks import read_box, iter_block_entities


def read(path):
    return json.loads(path.read_text('utf8'))


def prepare(world, output):
    receipt = read(world / 'r48_underground_sortie.json')
    assert receipt['schema'] == 48 and receipt['installed']
    assert receipt['dimension'] == 'projectseele:geofront'
    assert receipt['door_alignment_revision'] == 52
    owner = read(world / 'ROOT_MECHANICAL_OWNER.json')
    directory = read(world / 'ROOT_RUNTIME_DIRECTORY.json')
    assert all(any(leg['id'] == f'unit{unit}/exit2/upright_continuous'
                   for leg in directory['legs']) for unit in range(3))
    protected = set()
    for gate in owner['gates']:
        rows = gate['collision_steps']
        if isinstance(rows, dict):
            rows = json.loads(gzip.decompress((world / rows['cells_file']).read_bytes()))
        protected.update(tuple(cell['position']) for step in rows for cell in step)
        protected.update(tuple(cell['position']) for cell in gate.get('supports', []))
    forward = []
    scope = []
    seen = set()
    clear = 0
    assert len(receipt['plans']) == 3
    for plan in receipt['plans']:
        lane = plan['variant']
        assert lane in (0, 1, 2) and lane not in seen
        seen.add(lane)
        cx = (-12, 30, 72)[lane]
        lo, hi = (cx - 15, -410, -19), (cx + 15, -346, -17)
        assert plan['wall_aperture'] == [list(lo), list(hi)]
        assert plan['collision_planes'] == [-19, -18, -17]
        cells = read_box(world, 'projectseele:geofront', lo, hi)
        assert len(cells) == 31 * 65 * 3
        assert not list(iter_block_entities(world, 'projectseele:geofront', lo, hi))
        assert not protected.intersection(cells), 'Current gate or support owns old frontage'
        assert set(cells.values()) <= {'minecraft:barrier', 'minecraft:air'}, Counter(cells.values())
        for position, state in cells.items():
            if state == 'minecraft:air':
                clear += 1
                continue
            forward.append(dict(pos=list(position), before=state, after='minecraft:air',
                                before_nbt=None, after_nbt=None,
                                purpose='retired_R48_horizontal_exit_door_proxy'))
        scope.append(dict(receipt_lane=lane, bounds=[list(lo), list(hi)],
                          actual_states=dict(Counter(cells.values()))))
    assert len(forward) + clear == 18135
    output.mkdir(parents=True, exist_ok=True)
    for name, value in [('forwardPatch.json', forward),
                        ('inversePatch.json', [dict(row, before=row['after'], after=row['before']) for row in forward]),
                        ('positiveEditMask.json', [row['pos'] for row in forward])]:
        (output / name).write_text(json.dumps(value, separators=(',', ':')) + '\n', 'utf8')
    metadata = ['ROOT_MECHANICAL_OWNER.json', 'ROOT_ASSEMBLY_BUNDLE.json',
                'ROOT_RUNTIME_DIRECTORY.json', 'r48_underground_sortie.json']
    (output / 'inverse').mkdir(exist_ok=True)
    for name in metadata:
        shutil.copy2(world / name, output / 'inverse' / name)
    manifest = dict(world=str(world), static_cells=len(forward),
                    metadata_preconditions=metadata, world_tables=[])
    construction = dict(world=str(world), installed=False, dimension='projectseele:geofront',
                        scope=scope, changed_static_cells=len(forward), already_clear=clear,
                        source='Installed r48_underground_sortie.json revision 52; prepare_underground_r48.py wall_aperture',
                        retirement='UndergroundSortieR48.enabled and maintainDoor stop when NervRouteRuntimeR52 claims the original fleet; current ROOT replaces the horizontal route with explicit upright source paths.',
                        cause='The continuous civil generator preserved minecraft:barrier without filtering these retired horizontal-door proxies.',
                        preconditions='Exact original receipt, all nine full planes measured, only barrier/air, no block entities and no current gate phase or gate support overlap.',
                        unchanged=['original apron and wall steel', 'all active ROOT gates and supports',
                                   'metadata and navigation', 'entities, players, missions and traffic'],
                        acceptance='Apply cold under session.lock with exact old-state checks; resume original tasks and their full production collision proof.')
    (output / 'installation_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', 'utf8')
    (output / 'construction.json').write_text(json.dumps(construction, indent=2) + '\n', 'utf8')
    print(json.dumps(dict(prepared_cells=len(forward), already_clear=clear, scope=scope)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.world, args.output)
