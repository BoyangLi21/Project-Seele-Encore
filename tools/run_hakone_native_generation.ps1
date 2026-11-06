param(
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [Parameter(Mandatory=$true)][string]$CacheDirectory,
    [Parameter(Mandatory=$true)][string]$Repository,
    [Parameter(Mandatory=$true)][string]$Java,
    [Parameter(Mandatory=$true)][string]$IsolationAgent
)
$ErrorActionPreference = 'Stop'
$taskOut = (Resolve-Path -LiteralPath $OutputDirectory).Path
$taskCache = (Resolve-Path -LiteralPath $CacheDirectory).Path
$taskRepo = (Resolve-Path -LiteralPath $Repository).Path
$taskPlan = Get-Content -LiteralPath (Join-Path $taskOut 'plan.json') -Raw | ConvertFrom-Json
$taskWorld = [System.IO.Path]::GetFullPath((Join-Path $taskCache 'SEELE_R53_WORLD'))
if ($taskWorld -ne [System.IO.Path]::GetFullPath($taskPlan.cache_world) -or $taskCache -notmatch '[\\/]cache-server$') { throw 'Use the explicitly prepared isolated cache only' }
$taskLog = Join-Path $taskOut 'stdout.log'
$taskErr = Join-Path $taskOut 'stderr.log'
$taskReceipt = Join-Path $taskOut 'input-isolation.json'
foreach ($taskFile in @($taskLog,$taskErr,$taskReceipt,(Join-Path $taskOut 'normal-stop.json'))) {
    if (Test-Path -LiteralPath $taskFile) { throw 'Fresh generation outputs required' }
}
$taskProperties = Join-Path $taskCache 'server.properties'
Copy-Item -LiteralPath $taskProperties -Destination (Join-Path $taskOut 'server.properties.before')
$taskConfig = [System.IO.File]::ReadAllText($taskProperties) -replace '(?m)^max-tick-time=.*$', 'max-tick-time=300000'
[System.IO.File]::WriteAllText($taskProperties,$taskConfig,(New-Object System.Text.UTF8Encoding($false)))
$taskProcess = $null
$taskStopSent = $false
try {
    $taskProcess = Start-Process -FilePath $Java -ArgumentList '@user_jvm_args.txt','@libraries/net/minecraftforge/forge/1.20.1-47.4.10/win_args.txt','nogui' -WorkingDirectory $taskCache -WindowStyle Hidden -RedirectStandardOutput $taskLog -RedirectStandardError $taskErr -PassThru
    $taskProcess.Id | Set-Content -LiteralPath (Join-Path $taskOut 'pid.txt')
    Write-Output "Started isolated native generation; requested $($taskPlan.chunks.Count) chunks"
    $taskDeadline = (Get-Date).AddMinutes(4)
    do {
        Start-Sleep -Milliseconds 400
        $taskProcess.Refresh()
        if ($taskProcess.HasExited) { throw 'Cache exited before isolation gate' }
        $taskReady = (Test-Path -LiteralPath $taskLog) -and (Select-String -LiteralPath $taskLog -Pattern 'Preparing saved mechanical resources before world simulation|Preparing level ' -Quiet)
    } until ($taskReady -or (Get-Date) -gt $taskDeadline)
    if (-not $taskReady) { throw 'Cache initialization gate timed out' }
    & $Java -cp (Join-Path $taskRepo '.Codex/native1023') R53ReadOnlyAttach1023 $taskProcess.Id $IsolationAgent $taskReceipt
    if ($LASTEXITCODE -ne 0) { throw 'Cache isolation attach failed' }
    $taskDeadline = (Get-Date).AddMinutes(5)
    do {
        Start-Sleep -Milliseconds 500
        $taskProcess.Refresh()
        if ($taskProcess.HasExited) { throw 'Cache exited during initialization' }
        $taskReady = Select-String -LiteralPath $taskLog -Pattern 'Done \(' -Quiet
    } until ($taskReady -or (Get-Date) -gt $taskDeadline)
    if (-not $taskReady) { throw 'Cache initialization timed out' }
    & $Java -cp (Join-Path $taskRepo '.Codex/native1023') R53ReadOnlyAttach1023 $taskProcess.Id (Join-Path $taskOut 'native-generate.jar') $taskOut
    if ($LASTEXITCODE -ne 0) { throw 'Native generation attach failed' }
    Write-Output 'Isolated native generation attached'
    $taskDeadline = (Get-Date).AddMinutes(60)
    do {
        Start-Sleep -Seconds 2
        $taskProcess.Refresh()
        if ($taskProcess.HasExited) { throw 'Cache exited during generation' }
        if (Test-Path -LiteralPath (Join-Path $taskOut 'error.txt')) { throw (Get-Content -LiteralPath (Join-Path $taskOut 'error.txt') -Raw) }
        $taskComplete = $false
        if (Test-Path -LiteralPath (Join-Path $taskOut 'progress.json')) {
            try { $taskProgress = Get-Content -LiteralPath (Join-Path $taskOut 'progress.json') -Raw | ConvertFrom-Json; $taskComplete = $taskProgress.generated } catch { $taskComplete = $false }
        }
    } until ($taskComplete -or (Get-Date) -gt $taskDeadline)
    if (-not $taskComplete) { throw 'Native generation deadline reached' }
    & $Java -cp (Join-Path $taskRepo '.Codex/native1023') R53ReadOnlyAttach1023 $taskProcess.Id (Join-Path $taskRepo '.Codex/cache-stop-r55.jar') ($taskWorld + '|' + (Join-Path $taskOut 'normal-stop.json'))
    if ($LASTEXITCODE -ne 0) { throw 'Ordinary cache stop failed' }
    $taskStopSent = $true
    Write-Output 'Native generation complete; ordinary stop submitted'
} finally {
    if ($null -ne $taskProcess) {
        $taskProcess.Refresh()
        if (-not $taskProcess.HasExited -and -not $taskStopSent) {
            & $Java -cp (Join-Path $taskRepo '.Codex/native1023') R53ReadOnlyAttach1023 $taskProcess.Id (Join-Path $taskRepo '.Codex/cache-stop-r55.jar') ($taskWorld + '|' + (Join-Path $taskOut 'failure-stop.json'))
        }
        if (-not $taskProcess.HasExited) { Wait-Process -Id $taskProcess.Id -Timeout 60 -ErrorAction SilentlyContinue }
        $taskProcess.Refresh()
        if (-not $taskProcess.HasExited) { throw 'Cache still running after ordinary stop; inspect before any world IO' }
    }
    Copy-Item -LiteralPath (Join-Path $taskOut 'server.properties.before') -Destination $taskProperties
}
Write-Output 'Isolated cache stopped; server properties restored'

