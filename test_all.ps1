# Run from the repository root even when invoked from another working directory.
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $RepoRoot

$Python = Join-Path $RepoRoot "venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    Write-Host "`n[ERROR] Python executable not found: $Python" -ForegroundColor Red
    exit 1
}

$env:PYTHONPATH = $RepoRoot

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Running Picoripi Test Suite & Verification" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

Write-Host "`n[1/3] Running Unit & Integration Tests..." -ForegroundColor Yellow
& $Python -m pytest -n auto tests/
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n[ERROR] Unit/Integration Tests Failed!" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "`n[2/3] Running Performance Tests..." -ForegroundColor Yellow
& $Python -m pytest -n auto -m performance tests/test_performance.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n[ERROR] Performance Tests Failed!" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "`n[3/3] Running Ruff Linter Checks..." -ForegroundColor Yellow
& $Python -m ruff check .
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n[ERROR] Ruff Linter Checks Failed!" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "`n=========================================" -ForegroundColor Green
Write-Host "All Checks Passed Successfully!" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
exit 0
