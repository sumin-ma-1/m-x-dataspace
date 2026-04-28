#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

Write-Step "1) docker compose up (ui + app + aas)"
docker compose --profile ui --profile app up -d --build edc-cp edc-dp provider-cp provider-dp aas-env app edc-ui
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

try {
    Write-Step "2) wait for FastAPI health"
    $deadline = (Get-Date).AddSeconds(240)
    $ok = $false
    while ((Get-Date) -lt $deadline) {
        try {
            $health = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:18000/api/v1/health" -TimeoutSec 3
            if ($health.status -eq "ok") { $ok = $true; break }
        } catch { }
        Start-Sleep -Seconds 2
    }
    if (-not $ok) { throw "FastAPI health check failed" }

    Write-Step "3) verify AAS proxy reachability through FastAPI"
    $deadlineAas = (Get-Date).AddSeconds(120)
    $aasReady = $false
    while ((Get-Date) -lt $deadlineAas) {
        try {
            $shells = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:18000/proxy/aas/registry/shells" -TimeoutSec 10
            $aasReady = $true
            break
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    if (-not $aasReady) { throw "AAS proxy not reachable at /proxy/aas/registry/shells" }
    Write-Host ("shells fetched: " + @($shells).Count) -ForegroundColor Green

    Write-Step "4) seed sample shell descriptor"
    python scripts/seed_aas_registry.py --registry-base "http://127.0.0.1:38081"
    if ($LASTEXITCODE -ne 0) { throw "seed_aas_registry.py failed" }

    Write-Step "5) seed EDC asset with AAS metadata"
    python scripts/aas_demo.py
    if ($LASTEXITCODE -ne 0) { throw "aas_demo.py failed" }

    Write-Step "6) verify UI AAS endpoint through nginx"
    $uiShells = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:18080/aas/api/shells" -TimeoutSec 20
    Write-Host ("ui shells fetched: " + @($uiShells).Count) -ForegroundColor Green

    Write-Host ""
    Write-Host "verify_aas.ps1 completed successfully." -ForegroundColor Green
}
finally {
    Write-Step "7) docker compose down"
    docker compose --profile ui --profile app down
}
