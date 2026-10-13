"""Prepare a metadata-only profile run on the existing R10 fixture; never launch or copy a world."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PREVIOUS = ROOT / 'artifacts/r52_native_finisher_runtime'
OUT = ROOT / 'artifacts/r52_native_finisher_profile'
GAME = Path('D:/eva/artifacts/r51_nonmap_release/native_r51/game')
WORLD = GAME / 'saves/SEELE_FIRST_BATTLE_REVIEW_R10'
JFC = ROOT / '.Codex/r52_first_battle_runtime/native_profile.jfc'


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true', help='Write launch text only; no launch, staging or world mutation')
    parser.add_argument('--output-directory', '--output', dest='output_directory', type=Path, default=OUT,
                        help='Fresh evidence directory under ROOT/artifacts/r52_native_finisher_profile*')
    args = parser.parse_args()
    out = args.output_directory.resolve()
    artifacts = (ROOT / 'artifacts').resolve()
    assert out.is_relative_to(artifacts) and out.relative_to(artifacts).parts[0].startswith('r52_native_finisher_profile'), 'Profile evidence must stay under ROOT/artifacts/r52_native_finisher_profile*'
    previous = json.loads((PREVIOUS / 'PREPARED_INPUTS.json').read_text('utf8'))
    spec = json.loads((PREVIOUS / 'launch.json').read_text('utf8'))
    bundle = Path(previous['bundle_directory']).resolve()
    contract = json.loads((bundle / 'combat_bundle_r44.json').read_text('utf8'))
    assert len(contract['files']) == 28
    fingerprints = {}
    for name, expected in contract['files'].items():
        file = (bundle / name).resolve()
        assert file.is_relative_to(bundle) and file.is_file(), 'Missing/unsafe bundle member: ' + name
        actual = digest(file)
        assert actual == expected == previous['runtime_fingerprints'][name], 'Old R51 comparison input changed: ' + name
        fingerprints[name] = actual
    assert digest(bundle / 'combat_bundle_r44.json') == previous['bundle_manifest_sha256']
    assert WORLD.resolve() == Path(spec['world']).resolve() and (WORLD / 'level.dat').is_file()
    assert not (WORLD / 'r10_resume_expected.json').exists(), 'Resume fixture would bypass fresh setup'
    review = WORLD / 'r10_first_battle_review.json'
    assert json.loads(review.read_text('utf8'))['passed'], 'Previous isolated fixture did not complete normally'
    jar = GAME / 'mods/projectseele-0.1.0-all.jar'
    with zipfile.ZipFile(jar) as archive:
        ready = (b'firstBattleFrameMetadataR52' in archive.read('com/projectseele/client/visual/FirstBattleR10Client.class')
                 and b'ownsAnatomicalHandsR52' in archive.read('com/projectseele/entity/FirstBattleClip.class'))
    assert JFC.is_file()
    print(json.dumps(dict(mode='prepare' if args.prepare else 'read_only_plan', world=str(WORLD),
                          reused_fixture=True, checked_bundle_files=len(fingerprints), staged_diagnostic_jar_ready=ready,
                          output=str(out), screenshots=False, bone_witness=False, client_started=False), indent=2))
    if not args.prepare:
        return
    assert ready, 'Root must stage the newly built metadata/conditional-hand JAR first'
    assert not out.exists(), 'Preserve existing profile evidence; use --output-directory for a fresh attempt directory'
    remove = ('regionalBuild', 'nativeReviewWorld', 'combatBundleDirectory', 'firstBattleReviewClip',
              'firstBattleMovieOnly', 'firstBattleNoFrameCaptureR52', 'firstBattleKeyFramesR52',
              'firstBattleFrameMetadataR52', 'firstBattleCaptureOutputR52', 'firstBattleRuntimeWitnessR52',
              'firstBattleRuntimeWitnessR52Output', 'r47NativeCommandInbox')
    command = [v for v in spec['command'] if not any(v.startswith('-Dprojectseele.' + key + '=') for key in remove)]
    props = dict(regionalBuild='r10-firstbattle', firstBattleMovieOnly='true', firstBattleNoFrameCaptureR52='true',
                 firstBattleKeyFramesR52='false', firstBattleFrameMetadataR52='true', firstBattleRuntimeWitnessR52='false',
                 combatBundleDirectory=str(bundle), firstBattleCaptureOutputR52=str(out / 'frame_metadata'),
                 r47NativeCommandInbox=str(out / 'commands.json'))
    command[1:1] = ['-Dprojectseele.' + key + '=' + value for key, value in props.items()]
    command[command.index('--gameDir') + 1] = str(GAME)
    command[command.index('--quickPlaySingleplayer') + 1] = WORLD.name
    out.mkdir(parents=True)
    staged = dict(path=str(jar), sha256=digest(jar))
    prepared = dict(command=command, environment=spec.get('environment', {}), workingDirectory=str(GAME),
                    world=str(WORLD), staged_jar=staged, jfr_settings=str(JFC), jfr_output=str(out / 'scene_profile.jfr'),
                    source_launch=str(PREVIOUS / 'launch.json'), reused_fixture=True, native_only=True)
    (out / 'launch.json').write_text(json.dumps(prepared, indent=2), 'utf8')
    (out / 'launch.args').write_text('\n'.join(quote(v) for v in command[1:]) + '\n', 'utf8')
    (out / 'commands.json').write_text(json.dumps(dict(seq=1, commands=[])), 'utf8')
    (out / 'previous_fixture_review.json').write_bytes(review.read_bytes())
    receipt = dict(staged_jar=staged, bundle_id=contract['bundle_id'], bundle_directory=str(bundle),
                   bundle_manifest_sha256=digest(bundle / 'combat_bundle_r44.json'), runtime_fingerprints=fingerprints,
                   jfr_settings_sha256=digest(JFC), properties=props, previous_native_evidence_preserved=True,
                   reused_fixture=True, fixture_level_sha256_before_launch=digest(WORLD / 'level.dat'),
                   fixture_restart='stage0 clears active encounter/discards old mobs; replay-tagged fresh angel bypasses completedPilots; no resume file',
                   world_or_asset_directory_copies=0, world_files_written_by_preparation=0, client_started=False)
    (out / 'PREPARED_INPUTS.json').write_text(json.dumps(receipt, indent=2), 'utf8')
    (out / 'run_hidden_profile.ps1').write_text(RUNNER, 'ascii')
    print('Prepared profile launch and JFR trigger text; no Java started, no world written')


RUNNER = r'''param([int]$TimeoutSeconds = 600, [int]$StartupTimeoutSeconds = 450, [int]$WarmupTimeoutSeconds = 150, [int]$SceneTimeoutSeconds = 90)
$ErrorActionPreference = 'Stop'
function Read-R52AppendedLines([IO.FileStream]$Stream, [object]$State) {
    # .NET Framework StreamReader.Peek caches EOF on redirected growing logs.
    # Read actual newly appended bytes and keep incomplete UTF-8/lines for later.
    $taskAvailable = $Stream.Length - $Stream.Position
    while ($taskAvailable -gt 0) {
        $taskBytes = [byte[]]::new([Math]::Min(65536, $taskAvailable))
        $taskRead = $Stream.Read($taskBytes, 0, $taskBytes.Length)
        if ($taskRead -eq 0) { break }
        $taskChars = [char[]]::new([Text.Encoding]::UTF8.GetMaxCharCount($taskRead))
        $taskCount = $State.decoder.GetChars($taskBytes, 0, $taskRead, $taskChars, 0, $false)
        $State.pending += [string]::new($taskChars, 0, $taskCount)
        $taskLastNewline = $State.pending.LastIndexOf("`n")
        if ($taskLastNewline -ge 0) {
            $taskComplete = $State.pending.Substring(0, $taskLastNewline)
            $State.pending = $State.pending.Substring($taskLastNewline + 1)
            foreach ($taskLine in $taskComplete.Split("`n")) { $taskLine.TrimEnd("`r") }
        }
        $taskAvailable = $Stream.Length - $Stream.Position
    }
}
$taskOut = $PSScriptRoot
$taskSpec = Get-Content -LiteralPath (Join-Path $taskOut 'launch.json') -Raw | ConvertFrom-Json
$taskJarHash = (Get-FileHash -LiteralPath $taskSpec.staged_jar.path -Algorithm SHA256).Hash.ToLowerInvariant()
if ($taskJarHash -ne $taskSpec.staged_jar.sha256) { throw 'Staged JAR changed after profile preparation' }
foreach ($entry in $taskSpec.environment.PSObject.Properties) { [Environment]::SetEnvironmentVariable($entry.Name, [string]$entry.Value, 'Process') }
$taskArgs = '@"' + (Join-Path $taskOut 'launch.args') + '"'
$taskLog = Join-Path $taskOut 'process.log'
$taskClock = [Diagnostics.Stopwatch]::StartNew()
$taskStarted = [DateTime]::UtcNow.ToString('o')
$taskProcess = Start-Process -FilePath $taskSpec.command[0] -ArgumentList $taskArgs -WorkingDirectory $taskSpec.workingDirectory -WindowStyle Hidden -RedirectStandardOutput $taskLog -RedirectStandardError (Join-Path $taskOut 'process.error.log') -PassThru
$taskProcessHandle = $taskProcess.Handle # Retain a live handle so Windows PowerShell can retrieve ExitCode after exit.
@{pid=$taskProcess.Id; started_utc=$taskStarted} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskOut 'RUNNING.json') -Encoding UTF8
$taskRecorderStarted = $false
$taskRecorderAt = $null
$taskRecorderExit = $null
$taskStream = $null
$taskReadState = [PSCustomObject]@{decoder=[Text.Encoding]::UTF8.GetDecoder(); pending=''}
$taskPhase = 'startup'
$taskPhaseStart = 0.0
$taskInGameAt = $null
$taskBoardedAt = $null
$taskWarmupTicks = 0
try {
    while (-not $taskProcess.HasExited -and $taskClock.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        $taskPhaseBudget = switch ($taskPhase) { 'startup' { $StartupTimeoutSeconds } 'warmup' { $WarmupTimeoutSeconds } 'scene' { $SceneTimeoutSeconds } 'shutdown' { 45 } }
        if ($taskClock.Elapsed.TotalSeconds - $taskPhaseStart -ge $taskPhaseBudget) { break }
            if ($null -eq $taskStream -and (Test-Path -LiteralPath $taskLog)) {
                $taskStream = [IO.FileStream]::new($taskLog, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
            }
            if ($null -ne $taskStream) {
                foreach ($taskLine in (Read-R52AppendedLines $taskStream $taskReadState)) {
                    if ($taskLine.Contains('Total time to load game and open world was')) { $taskInGameAt = [DateTime]::UtcNow.ToString('o') }
                    if ($taskPhase -eq 'startup' -and $taskLine.Contains('R10 BATTLE REVIEW PASS native_boarding')) { $taskPhase = 'warmup'; $taskPhaseStart = $taskClock.Elapsed.TotalSeconds; $taskBoardedAt = [DateTime]::UtcNow.ToString('o') }
                    $taskWarmupMatch = [regex]::Match($taskLine, 'R18 MOVIE WARMUP ticks=(\d+)')
                    if ($taskWarmupMatch.Success) { $taskWarmupTicks = [int]$taskWarmupMatch.Groups[1].Value }
                    if ($taskLine.Contains('R10 FIRST BATTLE COMPLETE')) { $taskPhase = 'shutdown'; $taskPhaseStart = $taskClock.Elapsed.TotalSeconds }
                    if (-not $taskRecorderStarted -and $taskLine.Contains('R10 FIRST BATTLE START')) {
                        $taskPhase = 'scene'; $taskPhaseStart = $taskClock.Elapsed.TotalSeconds
                        $taskRecorderStarted = $true
                        $taskRecorderAt = [DateTime]::UtcNow.ToString('o')
                        $taskJcmd = Join-Path (Split-Path $taskSpec.command[0]) 'jcmd.exe'
                        & $taskJcmd $taskProcess.Id JFR.start 'name=r52_first_battle' ('settings=' + $taskSpec.jfr_settings) 'duration=35s' ('filename=' + $taskSpec.jfr_output) 'maxsize=64m' 'disk=true' 'dumponexit=true' *> (Join-Path $taskOut 'JFR_START.log')
                        $taskRecorderExit = $LASTEXITCODE
                        break
                    }
                }
            }
        Start-Sleep -Milliseconds 250
    }
} finally { if ($null -ne $taskStream) { $taskStream.Dispose() } }
$taskTimedOut = -not $taskProcess.HasExited
if ($taskTimedOut) {
    @{seq=1000; commands=@(); quit=$true} | ConvertTo-Json -Compress | Set-Content -LiteralPath (Join-Path $taskOut 'commands.json') -Encoding ASCII
    $taskProcess.WaitForExit(30000) | Out-Null
}
$taskProcess.Refresh()
$taskExited = $taskProcess.HasExited
if ($taskExited) { $taskProcess.WaitForExit() } # Flush redirected output; this does not wait on a running process.
$taskClock.Stop()
$taskResult = @{started_utc=$taskStarted; in_game_utc=$taskInGameAt; boarded_utc=$taskBoardedAt; last_warmup_ticks=$taskWarmupTicks; elapsed_seconds=$taskClock.Elapsed.TotalSeconds; overall_timeout_seconds=$TimeoutSeconds; pid=$taskProcess.Id; timed_out=$taskTimedOut; timeout_phase=$taskPhase; exited=$taskExited; exit_code=$null; world=$taskSpec.world; reused_fixture=$true; natural_review_exit=($taskExited -and -not $taskTimedOut); jfr_triggered=$taskRecorderStarted; jfr_started_utc=$taskRecorderAt; jfr_start_exit_code=$taskRecorderExit; jfr_path=$taskSpec.jfr_output}
if ($taskExited) { $taskResult.exit_code = $taskProcess.ExitCode }
$taskResult | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskOut 'RUN_RESULT.json') -Encoding UTF8
Write-Output ('R52 profile review elapsed seconds: ' + [Math]::Round($taskClock.Elapsed.TotalSeconds, 2))
if (-not $taskExited -or $taskTimedOut) { throw 'Profile deadline exceeded; normal stop requested, no process kill' }
if ($taskProcess.ExitCode -ne 0) { throw ('Client exit code: ' + $taskProcess.ExitCode) }
if (-not $taskRecorderStarted -or $taskRecorderExit -ne 0) { throw 'JFR recording did not start at battle trigger' }
'''

if __name__ == '__main__':
    main()
