[CmdletBinding()]
param()

# One-time local PostgreSQL bootstrap for Windows. Run from an elevated PowerShell.
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pgRoot = 'C:\Program Files\PostgreSQL\17'
$pgBin = Join-Path $pgRoot 'bin'
$dataDir = Join-Path $pgRoot 'data'
$hbaPath = Join-Path $dataDir 'pg_hba.conf'
$backupPath = "$hbaPath.project-backup"
$serviceName = 'postgresql-x64-17'

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script from an Administrator PowerShell window.'
}
if (-not (Test-Path (Join-Path $pgBin 'psql.exe'))) {
    throw "PostgreSQL 17 was not found at $pgRoot. Install it first."
}
if (-not (Test-Path $hbaPath)) {
    throw "PostgreSQL data directory was not found: $dataDir"
}

$localHostPattern = "^\s*host\s+all\s+all\s+127\.0\.0\.1/32\s+"
$authReplacementPattern = "(\s+)(scram-sha-256|md5)(\s*)$"
$trustReplacement = '$1trust$3'
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
$service = Get-Service -Name $serviceName -ErrorAction Stop
$restoreNeeded = $false

try {
    Copy-Item $hbaPath $backupPath -Force
    $restoreNeeded = $true
    $changed = $false
    $updated = Get-Content $hbaPath | ForEach-Object {
        if ($_ -match $localHostPattern) {
            $changed = $true
            $_ -replace $authReplacementPattern, $trustReplacement
        } else {
            $_
        }
    }
    if (-not $changed) {
        throw 'The local IPv4 authentication rule was not found; no PostgreSQL configuration was changed.'
    }
    [System.IO.File]::WriteAllLines($hbaPath, [string[]]$updated, $utf8NoBom)

    Restart-Service -Name $serviceName -Force
    Start-Sleep -Seconds 2

    $securePassword = Read-Host 'Enter a new password for the postgres administrator' -AsSecureString
    $postgresPassword = [System.Net.NetworkCredential]::new('', $securePassword).Password
    if ([string]::IsNullOrWhiteSpace($postgresPassword)) {
        throw 'The postgres password cannot be empty.'
    }
    $escapedPostgresPassword = $postgresPassword.Replace("'", "''")
    $alterPostgresSql = "ALTER ROLE postgres WITH PASSWORD '$escapedPostgresPassword';"
    & (Join-Path $pgBin 'psql.exe') -U postgres -h 127.0.0.1 -d postgres -v ON_ERROR_STOP=1 -c $alterPostgresSql
    if ($LASTEXITCODE -ne 0) { throw 'Could not set the postgres administrator password.' }

    $appPassword = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ })
    $roleQuery = "SELECT 1 FROM pg_roles WHERE rolname = 'essay_app'"
    $roleExists = & (Join-Path $pgBin 'psql.exe') -U postgres -h 127.0.0.1 -d postgres -tAc $roleQuery
    if (-not ($roleExists -match '1')) {
        $createRoleSql = "CREATE USER essay_app WITH PASSWORD '$appPassword';"
        & (Join-Path $pgBin 'psql.exe') -U postgres -h 127.0.0.1 -d postgres -v ON_ERROR_STOP=1 -c $createRoleSql
    } else {
        $alterRoleSql = "ALTER ROLE essay_app WITH PASSWORD '$appPassword';"
        & (Join-Path $pgBin 'psql.exe') -U postgres -h 127.0.0.1 -d postgres -v ON_ERROR_STOP=1 -c $alterRoleSql
    }
    if ($LASTEXITCODE -ne 0) { throw 'Could not create or update the essay_app database user.' }

    $databaseQuery = "SELECT 1 FROM pg_database WHERE datname = 'essay_evaluation'"
    $databaseExists = & (Join-Path $pgBin 'psql.exe') -U postgres -h 127.0.0.1 -d postgres -tAc $databaseQuery
    if (-not ($databaseExists -match '1')) {
        & (Join-Path $pgBin 'psql.exe') -U postgres -h 127.0.0.1 -d postgres -v ON_ERROR_STOP=1 -c 'CREATE DATABASE essay_evaluation OWNER essay_app;'
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the essay_evaluation database.' }
    }

    $envFile = Join-Path $projectRoot 'backend\.env'
    $envExample = Join-Path $projectRoot 'backend\.env.example'
    if (-not (Test-Path $envFile)) {
        if (-not (Test-Path $envExample)) { throw "Missing environment template: $envExample" }
        Copy-Item $envExample $envFile
    }
    $databaseUrl = 'DATABASE_URL=postgresql+asyncpg://essay_app:{0}@127.0.0.1:5432/essay_evaluation' -f $appPassword
    $lines = @((Get-Content $envFile | Where-Object { $_ -notmatch '^DATABASE_URL=' }), $databaseUrl)
    [System.IO.File]::WriteAllLines($envFile, [string[]]$lines, $utf8NoBom)
}
finally {
    if ($restoreNeeded) {
        Copy-Item $backupPath $hbaPath -Force
        Restart-Service -Name $serviceName -Force
        Remove-Item $backupPath -Force -ErrorAction SilentlyContinue
    }
}

$backendDir = Join-Path $projectRoot 'backend'
$pythonExe = Join-Path $backendDir '.venv\Scripts\python.exe'
if (-not (Test-Path $pythonExe)) {
    throw "Backend virtual environment was not found: $pythonExe"
}
Push-Location $backendDir
try {
    & $pythonExe -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
}
finally {
    Pop-Location
}

Write-Host 'Local PostgreSQL is configured and migrations are complete. Run .\start.ps1 now.'
