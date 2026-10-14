"""Prepare an HQ-only conservation ledger and uninstalled candidates from the current world.

No --apply mode, no old-world default, no simulator, no Anvil writes. The four
station/platform byte candidates are intentionally NOT an installable railway
transaction until Root supplies and verifies the new approach graph/progress.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
from collections import Counter

import nbtlib
import numpy as np

from prepare_mtr_member_patch_r52 import Parser, patch, map_child, point, edge
from facility_frame_nbt_r52 import block_entity_in_frame, actor_in_frame, unpack_position
from r52_spatial_plan import Frame

HQ = 0x7F36F8DC34907D9B
PLATFORMS = {0x910C703E8C195E14, 0x5F8F651005220016, 0x7503CEFA3D9A08FC}
PREFIX = 'mtr/projectseele/geofront/'
FRAME = Frame(0, 0, -93, 0)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def ident(value):
    return int(value) & ((1 << 64) - 1)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def snapshot(world):
    rows = {}
    for path in sorted((world / 'mtr').rglob('*')):
        if not path.is_file():
            continue
        if path.is_symlink() or path.is_junction():
            raise ValueError('MTR linked member rejected: ' + str(path))
        before = path.stat()
        raw = path.read_bytes()
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError('MTR changed during read: ' + str(path))
        parser = Parser(raw)
        node = parser.node()
        if not isinstance(node.value, dict):
            raise ValueError('Expected native map: ' + str(path))
        relative = path.relative_to(world).as_posix()
        rows[relative] = dict(raw=raw, node=node, tail=raw[parser.offset:],
                              kind=relative.split('/')[3] if relative.startswith(PREFIX) else 'other_dimension')
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--survey', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    world, survey, out = args.world.resolve(), args.survey.resolve(), args.out.resolve()
    if out == world or world in out.parents or out.exists():
        raise ValueError('Fresh output outside WORLD required')
    if not (world / 'level.dat').is_file():
        raise ValueError('Explicit existing world required')
    frozen = json.loads(args.baseline.read_text(encoding='utf-8'))
    if Path(frozen['world']).resolve() != world:
        raise ValueError('Baseline world differs from requested world')
    base_files = {r['path'].replace('\\', '/'): r['sha256'] for r in frozen['files']}
    metadata_names = ('r44_public_station_gates.json', 'regional_plan.json')
    metadata_bytes = {name: (world / name).read_bytes() for name in metadata_names}
    for name, raw in metadata_bytes.items():
        if sha(raw) != base_files.get(name):
            raise ValueError('Initial HQ preparation requires original metadata; this file already changed or moved: ' + name)
    records = snapshot(world)
    expected_mtr = {n: h for n, h in base_files.items() if n.startswith('mtr/')}
    if set(records) != set(expected_mtr) or any(sha(r['raw']) != expected_mtr[n] for n, r in records.items()):
        raise ValueError('Current native MTR differs from this new-world frozen baseline; re-audit progress first')
    by_kind = {kind: {n: r for n, r in records.items() if r['kind'] == kind}
               for kind in ('stations', 'platforms', 'routes', 'rails', 'depots', 'sidings', 'settings')}
    counts = {k: len(v) for k, v in by_kind.items()}
    required = {'stations': 20, 'platforms': 38, 'routes': 6, 'rails': 171, 'depots': 6, 'sidings': 6}
    if any(counts[k] != v for k, v in required.items()):
        raise ValueError(('Unexpected native inventory', counts))
    hq = [(n, r) for n, r in by_kind['stations'].items() if ident(r['node'].value['id']) == HQ]
    platforms = [(n, r) for n, r in by_kind['platforms'].items() if ident(r['node'].value['id']) in PLATFORMS]
    if len(hq) != 1 or len(platforms) != 3:
        raise ValueError('Original HQ and three original platform identities required')
    platform_points = {point(r['node'].value[k]) for _, r in platforms for k in ('position1', 'position2')}
    boundary = {n: r for n, r in by_kind['rails'].items()
                if any(point(r['node'].value[k]) in platform_points for k in ('position1', 'position2'))}
    if len(boundary) != 10:
        raise ValueError(('Changed original immediate HQ rail boundary', len(boundary)))
    boundary_edges = {edge(r['node'].value['position1'], r['node'].value['position2']) for r in boundary.values()}
    vehicles = []
    for n, r in by_kind['sidings'].items():
        for vehicle in r['node'].value.get('vehicles', []):
            vehicles.append(dict(siding_member=n, vehicle_id=f"{ident(vehicle['id']):016X}", original_saved_fields=vehicle))
    if len(vehicles) != 40 or len({v['vehicle_id'] for v in vehicles}) != 40:
        raise ValueError('Original forty unique vehicles required')
    affected_paths = []
    for kind, fields in [('depots', ('path',)), ('sidings', ('pathSidingToMainRoute', 'pathMainRouteToSiding'))]:
        for n, r in by_kind[kind].items():
            for field in fields:
                hits = [i for i, p in enumerate(r['node'].value.get(field, []))
                        if edge(p['startPosition'], p['endPosition']) in boundary_edges]
                if hits:
                    affected_paths.append(dict(member=n, field=field, old_indices=hits))
    out.mkdir(parents=True)
    operations = []
    for n, r in hq + platforms:
        old = r['node'].value
        new = copy.deepcopy(old)
        for k in ('position1', 'position2'):
            new[k]['y'] -= 93
        trace = []
        after = patch(r['node'], new, trace) + r['tail']
        reread = Parser(after)
        new_node = reread.node()
        assert new_node.value == new and after[reread.offset:] == r['tail']
        for k in old:
            if k not in ('position1', 'position2'):
                assert map_child(r['node'], k).raw == map_child(new_node, k).raw
        for stage, raw in [('before', r['raw']), ('position_only_after_NOT_INSTALLABLE', after)]:
            p = out / stage / n
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(raw)
        operations.append(dict(member=n, before_sha256=sha(r['raw']), after_sha256=sha(after),
                               precise_fields=trace, identity_unchanged=True, opaque_tail_bytes=len(r['tail'])))
    platform_map = {}
    for _, r in platforms:
        a, b = (point(r['node'].value[k]) for k in ('position1', 'position2'))
        middle = tuple((a[i] + b[i]) // 2 for i in range(3))
        platform_map[middle] = FRAME.block(middle)
    source = np.load(survey / 'hq_station_complete.npz')
    origin = tuple(map(int, source['origin']))
    shape = source['states'].shape
    lo = list(origin)
    hi = [origin[0] + shape[2] - 1, origin[1] + shape[0] - 1, origin[2] + shape[1] - 1]
    source_devices = json.loads((survey / 'hq_station_complete_devices.json').read_text(encoding='utf-8'))
    device_plan = []
    for r in source_devices:
        old = nbtlib.parse_nbt(r['nbt'])
        new = block_entity_in_frame(old, FRAME, reference_positions=platform_map)
        device_plan.append(dict(id=r['id'], original=r['pos'], destination=list(FRAME.block(r['pos'])),
                                before_snbt=old.snbt(), after_snbt=new.snbt(),
                                requires_final_component_owner_mask=True))
    write(out / 'STATION_DEVICES_TRANSLATION_CANDIDATE.json', device_plan)
    actors = json.loads((survey / 'ORIGINAL_ALL_ACTORS.json').read_text(encoding='utf-8'))['actors']
    actor_plan = []
    for r in actors:
        old = nbtlib.parse_nbt(r['snbt'])
        if str(old.get('StaffId', '')) != 'guard/hq_station':
            continue
        new = actor_in_frame(old, FRAME)
        actor_plan.append(dict(uuid=r['uuid'], original=r['pos'], destination=list(map(float, new['Pos'])),
                               before_snbt=old.snbt(), after_snbt=new.snbt(), original_entity_count=len(actors)))
    if len(actor_plan) != 1:
        raise ValueError('Expected exact original HQ guard identity')
    write(out / 'HQ_GUARD_CANDIDATE.json', actor_plan)
    gates_path = world / 'r44_public_station_gates.json'
    gates = json.loads(metadata_bytes['r44_public_station_gates.json'].decode('utf-8'))
    gate_plan = []
    for row in gates['gates']:
        if ident(row['station_id']) != HQ:
            continue
        new = copy.deepcopy(row)
        new['position'] = list(FRAME.block(row['position']))
        new['station_bounds'] = [list(FRAME.block(p)) for p in row['station_bounds']]
        gate_plan.append(dict(before=row, after=new))
    if len(gate_plan) != 6:
        raise ValueError('Expected all six original HQ public gates')
    write(out / 'HQ_PUBLIC_GATES_CANDIDATE.json', dict(source_sha256=sha(gates_path.read_bytes()), rows=gate_plan,
                                                     all_other_gate_entries_must_be_preserved=True))
    regional_path = world / 'regional_plan.json'
    regional = json.loads(metadata_bytes['regional_plan.json'].decode('utf-8'))
    station_row = next(r for r in regional['stations'] if r['id'] == 'hq')
    zone_row = next(r for r in regional['zones'] if r['id'] == 'nerv_headquarters_station')
    new_station, new_zone = copy.deepcopy(station_row), copy.deepcopy(zone_row)
    new_station['pos'] = list(FRAME.block(station_row['pos']))
    new_zone['floor'] -= 93
    write(out / 'HQ_REGIONAL_METADATA_CANDIDATE.json', dict(source_sha256=sha(regional_path.read_bytes()),
          stations_hq=dict(before=station_row, after=new_station),
          zones_nerv_headquarters_station=dict(before=zone_row, after=new_zone),
          note='XZ coarse corridor intent is not actual rail geometry; native curves/derived navigation require rebuild'))
    # Check every input again after the read-only preparation; never preserve a mixed live epoch.
    if any(sha((world / n).read_bytes()) != sha(r['raw']) for n, r in records.items()):
        raise ValueError('MTR changed while candidate was prepared')
    if any((world / name).read_bytes() != raw for name, raw in metadata_bytes.items()):
        raise ValueError('HQ metadata changed during read-only candidate preparation')
    boundary_rows = [dict(member=n, before_sha256=sha(r['raw']), data=r['node'].value) for n, r in boundary.items()]
    write(out / 'CURRENT_TEN_RAIL_BOUNDARY.json', boundary_rows)
    mutable_positions = {n for n, _ in hq + platforms}
    report = dict(schema='projectseele.complete-hq-conservation-candidate.v1', world=str(world), world_written=False,
                  ready_to_install=False, station_shift=[0, -93, 0], original_counts=counts, vehicles=vehicles,
                  world_source_baseline_sha256=sha(args.baseline.read_bytes()),
                  all_current_mtr_match_frozen_new_world=True, source_mtr_hashes={n: sha(r['raw']) for n, r in records.items()},
                  original_non_HQ_stations=19, original_non_HQ_platforms=35, original_total_platforms=38,
                  source_station_survey=dict(lo=lo, hi=hi, destination_lo=list(FRAME.block(lo)),
                     destination_hi=list(FRAME.block(hi)), device_count=len(device_plan),
                     device_counts=dict(Counter(r['id'] for r in device_plan)), survey_is_not_ownership_mask=True),
                  position_only_operations=operations, affected_saved_paths=affected_paths,
                  protected_other_dimension_and_station_platform_route_bytes={n:sha(r['raw']) for n,r in records.items()
                    if r['kind'] in ('stations','platforms','routes','other_dimension') and n not in mutable_positions},
                  unchanged_external_endpoints=sorted({point(r['node'].value[k]) for r in boundary.values()
                    for k in ('position1','position2') if point(r['node'].value[k]) not in platform_points}),
                  platform_reference_mapping=[dict(before=list(a),after=list(b))for a,b in platform_map.items()],
                  required_before_any_install=['Root complete station ownership mask including shared pyramid entrance cells',
                    'Root final necessary approach geometry preserving every external endpoint and other station/rail component',
                    'Current native RailMath lengths and whole-train/tunnel/door collision against this new map',
                    'Same-frozen-epoch native assembled paths for original40 and per-vehicle local-progress/next-stop mapping',
                    'Atomic geometry + typed devices + original NPC + MTR rail/path/progress + metadata transaction with rollback',
                    'Only then fresh derived transit curves, graph edges/lifts, destinations and wayfinding hashes',
                    'Current installed-copy station access, both-direction ride, signals, reload and user visual review'])
    write(out / 'HQ_MIGRATION_CANDIDATE.json', report)
    print(json.dumps(dict(output=str(out), world_written=False, ready_to_install=False,
                          counts=counts, original_vehicles=len(vehicles), immediate_boundary_rails=len(boundary),
                          station_devices=len(device_plan), guard_uuid=actor_plan[0]['uuid'], hq_gates=len(gate_plan)), ensure_ascii=True))


if __name__ == '__main__':
    main()
