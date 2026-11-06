"""One preservation and installation check for cold station deliveries.

Exact bytes and archive members are compared directly. Preservation is only a
regression guard; this module never claims geometry, appearance or playability.
The caller owns the stopped-world lock when using the functions directly.
"""
import argparse
import json
import re
import shutil
import zipfile
from pathlib import Path

import nbtlib
from native_transit_additions import inventory, assert_preserved
from install_r53_carrier_trays import stopped_world


def read(path):
    return json.loads(Path(path).read_text('utf-8-sig'))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), 'utf8')


def archive_exact(before, after):
    with zipfile.ZipFile(before) as a, zipfile.ZipFile(after) as b:
        if a.namelist() != b.namelist() and set(a.namelist()) != set(b.namelist()):
            raise ValueError('Client archive members changed')
        if len(a.namelist()) != len(set(a.namelist())) or len(b.namelist()) != len(set(b.namelist())):
            raise ValueError('Duplicate client archive members')
        for name in a.namelist():
            if a.read(name) != b.read(name):
                raise ValueError('Client archive content changed: ' + name)


def capture_identity(world, candidate, prior_client=None):
    """prior_client=False leaves the client out: other work may publish it."""
    world, candidate = Path(world), Path(candidate)
    target = candidate / 'identity-before'
    target.mkdir(exist_ok=False)
    files = []
    for source in [world/'level.dat', world/'level.dat_old',
                   *sorted((world/'playerdata').glob('*')),
                   *sorted((world/'dimensions/projectseele/geofront/entities').glob('*.mca'))]:
        if not source.is_file():
            continue
        rel = source.relative_to(world)
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        files.append(rel.as_posix())
    if 'level.dat' not in files:
        raise ValueError('Actual world identity is missing')
    write(target/'files.json', files)
    client = world.parent.parent/'mods/projectseele-0.1.0-all.jar'
    if prior_client is False:
        return files
    if prior_client is None:
        shutil.copy2(client, candidate/'client-before.jar')
    else:
        archive_exact(prior_client, client)
        (candidate/'client-before.jar').hardlink_to(prior_client)
    return files


def validate_receipt(receipt, manifest, production_log, device_count):
    """Validate independent producer and installer records without world IO."""
    additions = manifest.get('native_additions', [])
    if len(additions) != len(set(additions)):
        raise ValueError('Duplicate declared native additions')
    if receipt.get('status') != 'installed' or not receipt.get('changed_section_readback'):
        raise ValueError('Installation or changed-section readback incomplete')
    if receipt.get('cells') != manifest['cells']:
        raise ValueError('Installed cell count differs from frozen candidate')
    if receipt.get('native_additions', 0) != len(additions):
        raise ValueError('Installed native additions differ from frozen candidate')
    if receipt.get('changed_device_nbt_readback', 0) != device_count:
        raise ValueError('Device payload readback incomplete')
    if receipt.get('metadata_readback') != receipt.get('metadata_files'):
        raise ValueError('Generation/native metadata readback incomplete')
    if receipt.get('jar_classes', 0):
        raise ValueError('This station release does not authorize client class changes')
    if 'BUILD SUCCESSFUL' not in production_log:
        raise ValueError('Production replay did not finish successfully')
    matches = re.findall(r'Production surface replay: (\d+) chunks, ([\d,]+) changed cells', production_log)
    if len(matches) != 1:
        raise ValueError('Expected one unambiguous production replay result')
    chunks, cells = (int(n.replace(',', '')) for n in matches[0])
    if cells != manifest['cells'] or chunks + len(additions) != receipt['metadata_files']:
        raise ValueError('Production replay differs from installed scope')
    return dict(changed_cells=cells, recipe_chunks=chunks,
                new_native_members=len(additions), device_payloads=device_count)


def verify_preservation(world, candidate):
    world, candidate = Path(world), Path(candidate)
    manifest = read(candidate/'manifest.json')
    baseline = inventory(candidate/'preserved-native')
    additions = [Path(n).relative_to('mtr').as_posix() for n in manifest.get('native_additions', [])]
    if any('..' in Path(n).parts for n in additions):
        raise ValueError('Native addition escapes its database')
    assert_preserved(world, baseline, additions)
    for name in additions:
        if (candidate/'after/mtr'/name).read_bytes() != (world/'mtr'/name).read_bytes():
            raise ValueError('Installed native addition differs: ' + name)
    files = read(candidate/'identity-before/files.json')
    for name in files:
        rel = Path(name)
        if rel.is_absolute() or '..' in rel.parts:
            raise ValueError('Identity inventory escapes actual world')
        if (candidate/'identity-before'/rel).read_bytes() != (world/rel).read_bytes():
            raise ValueError('World/player/entity identity changed: ' + name)
    jar = (candidate/'client-before.jar').exists()
    if jar:
        archive_exact(candidate/'client-before.jar', world.parent.parent/'mods/projectseele-0.1.0-all.jar')
    return dict(identity_files_exact=len(files), old_native_members_exact=len(baseline),
                new_native_members_exact=len(additions), whole_client_jar_exact=jar)


def verify_delivery(world, candidate, installation, production_log):
    candidate = Path(candidate)
    tags = nbtlib.load(candidate/'block-entities.dat')['Changes']
    report = validate_receipt(read(installation), read(candidate/'manifest.json'),
                              Path(production_log).read_text('utf-8-sig', errors='replace'), len(tags))
    report.update(verify_preservation(world, candidate))
    report.update(passed=True, world_written=False, production_replay_passed=True,
                  geometry_or_live_acceptance_claim=False)
    return report


def main(args):
    try:
        with stopped_world(args.world):
            report = verify_delivery(args.world, args.candidate, args.installation, args.production_log)
        write(args.out, report)
        print('DELIVERY PASS: installed scope, production replay, identity, native transport and client preserved.')
    except Exception as error:
        write(args.out, dict(passed=False, failures=[str(error)], world_written=False))
        print('DELIVERY FAIL: ' + str(error))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    for key in ('world', 'candidate', 'installation', 'production-log', 'out'):
        parser.add_argument('--' + key, type=Path, required=True)
    main(parser.parse_args())
