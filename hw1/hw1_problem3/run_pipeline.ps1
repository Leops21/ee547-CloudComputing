param()

Write-Output "Starting Multi-Container Pipeline"
Write-Output "================================="

# Clean previous runs
docker-compose down -v 2>$null

# Create temp directory
$tempDir = New-Item -ItemType Directory -Force -Path (Join-Path $env:TEMP ("pipeline_" + [guid]::NewGuid()))

# Copy local test_urls.txt into temp (with the same name)
Copy-Item ".\test_urls.txt" "$tempDir\test_urls.txt" -Force

Write-Output "URLs to process:"
Get-Content "$tempDir\test_urls.txt"
Write-Output ""

# Build containers
Write-Output "Building containers..."
docker-compose build

# Start pipeline
Write-Output "Starting pipeline..."
docker-compose up -d

# Wait for containers to initialize
Start-Sleep -Seconds 3

# Inject URLs (keep name as test_urls.txt because fetch.py expects it)
Write-Output "Injecting URLs..."
docker cp "$tempDir\test_urls.txt" pipeline-fetcher:/shared/input/test_urls.txt

# Monitor completion
Write-Output "Processing..."
$maxWait = 300  # 5 minutes
$elapsed = 0

while ($elapsed -lt $maxWait) {
    $exists = docker exec pipeline-analyzer test -f /shared/analysis/final_report.json 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Output "Pipeline complete"
        break
    }
    Start-Sleep -Seconds 5
    $elapsed += 5
}

if ($elapsed -ge $maxWait) {
    Write-Output "Pipeline timeout after $maxWait seconds"
    docker-compose logs
    docker-compose down
    exit 1
}

# Extract results
New-Item -ItemType Directory -Force -Path "output" | Out-Null
docker cp pipeline-analyzer:/shared/analysis/final_report.json output/
docker cp pipeline-analyzer:/shared/status output/

# Cleanup
docker-compose down

# Display summary
if (Test-Path "output/final_report.json") {
    Write-Output ""
    Write-Output "Results saved to output/final_report.json"
    python -m json.tool output/final_report.json | Select-Object -First 20
} else {
    Write-Output "Pipeline failed - no output generated"
    exit 1
}
