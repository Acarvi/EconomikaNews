$ErrorActionPreference = "Continue"

function Write-Section {
    param([Parameter(Mandatory = $true)][string]$Title)
    Write-Host ""
    Write-Host "==== $Title ===="
}

function Invoke-HealthCheck {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string[]]$Urls
    )

    foreach ($url in $Urls) {
        try {
            Invoke-RestMethod -Uri $url -TimeoutSec 3 | Out-Null
            Write-Host "[OK] $Name online at $url"
            return
        } catch {
            continue
        }
    }

    Write-Host "[WARN] $Name is not responding at: $($Urls -join ', ')"
}

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$overallExitCode = 0

Write-Section "Git Status"
git status
if ($LASTEXITCODE -ne 0) { $overallExitCode = 1 }

Write-Section "Python Compile"
python -m py_compile server.py main.py core/viral_scout.py core/publisher.py services/discovery/x_sources.py
if ($LASTEXITCODE -ne 0) { $overallExitCode = 1 }

Write-Section "Pytest"
pytest -q
if ($LASTEXITCODE -ne 0) { $overallExitCode = 1 }

Write-Section "Service Health"
Invoke-HealthCheck -Name "CentralAIService" -Urls @("http://localhost:8080/health")
Invoke-HealthCheck -Name "CentralPublishingHub" -Urls @("http://localhost:8000/health", "http://localhost:8000/docs", "http://localhost:8000/")

exit $overallExitCode
