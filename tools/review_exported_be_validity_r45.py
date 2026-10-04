"""Reclassify frozen audit records against a root-captured actual registry export; no world reads/writes."""
from pathlib import Path
import argparse, collections, gzip, hashlib, json

SCHEMA = 'projectseele.runtime-be-valid-blocks.r45.v15'
OWN = Path(__file__).resolve().parents[1] / 'artifacts/rebuild_r45/be_state_mismatch_sol_v15'


def state_key(state):
    if not state:
        return None
    name, sep, tail = state.partition('[')
    if not sep:
        return name, ()
    if not tail.endswith(']'):
        raise ValueError('Invalid state syntax')
    props = tuple(sorted(part.split('=', 1) for part in tail[:-1].split(',') if part))
    return name, tuple(tuple(pair) for pair in props)


def validate(export):
    if export.get('schema') != SCHEMA or not export.get('complete_registry_enumeration') or export.get('errors'):
        raise ValueError('Incomplete/wrong-schema registry capture cannot close UNKNOWN')
    if export.get('world_written') is not False or export.get('world_chunks_read_or_loaded') is not False:
        raise ValueError('Not the registry-only helper evidence')
    types = export.get('types', [])
    result = {}
    for row in types:
        if row['be_id'] in result:
            raise ValueError('Duplicate registry type')
        if row.get('relation_scope') not in {'STANDARD_BLOCK_ENTITY_TYPE_BLOCK_ID_MEMBERSHIP', 'CUSTOM_TYPE_DEFAULT_STATES_ONLY'}:
            raise ValueError('Unknown relation scope')
        result[row['be_id']] = row
    if len(result) != export.get('registered_type_count'):
        raise ValueError('Registry capture count mismatch')
    return result


def classification(row, types, probes):
    state = state_key(row.get('state'))
    if state is None:
        return 'UNKNOWN_STATE'
    key = row.get('be_id', ''), state
    if key in probes:
        return 'VALID_RUNTIME_EXACT_STATE' if probes[key] else 'RUNTIME_TYPE_MISMATCH'
    if row.get('be_id') not in types:
        return 'UNKNOWN_UNREGISTERED_TYPE'
    type_row = types[row['be_id']]
    if type_row['relation_scope'] != 'STANDARD_BLOCK_ENTITY_TYPE_BLOCK_ID_MEMBERSHIP':
        return 'UNKNOWN_CUSTOM_STATE_RELATION'
    return 'VALID_RUNTIME_BLOCK_MEMBERSHIP' if state[0] in type_row['valid_default_block_ids'] else 'RUNTIME_TYPE_MISMATCH'


def review(export_path, records, out):
    export_path, records, out = map(Path, (export_path, records, out))
    export_bytes = export_path.read_bytes()
    export_sha = hashlib.sha256(export_bytes).hexdigest()
    export = json.loads(export_bytes.decode('utf-8-sig')); types = validate(export)
    probes = {}
    for row in export.get('exact_state_probes', []):
        if row.get('complete'):
            key = row['be_id'], state_key(row['state'])
            if key in probes and probes[key] != row['is_valid']:
                raise ValueError('Conflicting runtime probes')
            probes[key] = row['is_valid']
    if out.exists() or not out.resolve().is_relative_to(OWN.resolve()):
        raise ValueError('Fresh owned artifact output required')
    out.mkdir(parents=True)
    counts, issues, total = collections.Counter(), [], 0
    with gzip.open(records, 'rt', encoding='utf-8') as src, gzip.open(out/'reclassified_records.jsonl.gz', 'wt', encoding='utf-8') as dst:
        for line in src:
            row = json.loads(line); verdict = classification(row, types, probes); total += 1
            counts[row.get('be_id', ''), verdict] += 1
            row['runtime_registry_classification'] = verdict
            row['registry_export_sha256'] = export_sha
            row['native_tick_pass'] = False
            if not verdict.startswith('VALID_RUNTIME_'):
                issues.append(row)
            dst.write(json.dumps(row, ensure_ascii=False)+'\n')
    (out/'issues_with_full_nbt.json').write_text(json.dumps(issues, ensure_ascii=False, indent=2), 'utf-8')
    summary = {'schema': 'projectseele.offline-runtime-be-review.r45.v15', 'record_scope': str(records), 'record_count': total,
               'registry_export_sha256': export_sha,
               'records_sha256': hashlib.sha256(records.read_bytes()).hexdigest(), 'loaded_mod_versions': export.get('loaded_mod_versions'),
               'type_counts': [{'be_id': be, 'classification': verdict, 'count': n} for (be, verdict), n in sorted(counts.items())],
               'issue_count': len(issues), 'world_read_or_written': False, 'native_tick_pass': False,
               'root_installed_jar_provenance_match': 'REQUIRED_SEPARATE_ROOT_RECEIPT',
               'limit': 'Registry validity only; custom types remain UNKNOWN outside exact probes. Physical blocks, SavedData, and frozen journals must retain separate record scopes. No automatic repairs/deletions.'}
    (out/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), 'utf-8')
    return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--registry-export', type=Path, required=True)
    p.add_argument('--records', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(); print(json.dumps(review(a.registry_export, a.records, a.out), ensure_ascii=False, indent=2))
