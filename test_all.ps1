# The full check before a commit: tests, the performance lane, the linter.
# The commands themselves live in tasks.py; it picks the project's Python environment.
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $RepoRoot

$Launcher = Get-Command python, py -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $Launcher) {
    Write-Host "`n[ERROR] Python was not found on PATH." -ForegroundColor Red
    exit 1
}

$Steps = @(
    @{ Title = "Unit & Worker Tests (Parallel)"; Command = "test" },
    @{ Title = "Performance Tests"; Command = "test-perf" },
    @{ Title = "Ruff Linter Checks"; Command = "lint" }
)

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Running Picoripi Test Suite & Verification" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

$Number = 0
foreach ($Step in $Steps) {
    $Number++
    Write-Host "`n[$Number/$($Steps.Count)] Running $($Step.Title)..." -ForegroundColor Yellow
    & $Launcher.Source tasks.py $Step.Command
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`n[ERROR] $($Step.Title) Failed!" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

Write-Host "`n=========================================" -ForegroundColor Green
Write-Host "All Checks Passed Successfully!" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
exit 0
