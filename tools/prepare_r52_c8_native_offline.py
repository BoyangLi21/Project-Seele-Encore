"""Pure offline C8 launch/tool preflight. No game staging, world writes, attach or launch."""
from pathlib import Path
import argparse, hashlib, json, os, subprocess, sys, zipfile
from release_r45_contract import class_protocol

ROOT = Path(__file__).resolve().parents[1]
JDK = Path('C:/Users/liboy/jdks/jdk-17.0.19+10/bin')
ASM_DIR = Path('C:/Users/liboy/AppData/Roaming/.minecraft/libraries/org/ow2/asm')
ASM = [ASM_DIR / (name + '/9.8/' + name + '-9.8.jar') for name in ('asm', 'asm-tree', 'asm-analysis')]
PREVIOUS = ROOT / 'artifacts/r52_native_combined_candidate7/launch.json'
RUNTIME = ROOT / 'artifacts/r52_runtime_candidate/projectseele-local-maps'
FUTURE = ROOT / 'artifacts/r52_native_combined_candidate8'
GAME = Path('D:/eva/artifacts/r51_nonmap_release/native_r51/game')
BODY_SHA = 'cd9ba815c44a6ca60824417ae76b25de9db1936b655ec035b62775fa41d380f9'
CLIP_SHA = '5164edbb96722e37e97fe5d0f002e2cbf157d6824a9c652b48430a89ca207873'

def sha(p):
    with Path(p).open('rb') as stream:return hashlib.file_digest(stream, 'sha256').hexdigest()

def read(p):return json.loads(Path(p).read_text('utf-8-sig'))

def write(p, d):Path(p).write_text(json.dumps(d, indent=2) + '\n', 'utf8')

def quote(v):
    assert not any(c in v for c in '\r\n\0')
    return '"' + v.replace('\\', '\\\\').replace('"', '\\"') + '"'

def unique_properties(command):
    rows = {}
    for arg in command:
        if arg.startswith('-D'):
            name, _, value = arg[2:].partition('=')
            assert name not in rows, 'Duplicate JVM property: ' + name
            rows[name] = value
    return rows

