# Starts DB/Adminer, loads data, runs sample queries
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Compose {
    param([Parameter(ValueFromRemainingArguments=$true)]$Args)
    try {
        & docker compose @Args
    } catch {
        & docker-compose @Args
    }
}

Write-Host "+++++++ Starting PostgreSQL and Adminer +++++++" -ForegroundColor Cyan

# using start-process to avoid block on logs
Start-Process -FilePath "docker" -ArgumentList "compose up -d db adminer" -NoNewWindow -Wait

# function to wait until PostgreSQL is ready
function Wait-ForDatabase {
    Write-Host "waiting for database" -ForegroundColor Yellow
    $maxTries = 20
    for ($i = 1; $i -le $maxTries; $i++) {
        $status = docker exec problem1-db-1 pg_isready -U transit -d transit -h localhost 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Database ready!" -ForegroundColor Green
            return
        }
        Start-Sleep -Seconds 2
    }
    throw "Database not ready in time"
}

Wait-ForDatabase

Write-Host "+++++++ Loading data +++++++" -ForegroundColor Cyan
Invoke-Compose run --rm app python load_data.py `
  --host db --dbname transit --user transit --password transit123 --datadir /app/data

Write-Host "`n+++++++ Running sample queries +++++++" -ForegroundColor Yellow
Invoke-Compose run --rm app python queries.py --query Q1 --dbname transit --host db --user transit --password transit123
Invoke-Compose run --rm app python queries.py --query Q3 --dbname transit --host db --user transit --password transit123

Write-Host "`nAdminer UI at http://localhost:8080  (System: PostgreSQL, Server: db, Username: transit, Password: transit123, Database: transit)" -ForegroundColor Green
