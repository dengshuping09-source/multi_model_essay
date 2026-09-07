[CmdletBinding()]
param(
    [int]$DatabaseTimeoutSeconds = 60,
    [int]$ServiceTimeoutSeconds = 30,
    [int]$PostgresPort = 5432
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$BackendDirectory = Join-Path $ProjectRoot "backend"
$FrontendDirectory = Join-Path $ProjectRoot "frontend"
$LogDirectory = Join-Path $ProjectRoot "logs"
$BackendUrl = "http://127.0.0.1:8000"
$FrontendUrl = "http://127.0.0.1:5173"

function Test-HttpEndpoint {
    param([Parameter(Mandatory)][string]$Url)

    try {
        return (Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 $Url).StatusCode -eq 200
    } catch {
        return $false
    }
}

function Wait-ForHttpEndpoint {
    param(
        [Parameter(Mandatory)][string]$Url,
        [Parameter(Mandatory)][int]$TimeoutSeconds,
        [Parameter(Mandatory)][string]$Name
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-HttpEndpoint $Url) {
            Write-Host "[OK] $Name is ready."
            return
        }
        Start-Sleep -Seconds 1
    }
    throw "$Name did not become ready within $TimeoutSeconds seconds. Check logs in $LogDirectory."
}

function Test-PostgresPort {
    param([Parameter(Mandatory)][int]$Port)

    return Test-NetConnection -ComputerName "127.0.0.1" -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue
}

function Wait-ForPostgresPort {
    param(
        [Parameter(Mandatory)][int]$Port,
        [Parameter(Mandatory)][int]$TimeoutSeconds
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-PostgresPort -Port $Port) {
            Write-Host "[OK] PostgreSQL is ready."
            return
        }
        Start-Sleep -Seconds 2
    }
    throw "PostgreSQL is not reachable on 127.0.0.1:$Port within $TimeoutSeconds seconds."
}

function Start-LocalPostgres {
    param([Parameter(Mandatory)][int]$Port)

    if (Test-PostgresPort -Port $Port) {
        Write-Host "[OK] PostgreSQL is already running locally."
        return $true
    }
    $service = Get-Service -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "postgresql*" -or $_.DisplayName -like "PostgreSQL*" } |
        Select-Object -First 1
    if ($null -eq $service) {
        return $false
    }
    if ($service.Status -ne "Running") {
        Write-Host "Starting local PostgreSQL service..."
        Start-Service -Name $service.Name
    }
    Wait-ForPostgresPort -Port $Port -TimeoutSeconds $DatabaseTimeoutSeconds
    return $true
}

function Start-DockerPostgres {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        return $false
    }
    if (-not (Test-Path (Join-Path $ProjectRoot ".env"))) {
        throw "Missing .env for Docker Compose. Create it from .env.example and set PostgreSQL credentials."
    }
    Write-Host "Starting PostgreSQL with Docker Compose..."
    & docker compose up -d postgres
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose could not start PostgreSQL."
    }
    Wait-ForPostgresPort -Port $PostgresPort -TimeoutSeconds $DatabaseTimeoutSeconds
    return $true
}

