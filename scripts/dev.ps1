param(
    [ValidateSet('help', 'start', 'stop', 'restart', 'clean')]
    [string]$Command = 'help'
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$Root = Split-Path -Parent $PSScriptRoot
$RunDir = Join-Path $Root '.run'
# Bind and probe 127.0.0.1 explicitly: "localhost" may resolve to ::1 first, and a
# refused IPv6 connection takes Windows about two seconds before it tries IPv4.
$Servers = @(
    @{ Name = 'backend'; Port = 8000; Url = 'http://127.0.0.1:8000/readyz'; Directory = 'backend'
       CommandLine = 'uv run uvicorn app.main:app --host 127.0.0.1 --port 8000' },
    @{ Name = 'frontend'; Port = 4200; Url = 'http://127.0.0.1:4200'; Directory = 'frontend'
       CommandLine = 'npm start -- --host 127.0.0.1 --port 4200' }
)

function Invoke-Step([string]$CommandLine, [string]$Directory = '.') {
    Write-Host "> $CommandLine" -ForegroundColor Cyan
    Push-Location (Join-Path $Root $Directory)
    try {
        # Merge stderr inside cmd: Windows PowerShell would turn every stderr line of a
        # native command (docker and alembic log progress there) into an error.
        cmd /c "$CommandLine 2>&1"
        if ($LASTEXITCODE -ne 0) { throw "'$CommandLine' failed with exit code $LASTEXITCODE" }
    } finally {
        Pop-Location
    }
}

function Get-ListenerIds([int]$Port) {
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
}

function Start-Server($Server) {
    if (Get-ListenerIds $Server.Port) {
        Write-Host "$($Server.Name) already running"
        return
    }
    $log = Join-Path $RunDir "$($Server.Name).log"
    # Start-Process creates an independent process: it keeps running after this terminal
    # is closed and does not inherit (and hold open) the caller's pipes.
    $Server.Process = Start-Process cmd -ArgumentList '/c', "$($Server.CommandLine) > `"$log`" 2>&1" `
        -WorkingDirectory (Join-Path $Root $Server.Directory) -WindowStyle Hidden -PassThru
}

function Wait-Server($Server) {
    $deadline = (Get-Date).AddSeconds(120)
    while ((Get-Date) -lt $deadline -and -not ($Server.Process -and $Server.Process.HasExited)) {
        try {
            Invoke-WebRequest $Server.Url -UseBasicParsing -TimeoutSec 2 | Out-Null
            return
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    $log = Join-Path $RunDir "$($Server.Name).log"
    if (Test-Path $log) { Get-Content $log -Tail 20 }
    throw "$($Server.Name) did not start, see $log"
}

function Stop-Servers {
    foreach ($server in $Servers) {
        foreach ($id in Get-ListenerIds $server.Port) {
            # /T stops the child processes too: stopping only the launcher (npm, uv)
            # leaves the real server holding the port.
            cmd /c "taskkill /F /T /PID $id >nul 2>&1"
        }
    }
}

function Start-All {
    Invoke-Step 'docker compose up -d --wait'
    Invoke-Step 'uv run alembic upgrade head' 'backend'
    if (-not (Test-Path (Join-Path $Root 'frontend\node_modules'))) { Invoke-Step 'npm ci' 'frontend' }
    New-Item -ItemType Directory -Force $RunDir | Out-Null
    foreach ($server in $Servers) { Start-Server $server }
    foreach ($server in $Servers) { Wait-Server $server }
    Write-Host 'Backend:  http://localhost:8000/docs  (log: .run\backend.log)' -ForegroundColor Green
    Write-Host 'Frontend: http://localhost:4200       (log: .run\frontend.log)' -ForegroundColor Green
}

function Stop-All {
    Stop-Servers
    Invoke-Step 'docker compose down'
}

function Clear-All {
    Stop-Servers
    Invoke-Step 'docker compose down --volumes --remove-orphans'
    if (Test-Path $RunDir) { Remove-Item -Recurse -Force $RunDir }
}

try {
    switch ($Command) {
        'start' { Start-All }
        'stop' { Stop-All }
        'restart' { Stop-All; Start-All }
        'clean' { Clear-All }
        default {
            Write-Host 'make start    start the database, apply migrations, run backend and frontend in the background'
            Write-Host 'make stop     stop backend, frontend and the containers; data is kept'
            Write-Host 'make restart  stop, then start'
            Write-Host 'make clean    stop, then delete containers, volumes with the database data and logs; images are kept'
        }
    }
} catch {
    Write-Host $_ -ForegroundColor Red
    exit 1
}
