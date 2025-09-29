param(
    [string]$Port = "8080"
)

Write-Host "Starting ArXiv API server on port $Port"
Write-Host "Access at: http://localhost:$Port"
Write-Host ""
Write-Host "Available endpoints:"
Write-Host "  GET /papers"
Write-Host "  GET /papers/{arxiv_id}"
Write-Host "  GET /search?q={query}"
Write-Host "  GET /stats"
Write-Host ""

docker run --rm --name arxiv-server -p "$Port`:8080" arxiv-server:latest