param([string]$OutputRoot='D:/eva/artifacts/rebuild_r44/combat/all_body_contact_v19')
$ErrorActionPreference='Stop'
$combatRepo='D:/eva'
$combatBlender='C:/Program Files/Blender Foundation/Blender 5.1/blender.exe'
$combatPython='C:/Python314/python.exe'
$combatArt=Join-Path $combatRepo 'artifacts/rebuild_r44/combat'
$combatSource=Join-Path $combatArt 'locomotion_sequence_v5_run_seam_study'
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
$combatRows=@(
    @{rig=0;actor='eva_unit00';raw='locomotion_raw_run_seam_unit00_v2'},
    @{rig=2;actor='eva_unit02';raw='locomotion_raw_run_seam_unit02_v2'},
    @{rig=3;actor='eva_prototype';raw='locomotion_raw_source_timing_un00_v1'},
    @{rig=4;actor='eva_un01';raw='locomotion_raw_source_timing_un01_v1'}
)
function Invoke-ProductionStep {
    param([string]$Executable,[string[]]$Arguments,[string]$Directory,[string]$Label,[string]$RequiredFile)
    $stepRecord=@{label=$Label;started=(Get-Date).ToString('o');executable=$Executable;arguments=$Arguments;state='RUNNING'}
    $stepRecord | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Directory ($Label+'_status.json'))
    $stepJob=Start-Process -FilePath $Executable -ArgumentList $Arguments -WorkingDirectory $combatRepo -WindowStyle Hidden -RedirectStandardOutput (Join-Path $Directory ($Label+'_stdout.log')) -RedirectStandardError (Join-Path $Directory ($Label+'_stderr.log')) -PassThru
    $stepJob.Id | Set-Content -LiteralPath (Join-Path $Directory ($Label+'_pid.txt'))
    $stepJob.WaitForExit()
    $stepRecord.ended=(Get-Date).ToString('o');$stepRecord.exit_code=$stepJob.ExitCode
    if ($stepJob.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $RequiredFile)) {
        $stepRecord.state='FAILED';$stepRecord | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Directory ($Label+'_status.json'))
        throw ('Production failed: '+$Label+'; read the exact stdout/stderr and required artifact.')
    }
    $stepRecord.state='GENERATED_UNAPPROVED';$stepRecord.required_artifact=$RequiredFile
    $stepRecord.artifact_sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $RequiredFile).Hash
    $stepRecord | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Directory ($Label+'_status.json'))
}
foreach ($combatRow in $combatRows) {
    $combatActor=$combatRow.actor;$combatRig=$combatRow.rig
    $combatOut=Join-Path $OutputRoot $combatActor
    if (Test-Path -LiteralPath (Join-Path $combatOut 'captured_runtime_export_receipt.json')) {
        $combatComplete=Get-Content -LiteralPath (Join-Path $combatOut 'captured_runtime_export_receipt.json') -Raw | ConvertFrom-Json
        $combatProfile=Join-Path $combatOut ('eva_locomotion_capture_r44_'+$combatRig+'.json')
        if ((Test-Path -LiteralPath $combatProfile) -and (Get-FileHash -Algorithm SHA256 -LiteralPath $combatProfile).Hash.ToLower() -eq $combatComplete.sha256) {continue}
    }
    $combatRaw=Join-Path $combatArt $combatRow.raw
    New-Item -ItemType Directory -Path $combatRaw -Force | Out-Null
    $combatFixture=Join-Path $combatArt ('five_body_contact_calibration/'+$combatActor+'/fixture.json')
    if ($combatRig -lt 3) {
        Invoke-ProductionStep $combatBlender @('--background','--threads','2','--python-exit-code','1','--python',(Join-Path $combatRepo 'tools/build_rokoko_leg_comparison_r44.py'),'--','--out',$combatRaw,'--source',$combatSource,'--fixture',$combatFixture,'--neutral-root-calibration') $combatRaw 'retarget' (Join-Path $combatRaw 'rokoko_continuous_legs_r44.blend')
    }
    if (-not (Test-Path -LiteralPath (Join-Path $combatRaw 'operator_receipt.json'))) {throw ('Missing completed original retarget: '+$combatRaw)}
    New-Item -ItemType Directory -Path $combatOut -Force | Out-Null
    $combatHull=Join-Path $combatOut 'floor_extrema'
    New-Item -ItemType Directory -Path $combatHull -Force | Out-Null
    Invoke-ProductionStep $combatPython @((Join-Path $combatRepo 'tools/prepare_rigid_floor_extrema_r44.py'),'--fixture',$combatFixture,'--out',$combatHull) $combatHull 'extrema' (Join-Path $combatHull 'rigid_floor_extrema_receipt.json')
    $combatSnapshot=Join-Path $combatOut 'authoring_sources'
    New-Item -ItemType Directory -Path $combatSnapshot -Force | Out-Null
    foreach ($combatScript in @('author_rokoko_contacts_r44.py','blender_coupled_contact_r44.py','prepare_rigid_floor_extrema_r44.py')) {
        Copy-Item -LiteralPath (Join-Path $combatRepo ('tools/'+$combatScript)) -Destination (Join-Path $combatSnapshot $combatScript)
    }
    if (-not ((Test-Path -LiteralPath (Join-Path $combatOut 'rokoko_continuous_legs_r44.blend')) -and (Test-Path -LiteralPath (Join-Path $combatOut 'contact_pass_receipt.json')))) {
        Invoke-ProductionStep $combatBlender @('--background','--threads','2','--python-exit-code','1',(Join-Path $combatRaw 'rokoko_continuous_legs_r44.blend'),'--python',(Join-Path $combatRepo 'tools/author_rokoko_contacts_r44.py'),'--','--raw',$combatRaw,'--out',$combatOut,'--bridge','12','--surface-support','--armored-prone','--coupled-body-support','--elbow-bearing','--checkpoint-every','120','--surface-hulls',$combatHull) $combatOut 'author' (Join-Path $combatOut 'rokoko_continuous_legs_r44.blend')
    }
    Invoke-ProductionStep $combatBlender @('--background','--threads','2','--python-exit-code','1',(Join-Path $combatOut 'rokoko_continuous_legs_r44.blend'),'--python',(Join-Path $combatRepo 'tools/audit_locomotion_scene_r44.py'),'--','--out',$combatOut) $combatOut 'reopen_audit' (Join-Path $combatOut 'saved_skin_fk_audit.json')
    Invoke-ProductionStep $combatPython @((Join-Path $combatRepo 'tools/export_tv_exchange_r44.py'),'--out',$combatOut) $combatOut 'export_reload' (Join-Path $combatOut 'export_readback.json')
    Invoke-ProductionStep $combatPython @((Join-Path $combatRepo 'tools/export_captured_locomotion_r44.py'),'--out',$combatOut,'--rig',[string]$combatRig,'--body-profile',(Join-Path $combatRepo '.Codex/r44-network-client/projectseele-local-maps/eva_body_r43.json')) $combatOut 'runtime_export' (Join-Path $combatOut 'captured_runtime_export_receipt.json')
}
@{state='ALL_GENERATED_UNAPPROVED';completed=(Get-Date).ToString('o');scope='Four independent actual rigs; Unit01 separate V19 process. Native/art/fullspeed review and attacks remain required.'} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $OutputRoot 'generation_complete.json')
