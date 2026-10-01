"""Freeze every bounded batch as one native JVM input; never launch or write a world."""
from pathlib import Path
from collections import Counter
import argparse, hashlib, json

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('selection', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    assert not args.output.exists(), 'Use a new attempt name; preserve all earlier inputs and results'
    selection = json.loads(args.selection.read_text('utf8'))
    assert not selection.get('world_changed') and selection['native_execution_pending']
    args.output.mkdir(parents=True)
    seen = set()
    inputs, jobs, counts, feature_counts = [], [], Counter(), Counter()
    max_available = max_origins = 0
    measured_soil = Counter()
    biome_features = {}
    for i, source_name in enumerate(selection['jobs']):
        source = Path(source_name)
        job = json.loads(source.read_text('utf8'))
        assert job['read_only'] and job['dimension'] == 'projectseele:geofront'
        assert 0 < len(job['chunks']) <= 128
        available = {tuple(q) for q in job['available_chunks']}
        assert len(available) <= 1152
        for q in job['chunks']:
            key = q['x'], q['z'], q['layer']
            assert key not in seen, ('Duplicate origin', key)
            seen.add(key)
            assert all((q['x'] + dx, q['z'] + dz) in available for dx in (-1, 0, 1) for dz in (-1, 0, 1))
            counts[q['layer']] += 1
            counts[q['layer'] + '/' + q['biome']] += 1
            measured_soil[q['layer'] + '/' + q['biome']] += q['measured_soil_cells']
            if q['biome'] not in biome_features:
                biome_file = ROOT / 'src/main/resources/data/projectseele/worldgen/biome' / (q['biome'].split(':')[1] + '.json')
                biome_features[q['biome']] = json.loads(biome_file.read_text('utf8'))['features'][9]
            for feature in biome_features[q['biome']]:
                feature_counts[q['layer'] + '/' + feature] += 1
        path = args.output / f'batch_{i:04d}.json'
        # The single-JVM property targets the manifest. Per-batch invocation text
        # is retained only as provenance and cannot instruct separate restarts.
        job.pop('invocation', None)
        job['source_selection'] = args.selection.resolve().as_posix()
        path.write_text(json.dumps(job, ensure_ascii=False), 'utf8')
        jobs.append(path.resolve().as_posix())
        inputs.append(dict(job=jobs[-1], sha256=digest(path), source=str(source), source_sha256=digest(source),
                           origins=len(job['chunks']), available_chunks=len(available)))
        max_origins = max(max_origins, len(job['chunks']))
        max_available = max(max_available, len(available))
    assert len(seen) == selection['eligible_chunks']
    manifest = args.output / 'manifest.json'
    manifest.write_text(json.dumps(dict(jobs=jobs, read_only=True, selected_origins=len(seen),
        selection_sha256=digest(args.selection), input_epochs=inputs), ensure_ascii=False, indent=2), 'utf8')
    sources = [ROOT / 'src/main/java/com/projectseele/world' / f'{name}.java' for name in
               ('RegionalEcologyRetrofitR44', 'NativeEcologyPlanLedgerR44', 'NativeEcologyBiomesR44', 'RegionalEcologyBiomeSourceR44',
                'NativeGeofrontVegetationR44', 'NativeEcologyFeatureProtectionR44', 'NativeEcologyFeatureControlsR44', 'GeoFrontBoundedChunkGenerator', 'EcologyFutureGenerationR44')]
    sources.extend([ROOT/'src/main/java/com/projectseele/mixin/EcologyPlacedFeatureR44Mixin.java',
                    ROOT/'src/main/resources/projectseele.mixins.json',ROOT/'src/main/resources/data/projectseele/dimension/geofront.json',
                    ROOT/'src/main/resources/data/projectseele/dimension_type/geofront.json'])
    sources.extend(ROOT.glob('src/main/resources/data/projectseele/worldgen/biome/geofront_*.json'))
    source_epochs = [dict(path=str(p), sha256=digest(p)) for p in sources]
    contract = dict(input=manifest.resolve().as_posix(), input_sha256=digest(manifest),
        source_epochs=source_epochs, native_execution_pending=True, world_written=False,
        world=selection['measured_world'], selected_origins=len(seen), batches=len(jobs),
        single_jvm=True, sequential_batches=True, origin_counts=dict(counts), measured_soil_cells=dict(measured_soil),
        expected_registered_feature_calls_from_source=dict(feature_counts),
        command=f'python -X utf8 tools/run_headless_r44.py ecology "{manifest.resolve().as_posix()}" --timeout 21600',
        complete_marker=manifest.resolve().as_posix()+'.complete.json', failed_marker=manifest.resolve().as_posix()+'.failed.json',
        limits=dict(max_input_origins_per_batch=max_origins, max_declared_available_chunks=max_available,
            hard_max_input_origins_per_batch=128, hard_max_available_chunk_ids=1152,
            single_feature_pending_cells=65536, batch_overlay_plus_pending_cells=1048576,
            single_feature_detached_scratch_chunks=16, disk_ledger_cached_sections=96,
            maximum_sparse_cells_in_ledger_cache=96*4096, merged_biome_sections_per_shard=512,
            launcher_heap_max='4G', measured_heap_and_loaded_chunk_high_water_marks='Reported per native batch; no byte estimate or unloaded-chunk guarantee inferred from cell limits'),
        lifecycle='One shared disk ledger for the entire manifest. Export each batch, merge biomes, flush and clear overlay/baseline/NBT/trials/scratch. No forced tickets; vanilla short load tickets expire. Final merged biome shards are the only applyable biome plans.',
        requirements_before_native_author=[
            'Root freezes newly compiled class/resources and preserves effective world datapack regional biome source.',
            'If retiring the complete old grid layout, root applies its exact full-component retirement before authoring reseed. Otherwise protected original trees will correctly roll back overlapping native features.',
            'Every batch/result must be complete, every expected origin and registered feature called. A resource-limit error is a failed attempt, never a protection success.',
            'Run audit_ecology_sequence_r44.py and validate_ecology_manifest_r44.py on the final complete marker. Never apply intermediate raw batch biome plans.'
        ],
        interpretation='Selection/source-call denominators are proposed work only. Native realized cells, applied cells, growth/reload and actual client/visual quality have separate receipts and cannot be substituted for one another.')
    (args.output/'execution_contract.json').write_text(json.dumps(contract, ensure_ascii=False, indent=2), 'utf8')
    print(json.dumps({k:v for k,v in contract.items() if k in ('input','selected_origins','batches','single_jvm','origin_counts','limits','command')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
