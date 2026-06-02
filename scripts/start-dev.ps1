param(
    [string]$MysqlPassword = "275874",
    [string]$DatabaseName = "cscec_safety"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Alembic = Join-Path $Root ".venv\Scripts\alembic.exe"

function Test-MysqlPort {
    param([int]$Port)
    $script = @"
import pymysql
try:
    conn = pymysql.connect(host='127.0.0.1', port=$Port, user='root', password='$MysqlPassword', charset='utf8mb4', autocommit=True, connect_timeout=3)
    with conn.cursor() as cursor:
        cursor.execute("CREATE DATABASE IF NOT EXISTS $DatabaseName CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    conn.close()
    print("ok")
except Exception as exc:
    print(f"failed: {exc}")
    raise SystemExit(1)
"@
    Push-Location $Root
    try {
        $script | & $Python - *> $null
        if ($LASTEXITCODE -eq 0) {
            return $true
        }
        return $false
    }
    finally {
        Pop-Location
    }
}

function Invoke-Native {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $FilePath $($Arguments -join ' ')"
    }
}

if (-not (Test-Path $Python)) {
    py -3.12 -m venv (Join-Path $Root ".venv")
    & $Python -m pip install -e "$Backend[dev]"
}

$dbPort = $null
if (Test-MysqlPort -Port 3307) {
    $dbPort = 3307
}
elseif (Test-MysqlPort -Port 3306) {
    $dbPort = 3306
}
else {
    Write-Host "No MySQL instance is reachable on 3307 or 3306. Start Docker Desktop or local MySQL, then rerun this script."
    exit 1
}

$env:DATABASE_URL = "mysql+pymysql://root:$MysqlPassword@127.0.0.1:$dbPort/$DatabaseName"

Push-Location $Backend
Invoke-Native -FilePath $Alembic -Arguments @("upgrade", "head")
Invoke-Native -FilePath $Python -Arguments @("scripts\seed_demo_data.py")
Pop-Location

foreach ($port in @(8000, 5173)) {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}

$backendCmd = @"
`$env:DATABASE_URL='$env:DATABASE_URL'
Set-Location '$Backend'
& '$Python' -m uvicorn app.main:app --host 127.0.0.1 --port 8000
"@
Start-Process -FilePath powershell -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $backendCmd) -WindowStyle Hidden

$frontendCmd = @"
Set-Location '$Frontend'
npm run dev -- --host 127.0.0.1 --port 5173
"@
Start-Process -FilePath powershell -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $frontendCmd) -WindowStyle Hidden

Start-Sleep -Seconds 6
Write-Host "Database: $env:DATABASE_URL"
Write-Host "Backend:  http://127.0.0.1:8000/docs"
Write-Host "Frontend: http://127.0.0.1:5173"
