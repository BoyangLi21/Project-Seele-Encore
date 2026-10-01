param([string]$OutputRoot='D:/eva/artifacts/rebuild_r44/combat/all_attack_contact_v1',
      [string]$CaptureSource='D:/eva/artifacts/rebuild_r44/combat/complete_attack_source_v1')
$ErrorActionPreference='Stop'
$combatRepo='D:/eva';$combatBlender='C:/Program Files/Blender Foundation/Blender 5.1/blender.exe';$combatPython='C:/Python314/python.exe'
$combatArt=Join-Path $combatRepo 'artifacts/rebuild_r44/combat';$combatSource=$CaptureSource
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
function Invoke-AttackStep {
    param([string]$Executable,[string[]]$Arguments,[string]$Directory,[string]$Label,[string]$RequiredFile)
    $combatRecord=@{label=$Label;started=(Get-Date).ToString('o');executable=$Executable;arguments=$Arguments;state='RUNNING'}
    $combatRecord | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Directory ($Label+'_status.json'))
    $combatChild=Start-Process -FilePath $Executable -ArgumentList $Arguments -WorkingDirectory $combatRepo -WindowStyle Hidden -RedirectStandardOutput (Join-Path $Directory ($Label+'_stdout.log')) -RedirectStandardError (Join-Path $Directory ($Label+'_stderr.log')) -PassThru
    $combatChild.Id | Set-Content -LiteralPath (Join-Path $Directory ($Label+'_pid.txt'));$combatChild.WaitForExit()
    $combatRecord.ended=(Get-Date).ToString('o');$combatRecord.exit_code=$combatChild.ExitCode
    if ($combatChild.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $RequiredFile)) {
        $combatRecord.state='FAILED';$combatRecord | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Directory ($Label+'_status.json'));throw ('Attack production failed '+$Label)
    }
    $combatRecord.state='GENERATED_UNAPPROVED';$combatRecord.artifact_sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $RequiredFile).Hash
    $combatRecord | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Directory ($Label+'_status.json'))
}
foreach ($combatRow in @(@{rig=0;actor='eva_unit00'},@{rig=2;actor='eva_unit02'},@{rig=3;actor='eva_prototype'},@{rig=4;actor='eva_un01'})) {
    $combatRig=$combatRow.rig;$combatActor=$combatRow.actor;$combatOut=Join-Path $OutputRoot $combatActor;$combatRaw=Join-Path $combatOut 'raw'
    New-Item -ItemType Directory -Path $combatOut,$combatRaw -Force | Out-Null
    if (Test-Path -LiteralPath (Join-Path $combatOut 'current_attack_export_receipt.json')) {
        $combatComplete=Get-Content -LiteralPath (Join-Path $combatOut 'current_attack_export_receipt.json') -Raw | ConvertFrom-Json
        $combatProfile=Join-Path $OutputRoot ('runtime_profiles/eva_gameplay_r44_'+$combatRig+'.json')
        if ((Test-Path -LiteralPath $combatProfile) -and (Get-FileHash -Algorithm SHA256 -LiteralPath $combatProfile).Hash.ToLower() -eq $combatComplete.sha256) {continue}
    }
    if ($combatRig -ge 3) {
        # Bound memory to one active UN author/importer across the independent
        # locomotion and attack producers. This does not touch either process.
        while ($true) {
            $combatHeavy=Get-CimInstance Win32_Process -Filter "Name='blender.exe'" | Where-Object {$_.CommandLine -match 'eva_prototype|eva_un01|source_timing_un00|source_timing_un01'}
            if (-not $combatHeavy) {break};Start-Sleep -Seconds 10
        }
    }
    $combatFixture=Join-Path $combatArt ('five_body_contact_calibration/'+$combatActor+'/fixture.json')
    if (-not ((Test-Path -LiteralPath (Join-Path $combatRaw 'operator_receipt.json')) -and (Test-Path -LiteralPath (Join-Path $combatRaw 'rokoko_continuous_legs_r44.blend')))) {
        Invoke-AttackStep $combatBlender @('--background','--threads','2','--python-exit-code','1','--python',(Join-Path $combatRepo 'tools/build_rokoko_leg_comparison_r44.py'),'--','--out',$combatRaw,'--source',$combatSource,'--fixture',$combatFixture,'--neutral-root-calibration') $combatRaw 'retarget' (Join-Path $combatRaw 'rokoko_continuous_legs_r44.blend')
    }
    $combatHull=Join-Path $combatOut 'floor_extrema';New-Item -ItemType Directory -Path $combatHull -Force | Out-Null
    Invoke-AttackStep $combatPython @((Join-Path $combatRepo 'tools/prepare_rigid_floor_extrema_r44.py'),'--fixture',$combatFixture,'--out',$combatHull) $combatHull 'extrema' (Join-Path $combatHull 'rigid_floor_extrema_receipt.json')
    $combatSnapshot=Join-Path $combatOut 'authoring_sources';New-Item -ItemType Directory -Path $combatSnapshot -Force | Out-Null
    foreach ($combatScript in @('author_rokoko_contacts_r44.py','blender_coupled_contact_r44.py','blender_combat_fist_r44.py')) {Copy-Item -LiteralPath (Join-Path $combatRepo ('tools/'+$combatScript)) -Destination (Join-Path $combatSnapshot $combatScript)}
    Invoke-AttackStep $combatBlender @('--background','--threads','2','--python-exit-code','1',(Join-Path $combatRaw 'rokoko_continuous_legs_r44.blend'),'--python',(Join-Path $combatRepo 'tools/author_rokoko_contacts_r44.py'),'--','--raw',$combatRaw,'--out',$combatOut,'--bridge','12','--coupled-body-support','--combat-fists','--surface-hulls',$combatHull,'--checkpoint-every','120') $combatOut 'author' (Join-Path $combatOut 'rokoko_continuous_legs_r44.blend')
    Invoke-AttackStep $combatBlender @('--background','--threads','2','--python-exit-code','1',(Join-Path $combatOut 'rokoko_continuous_legs_r44.blend'),'--python',(Join-Path $combatRepo 'tools/audit_locomotion_scene_r44.py'),'--','--out',$combatOut) $combatOut 'reopen' (Join-Path $combatOut 'saved_skin_fk_audit.json')
    Invoke-AttackStep $combatPython @((Join-Path $combatRepo 'tools/export_tv_exchange_r44.py'),'--out',$combatOut) $combatOut 'export_reload' (Join-Path $combatOut 'export_readback.json')
    $combatProfileOut=Join-Path $OutputRoot 'runtime_profiles';New-Item -ItemType Directory -Path $combatProfileOut -Force | Out-Null
    Invoke-AttackStep $combatPython @((Join-Path $combatRepo 'tools/export_current_attack_profile_r44.py'),'--out',$combatOut,'--baseline-profile',(Join-Path $combatArt ('motion/eva_gameplay_r44_'+$combatRig+'.json')),'--body-profile',(Join-Path $combatRepo '.Codex/r44-network-client/projectseele-local-maps/eva_body_r43.json'),'--destination',$combatProfileOut,'--rig',[string]$combatRig) $combatOut 'runtime_export' (Join-Path $combatOut 'current_attack_export_receipt.json')
}
@{state='ALL_GENERATED_UNAPPROVED';completed=(Get-Date).ToString('o');scope='Independent fullbody guard/jab/cross/hook/heavy production; paired reactions, weapons/low attacks/TV climax/native/fullspeed/user review remain open.'} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $OutputRoot 'generation_complete.json')
