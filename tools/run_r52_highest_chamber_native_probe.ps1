param(
    [Parameter(Mandatory=$true)][int]$RootJavaProcessId,
    [Parameter(Mandatory=$true)][string]$Plan,
    [Parameter(Mandatory=$true)][string]$Output
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $PSScriptRoot
$Candidate = [IO.Path]::GetFullPath('D:/eva/artifacts/r52_fresh_from_r51_20261009/runtime_directory/candidate')
$Plan = [IO.Path]::GetFullPath($Plan)
$Output = [IO.Path]::GetFullPath($Output)
if ($RootJavaProcessId -le 0) { throw 'An existing actual QA client PID is required; the probe never launches a game.' }
foreach ($CandidatePath in @($Plan,$Output)) {
    if (-not $CandidatePath.StartsWith($Candidate + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'Candidate-only plan/report paths are required.' }
}
if (-not (Test-Path -LiteralPath $Plan)) { throw 'Prepare the exact final candidate plan before native interaction.' }
if (Test-Path -LiteralPath $Output) { throw 'Preserve previous native probe evidence; use a fresh filename.' }
$Java = 'C:/Users/liboy/jdks/jdk-17.0.19+10/bin/java.exe'
$Classes = Join-Path $Repo '.Codex/r52_owner_draft/chamber_probe_classes'
$Agent = Join-Path $Repo '.Codex/r52_owner_draft/r52_highest_chamber_native_probe_agent.jar'
& $Java --add-modules jdk.attach -cp $Classes R52HighestChamberNativeProbeAttach $RootJavaProcessId $Agent $Plan $Output
if ($LASTEXITCODE -ne 0) { throw "Native probe refused or failed to attach, exit $LASTEXITCODE." }
Write-Output "Actual native card/reader probe scheduled: $Output. Its PASS verifies only this permission/image contract; visual review remains separate."
