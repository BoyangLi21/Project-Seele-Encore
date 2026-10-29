"""Cold, reversible installation of the measured Lake Ashi terrain patch."""
from pathlib import Path
from collections import defaultdict
from itertools import zip_longest
import argparse, gzip, json, shutil, sys, time
sys.path.append(str(Path(__file__).resolve().parents[1] / '.Codex/map-deps'))
from apply_s20_approved_semantic_repairs import Change, rewrite_region, atomic_replace
from install_r53_carrier_trays import stopped_world
from measure_world_r40 import MeasuredWorld
from query_blocks import dimension_dir
from plan_ashi_landscape_r54 import NATURAL


def main():
    p = argparse.ArgumentParser(__doc__)
    for name in ('world', 'candidate', 'backup'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    m = json.loads((a.candidate / 'manifest.json').read_text('utf8'))
    assert a.world.resolve() == Path(m['world']).resolve() and m['revision'] == 55
    assert not a.backup.exists(), 'Installation backup already exists; do not replay'
    groups = defaultdict(lambda: defaultdict(list))
    count = 0
    with gzip.open(a.candidate / 'forward.jsonl.gz', 'rt', encoding='utf8') as fw, \
         gzip.open(a.candidate / 'inverse.jsonl.gz', 'rt', encoding='utf8') as inverse:
        for left, right in zip_longest(fw, inverse):
            assert left is not None and right is not None
            r, back = json.loads(left), json.loads(right)
            x, y, z = r['pos']
            assert r['pos'] == back['pos'] and r['before'] == back['after'] and r['after'] == back['before']
            assert all(r.get(k) is None and back.get(k) is None for k in ('before_nbt', 'after_nbt'))
            assert y >= 48 and all(m['bounds'][0][i] <= v <= m['bounds'][1][i] for i, v in enumerate((x,y,z)))
            assert r['before'].split('[')[0] in NATURAL, 'Never replace an existing device or structure'
            groups[x >> 9, z >> 9][x >> 4, z >> 4].append(Change(
                'r55-ashi', x, y, z, sys.intern(r['before']), sys.intern(r['after']), 'measured-surface', 'Lake and approach'))
            count += 1
    assert count == m['cells']
    region = dimension_dir(a.world, m['dimension']) / 'region'
    start = time.monotonic()
    with stopped_world(a.world):
        a.backup.mkdir(parents=True)
        prepared = {}
        for (rx, rz), chunks in groups.items():
            path = region / f'r.{rx}.{rz}.mca'
            shutil.copy2(path, a.backup / path.name)
            prepared[path] = rewrite_region(path, chunks, surface_rebuild=True)
            print(f'Prepared {len(prepared)}/{len(groups)} regions', flush=True)
        written = []
        try:
            for path, raw in prepared.items():
                atomic_replace(path, raw)
                written.append(path)
            # Read back only the changed sections through the common reader.
            for chunks in groups.values():
                measured = MeasuredWorld(a.world, m['dimension'])
                for changes in chunks.values():
                    for c in changes:
                        measured.selected[c.x >> 4, c.z >> 4].add(c.y >> 4)
                measured.load()
                for changes in chunks.values():
                    for c in changes:
                        assert measured.get(c.x,c.y,c.z) == c.after, ('Writeback mismatch', c.x,c.y,c.z)
            metadata = a.world / 'surface_geography_r55.json'
            assert not metadata.exists(), 'Existing map metadata must be explicitly merged'
            atomic_replace(metadata, (a.candidate / metadata.name).read_bytes())
        except BaseException:
            for path in written:
                atomic_replace(path, (a.backup / path.name).read_bytes())
            raise
        for name in ('forward.jsonl.gz', 'inverse.jsonl.gz', 'manifest.json'):
            shutil.copy2(a.candidate / name, a.backup / name)
        report = dict(installed=True, cells=count, regions=len(prepared), actual_world=str(a.world),
                      surface_readback=True, progress_files_written=[], runtime_checks_added=False,
                      minimum_y=48, seconds=round(time.monotonic()-start),
                      visual_acceptance='Player review', lod_refresh='Required next')
        (a.backup / 'installation.json').write_text(json.dumps(report,indent=2),'utf8')
        print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
