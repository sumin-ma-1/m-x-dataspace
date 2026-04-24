#Requires -Version 5.1
<#
.SYNOPSIS
  원클릭 검증: pytest → docker compose build/up → CP/DP 헬스 확인 → compose down

.DESCRIPTION
  - Python 테스트는 로컬에서 실행합니다.
  - EDC 이미지는 Docker 공식 Gradle/Temurin 이미지로 빌드됩니다.
  - CP/DP 라이브니스 경로는 EDC api-observability 확장의 /check/liveness + 버전 prefix 입니다.

  참고:
  - Docker Compose: https://docs.docker.com/compose/
  - EDC Observability: Connector 저장소 extensions/common/api/api-observability
  - 실행: Windows PowerShell 에서 `powershell -File scripts/verify.ps1`
#>

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

Write-Step "1) Python unit tests (catena-x-sw-sample)"
python -m pytest "catena-x-sw-sample/tests" -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Step "2) docker compose config (syntax)"
docker compose config | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Step "3) docker compose build (edc-cp, edc-dp)"
docker compose build edc-cp edc-dp
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Step "4) docker compose up (edc-cp, edc-dp)"
docker compose up -d edc-cp edc-dp
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

try {
    Write-Step "5) Wait for health (max ~180s)"
    $deadline = (Get-Date).AddSeconds(180)
    $cpOk = $false
    $dpOk = $false
    while ((Get-Date) -lt $deadline) {
        if (-not $cpOk) {
            try {
                Invoke-WebRequest -Uri "http://127.0.0.1:19191/api/check/liveness" -UseBasicParsing -TimeoutSec 3 | Out-Null
                $cpOk = $true
            } catch { }
        }
        if (-not $dpOk) {
            try {
                Invoke-WebRequest -Uri "http://127.0.0.1:19192/api/check/liveness" -UseBasicParsing -TimeoutSec 3 | Out-Null
                $dpOk = $true
            } catch { }
        }
        if ($cpOk -and $dpOk) { break }
        Start-Sleep -Seconds 2
    }

    if (-not $cpOk) { throw "edc-cp did not become healthy on http://127.0.0.1:19191/api/check/liveness" }
    if (-not $dpOk) { throw "edc-dp did not become healthy on http://127.0.0.1:19192/api/check/liveness" }

    Write-Host "CP/DP liveness OK." -ForegroundColor Green
}
finally {
    Write-Step "6) docker compose down"
    docker compose down
}

Write-Host ""
Write-Host "verify.ps1 completed successfully." -ForegroundColor Green
