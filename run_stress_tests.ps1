# PowerShell script to run stress tests 20 times and calculate the results.
$ErrorActionPreference = "Stop"

$TotalRuns = 20
$PassedRuns = 0
$FailedRun = 0

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Starting Picoripi 20-run Parallel Stress Test Suite" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

for ($i = 1; $i -le $TotalRuns; $i++) {
    Write-Host "`n--- RUN $i OF $TotalRuns ---" -ForegroundColor Yellow
    
    # Run the parallel test suite script
    $StartTime = Get-Date
    powershell -ExecutionPolicy Bypass -File .\test_all.ps1
    $Duration = (Get-Date) - $StartTime
    
    if ($LASTEXITCODE -ne 0) {
        $FailedRun = $i
        Write-Host "`n[ERROR] Test suite failed on Run $i after $($Duration.TotalSeconds) seconds!" -ForegroundColor Red
        break
    } else {
        $PassedRuns++
        Write-Host "[SUCCESS] Run $i completed successfully in $($Duration.TotalSeconds) seconds." -ForegroundColor Green
    }
}

Write-Host "`n==================================================" -ForegroundColor Cyan
Write-Host "Stress Test Results Summary:" -ForegroundColor Cyan
Write-Host "Total Scheduled Runs: $TotalRuns" -ForegroundColor Cyan
Write-Host "Successfully Passed:  $PassedRuns" -ForegroundColor Green

if ($FailedRun -gt 0) {
    Write-Host "Failed Run Index:     $FailedRun" -ForegroundColor Red
    Write-Host "Status:               FAILED ❌" -ForegroundColor Red
    exit 1
} else {
    Write-Host "Status:               ALL PASSED ✅" -ForegroundColor Green
    exit 0
}
