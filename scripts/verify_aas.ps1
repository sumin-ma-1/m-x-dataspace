#Requires -Version 5.1
<#
.SYNOPSIS
  One-click: Compose up (ui+app+aas) -> health -> AAS proxy -> seed BaSyx + EDC -> UI nginx /aas/api/shells.

.DESCRIPTION
  Step 6 uses the same path as the browser: http://127.0.0.1:18080/aas/api/shells -> nginx -> FastAPI /proxy/aas/registry/shells -> BaSyx.
  BaSyx often returns { "paging_metadata": {...}, "result": [ ... ] }; shell count must use .result, not @($obj).Count.

.PARAMETER KeepStack
  If set, do not run `docker compose down` at the end (useful to inspect UI after verify).

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_aas.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_aas.ps1 -KeepStack
#>
param(
    [switch]$KeepStack
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Get-AasShellCountFromResponse {
    param($Payload)
    if ($null -eq $Payload) { return 0 }
    # BaSyx: { "paging_metadata": {...}, "result": [ ... ] } — must check .result before IEnumerable
    $names = @()
    if ($null -ne $Payload.PSObject) { $names = $Payload.PSObject.Properties.Name }
    if ($names -contains "result") {
        $r = $Payload.result
        if ($null -eq $r) { return 0 }
        if ($r -is [System.Array]) { return $r.Count }
        return 1
    }
    if ($Payload -is [System.Array]) { return $Payload.Count }
    return 0
}

function Wait-HttpOk {
    param(
        [string]$Uri,
        [int]$TimeoutSec = 120,
        [int]$IntervalSec = 2
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $raw = curl.exe -s -o NUL -w "%{http_code}" $Uri 2>&1
            $code = 0
            if (-not [int]::TryParse($raw.Trim(), [ref]$code)) { $code = 0 }
            if ($code -ge 200 -and $code -lt 300) { return $true }
        } catch { }
        Start-Sleep -Seconds $IntervalSec
    }
    return $false
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
    $shells = $null
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
    $n = Get-AasShellCountFromResponse $shells
    Write-Host ("shells fetched (FastAPI proxy): " + $n) -ForegroundColor Green

    Write-Step "4) wait for UI (nginx) on :18080 before UI-proxy checks"
    if (-not (Wait-HttpOk -Uri "http://127.0.0.1:18080/" -TimeoutSec 180)) {
        throw "edc-ui (nginx) did not respond on http://127.0.0.1:18080/"
    }

    Write-Step "5) seed sample shell descriptor (host -> BaSyx :38081)"
    python scripts/seed_aas_registry.py --registry-base "http://127.0.0.1:38081"
    if ($LASTEXITCODE -ne 0) { throw "seed_aas_registry.py failed" }

    Write-Step "6) seed EDC asset with AAS metadata"
    python scripts/aas_demo.py
    if ($LASTEXITCODE -ne 0) { throw "aas_demo.py failed" }

    Write-Step "7) verify UI AAS endpoint through nginx (/aas/api/shells == UI + nginx + app + BaSyx)"
    $deadlineUi = (Get-Date).AddSeconds(120)
    $uiShells = $null
    $uiOk = $false
    while ((Get-Date) -lt $deadlineUi) {
        try {
            $raw = curl.exe -s -o NUL -w "%{http_code}" "http://127.0.0.1:18080/aas/api/shells" 2>&1
            $code = 0
            if (-not [int]::TryParse($raw.Trim(), [ref]$code)) { $code = 0 }
            if ($code -ge 200 -and $code -lt 300) {
                $uiShells = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:18080/aas/api/shells" -TimeoutSec 20
                $uiOk = $true
                break
            }
        } catch { }
        Start-Sleep -Seconds 2
    }
    if (-not $uiOk) { throw "UI AAS proxy not reachable at http://127.0.0.1:18080/aas/api/shells (HTTP not 2xx after wait)" }
    $uiCount = Get-AasShellCountFromResponse $uiShells
    Write-Host ("ui shells fetched (via nginx /aas/api/shells): " + $uiCount) -ForegroundColor Green
    if ($uiCount -lt 1) { throw "Expected at least 1 shell in BaSyx result after seed; got count=$uiCount" }

    Write-Host ""
    Write-Host "verify_aas.ps1 completed successfully." -ForegroundColor Green
    if ($KeepStack) {
        Write-Host "Stack left running (-KeepStack). Open http://localhost:18080/aas" -ForegroundColor Yellow
    }
}
finally {
    if (-not $KeepStack) {
        Write-Step "8) docker compose down"
        docker compose --profile ui --profile app down
    } else {
        Write-Step "8) skip docker compose down (-KeepStack)"
    }
}
