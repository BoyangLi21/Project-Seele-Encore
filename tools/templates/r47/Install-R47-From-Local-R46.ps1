param(
    [string]$MinecraftRoot = (Join-Path $env:APPDATA '.minecraft'),
    [switch]$EnableShaders,
    [switch]$SkipPersonalVisuals
)
$ErrorActionPreference = 'Stop'
$packageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$baseVersion = 'Project_SEELE_Encore_R46_20261004'
$newVersion = 'Project_SEELE_Encore_R47_20261005'
$versionsRoot = [IO.Path]::GetFullPath((Join-Path $MinecraftRoot 'versions'))
$sourceRoot = [IO.Path]::GetFullPath((Join-Path $versionsRoot $baseVersion))
$targetRoot = [IO.Path]::GetFullPath((Join-Path $versionsRoot $newVersion))
if (-not $targetRoot.StartsWith($versionsRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'New instance escapes the chosen versions directory.' }
if ($targetRoot -eq $sourceRoot -or (Test-Path -LiteralPath $targetRoot)) { throw 'R46 and existing R47 instances are preserved. Choose a new installation directory.' }
$vanillaJar = Join-Path $sourceRoot ($baseVersion + '.jar')
$profile = Join-Path $packageRoot ('profile_templates\' + $newVersion + '.json')
if (-not (Test-Path -LiteralPath $vanillaJar -PathType Leaf)) { throw 'Retained local R46 instance is absent. Install Minecraft 1.20.1 / Forge 47.4.10 as a fresh isolated version in PCL and copy this file bundle manually.' }
if (-not (Test-Path -LiteralPath $profile -PathType Leaf)) { throw 'R47 Forge profile template is absent.' }
foreach ($name in @('mods','config','projectseele-local-maps','resourcepacks','shaderpacks')) {
    if (-not (Test-Path -LiteralPath (Join-Path $packageRoot $name) -PathType Container)) { throw ('Complete package directory missing: ' + $name) }
}
# All checks precede the first new-directory write. No delete/move, server
# start, download, or alteration of the source R46/PCL profile is performed.
New-Item -ItemType Directory -Path $targetRoot | Out-Null
Copy-Item -LiteralPath $profile -Destination (Join-Path $targetRoot ($newVersion + '.json'))
Copy-Item -LiteralPath $vanillaJar -Destination (Join-Path $targetRoot ($newVersion + '.jar'))
foreach ($name in @('mods','config','projectseele-local-maps','resourcepacks','shaderpacks','PCL')) {
    $source = Join-Path $packageRoot $name
    if (Test-Path -LiteralPath $source) { Copy-Item -LiteralPath $source -Destination $targetRoot -Recurse }
}
foreach ($name in @('options.txt','private_shader_recipe_v12.json','Install-LocalPrivateVisuals.v12.ps1','COMPLEMENTARY_CREDITS.txt','README_R47.zh.md','MANUAL_R47.zh.md','NEXT_ROUND_R47.zh.md','R47_BATCH.json')) {
    $source = Join-Path $packageRoot $name
    if (Test-Path -LiteralPath $source) { Copy-Item -LiteralPath $source -Destination (Join-Path $targetRoot $name) }
}
if (-not $SkipPersonalVisuals) {
    $adapter = Join-Path $targetRoot 'Install-LocalPrivateVisuals.v12.ps1'
    & $adapter -GameDirectory $targetRoot `
        -OriginalArchive (Join-Path $targetRoot 'shaderpacks\ComplementaryUnbound_r5.3.zip') `
        -RecipePath (Join-Path $targetRoot 'private_shader_recipe_v12.json') `
        -PrivateLocal -Apply -Enable:$EnableShaders
    if (-not (Test-Path -LiteralPath (Join-Path $targetRoot 'shaderpacks\SEELE_Local_Cavern_R47_Private_v1.zip') -PathType Leaf)) { throw 'R47 personal shader was not created; do not launch this incomplete new instance.' }
    Write-Host 'R47 personal shader was built from the retained original before PCL launch and selected in this new instance only.'
}
Write-Host ('Prepared new isolated PCL version: ' + $targetRoot)
Write-Host 'This ZIP is an instance file bundle, not a claimed direct PCL modpack import. The existing shared libraries/assets are reused by the preserved Forge profile.'
