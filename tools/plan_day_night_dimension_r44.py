"""Freeze exact source and enabled-pack day/night candidates without installing them."""
from pathlib import Path
import argparse, hashlib, json, re, zipfile
import nbtlib

ROOT = Path(__file__).resolve().parents[1]
KEY = 'data/projectseele/dimension_type/geofront.json'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def main():
    p = argparse.ArgumentParser(); p.add_argument('output', type=Path)
    p.add_argument('--world', type=Path, default=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW')
    a = p.parse_args(); assert not a.output.exists(), 'Preserve earlier immutable plans'
    level = nbtlib.load(a.world/'level.dat')['Data']
    enabled = [str(t) for t in level['DataPacks']['Enabled']]
    providers = [(ROOT/'src/main/resources'/KEY, 'shipped source', None)]
    unsupported = []
    for i, name in enumerate(enabled):
        if not name.startswith('file/'): continue
        pack = a.world/'datapacks'/name.removeprefix('file/')
        if pack.is_dir() and (pack/KEY).exists(): providers.append((pack/KEY, 'enabled world override', i))
        elif pack.is_file() and zipfile.is_zipfile(pack):
            with zipfile.ZipFile(pack) as archive:
                if KEY in archive.namelist(): unsupported.append(str(pack))
    assert not unsupported, ('Review enabled zipped dimension provider', unsupported)
    a.output.mkdir(parents=True); rows = []
    for i, (target, kind, priority) in enumerate(providers):
        raw = target.read_bytes(); before = json.loads(raw); after = dict(before); after.pop('fixed_time', None)
        # Retain all formatting and unrelated bytes as well as semantic fields.
        candidate, count = re.subn(rb'(?m)^[ \t]*"fixed_time"[ \t]*:[ \t]*-?\d+[ \t]*,[ \t]*\r?\n', b'', raw)
        assert count == (1 if 'fixed_time' in before else 0)
        assert json.loads(candidate) == after
        old = a.output/f'provider_{i:02d}.before.json'; new = a.output/f'provider_{i:02d}.after.json'
        old.write_bytes(raw); new.write_bytes(candidate)
        rows.append(dict(target=str(target.resolve()), kind=kind, pack_priority=priority,
            before=str(old.resolve()), after=str(new.resolve()), before_sha256=sha(raw), after_sha256=sha(candidate),
            removed_fixed_time=before.get('fixed_time'), unchanged_fields=after, inverse_is_exact_original_bytes=True))
    world_rows = [r for r in rows if r['kind']=='enabled world override']
    effective = max(world_rows, key=lambda r:r['pack_priority']) if world_rows else rows[0]
    plan = dict(world=str(a.world.resolve()), enabled_packs=enabled, providers=rows, effective_provider=effective['target'],
        forward=[dict(target=r['target'], expected_sha256=r['before_sha256'], bytes_from=r['after']) for r in rows],
        inverse=[dict(target=r['target'], expected_sha256=r['after_sha256'], bytes_from=r['before']) for r in rows],
        world_written=False, source_written=False, native_day_night_verified=False, visual_verified=False,
        reference=dict(url='https://evangelion.fandom.com/wiki/GeoFront', inspected_by='root',
            cited_secondary_source='Evangelion Chronicle 03/24: reflected sunlight, trees, grass, lake and day/night',
            engineering_inference='Remove obsolete fixed noon from both providers to permit the native day clock; retain the existing light/sky design until actual day/night review.'),
        producer='tools/prepare_tv_world_preview.py copies the shipped source type before changing effects; removing source fixed_time also prevents new preview recurrence.',
        lifecycle=['Root installs exact source and effective enabled-pack candidates only when no Minecraft process owns the world.',
            'Root freezes rebuilt resources, then cold-loads the same world; runtime fixedTime must be absent.',
            'Capture dayTime 6000 and 18000 with unchanged shader/exposure, at surface city, road tunnel/valley, underground lake/forest and operational facility.',
            'Record actual_fixed_time=-1, actual_day_time, ambient_light and current effective provider hash for every scene.',
            'Verify natural clock advance, reload persistence and unchanged identity/progress; photographs restore elapsed world dayTime via the existing review cleanup.',
            'After approval retain native day/night. Exact inverse is a rollback for failure, not automatic restoration of the obsolete fixed noon.'])
    (a.output/'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), 'utf8')
    print('Immutable day/night candidate', len(rows), 'providers; effective', effective['target'])


if __name__ == '__main__': main()