function Stop-BackendListener {
    $allPython = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue)
    $listenerPids = @(
        Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
    )
    $rootPids = @(
        $allPython |
            Where-Object {
                $_.CommandLine -and (
                    ($_.CommandLine -match 'app\.py' -and $_.CommandLine -match [regex]::Escape($BackendDirectory)) -or
                    ($_.CommandLine -match 'uvicorn\s+app\.main:app' -and $_.CommandLine -match '--port\s+8000')
                )
            } |
            Select-Object -ExpandProperty ProcessId
    ) + $listenerPids
    $processIds = @($rootPids | Where-Object { $_ -and $_ -ne 0 } | Select-Object -Unique)
    do {
        $children = @(
            $allPython |
                Where-Object { $processIds -contains $_.ParentProcessId -and $processIds -notcontains $_.ProcessId } |
                Select-Object -ExpandProperty ProcessId
        )
        if ($children.Count -gt 0) { $processIds += $children }
    } while ($children.Count -gt 0)
    foreach ($processId in ($processIds | Select-Object -Unique | Sort-Object -Descending)) {
        Write-Host "Stopping existing FastAPI process (PID $processId)..."
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
    if ($processIds.Count -gt 0) { Start-Sleep -Seconds 2 }
}
if (-not (Test-Path (Join-Path $BackendDirectory ".env"))) {
    throw "Missing backend/.env. Create it from backend/.env.example and set DATABASE_URL before starting the project."
}
if (-not (Test-Path (Join-Path $BackendDirectory ".venv\Scripts\python.exe"))) {
    throw "Missing backend virtual environment. Create it and install backend/requirements.txt first."
}
if (-not (Test-Path (Join-Path $FrontendDirectory "node_modules"))) {
    throw "Missing frontend/node_modules. Run 'npm install' in frontend first."
}

New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null
Set-Location $ProjectRoot

if (-not (Start-LocalPostgres -Port $PostgresPort)) {
    if (-not (Start-DockerPostgres)) {
        throw "PostgreSQL is not installed or running. Install PostgreSQL for Windows, configure backend/.env, then run this script again."
    }
}

 $backendHealthUrl = "$BackendUrl/api/health"
 $databaseHealthUrl = "$BackendUrl/api/health/database"
 $backendIsRunning = Test-HttpEndpoint $backendHealthUrl
 $databaseIsHealthy = $backendIsRunning -and (Test-HttpEndpoint $databaseHealthUrl)
 if ($backendIsRunning -and $databaseIsHealthy) {
    Write-Host "[OK] FastAPI and its database connection are already healthy."
} else {
    if ($backendIsRunning) {
        Write-Host "FastAPI is running but its database connection is unhealthy; refreshing the process after .env changes."
        Stop-BackendListener
    }
    Write-Host "Starting FastAPI..."
    $backendProcess = @{
        FilePath = Join-Path $BackendDirectory ".venv\Scripts\python.exe"
        ArgumentList = @("app.py")
        WorkingDirectory = $BackendDirectory
        WindowStyle = "Hidden"
        RedirectStandardOutput = Join-Path $LogDirectory "backend.log"
        RedirectStandardError = Join-Path $LogDirectory "backend-error.log"
    }
    Start-Process @backendProcess
    Wait-ForHttpEndpoint -Url "$BackendUrl/api/health" -TimeoutSeconds $ServiceTimeoutSeconds -Name "FastAPI"
}
Wait-ForHttpEndpoint -Url "$BackendUrl/api/health/database" -TimeoutSeconds $ServiceTimeoutSeconds -Name "FastAPI database connection"

if (Test-HttpEndpoint $FrontendUrl) {
    Write-Host "[OK] Vue is already running."
} else {
    Write-Host "Starting Vue..."
    $frontendProcess = @{
        FilePath = "npm.cmd"
        ArgumentList = @("run", "dev", "--", "--host", "127.0.0.1", "--port", "5173")
        WorkingDirectory = $FrontendDirectory
        WindowStyle = "Hidden"
        RedirectStandardOutput = Join-Path $LogDirectory "frontend.log"
        RedirectStandardError = Join-Path $LogDirectory "frontend-error.log"
    }
    Start-Process @frontendProcess
    Wait-ForHttpEndpoint -Url $FrontendUrl -TimeoutSeconds $ServiceTimeoutSeconds -Name "Vue"
}

Write-Host ""
Write-Host "Project is ready:"
Write-Host "  Vue:      $FrontendUrl"
Write-Host "  FastAPI:  $BackendUrl"
Write-Host "  API docs: $BackendUrl/api/docs"
Write-Host "  Health:   $BackendUrl/api/health"
