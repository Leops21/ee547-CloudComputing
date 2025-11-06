# builds, runs, executes all queries, and tears down
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

Write-Host "+++++++ Build +++++++" -ForegroundColor Cyan
./build.ps1

Write-Host "`n+++++++ Run +++++++" -ForegroundColor Cyan
./run.ps1

Write-Host "`n+++++++ Testing all queries +++++++" -ForegroundColor Cyan
for ($i = 1; $i -le 10; $i++) {
    $q = "Q$($i)"
    Write-Host "Running $q ..." -ForegroundColor Yellow
    Invoke-Compose run --rm app python queries.py --query $q --dbname transit --host db --user transit --password transit123 --format json
}

Write-Host "`n+++++++ Shutting down +++++++" -ForegroundColor Cyan
Invoke-Compose down
