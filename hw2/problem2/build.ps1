# Part G: build.ps1

Write-Host "Building autoencoder training container"
docker build -t arxiv-embeddings:latest .
Write-Host "Build complete"
