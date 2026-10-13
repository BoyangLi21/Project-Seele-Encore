"""Prepare one camera3/contact/ordinary-recovery native run using the existing lab."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PREVIOUS = ROOT / 'artifacts/r52_native_finisher_candidate2'
OUT = ROOT / 'artifacts/r52_native_finisher_candidate3'
CLIP = ROOT / 'artifacts/r52_finisher_camera3/first_battle_r52_camera3.json'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def quote(value):
    assert not any(char in value for char in '\r\n\0')
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def main():
    global OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jar', type=Path)
    parser.add_argument('--clip', type=Path, default=CLIP)
    parser.add_argument('--out',type=Path,default=OUT)
    args = parser.parse_args()
    OUT=args.out.resolve();assert OUT.is_relative_to(ROOT/'artifacts')
    clip_path = args.clip.resolve()
    assert clip_path.is_relative_to(ROOT / 'artifacts')
    if OUT.exists():
        assert not (OUT / 'RUNNING.json').exists(), 'Preserve existing evidence; never overwrite an attempted run'
        assert not json.loads((OUT / 'launch.json').read_text('utf8'))['ready_to_launch']
    spec = json.loads((PREVIOUS / 'launch.json').read_text('utf-8-sig'))
    world = Path(spec['world'])
    assert world.name == 'SEELE_FIRST_BATTLE_REVIEW_R10'
    assert (world / 'level.dat').is_file() and not (world / 'r10_resume_expected.json').exists()
    assert json.loads((world / 'r10_first_battle_review.json').read_text('utf8'))['passed']
    bundle = Path(spec['bundle_directory'])
    for name, expected in spec['runtime_fingerprints'].items():
        assert digest(bundle / name) == expected
    ready = args.jar is not None
    jar = args.jar.resolve() if ready else Path(spec['staged_jar']['path'])
    if ready:
        with zipfile.ZipFile(jar) as archive:
            assert b'firstBattleFollowupOrdinaryReviewR52' in archive.read('com/projectseele/visual/FirstBattleR10Review.class')
            assert b'firstBattleControlRecoveryCaptureR52' in archive.read('com/projectseele/visual/FirstBattleR10Review.class')
            assert 'com/projectseele/mixin/client/FirstBattleContactDrawWitnessR52Mixin.class' in archive.namelist()
        assert jar == Path(spec['staged_jar']['path']).resolve(), 'Root stages the new JAR in the existing QA instance'
    else:
        ready = False
    remove = ('firstBattleReviewClip', 'firstBattleNoFrameCaptureR52', 'firstBattleKeyFramesR52',
              'firstBattleFrameMetadataR52', 'firstBattleRuntimeWitnessR52Output', 'firstBattleCaptureOutputR52',
              'r47NativeCommandInbox', 'firstBattleFollowupOrdinaryReviewR52', 'firstBattleCloseViewsR52',
              'firstBattleControlRecoveryCaptureR52')
    command = [value for value in spec['command'] if not any(value.startswith('-Dprojectseele.' + name + '=') for name in remove)]
    properties = dict(firstBattleReviewClip=str(clip_path), firstBattleNoFrameCaptureR52='false',
                      firstBattleKeyFramesR52='false', firstBattleFrameMetadataR52='false',
                      firstBattleRuntimeWitnessR52Output=str(OUT / 'native.jsonl'),
                      firstBattleCaptureOutputR52=str(OUT / 'frames'),
                      r47NativeCommandInbox=str(OUT / 'commands.json'),
                      firstBattleFollowupOrdinaryReviewR52='true', firstBattleCloseViewsR52='true',
                      firstBattleControlRecoveryCaptureR52='true')
    command[1:1] = ['-Dprojectseele.' + name + '=' + value for name, value in properties.items()]
    spec.update(command=command, candidate_sha256=digest(clip_path), ready_to_launch=ready,
                staged_jar=dict(path=str(jar), sha256=digest(jar)),
                review_clip=str(clip_path), full_native_frame_sequence=True,
                expected_scene_completions=2, expected_death_ages=[372, 372])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'launch.json').write_text(json.dumps(spec, indent=2), 'utf8')
    (OUT / 'launch.args').write_text('\n'.join(quote(value) for value in command[1:]) + '\n', 'utf8')
    (OUT / 'commands.json').write_text(json.dumps(dict(seq=1, commands=[])), 'utf8')
    (OUT / 'previous_fixture_review.json').write_bytes((world / 'r10_first_battle_review.json').read_bytes())
    runner = (PREVIOUS / 'run_hidden_candidate.ps1').read_text('utf-8-sig')
    runner = runner.replace('$taskDeathCount -ne 1 -or $taskDeathAge -ne 372',
                            '$taskDeaths.Count -ne 2 -or @($taskDeaths | Where-Object { $_.Groups[1].Value -ne "372" }).Count -gt 0 -or -not $taskWhole.Contains("R10 BATTLE REVIEW PASS movement_after_film")')
    runner = runner.replace('full_native_movie_captured=$false;', 'full_native_movie_captured=$false;full_native_frame_sequence_requested=$true;')
    (OUT / 'run_hidden_candidate.ps1').write_text(runner, 'ascii')
    receipt = dict(ready_to_launch=ready, candidate_sha256=digest(clip_path), source_launch=str(PREVIOUS / 'launch.json'),
                   reused_fixture=True, world_files_written_by_preparation=0, runtime_bundle_copies=0,
                   model_asset_copies=0, first_two_native_failure_evidence_preserved=True,
                   full_native_frame_sequence_requested=True, ordinary_followup_explicit_qa_rearm=True,
                   staged_jar=spec['staged_jar'], properties=properties, client_started=False)
    (OUT / 'PREPARED_INPUTS.json').write_text(json.dumps(receipt, indent=2), 'utf8')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
