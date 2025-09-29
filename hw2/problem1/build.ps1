# build.ps1
Write-Host "Building Docker image: arxiv-server:latest..."
docker build -t arxiv-server:latest .
if (0 -eq 0) {
    Write-Host "Build completed succesfully"
} else {
    Write-Host "Error in build"
    exit 0
}
