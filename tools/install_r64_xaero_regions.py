"""Install a subset of native Xaero surface and full-cave region conversions into an offline review client."""
import argparse
import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

from install_r53_carrier_trays import stopped_world


def leaf(map_root, layer, name):
    files = [p for p in ((map_root / layer / 'cache_1' / (name + suffix))
                         for suffix in ('.xwmc', '.xwmc.outdated')) if p.is_file()]
    if len(files) != 1:
        raise ValueError(f'Expected one native texture cache for {name} in {map_root / layer}, got {files}')
    return files[0]


def verify_archive(path, member):
    with zipfile.ZipFile(path) as archive:
        if archive.namelist() != [member] or archive.getinfo(member).file_size == 0:
            raise ValueError(f'Invalid {member} in {path}')
        if archive.testzip() is not None:
            raise ValueError(f'Unreadable native region payload in {path}')


def replace(src, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False) as temp:
        name = Path(temp.name)
    try:
        shutil.copy2(src, name)
        os.replace(name, dest)
    finally:
        name.unlink(missing_ok=True)


def install(source, world, output, regions):
    if not world.is_dir() or not (world / 'level.dat').is_file():
        raise ValueError('A complete stopped target world is required')
    client = world.parent.parent
    target = client / 'xaero/world-map' / world.name.replace('_', '^us^') / 'projectseele$geofront'
    if target.resolve() == source.resolve() or not target.is_dir():
        raise ValueError('Source must be a separate native conversion for this review world')
    if 'caveModeType:2' not in (source / 'dimension_config.txt').read_text('utf8'):
        raise ValueError('Native full-cave conversion did not finish')
    requested = {f'{x}_{z}' for x, z in regions}
    layers = [Path(), Path('caves/-2147483648')]
    plans = []
    inventories = []
    for layer in layers:
        raw = Path('cm$converted') / layer
        previous = {p.stem for p in (target / raw).glob('*.zip')}
        inventories.append(previous)
        if not requested <= previous:
            raise ValueError(f'Requested region absent from the shipped {layer} map')
        for name in sorted(requested):
            if not re.fullmatch(r'-?\d+_-?\d+', name):
                raise ValueError(f'Invalid native region id {name}')
            region = raw / (name + '.zip')
            cache = leaf(source, layer, name)
            old_cache = leaf(target, layer, name)
            for new, old, member in ((source / region, target / region, 'region.xaero'),
                                     (cache, old_cache, 'cache.xaero')):
                verify_archive(new, member)
                destination = target / new.relative_to(source)
                plans.append((new, old, destination))
    if inventories[0] != inventories[1]:
        raise ValueError('Shipped surface and cave map coverage differ')
    output.mkdir(parents=True, exist_ok=False)
    backup = output / 'before'
    writes = []
    with stopped_world(world):
        try:
            for new, old, destination in plans:
                if old == destination and old.read_bytes() == new.read_bytes():
                    continue
                saved = backup / old.relative_to(target)
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(old, saved)
                writes.append((old, destination, saved))
                replace(new, destination)
                if old != destination:
                    old.unlink()
            for new, old, destination in plans:
                if destination.read_bytes() != new.read_bytes() or old != destination and old.exists():
                    raise ValueError(f'Native file readback failed at {destination}')
            for layer, previous in zip(layers, inventories):
                current = {p.stem for p in (target / 'cm$converted' / layer).glob('*.zip')}
                if current != previous:
                    raise ValueError(f'Native map coverage changed in {layer}')
        except BaseException:
            for old, destination, saved in reversed(writes):
                replace(saved, old)
                if old != destination:
                    destination.unlink(missing_ok=True)
            raise
    report = dict(target=str(target), source=str(source), region_count=len(requested),
                  surface_regions=len(inventories[0]), cave_regions=len(inventories[1]),
                  requested_raw_and_cache_files=len(plans), replaced_files=len(writes),
                  native_payload_readback=True, all_other_region_files_preserved=True)
    (output / 'installation.json').write_text(json.dumps(report, indent=2), 'utf8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ('source', 'world', 'out', 'regions'):
        parser.add_argument('--' + argument, required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(install(args.source, args.world, args.out, json.loads(args.regions.read_text('utf8')))))
