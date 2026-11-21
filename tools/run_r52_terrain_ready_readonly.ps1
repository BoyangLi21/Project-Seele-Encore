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
if ($RootJavaProcessId -le 0) { throw 'An existing Root client PID is required; this tool never starts a game.' }
foreach ($ReportPath in @($Plan,$Output)) {
    if (-not $ReportPath.StartsWith($Candidate + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'Only candidate plan/report paths are allowed.' }
}
if (-not (Test-Path -LiteralPath $Plan)) { throw 'Prepare the concrete camera and required-section plan before observation.' }
if (Test-Path -LiteralPath $Output) { throw 'Preserve earlier camera observations; use a fresh output filename.' }
$Java = 'C:/Users/liboy/jdks/jdk-17.0.19+10/bin/java.exe'
$Classes = Join-Path $Repo '.Codex/r52_owner_draft/terrain_observer_classes'
$Agent = Join-Path $Repo '.Codex/r52_owner_draft/r52_terrain_ready_readonly_agent.jar'
& $Java --add-modules jdk.attach -cp $Classes R52TerrainReadyReadOnlyAttach $RootJavaProcessId $Agent $Plan $Output
if ($LASTEXITCODE -ne 0) { throw "Read-only terrain attachment failed with exit $LASTEXITCODE." }
Write-Output "Actual native observation scheduled; poll WAITING/READY/HOLD in $Output. No terrain or game option was changed."
