"""Stream a completed single-JVM author and report realized work, never planted work."""
from pathlib import Path
from collections import Counter, defaultdict
import argparse, csv, gzip, hashlib, json

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('complete_manifest', type=Path)
    parser.add_argument('--allow-legacy-metrics', action='store_true', help='Old calibration evidence only; missing resource/runtime metrics remain unmeasured')
    args = parser.parse_args()
    complete = json.loads(args.complete_manifest.read_text('utf8'))
    input_path = Path(complete.get('input_manifest', str(args.complete_manifest).removesuffix('.complete.json')))
    manifest = json.loads(input_path.read_text('utf8'))
    input_jobs = manifest.get('jobs', [str(input_path)])
    errors, missing_metrics, resources, differences = [], [], [], []
    counts, species, biome_groups = Counter(), defaultdict(Counter), defaultdict(Counter)
    features = {}
    native_epochs = manifest.get('input_epochs')
    report_path = args.complete_manifest.with_name(args.complete_manifest.name + '.coverage.json')
    tile_path = report_path.with_suffix('.tiles.csv')
    fields = ['batch','x','z','layer','biome','measured_soil_cells','runtime_centre_biome','runtime_centre_ground','runtime_biome_matches',
              'calls','native_placed','native_zero','protected_rollbacks','accepted_changed_mutations','elapsed_ms','completed']
    counts['expected_batches'] = len(input_jobs)
    if not complete.get('complete') or complete.get('batches') != len(input_jobs):
        errors.append('Final native marker is incomplete or has the wrong batch denominator')
    if complete.get('per_batch_biomes_applyable') is not False or not complete.get('cross_batch_vegetation_cells_disjoint'):
        errors.append('Missing final shared-ledger / merged-biome authority')
    if len(complete.get('block_plans', [])) != len(input_jobs):
        errors.append('Final native block plan count differs from bounded inputs')
    with tile_path.open('w', encoding='utf8', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=fields);writer.writeheader()
        for batch, job_path in enumerate(input_jobs):
            path = Path(job_path);job = json.loads(path.read_text('utf8'))
            if native_epochs and hashlib.sha256(path.read_bytes()).hexdigest() != native_epochs[batch]['sha256']:
                errors.append(f'Input hash changed after freezing: {path}')
            stem = path.with_suffix('')
            result_path = path.with_name(stem.name + '.result.json')
            if not result_path.exists():
                errors.append(f'No native batch result: {path}');continue
            result = json.loads(result_path.read_text('utf8'))
            if not result.get('native_preview_complete') or result.get('error'):
                errors.append(f'Native batch failed, cannot count its trials as success: {path}');continue
            counts['completed_batches'] += 1
            grouped = defaultdict(list)
            for trial in result['feature_trials']:
                cx, cz = map(int, trial['chunk'].split(','))
                grouped[cx, cz, trial['layer']].append(trial)
            origins = {(q['x'],q['z'],q['layer']):q for q in result.get('origin_results', [])}
            if not origins:
                missing_metrics.append(dict(batch=batch, kind='origin/runtime feature/resource metrics'))
            expected_keys = {(q['x'],q['z'],q['layer']) for q in job['chunks']}
            if set(grouped) - expected_keys or set(origins) - expected_keys:
                errors.append(f'Batch has an undeclared origin: {path}')
            observed_keys = set(origins) if origins else set(grouped)
            if job.get('biome_only') and not origins and result.get('chunks_processed') == len(expected_keys):
                observed_keys = expected_keys
            if observed_keys != expected_keys:
                errors.append(f'Batch is missing explicit expected origins: {path}')
            for q in job['chunks']:
                key = q['x'], q['z'], q['layer'];trial_rows = grouped[key];observed = origins.get(key, {})
                counts['expected_origins'] += 1
                group = q['layer'] + '/' + q.get('biome', 'biome_only')
                biome_groups[group]['origins'] += 1
                biome_groups[group]['measured_soil_cells'] += q.get('measured_soil_cells', 0)
                if job.get('biome_only'):
                    expected = []
                else:
                    if q['biome'] not in features:
                        biome_file = ROOT/'src/main/resources/data/projectseele/worldgen/biome'/(q['biome'].split(':')[1]+'.json')
                        features[q['biome']] = json.loads(biome_file.read_text('utf8'))['features'][9]
                    expected = features[q['biome']]
                if [t['feature'] for t in trial_rows] != expected:
                    errors.append(f'Registered feature order/count differs from source at {key}')
                if origins and observed.get('registered_feature_order', []) != expected:
                    errors.append(f'Runtime feature denominator differs at {key}')
                completed = key in observed_keys and (not origins or observed.get('completed'))
                if completed:counts['completed_origins'] += 1
                if observed.get('declared_biome_matches_runtime_centre') is False:
                    counts['runtime_centre_biome_differences'] += 1
                    if len(differences) < 32: differences.append(dict(batch=batch, **q, observed=observed['runtime_centre_biome'], ground=observed['runtime_centre_ground']))
                if observed.get('centre_soil_measurement_error'):
                    counts['unmeasured_centre_soils'] += 1
                row = dict(batch=batch,x=q['x'],z=q['z'],layer=q['layer'],biome=q.get('biome','biome_only'),measured_soil_cells=q.get('measured_soil_cells'),
                    runtime_centre_biome=observed.get('runtime_centre_biome'),runtime_centre_ground=observed.get('runtime_centre_ground'),
                    runtime_biome_matches=observed.get('declared_biome_matches_runtime_centre'),calls=len(trial_rows),
                    native_placed=sum(t['placed'] and not t['rolled_back_for_protection'] for t in trial_rows),
                    native_zero=sum(not t['placed'] and not t['rolled_back_for_protection'] for t in trial_rows),
                    protected_rollbacks=sum(t['rolled_back_for_protection'] for t in trial_rows),
                    accepted_changed_mutations=sum(t.get('accepted_changed_cells_against_logical_before',0) for t in trial_rows),
                    elapsed_ms=observed.get('elapsed_ms'),completed=bool(completed))
                writer.writerow(row)
                for label in ('calls','native_placed','native_zero','protected_rollbacks','accepted_changed_mutations'):
                    counts[label] += row[label];biome_groups[group][label] += row[label]
                for t in trial_rows:
                    if t.get('detached_scratch_chunks', 0) > 16:errors.append(f'Scratch chunk budget exceeded at {key}')
                    if t['rolled_back_for_protection'] and t.get('accepted_changed_cells_against_logical_before', 0):
                        errors.append(f'Protected feature committed mutations at {key}')
                    if not t['rolled_back_for_protection'] and t['candidate_cells'] and not t['placed']:
                        counts['native_false_with_pending_cells'] += 1
                    counts['rejected_write_attempts'] += t.get('rejected_write_attempts', 0)
            resource_keys = ('batch_peak_combined_candidate_cells','single_feature_peak_pending_cells','batch_cell_limit','single_feature_cell_limit',
                'jvm_used_heap_bytes','jvm_committed_heap_bytes','jvm_max_heap_bytes','jvm_sampled_peak_used_heap_bytes','loaded_chunks_at_batch_start','sampled_peak_loaded_chunks','batch_elapsed_ms')
            resources.append(dict(batch=batch, **{k:result[k] for k in resource_keys if k in result}))
            if any(k not in result for k in resource_keys):missing_metrics.append(dict(batch=batch,kind='incomplete resource samples'))
            if result.get('batch_peak_combined_candidate_cells', 0) > result.get('batch_cell_limit', 1048576):errors.append(f'Batch budget exceeded: {path}')
            if result.get('single_feature_peak_pending_cells', 0) > result.get('single_feature_cell_limit', 65536):errors.append(f'Feature budget exceeded: {path}')
            forward = path.with_name(stem.name + '.forward.jsonl.gz')
            count = 0
            with gzip.open(forward, 'rt', encoding='utf8') as stream:
                for line in stream:
                    change = json.loads(line);layer = 'geofront' if change['pos'][1] < 0 else 'surface'
                    species[layer][change['after'].partition('[')[0]] += 1;count += 1
                    if '_leaves[' in change['after']:
                        if 'persistent=true' in change['after']:errors.append('New native leaf is persistent: '+str(change['pos']))
                        if 'distance=7' in change['after']:counts['native_distance7_leaf_cells'] += 1
            if count != result.get('changed_cells', count):errors.append(f'Exact forward count differs from native result: {path}')
            counts['unique_native_planned_cells'] += count
            print('Audited batch',batch+1,'/',len(input_jobs),'origins',len(job['chunks']),'cells',count,flush=True)
    if counts['unique_native_planned_cells'] != complete['exported_cells']:errors.append('Final exported_cells differs from streamed plan cells')
    if complete.get('completed_origins', counts['completed_origins']) != counts['completed_origins']:errors.append('Final origin count differs from the actual per-origin ledger')
    if missing_metrics and not args.allow_legacy_metrics:errors.append('New sequence requires all native runtime and resource observations')
    groups = {k:dict(v) for k,v in biome_groups.items()}
    for group in groups.values():
        group['realized_placement_rate'] = group.get('native_placed',0)/max(1,group.get('calls',0))
        group['protection_rollback_rate'] = group.get('protected_rollbacks',0)/max(1,group.get('calls',0))
    calibration = json.loads((ROOT/'artifacts/rebuild_r44/ecology/calibration_inspection.json').read_text('utf8'))
    reference = dict(origins=calibration['origin_tiles'],calls=calibration['features'],cells=calibration['final_cells'],
        realized_placement_rate=calibration['effective_placements']/calibration['features'],
        protection_rollback_rate=len(calibration['protected_rollbacks'])/calibration['features'],
        comparison='First 18-origin sample only. Global biome mix and retained existing vegetation can legitimately differ; inspect per-biome/per-tile rates and actual built images, not a single threshold.')
    report = dict(input=str(input_path), complete_manifest=str(args.complete_manifest), counts=dict(counts), per_biome=groups,
        native_final_state_cells_by_layer={k:dict(v) for k,v in species.items()}, resource_observations=resources,
        runtime_biome_difference_sample=differences, runtime_biome_differences_full_csv=str(tile_path),
        missing_native_observations=missing_metrics, calibration_reference=reference, errors=errors,
        native_author_coverage_passed=not errors, runtime_biome_quality_pending=bool(missing_metrics or counts['runtime_centre_biome_differences'] or counts['unmeasured_centre_soils']),
        resource_limits_measured=not missing_metrics, exact_world_preflight_required='validate_ecology_manifest_r44.py',
        actual_world_applied=False, actual_growth_reload_passed=False, actual_client_and_visual_passed=False, user_approved=False,
        interpretation='Per-feature accepted changes are mutation counts, possibly revised within a batch. Only streamed final block cells are unique. A source feature denominator is neither a realized tree nor an applied/grown map.')
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('Native coverage passed',not errors,'planned cells',counts['unique_native_planned_cells'],'runtime biome differences',counts['runtime_centre_biome_differences'],'report',report_path,flush=True)
    if errors:raise SystemExit(1)


if __name__ == '__main__':
    main()
