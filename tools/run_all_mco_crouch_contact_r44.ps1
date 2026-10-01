param([string]$OutputRoot='D:/eva/artifacts/rebuild_r44/combat/all_mco_crouch_contact_v1')
$ErrorActionPreference='Stop'
$combatRepo='D:/eva';$combatBlender='C:/Program Files/Blender Foundation/Blender 5.1/blender.exe';$combatPython='C:/Python314/python.exe'
$combatSource='D:/eva/artifacts/rebuild_r44/combat/mco_crouch_source_v1'
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
function Invoke-CrouchStep {
    param([string]$Executable,[string[]]$Arguments,[string]$Directory,[string]$Label,[string]$RequiredFile)
    $combatRecord=@{label=$Label;started=(Get-Date).ToString('o');state='RUNNING';arguments=$Arguments}
    $combatRecord | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Directory ($Label+'_status.json'))
    $combatChild=Start-Process -FilePath $Executable -ArgumentList $Arguments -WorkingDirectory $combatRepo -WindowStyle Hidden -RedirectStandardOutput (Join-Path $Directory ($Label+'_stdout.log')) -RedirectStandardError (Join-Path $Directory ($Label+'_stderr.log')) -PassThru
    $combatProcessHandle=$combatChild.Handle; $combatChild.Id | Set-Content -LiteralPath (Join-Path $Directory ($Label+'_pid.txt'));$combatChild.WaitForExit()
    $combatRecord.ended=(Get-Date).ToString('o');$combatRecord.exit_code=$combatChild.ExitCode
    if($combatChild.ExitCode -ne 0 -or -not(Test-Path -LiteralPath $RequiredFile)){$combatRecord.state='FAILED';$combatRecord | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Directory ($Label+'_status.json'));throw ('Crouch source production failed '+$Label)}
    $combatRecord.state='GENERATED_UNAPPROVED';$combatRecord.sha256=([System.BitConverter]::ToString([System.Security.Cryptography.SHA256]::Create().ComputeHash([System.IO.File]::ReadAllBytes($RequiredFile)))).Replace("-","").ToLowerInvariant()
    $combatRecord | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Directory ($Label+'_status.json'))
}
foreach($combatRow in @(@{rig=0;actor='eva_unit00'},@{rig=2;actor='eva_unit02'},@{rig=3;actor='eva_prototype'},@{rig=4;actor='eva_un01'})){
    $combatRig=$combatRow.rig;$combatActor=$combatRow.actor;$combatOut=Join-Path $OutputRoot $combatActor;$combatRaw=Join-Path $combatOut 'raw';$combatHull=Join-Path $combatOut 'floor_extrema'
    New-Item -ItemType Directory -Path $combatOut,$combatRaw,$combatHull -Force | Out-Null
    $combatFixture='D:/eva/artifacts/rebuild_r44/combat/five_body_contact_calibration/'+$combatActor+'/fixture.json'
    $combatProfile=Join-Path $combatOut ('eva_locomotion_supplement_r44_'+$combatRig+'.json')
    if(Test-Path -LiteralPath $combatProfile){continue}
    if(-not(Test-Path -LiteralPath (Join-Path $combatRaw 'operator_receipt.json'))){Invoke-CrouchStep $combatBlender @('--background','--threads','2','--python-exit-code','1','--python','D:/eva/tools/build_rokoko_leg_comparison_r44.py','--','--out',$combatRaw,'--source',$combatSource,'--fixture',$combatFixture,'--neutral-root-calibration') $combatRaw 'retarget' (Join-Path $combatRaw 'rokoko_continuous_legs_r44.blend')}
    Invoke-CrouchStep $combatPython @('D:/eva/tools/prepare_rigid_floor_extrema_r44.py','--fixture',$combatFixture,'--out',$combatHull) $combatHull 'extrema' (Join-Path $combatHull 'rigid_floor_extrema_receipt.json')
    Invoke-CrouchStep $combatBlender @('--background','--threads','2','--python-exit-code','1',(Join-Path $combatRaw 'rokoko_continuous_legs_r44.blend'),'--python','D:/eva/tools/author_rokoko_contacts_r44.py','--','--raw',$combatRaw,'--out',$combatOut,'--bridge','12','--coupled-body-support','--surface-hulls',$combatHull,'--checkpoint-every','120') $combatOut 'author' (Join-Path $combatOut 'rokoko_continuous_legs_r44.blend')
    Invoke-CrouchStep $combatBlender @('--background','--threads','2','--python-exit-code','1',(Join-Path $combatOut 'rokoko_continuous_legs_r44.blend'),'--python','D:/eva/tools/audit_locomotion_scene_r44.py','--','--out',$combatOut) $combatOut 'reopen' (Join-Path $combatOut 'saved_skin_fk_audit.json')
    Invoke-CrouchStep $combatPython @('D:/eva/tools/export_tv_exchange_r44.py','--out',$combatOut) $combatOut 'export_reload' (Join-Path $combatOut 'export_readback.json')
    Invoke-CrouchStep $combatPython @('D:/eva/tools/export_captured_locomotion_r44.py','--out',$combatOut,'--rig',[string]$combatRig,'--body-profile','D:/eva/.Codex/r44-network-client/projectseele-local-maps/eva_body_r43.json','--supplemental') $combatOut 'runtime_export' $combatProfile
}
@{state='GENERATED_UNAPPROVED';completed=(Get-Date).ToString('o');scope='Four independently retargeted full37frame MCO crouch-walk source and physical contact authoring. Unit01 separately complete. Complete idle/entry/exit/prone source integration, native playback and art remain open. Existing private study provenance is not public redistribution clearance.'}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $OutputRoot 'generation_complete.json')
