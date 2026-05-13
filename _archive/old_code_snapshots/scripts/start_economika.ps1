$ErrorActionPreference = "Continue"

function Write-Status {
    param(
        [Parameter(Mandatory = $true)][string]$Level,
        [Parameter(Mandatory = $true)][string]$Message
    )
    Write-Host "[$Level] $Message"
}

function Test-Endpoint {
    param(
        [Parameter(Mandatory = $true)][string[]]$Urls
    )

    foreach ($url in $Urls) {
        try {
            Invoke-RestMethod -Uri $url -TimeoutSec 3 | Out-Null
            return $url
        } catch {
            continue
        }
    }

    return $null
}

function Start-LocalService {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        Write-Status "WARN" "$Name folder not found at $Path"
        return
    }

    try {
        Write-Status "START" "Trying to start $Name from $Path"
        Start-Process -FilePath "powershell" -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "cd '$Path'; python main.py" -WorkingDirectory $Path -WindowStyle Minimized | Out-Null
        Start-Sleep -Seconds 5
    } catch {
        Write-Status "WARN" "Could not start $Name automatically: $($_.Exception.Message)"
    }
}

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not (Test-Path -LiteralPath "main.py")) {
    Write-Status "ERROR" "main.py was not found in $repoRoot"
    exit 1
}

try {
    $pythonVersion = python --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Status "ERROR" "Python is not available in PATH"
        exit 1
    }
    Write-Status "OK" "Python found: $pythonVersion"
} catch {
    Write-Status "ERROR" "Python is not available in PATH"
    exit 1
}

$centralAiUrl = Test-Endpoint -Urls @("http://localhost:8080/health")
if ($centralAiUrl) {
    Write-Status "OK" "CentralAIService online at $centralAiUrl"
} else {
    Write-Status "WARN" "CentralAIService is not responding on http://localhost:8080/health"
    Start-LocalService -Name "CentralAIService" -Path "D:\Scripts\CentralAIService"
    $centralAiUrl = Test-Endpoint -Urls @("http://localhost:8080/health")
    if ($centralAiUrl) {
        Write-Status "OK" "CentralAIService online at $centralAiUrl"
    } else {
        Write-Status "WARN" "CentralAIService still offline. The GUI can open, but AI generation may fail."
    }
}

$publishingHubUrl = Test-Endpoint -Urls @("http://localhost:8000/health", "http://localhost:8000/docs", "http://localhost:8000/")
if ($publishingHubUrl) {
    Write-Status "OK" "CentralPublishingHub online at $publishingHubUrl"
} else {
    Write-Status "WARN" "CentralPublishingHub is not responding on /health, /docs, or /"
    Start-LocalService -Name "CentralPublishingHub" -Path "D:\Scripts\CentralPublishingHub"
    $publishingHubUrl = Test-Endpoint -Urls @("http://localhost:8000/health", "http://localhost:8000/docs", "http://localhost:8000/")
    if ($publishingHubUrl) {
        Write-Status "OK" "CentralPublishingHub online at $publishingHubUrl"
    } else {
        Write-Status "WARN" "CentralPublishingHub still offline. Publish actions may fail until it is started."
    }
}

Write-Status "START" "Launching EconomikaNoticias GUI"
python main.py
exit $LASTEXITCODE
