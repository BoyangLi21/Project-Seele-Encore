param([switch]$EnableShaders)
$ErrorActionPreference = 'Stop'
$gameDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$recipePath = Join-Path $gameDirectory 'private_shader_recipe_v12.json'
$errorPath = Join-Path $gameDirectory 'R48-Visual-Initialization-Error.txt'
$utf8 = [Text.UTF8Encoding]::new($false)
try {
    $recipe = Get-Content -LiteralPath $recipePath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($recipe.output_filename -ne 'SEELE_Local_Cavern_R48_Private_v1.zip') { throw 'Expected the named R48 local shader recipe.' }
    if ($recipe.input_filename -ne 'ComplementaryUnbound_r5.3.zip') { throw 'Expected the original shader input.' }
    $localShader = Join-Path $gameDirectory ('shaderpacks\' + $recipe.output_filename)
    $settings = $localShader + '.txt'
    $config = Join-Path $gameDirectory 'config\oculus.properties'
    if (-not (Test-Path -LiteralPath $localShader -PathType Leaf)) {
        & (Join-Path $gameDirectory 'Install-LocalPrivateVisuals.v12.ps1') `
            -GameDirectory $gameDirectory `
            -OriginalArchive (Join-Path $gameDirectory ('shaderpacks\' + $recipe.input_filename)) `
            -RecipePath $recipePath -PrivateLocal -Apply -Enable:$EnableShaders
        if (-not (Test-Path -LiteralPath $localShader -PathType Leaf)) { throw 'Local R48 shader preparation did not finish.' }
    }
    # The inherited installer validates its full output before the atomic ZIP move.
    # An interrupted settings/config write can resume without rebuilding that ZIP.
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead($localShader)
    try {
        $entry = $archive.GetEntry('SEELE_LOCAL_PRIVATE_ADAPTATION.txt')
        if ($null -eq $entry) { throw 'Existing local shader has no private-adaptation ownership record.' }
        $reader = [IO.StreamReader]::new($entry.Open(),$utf8)
        try { $credits = $reader.ReadToEnd() } finally { $reader.Dispose() }
        if ($credits -ne [string]$recipe.credits) { throw 'Existing local shader belongs to a different recipe; preserve it.' }
    } finally { $archive.Dispose() }
    if (-not (Test-Path -LiteralPath $settings -PathType Leaf)) {
        [IO.File]::WriteAllText($settings,[string]::Join("`n",$recipe.settings)+"`n",$utf8)
    }
    $lines = @()
    if (Test-Path -LiteralPath $config -PathType Leaf) { $lines = @(Get-Content -LiteralPath $config -Encoding UTF8) }
    $packLine = 'shaderPack=' + $recipe.output_filename
    $alreadySelected = $lines -contains $packLine
    if (-not $alreadySelected -or $EnableShaders) {
        [IO.Directory]::CreateDirectory((Split-Path -Parent $config)) | Out-Null
        if (Test-Path -LiteralPath $config -PathType Leaf) {
            [IO.File]::Copy($config,$config+'.before-r48-'+[Guid]::NewGuid().ToString('N'),$false)
        }
        $enabled = $EnableShaders -or ($alreadySelected -and ($lines -contains 'enableShaders=true'))
        $lines = @($lines | Where-Object { $_ -notmatch '^(enableShaders|shaderPack)=' })
        $lines += 'enableShaders=' + ([string][bool]$enabled).ToLowerInvariant()
        $lines += $packLine
        [IO.File]::WriteAllText($config,[string]::Join("`n",$lines)+"`n",$utf8)
    }
} catch {
    $detail = $_.Exception.ToString()
    [IO.File]::WriteAllText($errorPath,$detail,$utf8)
    Write-Error $detail
    exit 1
}
