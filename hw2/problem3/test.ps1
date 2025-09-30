# Test-AwsInspector.ps1
Write-Host "Testing AWS Inspector Script"

# Test 1: Authentication check
Write-Host "Test 1: Authentication check"
python aws_inspector.py --region us-east-1 --format json > $null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Authentication successful"
} else {
    Write-Host "Authentication failed"
    exit 1
}

# Test 2: JSON output format
Write-Host "Test 2: JSON output format"
python aws_inspector.py --region us-east-1 --format json --output test_output.json
if (Test-Path "test_output.json") {
    try {
        python -m json.tool test_output.json > $null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Valid JSON output generated"
        } else {
            Write-Host "Invalid JSON output"
        }
    } catch {
        Write-Host "JSON validation failed: $($_.Exception.Message)"
    }
    Remove-Item "test_output.json"
} else {
    Write-Host "Output file not created"
}

# Test 3: Table output format
Write-Host "Test 3: Table output format"
python aws_inspector.py --region us-east-1 --format table | Select-Object -First 10
Write-Host "Table format displayed"

# Test 4: Invalid region handling
Write-Host "Test 4: Invalid region handling"
python aws_inspector.py --region invalid-region 2> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Invalid region properly rejected"
} else {
    Write-Host "Invalid region accepted"
}

Write-Host ""
Write-Host "Testing complete. Review output above for any failures"
