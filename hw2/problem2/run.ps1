param(
    [Parameter(Mandatory = $true)]
    [string]$InputFile,

    [Parameter(Mandatory = $true)]
    [string]$OutputDir,

    [int]$Epochs = 50,
    [int]$BatchSize = 32
)

# validate input file
if (-not (Test-Path $InputFile)) {
    Write-Error "Error: Input file $InputFile not found"
    exit 1
}

# create output directory if needed
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
}

$absoluteInput = (Resolve-Path $InputFile).Path
$absoluteOutput = (Resolve-Path $OutputDir).Path

Write-Output "Training embeddings with settings:"
Write-Output "  Input: $absoluteInput"
Write-Output "  Output: $absoluteOutput"
Write-Output "  Epochs: $Epochs"
Write-Output "  Batch size: $BatchSize"

docker run --rm `
    --name arxiv-embeddings `
    -v "${absoluteInput}:/data/input/papers.json:ro" `
    -v "${absoluteOutput}:/data/output" `
    arxiv-embeddings:latest `
    /data/input/papers.json /data/output --epochs $Epochs --batch_size $BatchSize

Write-Output "Training complete. Output files:"
Get-ChildItem $absoluteOutput