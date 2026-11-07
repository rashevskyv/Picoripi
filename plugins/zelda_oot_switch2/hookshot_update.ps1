# Rebuilds Hookshot (github.com/NotRexed/Hookshot) when a newer release is out; the launcher runs this first.
# Any failure (no network, a build error) leaves the installed game as it is, and the launcher starts it anyway.
param([string]$Game, [string]$Nup, [string]$Original)
$ErrorActionPreference = "Stop"
$Game = (Resolve-Path $Game).Path
$stamp = Join-Path $Game ".hookshot_release"
try {
    $release = Invoke-RestMethod "https://api.github.com/repos/NotRexed/Hookshot/releases/latest" -TimeoutSec 15
} catch {
    Write-Host "Hookshot update check skipped: $($_.Exception.Message)"
    exit 0
}
if ((Test-Path $stamp) -and ((Get-Content $stamp -Raw).Trim() -eq "$($release.id)")) { exit 0 }
$asset = $release.assets | Where-Object { $_.name -like "HookshotBuilder*.zip" } | Select-Object -First 1
if (-not $asset) { Write-Host "Hookshot release $($release.tag_name) has no builder; update skipped."; exit 0 }
if (-not (Test-Path $Nup)) { $Nup = $Original }
Write-Host "New Hookshot release: $($release.name) ($($release.tag_name))."
Write-Host "Rebuilding the game from $Nup. This takes about 35 minutes; the game starts afterwards."
$update = Join-Path $Game ".update"
$builder = Join-Path $update "builder"
try {
    if (Test-Path $builder) { Remove-Item $builder -Recurse -Force }
    New-Item -ItemType Directory -Force $builder | Out-Null
    $zip = Join-Path $update $asset.name
    Invoke-WebRequest $asset.browser_download_url -OutFile $zip -UseBasicParsing
    tar -xf $zip -C $builder
    if ($LASTEXITCODE) { throw "the builder archive did not unpack" }
    Remove-Item $zip
    $tools = (Get-ChildItem $builder -Recurse -Directory -Filter tools | Where-Object { Test-Path (Join-Path $_.FullName "nx2\make_game.py") } | Select-Object -First 1).FullName
    if (-not $tools) { throw "the builder has no tools\nx2\make_game.py" }
    $env:EMSDK = Join-Path $tools "emsdk"
    $env:RX_CPM = Join-Path $tools "cpm"
    $env:WGPU_NATIVE = Join-Path $tools "wgpu-native"
    $env:PYTHONIOENCODING = "utf-8"
    Push-Location $tools
    try {
        & (Join-Path $tools "python\python.exe") -I (Join-Path $tools "nx2\make_game.py") --nup $Nup --out $Game --work (Join-Path $update "work") --language ru
        if ($LASTEXITCODE) { throw "make_game.py exited with code $LASTEXITCODE" }
    } finally { Pop-Location }
    Set-Content $stamp "$($release.id)" -Encoding ascii
    Write-Host "Hookshot updated to $($release.tag_name)."
} catch {
    Write-Host "Hookshot update failed: $($_.Exception.Message). Starting the installed game."
    Start-Sleep 5
}
