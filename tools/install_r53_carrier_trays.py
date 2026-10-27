"""Apply the explicit three-channel carrier construction with exact cell preconditions.

The shared region writer preserves unrelated chunks/NBT; its historical CLI
and fingerprint-report paths are not called. No digest records are generated.
Only the parent integration process runs this with the actual client stopped.
"""
import argparse
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
import shutil

from query_blocks import dimension_dir, iter_selected_sections, iter_block_entities
from apply_s20_approved_semantic_repairs import Change, rewrite_region, atomic_replace


@contextmanager
def stopped_world(world):
    with (world / 'session.lock').open('r+b') as handle:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.lockf(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == 'nt':
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.lockf(handle, fcntl.LOCK_UN)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    with stopped_world(args.world):
        install(args)


def install(args):
    read = lambda name: json.loads((args.candidate / name).read_text('utf8'))
    manifest = read('installation_manifest.json')
    assert args.world.resolve() == Path(manifest['world']).resolve(), 'Use the explicitly identified actual save'
    for name in manifest.get('metadata_preconditions', []):
        relative = Path(name)
        assert not relative.is_absolute() and '..' not in relative.parts and ':' not in name
        assert (args.world / relative).read_bytes() == (args.candidate / 'inverse' / relative).read_bytes(), 'Accepted equipment source changed: ' + name
    rows = read('forwardPatch.json'); inverse = read('inversePatch.json')
    changes = {tuple(r['pos']): r for r in rows}; undo = {tuple(r['pos']): r for r in inverse}
    assert len(changes) == len(rows) == len(undo) == manifest['static_cells'] > 0
    assert set(changes) == set(undo) == {tuple(p) for p in read('positiveEditMask.json')}
    requested = {}; sections = defaultdict(list)
    for at, row in changes.items():
        back = undo[at]
        assert row['before'] == back['after'] and row['after'] == back['before']
        assert all(r.get(k) is None for r in (row, back) for k in ('before_nbt', 'after_nbt')), 'This equipment packet must not replace a block entity'
        x, y, z = at;requested.setdefault((x >> 4, z >> 4), set()).add(y >> 4)
        sections[x >> 4, z >> 4, y >> 4].append(at)

    def actual_states():
        result = {}
        for cx, cz, sy, palette, indices in iter_selected_sections(args.world, 'projectseele:geofront', requested):
            for x, y, z in sections[cx, cz, sy]:
                result[x, y, z] = palette[int(indices[((y & 15) * 16 + (z & 15)) * 16 + (x & 15)])]
        assert set(result) == set(changes), 'Every proposed cell must be in a real fully generated section'
        return result

    actual = actual_states()
    conflicts = [(at, row['before'], actual[at]) for at, row in changes.items() if actual[at] != row['before']]
    assert not conflicts, ('Actual save changed; nothing written', conflicts[:12], len(conflicts))
    lo = tuple(min(p[i] for p in changes) for i in range(3));hi = tuple(max(p[i] for p in changes) for i in range(3))
    tags = dict(iter_block_entities(args.world, 'projectseele:geofront', lo, hi, selected_chunks=set(requested)))
    assert not set(tags).intersection(changes), 'Preserve every original complete block entity'
    if not args.apply:
        print(json.dumps(dict(cells=len(rows),chunks=len(requested),exact_preconditions=True,world_written=False)))
        return

    assert not args.backup.exists(), 'Choose a fresh recoverable backup directory'
    grouped = defaultdict(lambda: defaultdict(list));region_dir = dimension_dir(args.world, 'projectseele:geofront') / 'region'
    for at, row in changes.items():
        x, y, z = at
        grouped[region_dir / f'r.{x >> 9}.{z >> 9}.mca'][x >> 4, z >> 4].append(
            Change('r53-original-three-channel-trays', x, y, z, row['before'], row['after'],
                   'explicit-equipment-refit', row.get('purpose', 'original front lower-leaf clearance')))
    originals = {path: path.read_bytes() for path in grouped}
    rewritten = {path: rewrite_region(path, by_chunk) for path, by_chunk in grouped.items()}
    args.backup.mkdir(parents=True, exist_ok=False)
    for path in originals:shutil.copy2(path, args.backup / path.name)
    for name in ('ROOT_MECHANICAL_OWNER.json', 'ROOT_ASSEMBLY_BUNDLE.json'):
        shutil.copy2(args.world / name, args.backup / name)
    for name in manifest.get('world_tables', []):
        relative = Path(name)
        assert not relative.is_absolute() and '..' not in relative.parts and ':' not in name
        target = args.backup / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(args.world / relative, target)
    for name in ('forwardPatch.json', 'inversePatch.json', 'positiveEditMask.json', 'installation_manifest.json'):
        shutil.copy2(args.candidate / name, args.backup / name)
    replaced = []
    try:
        for path, content in rewritten.items():atomic_replace(path, content);replaced.append(path)
        after = actual_states()
        assert all(after[at] == row['after'] for at, row in changes.items()), 'Actual delivered cells failed readback'
        final_tags = dict(iter_block_entities(args.world, 'projectseele:geofront', lo, hi, selected_chunks=set(requested)))
        assert tags == final_tags, 'Original complete block-entity NBT changed'
    except Exception:
        for path in replaced:atomic_replace(path, originals[path])
        raise
    result = dict(world=str(args.world.resolve()),changed_cells=len(rows),changed_regions=len(replaced),
                  actual_cells_read_back=True,block_entity_nbt_preserved=len(tags),
                  progress_files_written=[],metadata_written=False,installed_at=datetime.now().isoformat())
    (args.backup / 'installation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(result))


if __name__ == '__main__':main()
