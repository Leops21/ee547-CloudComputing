param(
    [string]$InputFile,
    [string]$OutputDir
)

# verify number of args
if (-not $InputFile -or -not $OutputDir) {
    Write-Host "Usage: .\run.ps1 <input_file> <output_directory>"
    exit 1
}

# verify if file exists
if (-not (Test-Path $InputFile)) {
    Write-Host "Error: Input file $InputFile does not exist"
    exit 1
}

# create dir if does not exists
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
}

# paths
$InputPath = (Resolve-Path $InputFile).Path
$OutputPath = (Resolve-Path $OutputDir).Path

# run container
docker run --rm `
    --name http-fetcher `
    -v "${InputPath}:/data/input/urls.txt:ro" `
    -v "${OutputPath}:/data/output" `
    http-fetcher:latest

