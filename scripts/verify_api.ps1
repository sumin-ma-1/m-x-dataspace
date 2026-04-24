#Requires -Version 5.1
<#
.SYNOPSIS
  FastAPI + EDC 연동 API 스모크 테스트

.DESCRIPTION
  아래 순서로 검증합니다.
  1) docker compose up (consumer/provider CP/DP + app profile)
  2) FastAPI health 체크
  3) /api/v1/assets
  4) /api/v1/catalog
  5) /api/v1/dataset
  6) /api/v1/contract
  7) /api/v1/transfer

  참고:
  - EDC Management API 흐름: Catalog/Contract/Transfer system-tests (Eclipse EDC Connector)
  - 앱 엔드포인트: catena-x-sw-sample/app/api.py
#>

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Invoke-JsonPost {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [Parameter(Mandatory = $true)][object]$Body
    )
    $json = $Body | ConvertTo-Json -Depth 30
    return Invoke-RestMethod -Method Post -Uri $Uri -ContentType "application/json" -Body $json -TimeoutSec 180
}

Write-Step "1) docker compose config"
docker compose config | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Step "2) docker compose up (edc + app profile)"
docker compose --profile app up -d --build edc-cp edc-dp provider-cp provider-dp app
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

try {
    Write-Step "3) Wait for API health (http://127.0.0.1:18000/api/v1/health)"
    $deadline = (Get-Date).AddSeconds(240)
    $apiOk = $false
    while ((Get-Date) -lt $deadline) {
        try {
            $health = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:18000/api/v1/health" -TimeoutSec 3
            if ($health.status -eq "ok") {
                $apiOk = $true
                break
            }
        } catch { }
        Start-Sleep -Seconds 2
    }
    if (-not $apiOk) { throw "FastAPI health check failed on :18000" }
    Write-Host "Health OK." -ForegroundColor Green

    Write-Step "4) POST /api/v1/assets"
    $assetsResp = Invoke-JsonPost -Uri "http://127.0.0.1:18000/api/v1/assets" -Body @{}
    Write-Host ("asset_id={0}" -f $assetsResp.asset_id) -ForegroundColor Green

    Write-Step "5) POST /api/v1/catalog"
    $catalogResp = Invoke-JsonPost -Uri "http://127.0.0.1:18000/api/v1/catalog" -Body @{}
    $catalogCount = 0
    if ($catalogResp.catalog -and $catalogResp.catalog.catalog) {
        $catalogCount = @($catalogResp.catalog.catalog).Count
    }
    Write-Host ("catalog entries={0}" -f $catalogCount) -ForegroundColor Green

    Write-Step "6) POST /api/v1/dataset"
    $datasetReq = @{
        asset_id = "$($assetsResp.asset_id)"
    }
    $datasetResp = Invoke-JsonPost -Uri "http://127.0.0.1:18000/api/v1/dataset" -Body $datasetReq
    Write-Host ("dataset @type={0}" -f $datasetResp.dataset.'@type') -ForegroundColor Green

    Write-Step "7) POST /api/v1/contract"
    $contractResp = Invoke-JsonPost -Uri "http://127.0.0.1:18000/api/v1/contract" -Body @{}
    Write-Host ("contractAgreementId={0}" -f $contractResp.contract_agreement_id) -ForegroundColor Green

    Write-Step "8) POST /api/v1/transfer"
    $transferReq = @{
        contract_agreement_id = "$($contractResp.contract_agreement_id)"
    }
    $transferResp = Invoke-JsonPost -Uri "http://127.0.0.1:18000/api/v1/transfer" -Body $transferReq
    Write-Host ("transfer_process_id={0}" -f $transferResp.transfer_process_id) -ForegroundColor Green
    Write-Host ("transfer_state={0}" -f $transferResp.transfer_state) -ForegroundColor Green

    if ($transferResp.transfer_state -ne "COMPLETED") {
        throw "Expected transfer_state=COMPLETED, got $($transferResp.transfer_state)"
    }

    Write-Host ""
    Write-Host "verify_api.ps1 completed successfully." -ForegroundColor Green
}
finally {
    Write-Step "9) docker compose down"
    docker compose --profile app down
}
