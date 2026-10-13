"""Prepare one tiny flat R10 fixture and launch text; never start Java or copy assets."""
from pathlib import Path
import argparse, hashlib, json, time, zipfile
import nbtlib

ROOT = Path(__file__).resolve().parents[1]
QA = Path('D:/eva/artifacts/r51_nonmap_release/native_r51')
GAME = QA / 'game'
WORLD = GAME / 'saves/SEELE_FIRST_BATTLE_REVIEW_R10'
TEMPLATE = Path('D:/eva/run/saves/SEELE_EVA_MOTION_LAB/level.dat')
OUT = ROOT / 'artifacts/r52_native_finisher_runtime'


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def quote(value):
    if any(c in value for c in '\r\n\0'):
        raise ValueError('Single-line Java arguments required')
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def jar_ready(jar):
    with zipfile.ZipFile(jar) as archive:
        return (json.loads(archive.read('data/projectseele/dimension_type/geofront.json'))['min_y'] == -960
                and b'firstBattleKeyFramesR52' in archive.read('com/projectseele/client/visual/FirstBattleR10Client.class')
                and any('FirstBattleRuntimeWitnessR52' in name for name in archive.namelist()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true', help='Write the new fixture and launch text; no launch')
    parser.add_argument('--bundle', type=Path, default=GAME / 'projectseele-local-maps')
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    contract = json.loads((bundle / 'combat_bundle_r44.json').read_text('utf8'))
    fingerprints = {}
    for name, expected in contract['files'].items():
        file = (bundle / name).resolve()
        assert file.is_relative_to(bundle) and file.is_file(), 'Missing/unsafe bundle member: ' + name
        actual = digest(file)
        assert actual == expected, 'Matched bundle required: ' + name
        fingerprints[name] = actual
    level = nbtlib.load(TEMPLATE)
    data = level['Data']
    generator = data['WorldGenSettings']['dimensions']['minecraft:overworld']['generator']
    assert str(generator['type']) == 'minecraft:flat'
    assert sum(int(row['height']) for row in generator['settings']['layers']) == 4
    assert len(TEMPLATE.read_bytes()) < 100000
    jar = GAME / 'mods/projectseele-0.1.0-all.jar'
    ready = jar.is_file() and jar_ready(jar)
    print(json.dumps(dict(world=str(WORLD), template_bytes=TEMPLATE.stat().st_size,
                          template_sha256=digest(TEMPLATE), bundle_id=contract['bundle_id'],
                          checked_bundle_files=len(fingerprints), staged_r52_jar_ready=ready,
                          output=str(OUT), mode='prepare' if args.prepare else 'read_only_plan'), indent=2))
    if not args.prepare:
        return
    assert ready, 'Root must stage the newly built R52 JAR with witness/keyframe code first'
    assert WORLD.parent.resolve() == (GAME / 'saves').resolve() and not WORLD.exists(), 'Never overwrite/reuse a prior review cycle'
    assert not (OUT / 'launch.json').exists(), 'Preserve the existing prepared/run evidence'
    # No old registry snapshot, player, event state, region or datapack is imported.
    level.pop('fml', None)
    for key in ('Player', 'CustomBossEvents', 'ScheduledEvents', 'WanderingTraderId', 'DragonFight'):
        data.pop(key, None)
    data['LevelName'] = nbtlib.String('SEELE R52 isolated first-battle runtime fixture')
    for key, value in [('SpawnX', 0), ('SpawnY', -59), ('SpawnZ', -18), ('GameType', 1)]:
        data[key] = nbtlib.Int(value)
    data['SpawnAngle'] = nbtlib.Float(0)
    data['allowCommands'] = nbtlib.Byte(1)
    data['Time'] = data['DayTime'] = nbtlib.Long(6000)
    data['LastPlayed'] = nbtlib.Long(int(time.time() * 1000))
    data['GameRules']['spawnRadius'] = nbtlib.String('0')
    packs = data['DataPacks']
    packs['Enabled'] = nbtlib.List[nbtlib.String]([p for p in packs['Enabled'] if not str(p).startswith('file/')])
    spec = json.loads((QA / 'launch.json').read_text('utf8'))
    remove = ('r47NativeCommandInbox', 'regionalBuild', 'nativeReviewWorld', 'combatBundleDirectory',
              'firstBattleReviewClip', 'firstBattleMovieOnly', 'firstBattleNoFrameCaptureR52',
              'firstBattleKeyFramesR52', 'firstBattleCaptureOutputR52', 'firstBattleRuntimeWitnessR52',
              'firstBattleRuntimeWitnessR52Output')
    command = [v for v in spec['command'] if not any(v.startswith('-Dprojectseele.' + key + '=') for key in remove)]
    for key, value in [('--gameDir', str(GAME)), ('--quickPlaySingleplayer', WORLD.name), ('--width', '1280'), ('--height', '720')]:
        command[command.index(key) + 1] = value
    props = dict(regionalBuild='r10-firstbattle', firstBattleMovieOnly='true',
                 firstBattleNoFrameCaptureR52='true', firstBattleKeyFramesR52='true',
                 firstBattleRuntimeWitnessR52='true', combatBundleDirectory=str(bundle),
                 firstBattleCaptureOutputR52=str(OUT / 'keyframes'),
                 firstBattleRuntimeWitnessR52Output=str(OUT / 'native.jsonl'),
                 r47NativeCommandInbox=str(OUT / 'commands.json'))
    command[1:1] = ['-Dprojectseele.' + key + '=' + value for key, value in props.items()]
    OUT.mkdir(parents=True, exist_ok=True)
    WORLD.mkdir()
    level.save(WORLD / 'level.dat', gzipped=True)
    assert not any((WORLD / name).exists() for name in ('region', 'entities', 'playerdata', 'datapacks'))
    staged = dict(path=str(jar), sha256=digest(jar))
    prepared = dict(command=command, environment=spec.get('environment', {}), workingDirectory=str(GAME),
                    world=str(WORLD), staged_jar=staged, source_template=str(TEMPLATE), native_only=True)
    (OUT / 'launch.json').write_text(json.dumps(prepared, indent=2), 'utf8')
    (OUT / 'launch.args').write_text('\n'.join(quote(v) for v in command[1:]) + '\n', 'utf8')
    (OUT / 'commands.json').write_text(json.dumps(dict(seq=1, commands=[])), 'utf8')
    receipt = dict(template_sha256=digest(TEMPLATE), level_dat_sha256=digest(WORLD / 'level.dat'),
                   staged_jar=staged, bundle_id=contract['bundle_id'], bundle_directory=str(bundle),
                   bundle_manifest_sha256=digest(bundle / 'combat_bundle_r44.json'), runtime_fingerprints=fingerprints,
                   properties=props, world_or_asset_directory_copies=0, client_started=False)
    (OUT / 'PREPARED_INPUTS.json').write_text(json.dumps(receipt, indent=2), 'utf8')
    (OUT / 'run_hidden.ps1').write_text(RUNNER, 'ascii')
    print('Prepared isolated level.dat and launch text; no Java started')


RUNNER = r'''param([int]$TimeoutSeconds = 240)
$ErrorActionPreference = 'Stop'
$taskOut = $PSScriptRoot
$taskSpec = Get-Content -LiteralPath (Join-Path $taskOut 'launch.json') -Raw | ConvertFrom-Json
$taskJarHash = (Get-FileHash -LiteralPath $taskSpec.staged_jar.path -Algorithm SHA256).Hash.ToLowerInvariant()
if ($taskJarHash -ne $taskSpec.staged_jar.sha256) { throw 'Staged JAR changed after preparation' }
foreach ($entry in $taskSpec.environment.PSObject.Properties) {
    [Environment]::SetEnvironmentVariable($entry.Name, [string]$entry.Value, 'Process')
}
$taskArgs = '@"' + (Join-Path $taskOut 'launch.args') + '"'
$taskClock = [Diagnostics.Stopwatch]::StartNew()
$taskStarted = [DateTime]::UtcNow.ToString('o')
$taskProcess = Start-Process -FilePath $taskSpec.command[0] -ArgumentList $taskArgs -WorkingDirectory $taskSpec.workingDirectory -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskOut 'process.log') -RedirectStandardError (Join-Path $taskOut 'process.error.log') -PassThru
$taskTimedOut = -not $taskProcess.WaitForExit($TimeoutSeconds * 1000)
if ($taskTimedOut) {
    @{seq=1000; commands=@(); quit=$true} | ConvertTo-Json -Compress | Set-Content -LiteralPath (Join-Path $taskOut 'commands.json') -Encoding ASCII
    $taskProcess.WaitForExit(30000) | Out-Null
}
$taskProcess.Refresh()
$taskExited = $taskProcess.HasExited
$taskClock.Stop()
$taskResult = @{started_utc=$taskStarted; elapsed_seconds=$taskClock.Elapsed.TotalSeconds; pid=$taskProcess.Id; timed_out=$taskTimedOut; exited=$taskExited; exit_code=$null; world=$taskSpec.world; natural_review_exit=($taskExited -and -not $taskTimedOut)}
if ($taskExited) { $taskResult.exit_code = $taskProcess.ExitCode }
$taskResult | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskOut 'RUN_RESULT.json') -Encoding UTF8
Write-Output ('R52 native review elapsed seconds: ' + [Math]::Round($taskClock.Elapsed.TotalSeconds, 2))
if (-not $taskExited -or $taskTimedOut) { throw 'Review deadline exceeded; requested normal client stop, no process kill' }
if ($taskProcess.ExitCode -ne 0) { throw ('Client exit code: ' + $taskProcess.ExitCode) }
'''

if __name__ == '__main__':
    main()
