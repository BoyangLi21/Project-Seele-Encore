"""Prepare/launch independent tool-only input agent in the already existing isolated R10 flat fixture."""
from pathlib import Path
import argparse, hashlib, json, os, subprocess, time, zipfile

ROOT = Path(__file__).resolve().parents[1]
PREVIOUS = ROOT / 'artifacts/r52_native_finisher_candidate4/launch.json'
OUT = ROOT / 'artifacts/r52_native_ordinary_candidate5'
JDK = Path('C:/Users/liboy/jdks/jdk-17.0.19+10/bin')
ASM = Path('C:/Users/liboy/AppData/Roaming/.minecraft/libraries/org/ow2/asm/asm/9.8/asm-9.8.jar')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def quote(value):
    assert not any(c in value for c in '\r\n\0')
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def compile_tools(out):
    classes = out / 'tool_classes'
    classes.mkdir(parents=True, exist_ok=True)
    sources = [ROOT / 'tools/java/OrdinaryMotionR52Agent.java', ROOT / 'tools/java/OrdinaryMotionR52Attach.java']
    subprocess.run([str(JDK / 'javac.exe'), '-J-Xmx256m', '-cp', str(ASM), '-d', str(classes), *map(str, sources)], check=True)
    agent = out / 'ordinary_motion_agent.jar'
    with zipfile.ZipFile(agent, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('META-INF/MANIFEST.MF', 'Manifest-Version: 1.0\nAgent-Class: OrdinaryMotionR52Agent\nCan-Retransform-Classes: true\n\n')
        for file in classes.glob('OrdinaryMotionR52Agent*.class'):
            archive.write(file, file.name)
    receipt = dict(tool_sources={str(p.relative_to(ROOT)): digest(p) for p in sources}, tool_agent_sha256=digest(agent), production_build_invoked=False)
    (out / 'TOOL_COMPILE_RECEIPT.json').write_text(json.dumps(receipt, indent=2), 'utf8')
    print(json.dumps(receipt))


def prepare(out, handling_only=False):
    assert not (out / 'RUNNING.json').exists(), 'Preserve attempted native evidence'
    spec = json.loads(PREVIOUS.read_text('utf-8-sig'))
    world = Path(spec['world']).resolve()
    assert world.name == 'SEELE_FIRST_BATTLE_REVIEW_R10' and (world / 'level.dat').is_file()
    assert 'WORLD_R52' not in str(world)
    bundle = Path(spec['bundle_directory'])
    for name, expected in spec['runtime_fingerprints'].items():
        assert digest(bundle / name) == expected, name
    jar = Path(spec['staged_jar']['path'])
    with zipfile.ZipFile(jar) as archive:
        assert 'com/projectseele/entity/EvaProneLegSupportR52.class' in archive.namelist(), 'Latest Root-frozen JAR required'
        assert 'assets/projectseele/eva/prone_leg_support_hulls_r52.json' in archive.namelist()
        if handling_only:
            assert b'ordinaryStandingSupportLockedR52' in archive.read('com/projectseele/entity/EvaUnit01Entity.class'), 'Handling-only requires the C8 standing eligibility fix'
    command = [value for value in spec['command'] if not value.startswith('-Dprojectseele.firstBattle')
               and not any(value.startswith('-Dprojectseele.' + key + '=') for key in
                           ('regionalBuild', 'r47NativeCommandInbox', 'nativeReviewWorld', 'r44HandWitnessPath',
                            'ordinaryMotionWorldR52','ordinaryMotionOutputR52','nativeCollisionStatesR52','ordinaryHandlingOnlyR52'))]
    properties = dict(regionalBuild='ordinary-motion-r52', ordinaryMotionWorldR52=str(world),
                      ordinaryMotionOutputR52=str(out), r47NativeCommandInbox=str(out / 'commands.json'))
    if handling_only:properties['ordinaryHandlingOnlyR52']='true'
    command[1:1] = ['-Dprojectseele.' + name + '=' + value for name, value in properties.items()]
    command[1:1] = ['-XX:+EnableDynamicAgentLoading']
    for key in properties:assert sum(value.startswith('-Dprojectseele.'+key+'=') for value in command)==1,key
    spec.update(command=command, staged_jar=dict(path=str(jar), sha256=digest(jar)),
                world=str(world), properties=properties, ordinary_only=True, ready_to_launch=True)
    (out / 'launch.json').write_text(json.dumps(spec, indent=2), 'utf8')
    (out / 'launch.args').write_text('\n'.join(quote(value) for value in command[1:]) + '\n', 'utf8')
    (out / 'commands.json').write_text(json.dumps(dict(seq=1, commands=[])), 'utf8')
    (out / 'PREPARED_INPUTS.json').write_text(json.dumps(dict(staged_jar=spec['staged_jar'], world=str(world),
        bundle_directory=str(bundle), body_sha256=spec['runtime_fingerprints']['eva_body_r44.json'],
        reused_fixture=True, new_worlds=0, world_directory_copies=0, construction_world_access=False,
        production_source_modified=False, screenshots=True, profiler=False, properties=properties), indent=2), 'utf8')
    print('Prepared actual ordinary native run:', spec['staged_jar']['sha256'])


def start(out):
    assert not (out / 'RUNNING.json').exists(), 'Never overwrite an attempted native run'
    spec = json.loads((out / 'launch.json').read_text('utf8'))
    assert digest(Path(spec['staged_jar']['path'])) == spec['staged_jar']['sha256']
    log = (out / 'process.log').open('wb')
    error = (out / 'process.error.log').open('wb')
    env = dict(os.environ)
    env.update(spec.get('environment', {}))
    before = time.monotonic()
    process = subprocess.Popen([spec['command'][0], '@' + str(out / 'launch.args')], cwd=spec['workingDirectory'],
        env=env, stdout=log, stderr=error, creationflags=0x08000000)
    (out / 'RUNNING.json').write_text(json.dumps(dict(pid=process.pid, staged_jar=spec['staged_jar'],
        world=spec['world'], started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())), indent=2), 'utf8')
    print('Native ordinary started PID', process.pid, flush=True)
    attached = False
    while process.poll() is None and time.monotonic() - before < 600:
        text = (out / 'process.log').read_text('utf8', errors='replace')
        if not attached and 'logged in with entity id' in text:
            time.sleep(4)
            result = subprocess.run([str(JDK / 'java.exe'), '-cp', str(out / 'tool_classes'),
                'OrdinaryMotionR52Attach', str(process.pid), str(out / 'ordinary_motion_agent.jar')], capture_output=True, text=True)
            (out / 'attach.log').write_text(result.stdout + result.stderr, 'utf8')
            if result.returncode:
                print('Attach failed:', result.stderr[-2000:], flush=True)
                break
            attached = True
            print('Independent input/final pose/frame agent attached', flush=True)
        if (out / 'FAILURE.json').exists():
            print((out / 'FAILURE.json').read_text('utf8'), flush=True)
            break
        if attached and (out / 'CAPTURE_COMPLETE.json').exists():
            print('Native sequence and screenshot writer completed', flush=True)
        time.sleep(1)
    timed_out = process.poll() is None
    if timed_out:
        (out / 'commands.json').write_text(json.dumps(dict(seq=1000, commands=[], quit=True)), 'utf8')
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            pass
    log.close()
    error.close()
    result = dict(pid=process.pid, elapsed_seconds=time.monotonic() - before, exited=process.poll() is not None,
                  exit_code=process.poll(), attached=attached, timed_out=timed_out,
                  natural_review_exit=not timed_out and process.poll() == 0, native_visual_acceptance=False,
                  staged_jar=spec['staged_jar'], world=spec['world'])
    (out / 'RUN_RESULT.json').write_text(json.dumps(result, indent=2), 'utf8')
    print(json.dumps(result, indent=2), flush=True)
    assert not timed_out and process.returncode == 0 and (out / 'CAPTURE_COMPLETE.json').exists()
    assert json.loads((out / 'CAPTURE_COMPLETE.json').read_text('utf8'))['native_frames'] > 0, 'Input replay without native body/frame capture cannot qualify'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--previous',type=Path,default=PREVIOUS)
    parser.add_argument('--compile-tools', action='store_true')
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--handling-only', action='store_true')
    parser.add_argument('--start', action='store_true')
    args = parser.parse_args()
    PREVIOUS=args.previous.resolve()
    out = args.out.resolve()
    assert out.is_relative_to(ROOT / 'artifacts')
    out.mkdir(parents=True, exist_ok=True)
    if args.compile_tools:
        compile_tools(out)
    if args.prepare:
        prepare(out, args.handling_only)
    if args.start:
        start(out)
