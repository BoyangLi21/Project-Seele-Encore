"""Prepare a finite native generation pass in the isolated cache server only.

Existing FULL chunks are excluded. Snapshot target payloads and refresh nearby
context before starting the server; merge_hakone_missing_chunks owns publication.
"""
import argparse
import json
import shutil
import zipfile
from collections import Counter
from pathlib import Path

import nbtlib
from install_r53_carrier_trays import stopped_world
from install_hakone_array_patch import prepare_jar, atomic_replace
from map_pipeline.install.invariants import require_nbt_equal
from map_pipeline.launch_protection import load
from transplant_s22_authority import read_region, parse_chunk

DIM = Path('dimensions/projectseele/geofront')
PRIMARY = ('GeoFrontBoundedChunkGenerator', 'GeoFrontHeightR52', 'TvWorldPreviewTerrain',
           'TvAuthoredTerrainR44', 'FacilitySchemaV2', 'CityRigidGenerationR45',
           'CityRigidTopologyR45', 'CityLowriseAddonR48', 'RegionalEcologyBiomeSourceR44',
           'NativeGeofrontVegetationR44', 'NativeEcologyFeatureProtectionR44',
           'S24CoordinateTransform', 'FacilityWorldPolicy')


def rows(path):
    return read_region(path) if path.exists() and path.stat().st_size else (bytes(4096), [None] * 1024)


