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
# A release names its builder either as one zip or, since honest-eta, as parts listed in hookshot-setup.txt.
$asset = $release.assets | Where-Object { $_.name -like "HookshotBuilder*.zip" } | Select-Object -First 1
$setup = $release.assets | Where-Object { $_.name -eq "hookshot-setup.txt" } | Select-Object -First 1
if (-not $asset -and -not $setup) { Write-Host "Hookshot release $($release.tag_name) has no builder; update skipped."; exit 0 }
if (-not (Test-Path -LiteralPath $Nup)) { $Nup = $Original }   # the names hold [ ], which -Path reads as a pattern
Write-Host "New Hookshot release: $($release.name) ($($release.tag_name))."
Write-Host "Rebuilding the game from $Nup. This takes about 35 minutes; the game starts afterwards."
$update = Join-Path $Game ".update"
$tar = Join-Path $env:SystemRoot "System32\tar.exe"   # (Windows' own: it reads zip; a GNU tar earlier in PATH does not)
$builder = Join-Path $update "builder"
try {
    if (Test-Path $builder) { Remove-Item $builder -Recurse -Force }
    New-Item -ItemType Directory -Force $builder | Out-Null
    if ($setup) {
        # "part <sha256> <size> <folder> <top folder to take or -> <its new name or -> <url>"
        $parts = Join-Path $update "parts"
        New-Item -ItemType Directory -Force $parts | Out-Null
        $list = Join-Path $update "hookshot-setup.txt"   # (served as bytes, so read from a file)
        Invoke-WebRequest $setup.browser_download_url -OutFile $list -UseBasicParsing
        foreach ($line in Get-Content $list | Where-Object { $_ -like "part *" }) {
            $f = $line.Trim() -split " "
            $zip = Join-Path $parts "$($f[1]).zip"
            if (-not (Test-Path $zip) -or (Get-FileHash $zip -Algorithm SHA256).Hash -ne $f[1]) {
                Invoke-WebRequest $f[6] -OutFile $zip -UseBasicParsing
                if ((Get-FileHash $zip -Algorithm SHA256).Hash -ne $f[1]) { throw "$($f[6]) does not match its sha256" }
            }
            $target = Join-Path $builder $f[3]
            New-Item -ItemType Directory -Force $target | Out-Null
            if ($f[4] -eq "-") { & $tar -xf $zip -C $target }
            else {
                $temp = Join-Path $update "unpack"
                if (Test-Path $temp) { Remove-Item $temp -Recurse -Force }
                New-Item -ItemType Directory -Force $temp | Out-Null
                & $tar -xf $zip -C $temp
                Move-Item (Join-Path $temp $f[4]) (Join-Path $target $f[5])
                Remove-Item $temp -Recurse -Force
            }
            if ($LASTEXITCODE) { throw "$($f[6]) did not unpack" }
        }
    } else {
        $zip = Join-Path $update $asset.name
        Invoke-WebRequest $asset.browser_download_url -OutFile $zip -UseBasicParsing
        & $tar -xf $zip -C $builder
        if ($LASTEXITCODE) { throw "the builder archive did not unpack" }
        Remove-Item $zip
    }
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
