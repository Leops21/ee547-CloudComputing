param(
    [string]$Port = "8081"
)

# starts server on background w Docker
Write-Host "Starting server on port "
$process = Start-Process -FilePath "docker" `
    -ArgumentList @("run", "--rm", "--name", "arxiv-server-test", "-p", "$Port`:8080", "arxiv-server:latest") `
    -NoNewWindow -PassThru

# wait secs
Write-Host "Waiting for server startup"
Start-Sleep -Seconds 3

function Test-Endpoint($url, $desc) {
    Write-Host "Testing $desc..."
    try {
        $resp = Invoke-RestMethod -Uri $url -TimeoutSec 5
        Write-Host " $desc working"
    } catch {
        Write-Host " $desc failed"
    }
}

# test endpoints
Test-Endpoint "http://localhost:$Port/papers" "/papers endpoint"
Test-Endpoint "http://localhost:$Port/stats" "/stats endpoint"
Test-Endpoint "http://localhost:$Port/search?q=machine" "search endpoint"

# test 404
Write-Host "Testing 404 handling..."
try {
    $response = Invoke-WebRequest -Uri "http://localhost:$Port/invalid" -Method GET -UseBasicParsing -ErrorAction Stop
    Write-Host " 404 handling failed (got $($response.StatusCode))"
} catch [System.Net.WebException] {
    $statusCode = $_.Exception.Response.StatusCode.value__
    if ($statusCode -eq 404) {
        Write-Host " 404 handling working"
    } else {
        Write-Host " 404 handling failed (got $statusCode)"
    }
}

# stops container
Write-Host "Stopping server..."
docker stop arxiv-server-test | Out-Null

Write-Host "Tests complete"