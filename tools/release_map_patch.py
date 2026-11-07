"""Author and cold-publish a small exact block patch from a fresh capture.

Patch input lists every cell with its purpose. Each cell's current state must
equal the capture, original devices are refused, and no network, native or
identity state changes. Callers run their own geometric check and name its
report under error_reports; this tool proves the delta, not the design.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import nbtlib
import numpy as np

from author_hakone_lakefront import Editor
from install_r53_carrier_trays import stopped_world
from map_pipeline.corridors import publish_plan
from map_pipeline.delivery_check import capture_identity, read, verify_delivery, write
from map_pipeline.verify_corridors import write_replay_expected
from native_transit_additions import assert_preserved, inventory
from prepare_hakone_network_recipes import parallel_recipes

SCHEMA = 'map-cell-patch-v1'
CONTROL = 'map-patch-release.json'


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def author(a):
    spec = read(a.config)
    require(spec.get('schema') == SCHEMA, 'Unknown patch schema')
    source = Path(spec['source'])
    cap = read(source / 'capture.json')
    with np.load(source / 'measured.npz') as data:
        x0, z0, _, _ = map(int, data['bounds'])
        full = data['full'].copy()
    require(all(full[r['pos'][2] - z0, r['pos'][0] - x0] for r in spec['edits']), 'Every patched column needs a FULL capture')
    a.out.mkdir(exist_ok=False)
    for name in ('source', 'delta'):
        (a.out / name).mkdir()
    for path in (source / 'source').glob('*.npz'):
        os.link(path, a.out / 'source' / path.name)
    for name in ('capture.json', 'captured-devices.dat', 'measured.npz'):
        shutil.copy2(source / name, a.out / name)
    devices = {tuple(int(t[k]) for k in 'xyz') for t in nbtlib.load(source / 'captured-devices.dat')['Devices']}
    editor = Editor(a.out)
    rows = []
    for row in spec['edits']:
        pos = tuple(row['pos'])
        require(pos not in devices, ('Patch touches an original device', pos))
        before = editor.state(*pos, True)
        require(before == row['before'], ('Capture differs from declared before state', pos, before))
        require(before != row['after'], ('Patch cell changes nothing', pos))
        editor.put(*pos, row['after'])
        rows.append(dict(pos=list(pos), before=before, after=row['after'], purpose=row['purpose']))
    require(len({tuple(r['pos']) for r in rows}) == len(rows), 'Repeated patch cell')
    regions = editor.save()
    for region in regions:
        path = a.out / region['path']
        with np.load(path) as data:
            payload = {k: data[k] for k in data.files}
        np.savez_compressed(path, **payload, y_origin=-128, height=448)
        region.update(y_origin=-128, height=448)
    nbtlib.File({'Changes': nbtlib.List[nbtlib.Compound]([])}).save(a.out / 'block-entities.dat', gzipped=True)
    write(a.out / 'exact-edits.json', rows)
    write(a.out / 'forward-patch.json', dict(edits=rows, requires_exact_before=True))
    write(a.out / 'inverse-patch.json', dict(edits=[dict(pos=r['pos'], before=r['after'], after=r['before']) for r in rows],
                                             requires_exact_before=True))
    write(a.out / 'manifest.json', dict(schema=SCHEMA, world=cap['world'], source=str(source), cells=len(rows), regions=regions,
                                        vertical_extent=[-128, 319], device_changes=0, native_changes=[], native_additions=[],
                                        actor_changes=[], preserve_native_members=True, world_written=False))
    if spec.get('native_additions'):
        # Whole new native members only; the installer refuses to overwrite one.
        root = Path(spec['native_additions'])
        members = sorted(path.relative_to(root).as_posix() for path in root.rglob('*') if path.is_file())
        for name in members:
            target = a.out / 'after' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / name, target)
        manifest = read(a.out / 'manifest.json')
        manifest['native_additions'] = members
        write(a.out / 'manifest.json', manifest)
    write(a.out / 'functional-check.json', dict(errors=[], purposes=dict(Counter(r['purpose'] for r in rows))))
    print('Authored', len(rows), 'patch cells', dict(Counter(r['purpose'] for r in rows)))


def require_reports(a, spec):
    for name in spec['error_reports']:
        require(read(Path(name)).get('errors') == [], 'Failed or missing report: ' + name)
    require(spec.get('views_reviewed_by_root') is True, 'Exact voxel view review pending')


def prepare(a):
    spec = read(a.config)
    state = read(a.continuation)
    require(state['latest_installed_batch'] == a.batch - 1, 'Stale release batch')
    require_reports(a, spec)
    native = Path(spec['native_snapshot'])
    with stopped_world(a.world):
        assert_preserved(a.world, inventory(native))
        shutil.copytree(native, a.candidate / 'preserved-native')
        parallel_recipes(argparse.Namespace(candidate=a.candidate, world=a.world, regions=None, workers=2))
        capture_identity(a.world, a.candidate, False)
    write_replay_expected(a.candidate)
    write(a.candidate / CONTROL, dict(schema=SCHEMA, prepared_time_ns=time.time_ns(), batch=a.batch))
    print('Prepared map patch', read(a.candidate / 'manifest.json')['cells'], 'cells')


def install(a):
    spec = read(a.config)
    require_reports(a, spec)
    prepared = read(a.candidate / CONTROL)
    require(a.production_log.stat().st_mtime_ns >= prepared['prepared_time_ns'], 'Replay predates preparation')
    subprocess.run([sys.executable, str(Path(__file__).with_name('install_hakone_array_patch.py')), '--world', str(a.world),
                    '--candidate', str(a.candidate), '--backup', str(a.installation.parent), '--workers', '2'], check=True)


def record(a):
    spec = read(a.config)
    before = a.continuation.read_bytes()
    state = read(a.continuation)
    require(state['latest_installed_batch'] == a.batch - 1, 'Stale release batch')
    with stopped_world(a.world):
        check = verify_delivery(a.world, a.candidate, a.installation, a.production_log)
    write(a.candidate / 'delivery-check.json', check)
    write(a.delivery, {**check, 'batch': a.batch, 'label': spec['label'], 'candidate': str(a.candidate), 'installation': str(a.installation),
                       'world_written': True, 'client_jar_written': False, 'minimap_refreshed': False, 'distant_cache_refreshed': False})
    state.update(latest_installed_batch=a.batch, current_work=spec['continuation_work'])
    state.setdefault('pending_map_cache_releases', []).append(str(a.installation.parent))
    if spec.get('road_candidate'):
        # A regraded road must leave later street work reading the installed heights.
        authority, following = Path(state['planning_authority']), Path(spec['next_authority'])
        plan = publish_plan(Path(spec['road_candidate']), authority)
        shutil.copytree(authority, following)
        shutil.copy2(plan / 'network.npz', following / 'network.npz')
        state['planning_authority'] = str(following)
    work_path = Path(state['station_construction_worklist'])
    work = read(work_path)
    work.update(latest_installed_batch=a.batch, planning_authority=state['planning_authority'])
    write(work_path, work)
    require(a.continuation.read_bytes() == before, 'Continuation changed during verification')
    temporary = a.continuation.with_name('.patch-continuation.json')
    write(temporary, state)
    os.replace(temporary, a.continuation)
    print('Recorded map patch batch', a.batch, check['changed_cells'], 'cells')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('author', 'prepare', 'install', 'record'))
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--batch', type=int)
    for key in ('candidate', 'world', 'installation', 'production-log', 'delivery', 'continuation'):
        parser.add_argument('--' + key, type=Path)
    args = parser.parse_args()
    globals()[args.mode](args)
