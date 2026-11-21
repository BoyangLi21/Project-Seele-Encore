param(
    [Parameter(Mandatory=$true)][int]$RootJavaProcessId,
    [ValidateSet('parse','held','lifecycle')][string]$Mode = 'parse',
    [string]$Bundle,
    [string]$Output
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $PSScriptRoot
$Base = 'D:/eva/artifacts/r52_fresh_from_r51_20261009/runtime_directory'
$Candidate = [IO.Path]::GetFullPath((Join-Path $Base 'candidate'))
$Java = 'C:/Users/liboy/jdks/jdk-17.0.19+10/bin/java.exe'
$Classes = Join-Path $Repo '.Codex/r52_owner_draft/parser_agent_classes'
if ($RootJavaProcessId -le 0) { throw 'Actual existing Root JVM process ID required; this script never starts a game.' }
if ($Mode -in @('parse','lifecycle')) {
    if (-not $Bundle) { $Bundle = Join-Path $Candidate 'ROOT_ASSEMBLY_BUNDLE.json' }
    if (-not $Output) { $Output = Join-Path $Candidate $(if ($Mode -eq 'parse') { 'PRODUCTION_READONLY_PARSER.json' } else { 'NATIVE_RESTART_ORIGINAL_UUIDS.json' }) }
    $Bundle = [IO.Path]::GetFullPath($Bundle)
    if (-not $Bundle.StartsWith($Candidate + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Candidate-only bundle required.' }
    if (-not (Test-Path -LiteralPath $Bundle)) { throw 'Build the concrete candidate bundle before attaching its parser.' }
    if ($Mode -eq 'parse') { $Agent = Join-Path $Repo '.Codex/r52_owner_draft/r52_bundle_readonly_parser_agent.jar'; $Attach = 'R52BundleReadOnlyParserAttach' }
    else { $Agent = Join-Path $Repo '.Codex/r52_owner_draft/r52_lifecycle_readonly_agent.jar'; $Attach = 'R52LifecycleReadOnlyAttach' }
    $Input = $Bundle
} else {
    if (-not $Output) { $Output = Join-Path $Candidate 'NATIVE_SERVICE_HELD_CAPTURE.json.gz' }
    $Agent = Join-Path $Repo '.Codex/r52_owner_draft/r52_held_source_readonly_agent.jar'
    $Attach = 'R52HeldSourceReadOnlyAttach'
    $Input = Join-Path $Base 'units/ROOT_UNITS.json'
}
$Output = [IO.Path]::GetFullPath($Output)
if (-not $Output.StartsWith($Candidate + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Candidate-only report output required.' }
& $Java --add-modules jdk.attach -cp $Classes $Attach $RootJavaProcessId $Agent $Input $Output
if ($LASTEXITCODE -ne 0) { throw "Read-only attachment failed with exit $LASTEXITCODE. No install or actor change was requested." }
Write-Output "Read-only request scheduled on the real server thread: $Output"
