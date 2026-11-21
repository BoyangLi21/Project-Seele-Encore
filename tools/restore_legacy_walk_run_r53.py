"""Restore the user's preceding three-rig walk/run selection only."""
from pathlib import Path
import argparse
import copy
import hashlib
import json


def restore(runtime, previous):
    path = runtime / 'eva_body_r44.json'
    old = json.loads((previous / path.name).read_text('utf8'))
    body = json.loads(path.read_text('utf8'))
    assert body['motion']['bones'] == old['motion']['bones']
    for rig in ('0', '1', '2'):
        current = body['stance_clips_by_rig'][rig]
        source = old['stance_clips_by_rig'][rig]
        assert current['bones'] == source['bones']
        for name in ('walk', 'run'):
            current['clips'][name] = copy.deepcopy(source['clips'][name])
            # R50's new stride/contact table describes the rejected clips.
            # The earlier package uses the existing legacy cadence instead.
            contract = body.get('locomotion_contract_r43', {}).get(rig, {})
            contract.pop(name, None)
    body['r53_walk_run_selection'] = dict(source='installed_R48_preceding_gait', rigs=[0, 1, 2], clips=['walk', 'run'])
    data = json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode('utf8')
    path.write_bytes(data)
    manifest_path = runtime / 'combat_bundle_r44.json'
    manifest = json.loads(manifest_path.read_text('utf8'))
    manifest['files'][path.name] = hashlib.sha256(data).hexdigest()
    manifest['bundle_id'] = 'R53_REPAIRS_WITH_PRECEDING_WALK_RUN'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), 'utf8')
    actual = json.loads(path.read_text('utf8'))
    assert all(actual['stance_clips_by_rig'][rig]['clips'][name] == old['stance_clips_by_rig'][rig]['clips'][name]
               for rig in ('0', '1', '2') for name in ('walk', 'run'))
    print(json.dumps(dict(runtime=str(runtime), restored_clips=6, readback=True)))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--runtime', type=Path, required=True)
    p.add_argument('--previous', type=Path, required=True)
    args = p.parse_args()
    restore(args.runtime, args.previous)
