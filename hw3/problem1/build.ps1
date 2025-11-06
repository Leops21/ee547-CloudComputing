# builds the images
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

Write-Host "Building images..." -ForegroundColor Cyan
Invoke-Compose build
