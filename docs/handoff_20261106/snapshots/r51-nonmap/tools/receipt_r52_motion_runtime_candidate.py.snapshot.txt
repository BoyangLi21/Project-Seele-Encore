"""Verify the unique C12/R48 runtime candidate; write only C-local receipts."""
from pathlib import Path
import hashlib, json, zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/r52_runtime_candidate'
MAPS = OUT / 'projectseele-local-maps'
CLIP = ROOT / 'artifacts/r52_finisher_body3f_early_guard1/early_guard_core_surface_contact12.json'
CLIP_SHA = '5164edbb96722e37e97fe5d0f002e2cbf157d6824a9c652b48430a89ca207873'
BODY_SHA = 'cd9ba815c44a6ca60824417ae76b25de9db1936b655ec035b62775fa41d380f9'
ORIGINAL = ROOT / 'artifacts/r52_walk_run_restore/corrected_runtime/projectseele-local-maps/combat_bundle_r44.json'
UV_RECEIPT = ROOT / 'artifacts/r52_hand_uv_material_repair/FINAL_OVERLAY_RECEIPT.json'
C7_JAR = ROOT / 'artifacts/r52_unified_candidate7/projectseele-0.1.0-all.jar'
C7_SHA = '6f5bbf3c03c536fe96cd9d3d318f229b3eb5f6b0e23699b51c256bcc65d7d8be'

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def read(path):
    return json.loads(Path(path).read_text('utf-8-sig'))

def main():
    assert ROOT == Path('C:/Users/liboy/.codex/worktrees/r51-nonmap/eva')
    original, selected = read(ORIGINAL), read(MAPS / 'combat_bundle_r44.json')
    assert len(original['files']) == len(selected['files']) == 28
    assert original['files'].keys() == selected['files'].keys()
    assert {p.name for p in MAPS.iterdir() if p.is_file()} == set(selected['files']) | {'combat_bundle_r44.json'}
    assert sha(CLIP) == sha(MAPS / 'first_battle_r44.json') == CLIP_SHA
    assert selected['files']['eva_body_r44.json'] == sha(MAPS / 'eva_body_r44.json') == BODY_SHA
    rows = {}
    for name, expected in selected['files'].items():
        assert '/' not in name and '\\' not in name
        assert sha(MAPS / name) == expected, name
        if name != 'first_battle_r44.json':
            assert expected == original['files'][name], name
        rows[name] = dict(original_sha256=original['files'][name], selected_sha256=expected,
                          selected_path=str(MAPS / name), changed=original['files'][name] != expected,
                          source_path=str(CLIP) if name == 'first_battle_r44.json' else None,
                          original_contract_sha256=sha(ORIGINAL))
    body = read(MAPS / 'eva_body_r44.json')
    restored_body = read(ORIGINAL.parent / 'eva_body_r44.json')
    assert sha(ORIGINAL.parent / 'eva_body_r44.json') == BODY_SHA
    six_clips = {}
    for rig in ('0', '1', '2'):
        for name, source in (('walk', 'Male2_B3_Walk.bvh'), ('run', 'Male2_C3_Run.bvh')):
            clip = body['stance_clips_by_rig'][rig]['clips'][name]
            assert clip == restored_body['stance_clips_by_rig'][rig]['clips'][name]
            assert clip['source_file'] == source and 'r50_user_source' not in clip
            six_clips[rig + '/' + name] = dict(source_file=source, original_restored_clip_equal=True,
                canonical_sha256=hashlib.sha256(json.dumps(clip, sort_keys=True, separators=(',', ':')).encode()).hexdigest())
    assert sha(C7_JAR) == C7_SHA
    uv = read(UV_RECEIPT)
    assert len(uv['files']) == 4
    asset_rows = {}
    with zipfile.ZipFile(C7_JAR) as archive:
        for row in uv['files']:
            path = Path(uv['overlay_root']) / row['path']
            assert sha(path) == hashlib.sha256(archive.read(row['path'])).hexdigest() == row['sha256']
            asset_rows[row['path']] = dict(original_sha256=row['baseline_sha256'], selected_sha256=row['sha256'],
                                          selected_path=str(path), immutable_C7_readback_passed=True)
    report = dict(schema='projectseele.r52.motion-runtime-candidate.v1', source_root=str(ROOT),
        runtime_directory=str(MAPS), original_contract=str(ORIGINAL), original_contract_sha256=sha(ORIGINAL),
        selected_contract_sha256=sha(MAPS / 'combat_bundle_r44.json'), bundle_id=selected['bundle_id'],
        files=rows, runtime_changed_members=[name for name, row in rows.items() if row['changed']],
        required_jar_assets=asset_rows, reviewed_uv_receipt_sha256=sha(UV_RECEIPT),
        preserved_body_sha256=BODY_SHA, preserved_R48_six_clips=six_clips, body_top_level_keys=list(body),
        source_selection='Root selected C12 following front/side source preview; user artistic acceptance remains unclaimed',
        actual_C12_native_verified=False, C8_jar_qualification_pending=True,
        baseline_C7_jar=dict(path=str(C7_JAR), sha256=C7_SHA),
        protocol=69, world_written=False, game_written=False, runtime_candidate_only=True, user_accepted=False)
    (OUT / 'MOTION_RUNTIME_SELECTION_RECEIPT.json').write_text(json.dumps(report, indent=2) + '\n', 'utf8')
    print(json.dumps(dict(files=len(rows), changed=report['runtime_changed_members'], body=BODY_SHA,
                          final_clip=CLIP_SHA, four_uv=len(asset_rows), world_written=False, game_written=False)))

if __name__ == '__main__':
    main()
