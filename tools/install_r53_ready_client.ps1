param([Parameter(Mandatory=$true)][string]$TaskBase)
$ErrorActionPreference='Stop'
$taskReady=Join-Path $TaskBase 'ready-client'
$taskClient=Join-Path $TaskBase 'client'
$taskSource=Join-Path $taskReady 'projectseele-0.1.0-all.jar'
$taskTarget=Join-Path $taskClient 'mods/projectseele-0.1.0-all.jar'
$taskWorld=Join-Path $taskClient 'saves/SEELE_R53_WORLD'
$taskLightingName='starlight-1.1.2+forge.1cda73c.jar'
$taskLightingSource=Join-Path $taskReady $taskLightingName
if(Test-Path -LiteralPath $taskLightingSource){
    $taskLightingSha='cc89c6b2dd0db709586028c7732a57a3e6184f19cc2b98b25964c720c3ab434031e62de23e0dab022575d637b5e4a34b5813164d32ec356d56588da400e7d026'
    if((Get-FileHash -LiteralPath $taskLightingSource -Algorithm SHA512).Hash -ne $taskLightingSha){throw 'Pinned lighting mod differs'}
    $taskLightingTarget=Join-Path $taskClient ('mods/'+$taskLightingName)
    if(-not(Test-Path -LiteralPath $taskLightingTarget)-or (Get-FileHash -LiteralPath $taskLightingTarget -Algorithm SHA512).Hash -ne $taskLightingSha){
        Copy-Item -LiteralPath $taskLightingSource -Destination $taskLightingTarget -Force
        if((Get-FileHash -LiteralPath $taskLightingTarget -Algorithm SHA512).Hash -ne $taskLightingSha){throw 'Lighting mod installation readback differs'}
    }
    $taskLicenses=Join-Path $taskClient 'licenses'
    New-Item -ItemType Directory -Path $taskLicenses -Force | Out-Null
    foreach($taskLicenseName in @('Starlight-LGPL-3.0.txt','Starlight-NOTICE.txt','Starlight-1cda73c-source.zip')){
        $taskLicenseSource=Join-Path $taskReady $taskLicenseName
        $taskLicenseTarget=Join-Path $taskLicenses $taskLicenseName
        Copy-Item -LiteralPath $taskLicenseSource -Destination $taskLicenseTarget -Force
        if((Get-FileHash -LiteralPath $taskLicenseSource).Hash -ne (Get-FileHash -LiteralPath $taskLicenseTarget).Hash){throw 'Lighting license/source readback differs'}
    }
}
$taskSurfaceSource=Join-Path $TaskBase 'ready-world/surface_angel_assault_r52.json'
$taskSurfaceTarget=Join-Path $taskWorld 'surface_angel_assault_r52.json'
if((Test-Path -LiteralPath $taskSurfaceSource)-and(Test-Path -LiteralPath $taskWorld)-and -not(Test-Path -LiteralPath $taskSurfaceTarget)){
    Copy-Item -LiteralPath $taskSurfaceSource -Destination $taskSurfaceTarget
    if([IO.File]::ReadAllText($taskSurfaceSource) -cne [IO.File]::ReadAllText($taskSurfaceTarget)){throw 'Surface operation metadata readback differs'}
}
if(Test-Path -LiteralPath $taskSource){
    $taskFrom=Get-Item -LiteralPath $taskSource
    $taskTo=Get-Item -LiteralPath $taskTarget -ErrorAction SilentlyContinue
    if($null -eq $taskTo -or $taskFrom.Length -ne $taskTo.Length -or $taskFrom.LastWriteTimeUtc -ne $taskTo.LastWriteTimeUtc){
        Copy-Item -LiteralPath $taskSource -Destination $taskTarget -Force
        $taskInput=[IO.File]::OpenRead($taskSource)
        $taskOutput=[IO.File]::OpenRead($taskTarget)
        try {
            if($taskInput.Length -ne $taskOutput.Length){throw 'Client mod readback length differs'}
            $taskA=New-Object byte[] 1048576
            $taskB=New-Object byte[] 1048576
            while(($taskRead=$taskInput.Read($taskA,0,$taskA.Length)) -gt 0){
                $taskGot=0
                while($taskGot -lt $taskRead){$taskN=$taskOutput.Read($taskB,$taskGot,$taskRead-$taskGot);if($taskN -eq 0){throw 'Client mod readback ended early'};$taskGot+=$taskN}
                if([Convert]::ToBase64String($taskA,0,$taskRead) -cne [Convert]::ToBase64String($taskB,0,$taskRead)){throw 'Client mod readback differs'}
            }
        } finally {$taskInput.Dispose();$taskOutput.Dispose()}
    }
}
$taskShader='SEELE_Local_Cavern_R53_Private_v1.zip'
$taskShaderSource=Join-Path $taskReady $taskShader
if(Test-Path -LiteralPath $taskShaderSource){
    Copy-Item -LiteralPath $taskShaderSource -Destination (Join-Path $taskClient ('shaderpacks/'+$taskShader)) -Force
    $taskOldSettings=Join-Path $taskClient 'shaderpacks/SEELE_Local_Cavern_R50_Private_v1.zip.txt'
    $taskNewSettings=Join-Path $taskClient ('shaderpacks/'+$taskShader+'.txt')
    if((Test-Path -LiteralPath $taskOldSettings)-and -not(Test-Path -LiteralPath $taskNewSettings)){Copy-Item -LiteralPath $taskOldSettings -Destination $taskNewSettings}
    $taskOptions=Join-Path $taskClient 'config/oculus.properties'
    if(Test-Path -LiteralPath $taskOptions){
        $taskText=[IO.File]::ReadAllText($taskOptions)
        $taskText=$taskText.Replace('shaderPack=SEELE_Local_Cavern_R50_Private_v1.zip','shaderPack='+$taskShader)
        [IO.File]::WriteAllText($taskOptions,$taskText)
    }
}
