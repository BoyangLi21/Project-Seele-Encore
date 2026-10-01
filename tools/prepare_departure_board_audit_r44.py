"""Freeze the actual migrated fifty live-board configurations for native audit.

Reads only the inventory's exact current chunks, not the retired R19 positions.
Does not modify world, board rows, schedules, routes, source assets or players.
"""
from pathlib import Path
import argparse, hashlib, json
from query_blocks import iter_block_entities
from measure_world_r40 import MeasuredWorld

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/rebuild_r44/facility_transit_r44'
WORLD = ROOT / 'run/saves/SEELE_FIELD_R44_REVIEW'


def main(out, relocations=()):
    out = Path(out)
    if out.exists():
        raise ValueError('Choose a fresh preparation epoch')
    inventory = BASE / 'station_signs/full_sign_audit.json'
    items = [dict(q) for q in json.loads(inventory.read_text('utf8'))['boards'] if q['kind'] == 'live_departure']
    for movement in relocations:
        old, new = [tuple(map(int, value.split(','))) for value in movement.split(':')]
        matches = [q for q in items if tuple(q['position']) == old]
        if len(matches) != 1:
            raise ValueError('Relocation requires one exact declared source owner')
        matches[0]['position'] = list(new)
    if len(items) != 50:
        raise ValueError('Current owner inventory does not contain exactly fifty live boards')
    positions = [tuple(q['position']) for q in items]
    chunks = {(x // 16, z // 16) for x, y, z in positions}
    lo = tuple(min(q[i] for q in positions) - 1 for i in range(3))
    hi = tuple(max(q[i] for q in positions) + 1 for i in range(3))
    tags = dict(iter_block_entities(WORLD, 'projectseele:geofront', lo, hi, selected_chunks=chunks))
    w = MeasuredWorld(WORLD)
    for q in positions:
        w.around(q, 0)
    w.load()
    boards = []
    for q in positions:
        tag = tags.get(q)
        present = tag is not None and str(tag.get('id')) == 'projectseele:station_departure_board'
        config = None
        if present:
            config = {k: str(tag.get(k, '')) for k in ('Station', 'Route')}
            config.update({k: int(tag.get(k, -1 if k == 'NativePlatformId' else 0)) for k in ('PlatformCentre', 'NativePlatformId')})
            config.update({k: bool(tag.get(k, False)) for k in ('Wayfinding', 'AirService')})
        boards.append({'id': 'live_' + '_'.join(map(str, q)), 'position': q, 'state': w.block(q),
                       'chunk_full': w.status.get((q[0] // 16, q[2] // 16)) == 'full',
                       'actual_be_present': present, 'configuration': config,
                       'configuration_sha256': hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()})
    out.mkdir(parents=True)
    report = {'world': str(WORLD), 'dimension': 'projectseele:geofront', 'boards': boards,
              'expected_count': 50, 'actual_be_present_count': sum(q['actual_be_present'] for q in boards),
              'nearest_lookup_without_preferred_id': sum(q['configuration'] is not None and q['configuration']['NativePlatformId'] == -1 for q in boards),
              'inventory_sha256': hashlib.sha256(inventory.read_bytes()).hexdigest(),
              'explicit_root_owned_relocations': list(relocations),
              'production_source_sha256': hashlib.sha256((ROOT / 'src/main/java/com/projectseele/world/NativeStationDepartures.java').read_bytes()).hexdigest(),
              'native_passed': False, 'world_write_performed': False,
              'runtime_properties': {'projectseele.r44DepartureBoardAudit': 'true',
                                     'projectseele.r44DepartureBoardManifest': str((out / 'manifest.json').resolve()),
                                     'projectseele.r44DepartureBoardOutput': str((out / 'native_result.json').resolve())},
              'limits': 'Actual loaded BE, normal scheduled refresh, raw MTR predictions/clock and complete route topology are checked by the opt-in runtime driver. Missing, ambiguous or empty services remain explicit.'}
    (out / 'manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf8')
    print(json.dumps({k: report[k] for k in ('expected_count', 'actual_be_present_count', 'nearest_lookup_without_preferred_id', 'production_source_sha256')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--relocate', action='append', default=[], help='Explicit authorised oldXYZ:newXYZ; new BE is still independently reread')
    args = parser.parse_args()
    main(args.out,args.relocate)
