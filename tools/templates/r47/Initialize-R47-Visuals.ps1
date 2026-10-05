$ErrorActionPreference = 'Stop'
$gameDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$recipePath = Join-Path $gameDirectory 'private_shader_recipe_v12.json'
$recipe = Get-Content -LiteralPath $recipePath -Raw -Encoding UTF8 | ConvertFrom-Json
$localShader = Join-Path $gameDirectory ('shaderpacks\' + $recipe.output_filename)
# Each PCL launch may call this hook; completed local assets are preserved.
if (Test-Path -LiteralPath $localShader -PathType Leaf) { exit 0 }
try {
    & (Join-Path $gameDirectory 'Install-LocalPrivateVisuals.v12.ps1') `
        -GameDirectory $gameDirectory `
        -OriginalArchive (Join-Path $gameDirectory ('shaderpacks\' + $recipe.input_filename)) `
        -RecipePath $recipePath -PrivateLocal -Apply
    if (-not (Test-Path -LiteralPath $localShader -PathType Leaf)) {
        throw 'Local R47 shader preparation did not finish.'
    }
} catch {
    $detail = $_.Exception.ToString()
    [IO.File]::WriteAllText((Join-Path $gameDirectory 'R47-Visual-Initialization-Error.txt'), $detail)
    Write-Error $detail
    exit 1
}
