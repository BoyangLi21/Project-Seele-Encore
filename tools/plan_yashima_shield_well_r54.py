"""Prepare the measured original mountain shield well; never write the world.

Install the output (or its rollback/ directory) through install_r53_carrier_trays.py.
The original rack, finite cargo, outer shell, bottom slab and player state stay intact.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / '.Codex/map-deps'))
import nbtlib
from query_blocks import read_box, iter_block_entities

DIM = 'projectseele:geofront'
LO = (-1204, 121, -1455)
HI = (-1173, 174, -1424)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists(), 'Keep the original measured packet and choose a fresh output'
    old = read_box(args.world, DIM, LO, HI)
    tags = dict(iter_block_entities(args.world, DIM, LO, HI))
    desired = {(x, y, z): 'minecraft:barrier' if y == 174 else 'minecraft:air'
               for x in range(-1203, -1174) for y in range(122, 175)
               for z in range(-1454, -1425)}
    assert not set(tags).intersection(desired), 'Preserve every original block entity'
    allowed = {'minecraft:stone', 'projectseele:nerv_structural_panel', 'projectseele:nerv_floor_panel'}
    assert all(old[p] in allowed for p in desired), 'Original shield interior changed; inspect that local change'
    # Runtime rigid-city maintenance must not recreate the original solid cap/shaft.
    for cx, cz in sorted({(x >> 4, z >> 4) for x, y, z in desired}):
        path = args.world / 'dimensions/projectseele/geofront/data/city_rigid_generation_r45/chunks' / f'{cx}_{cz}.dat'
        if not path.exists():
            continue
        for entry in nbtlib.load(path)['Static']:
            n = int(entry['Pos'])
            p = (n >> 38, ((n & 4095) + 2048) % 4096 - 2048,
                 (((n >> 12) & 67108863) + 33554432) % 67108864 - 33554432)
            assert p not in desired, ('Maintained static owner must be updated before installation', p)
    rows = [dict(pos=p, before=old[p], after=s, before_nbt=None, after_nbt=None,
                 owner='r54/original_yashima_shield_well',
                 purpose='Original 29 x 29 m shield lift full 53 m descent; retain shell and base slab; dynamic support cover at Y174')
            for p, s in sorted(desired.items()) if old[p] != s]
    inverse = [dict(row, before=row['after'], after=row['before']) for row in rows]
    manifest = dict(schema='projectseele.r54.yashima-shield-well.v1', world=str(args.world.resolve()),
                    dimension=DIM, static_cells=len(rows), metadata_preconditions=[], world_tables=[],
                    bounds=[LO, HI], original_rack_uuid='ac13c75b-65ae-513a-81d2-bdf1c2803113',
                    unchanged_outer_shell=True, unchanged_bottom_y=121, maintained_static_overlap=0,
                    block_entity_count=len(tags), world_written=False)
    for folder, forward, reverse in ((args.out, rows, inverse), (args.out / 'rollback', inverse, rows)):
        folder.mkdir(parents=True)
        for name, data in (('forwardPatch.json', forward), ('inversePatch.json', reverse),
                           ('positiveEditMask.json', [r['pos'] for r in rows]),
                           ('installation_manifest.json', manifest)):
            (folder / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), 'utf8')
    print(json.dumps(dict(cells=len(rows), original_states=dict(Counter(r['before'] for r in rows)),
                          shaft_air_cells=29 * 29 * 52, support_cover_cells=29 * 29,
                          floor_y=121, world_written=False)))


if __name__ == '__main__':
    main()
