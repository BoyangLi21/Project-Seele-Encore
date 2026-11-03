param(
 [Parameter(Mandatory=$true)][string]$ArtifactRoot,
 [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9-]+$')][string]$BatchName,
 [Parameter(Mandatory=$true)][string]$CacheServer,
 [Parameter(Mandatory=$true)][string]$Repository,
 [Parameter(Mandatory=$true)][string]$Java
)
$ErrorActionPreference = 'Stop'
$taskLog = Join-Path $ArtifactRoot "work\$BatchName-stdout.log"
$taskErr = Join-Path $ArtifactRoot "work\$BatchName-stderr.log"
$taskReceipt = Join-Path $ArtifactRoot "$BatchName\input-isolation.json"
if (Test-Path -LiteralPath $taskReceipt) { throw 'Fresh isolation receipt required' }
$taskProcess = Start-Process -FilePath $Java -ArgumentList '@user_jvm_args.txt','@libraries/net/minecraftforge/forge/1.20.1-47.4.10/win_args.txt','nogui' -WorkingDirectory $CacheServer -WindowStyle Hidden -RedirectStandardOutput $taskLog -RedirectStandardError $taskErr -PassThru
$taskProcess.Id | Set-Content -LiteralPath (Join-Path $ArtifactRoot "work\$BatchName-pid.txt")
Write-Output "Started isolated cache PID $($taskProcess.Id)"
$taskDeadline = (Get-Date).AddMinutes(4)
do {
 Start-Sleep -Milliseconds 400
 $taskProcess.Refresh()
 if ($taskProcess.HasExited) { throw "Cache exited with $($taskProcess.ExitCode)" }
 $taskReady = (Test-Path -LiteralPath $taskLog) -and (Select-String -LiteralPath $taskLog -Pattern 'Preparing saved mechanical resources before world simulation|Preparing level ' -Quiet)
} until ($taskReady -or (Get-Date) -gt $taskDeadline)
if (-not $taskReady) { throw 'Cache did not reach initialization gate' }
& $Java -cp (Join-Path $Repository '.Codex\native1023') R53ReadOnlyAttach1023 $taskProcess.Id (Join-Path $ArtifactRoot 'cache-input-isolated.jar') $taskReceipt
if ($LASTEXITCODE -ne 0) { throw 'Cache isolation attach failed' }
Get-Content -LiteralPath $taskReceipt -Raw