def checked_run(command, log, env=None):
    r = subprocess.run(command, capture_output=True, text=True, encoding='utf8', errors='replace', env=env)
    Path(log).write_text(r.stdout + r.stderr, 'utf8')
    assert r.returncode == 0, str(log) + ': ' + (r.stdout + r.stderr)[-2000:]
    return r.stdout.strip()

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--jar', required=True, type=Path)
    ap.add_argument('--jar-sha256', required=True)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--baseline-only', action='store_true', help='Validate tools/schema using C7; never qualifies C8')
    args = ap.parse_args()
    jar, out = args.jar.resolve(), args.out.resolve()
    assert ROOT == Path('C:/Users/liboy/.codex/worktrees/r51-nonmap/eva')
    assert jar.is_relative_to(ROOT / 'artifacts') and jar.is_file()
    assert out.is_relative_to(ROOT / 'artifacts') and out != FUTURE
    assert len(args.jar_sha256) == 64 and sha(jar) == args.jar_sha256
    assert not out.exists(), 'Use a fresh offline preflight output; retain prior attempts'
    assert not FUTURE.exists(), 'Future native output must be entirely new'
    for dependency in ASM:assert dependency.is_file()
    selection_path = ROOT / 'artifacts/r52_runtime_candidate/MOTION_RUNTIME_SELECTION_RECEIPT.json'
    selection = read(selection_path)
    contract = read(RUNTIME / 'combat_bundle_r44.json')
    assert set(contract['files']) == set(selection['files']) and len(contract['files']) == 28
    for name, digest in contract['files'].items():assert sha(RUNTIME / name) == digest
    assert contract['files']['eva_body_r44.json'] == BODY_SHA
    assert contract['files']['first_battle_r44.json'] == CLIP_SHA
    with zipfile.ZipFile(jar) as z:
        assert len(z.namelist()) == len(set(z.namelist()))
        assert class_protocol(z.read('com/projectseele/network/SeeleNetwork.class')) == '69'
        for name, row in selection['required_jar_assets'].items():
            assert hashlib.sha256(z.read(name)).hexdigest() == row['selected_sha256'], name
        handling_fix = b'ordinaryStandingSupportLockedR52' in z.read('com/projectseele/entity/EvaUnit01Entity.class')
        weapon_guard_fix = b'retainNormalWeaponHistoryR52' in z.read('com/projectseele/client/render/EvaPoseTransition.class')
        assert args.baseline_only or handling_fix, 'C8 standing eligibility fix absent'
        assert args.baseline_only or weapon_guard_fix, 'C8 ordinary weapon guard exit fix absent'
    previous = read(PREVIOUS)
    world = Path(previous['world']).resolve()
    assert world == GAME.resolve() / 'saves/SEELE_FIRST_BATTLE_REVIEW_R10'
    assert 'WORLD_R52' not in str(world) and world.name == 'SEELE_FIRST_BATTLE_REVIEW_R10'
    assert (world / 'level.dat').is_file() and not (world / 'r10_resume_expected.json').exists()
    command = [v for v in previous['command'] if not v.startswith('-Dprojectseele.')]
    command = [v for v in command if v != '-XX:+EnableDynamicAgentLoading']
    properties = dict(regionalBuild='r10-firstbattle', firstBattleMovieOnly='true',
        firstBattleBerserkReviewR52='true', firstBattleFollowupOrdinaryReviewR52='false',
        firstBattleControlRecoveryCaptureR52='false', firstBattleCloseViewsR52='true',
        firstBattleNoFrameCaptureR52='false', firstBattleKeyFramesR52='false', firstBattleFrameMetadataR52='false',
        firstBattleRuntimeWitnessR52='true', firstBattleReviewClip=str(RUNTIME / 'first_battle_r44.json'),
        firstBattleCaptureOutputR52=str(FUTURE / 'firstbattle/frames'),
        firstBattleRuntimeWitnessR52Output=str(FUTURE / 'firstbattle/native.jsonl'),
        firstBattleThenOrdinaryR52='true', firstBattleThenHandlingR52='true', ordinaryHandlingOnlyR52='true',
        ordinaryMotionWorldR52=str(world), ordinaryMotionOutputR52=str(FUTURE / 'ordinary'),
        r47NativeCommandInbox=str(FUTURE / 'commands.json'), combatBundleDirectory=str(RUNTIME))
    command[1:1] = ['-Dprojectseele.' + k + '=' + v for k, v in properties.items()]
    command[1:1] = ['-XX:+EnableDynamicAgentLoading']
    actual_properties = unique_properties(command)
    assert all(actual_properties['projectseele.' + k] == v for k, v in properties.items())
    assert Path(command[command.index('--gameDir') + 1]).resolve() == GAME.resolve()
    assert command[command.index('--quickPlaySingleplayer') + 1] == world.name
    for key in ('firstBattleCaptureOutputR52', 'firstBattleRuntimeWitnessR52Output', 'ordinaryMotionOutputR52', 'r47NativeCommandInbox'):
        assert Path(properties[key]).is_relative_to(FUTURE) and not Path(properties[key]).exists()
    for arg in command:assert 'candidate7' not in arg or arg in command[command.index('-cp') + 1:command.index('-cp') + 2], 'Old candidate output in command'
    out.mkdir(parents=True)
    planned = dict(command=command, environment=previous.get('environment', {}), workingDirectory=str(GAME),
        world=str(world), immutable_jar=dict(path=str(jar), sha256=args.jar_sha256),
        staged_jar=dict(path=str(GAME / 'mods/projectseele-0.1.0-all.jar'), sha256=args.jar_sha256),
        bundle_directory=str(RUNTIME), runtime_fingerprints=contract['files'], candidate_sha256=CLIP_SHA,
        properties=properties, native_output=str(FUTURE), ready_to_launch=False,
        staging_pending=True, offline_only=True, baseline_only=args.baseline_only)
    write(out / 'PLANNED_LAUNCH.json', planned)
    (out / 'PLANNED_LAUNCH.args').write_text('\n'.join(quote(v) for v in command[1:]) + '\n', 'utf8')
    compile_dir = out / 'tool_classes'; compile_dir.mkdir()
    sources = [ROOT / 'tools/java' / n for n in ('OrdinaryMotionR52Agent.java', 'OrdinaryMotionR52Attach.java', 'VerifyC8ToolModesR52.java')]
    cp = ';'.join(map(str, ASM))
    checked_run([str(JDK / 'javac.exe'), '-J-Xmx256m', '-cp', cp, '-d', str(compile_dir), *map(str, sources)], out / 'compile.log')
    agent = out / 'ordinary_motion_agent.jar'
    with zipfile.ZipFile(agent, 'x', zipfile.ZIP_DEFLATED) as z:
        z.writestr('META-INF/MANIFEST.MF', 'Manifest-Version: 1.0\nAgent-Class: OrdinaryMotionR52Agent\nCan-Retransform-Classes: true\n\n')
        for p in compile_dir.glob('OrdinaryMotionR52Agent*.class'):z.write(p, p.name)
    env = dict(os.environ)
    env.update(R52_PREFLIGHT_OUT=str(out), R52_PREFLIGHT_JAR=str(jar), R52_PREFLIGHT_SHA256=args.jar_sha256,
               R52_PREFLIGHT_LAUNCH=str(out / 'PLANNED_LAUNCH.json'),
               R52_PREFLIGHT_HANDLING_ONLY='false' if args.baseline_only else 'true')
    reflected = checked_run([sys.executable, str(ROOT / '.codex/r52_ordinary_extended_preflight.py')], out / 'reflection.log', env)
    reflection = read(out / 'EXTENDED_CLASSFILE_REFLECTION_PREFLIGHT.json')
    assert not reflection['failed'] and len(reflection['checks']) >= 146
    client_jar = reflection['classes']['net.minecraft.client.Minecraft']['source']
    transformed = checked_run([str(JDK / 'java.exe'), '-cp', str(compile_dir) + ';' + cp,
        'VerifyC8ToolModesR52', str(jar), client_jar, str(out / 'verified_transforms')], out / 'transform.log')
    receipt = dict(schema='projectseele.r52.c8-offline-preflight.v1', immutable_jar=planned['immutable_jar'],
        baseline_only=args.baseline_only, C8_qualified=not args.baseline_only and handling_fix and weapon_guard_fix,
        source_root=str(ROOT), expected_native_output=str(FUTURE), runtime_contract_sha256=sha(RUNTIME / 'combat_bundle_r44.json'),
        selected_clip_sha256=CLIP_SHA, preserved_body_sha256=BODY_SHA, four_uv_members=4, protocol=69,
        unique_jvm_properties=len(actual_properties), property_keys_unique=True, planned_outputs_entirely_new=True,
        reflection_checks=len(reflection['checks']), reflection_failed=reflection['failed'],
        attach_modes_and_transformed_stacks=transformed, tool_agent_sha256=sha(agent),
        tool_sources={str(p.relative_to(ROOT)): sha(p) for p in sources},
        sequence=dict(final_C12_movies=1, repeated_ordinary_movie=0, ordinary_variants=[1], ordinary_ticks=210,
                      handling_exit_each_render_pose_ticks=[150,185], actual_transition_history_readback=True,
                      raw_first_and_first_berserk_main_draw_metadata=True, raw_eye_pixels_require_visible_actual_frame=True),
        planned_launch_sha256=sha(out / 'PLANNED_LAUNCH.json'), planned_args_sha256=sha(out / 'PLANNED_LAUNCH.args'),
        world_read_only=True, world_written=False, game_written=False, game_started=False, attach_executed=False,
        native_acceptance=False, user_artistic_acceptance=False,
        pending=['Root immutable C8 JAR and fresh qualified preflight'] if args.baseline_only else ['Root-controlled staging and native run'])
    write(out / 'OFFLINE_PREFLIGHT_RECEIPT.json', receipt)
    print(json.dumps(dict(passed=True, C8_qualified=receipt['C8_qualified'], baseline_only=args.baseline_only,
        reflection_checks=receipt['reflection_checks'], native_output=str(FUTURE), game_started=False, receipt=str(out / 'OFFLINE_PREFLIGHT_RECEIPT.json'))))

if __name__ == '__main__':main()
