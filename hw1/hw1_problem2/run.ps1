param(
    [Parameter(Mandatory = $true)]
    [string]$Query,

    [Parameter(Mandatory = $true)]
    [int]$MaxResults,

    [Parameter(Mandatory = $true)]
    [string]$OutputDir
)

# validating range
if ($MaxResults -lt 1 -or $MaxResults -gt 100) {
    Write-Error "Error: max_results must be between 1 and 100"
    exit 1
}

# create dir if does not exists
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
}

#  path
$absoluteOutput = (Resolve-Path $OutputDir).Path

# run cointainer
docker run --rm `
    -v "${absoluteOutput}:/data/output" `
    arxiv-processor:latest `
    "$Query" $MaxResults "/data/output"