def main(a):
    world, cache, out = a.world, a.cache, a.out
    if out.exists() or '/cache-server/' not in cache.resolve().as_posix():
        raise ValueError('Fresh output and isolated cache-server save required')
    x0, z0, x1, z1 = a.bounds
    if x0 % 16 or z0 % 16 or (x1 + 1) % 16 or (z1 + 1) % 16:
        raise ValueError('Use complete inclusive chunk bounds')
    with stopped_world(world), stopped_world(cache):
        data = nbtlib.load(world / 'level.dat')['Data']
        require_nbt_equal(data['WorldGenSettings'], nbtlib.load(cache / 'level.dat')['Data']['WorldGenSettings'])
        topologies = list((world / DIM / 'data').glob('projectseele_city_rigid_topology_r45_*.dat'))
        if len(topologies) != 1:
            raise ValueError('Expected one installed city topology')
        topology = nbtlib.load(topologies[0])
        if 'data' in topology:
            topology = topology['data']
        world_uuid = str(topology['WorldUUID'])
        chunks, counts, loaded = [], Counter(), {}
        for cx in range(x0 // 16, x1 // 16 + 1):
            for cz in range(z0 // 16, z1 // 16 + 1):
                region = cx // 32, cz // 32
                if region not in loaded:
                    loaded[region] = {kind: rows(world / DIM / kind / f'r.{region[0]}.{region[1]}.mca')[1]
                                      for kind in ('region', 'entities', 'poi')}
                slot = cz % 32 * 32 + cx % 32
                original = loaded[region]['region'][slot]
                tag = parse_chunk(original) if original is not None else None
                status = str(tag.get('Status', '')).removeprefix('minecraft:') if tag is not None else 'missing'
                if status == 'full':
                    counts['excluded_full'] += 1
                    continue
                if tag is not None and any(tag.get(k) for k in ('block_entities', 'entities', 'block_ticks', 'fluid_ticks', 'ToBeTicked', 'LiquidsToBeTicked')):
                    raise ValueError(f'Persistent protochunk contents: {(cx, cz)}')
                actors = loaded[region]['entities'][slot]
                if actors is not None and parse_chunk(actors).get('Entities'):
                    raise ValueError(f'Persistent actors in target: {(cx, cz)}')
                chunks.append((cx, cz))
                counts[status] += 1
        if not chunks:
            raise ValueError('No incomplete native chunks in requested bounds')
        guard = load(world)
        if set(chunks).intersection(guard.by_chunk):
            raise ValueError('Target intersects launch mechanics')
        actualjar = world.parent.parent / 'mods/projectseele-0.1.0-all.jar'
        cachejar = cache.parent / 'mods/projectseele-0.1.0-all.jar'
        with zipfile.ZipFile(actualjar) as actual, zipfile.ZipFile(cachejar) as cached:
            names = [n for n in actual.namelist() if n.endswith('.class') and any(
                n == 'com/projectseele/world/' + p + '.class' or n.startswith('com/projectseele/world/' + p + '$') for p in PRIMARY)]
            for name in names:
                if actual.read(name) != cached.read(name):
                    raise ValueError('Generation dependency differs: ' + name)
            terrain = {name: actual.read('data/projectseele/worldgen/' + name)
                       for name in ('hakone_surface.bin.gz', 'hakone_surface_blend.bin.gz')}
        regions = {(x // 32, z // 32) for x, z in chunks}
        context = {(x // 32, z // 32) for cx, cz in chunks
                   for x in (cx - 32, cx, cx + 32) for z in (cz - 32, cz, cz + 32)}
        out.mkdir(parents=True)
        (out / 'terrain-inputs').mkdir()
        for name, payload in terrain.items():
            (out / 'terrain-inputs' / name).write_bytes(payload)
        plan = dict(actual_world=str(world), cache_world=str(cache), bounds=a.bounds,
                    chunks=chunks, world_uuid=world_uuid, seed=int(data['WorldGenSettings']['seed']),
                    before_statuses=dict(counts), actual_world_written=False,
                    launch_guard_chunk_intersections=0)
        (out / 'plan.json').write_text(json.dumps(plan, indent=2), 'utf8')
        (out / 'chunks.json').write_text(json.dumps(chunks), 'utf8')
        (out / 'seed.txt').write_text(str(plan['seed']), 'utf8')
        (out / 'server-world.txt').write_text(str(cache.resolve()), 'utf8')
        shutil.copy2(a.agent, out / 'native-generate.jar')
        copied, removed = [], []

        def snapshot(relative):
            if (world / relative).exists():
                dest = out / 'actual-before' / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(world / relative, dest)

        def sync(relative):
            source, target = world / relative, cache / relative
            if not target.resolve().is_relative_to(cache.resolve()):
                raise ValueError('Cache path escaped')
            if target.exists():
                backup = out / 'cache-before' / relative
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
            if source.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                if source.read_bytes() != target.read_bytes():
                    raise ValueError('Cache readback failed: ' + str(relative))
                copied.append(str(relative))
            elif target.exists():
                target.unlink()
                removed.append(str(relative))

        snapshot(Path('level.dat'))
        for rx, rz in sorted(regions):
            for kind in ('region', 'entities', 'poi'):
                snapshot(DIM / kind / f'r.{rx}.{rz}.mca')
        for rx, rz in sorted(context):
            for kind in ('region', 'entities', 'poi'):
                sync(DIM / kind / f'r.{rx}.{rz}.mca')
        for group in ('chunks', 'surface'):
            folder = DIM / 'data/city_rigid_generation_r45' / group
            for name in sorted({f.name for root in (world, cache) for f in (root / folder).glob('*.dat')}):
                x, z = map(int, Path(name).stem.split('_'))
                if (x // 32, z // 32) in context:
                    sync(folder / name)
                if (x, z) in set(chunks):
                    snapshot(folder / name)
        for f in (world / DIM / 'data').glob('projectseele_city_*.dat'):
            sync(DIM / 'data' / f.name)
        for name in sorted({p.name for root in (world, cache) for p in root.glob('.projectseele_*.json')}):
            sync(Path(name))
        shutil.copy2(cachejar, out / 'cache-before/cache-runtime-before.jar')
        version = actualjar.stat().st_size, actualjar.stat().st_mtime_ns
        prepared = out / 'cache-runtime-prepared.jar'
        count = prepare_jar(cachejar, actualjar, prepared, terrain_consumer_only=True)
        if version != (actualjar.stat().st_size, actualjar.stat().st_mtime_ns):
            raise ValueError('Actual runtime changed during cache merge')
        atomic_replace(cachejar, prepared.read_bytes())
        report = dict(actual_world=str(world), cache_world=str(cache), actual_world_written=False,
                      copied_files=len(copied), removed_cache_files=removed,
                      context_regions=sorted(context), target_regions=sorted(regions),
                      target_chunks=len(chunks), before_statuses=dict(counts),
                      native_generation_classes_identical=len(names), terrain_classes_updated=count,
                      actual_game_time=int(data['Time']), launch_guard_chunk_intersections=0)
        (out / 'cache-preparation.json').write_text(json.dumps(report, indent=2), 'utf8')
        print(json.dumps(report), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(__doc__)
    for name in ('world', 'cache', 'out', 'agent'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--bounds', type=int, nargs=4, required=True)
    main(p.parse_args())
