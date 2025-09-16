Write-Output "Test 1: Single URL"
.\run_pipeline.ps1 -urls "https://www.example.com"

Write-Output "
Test 2: Multiple URLs from file"
https://www.example.com https://www.wikipedia.org https://httpbin.org/html = Get-Content .\test_urls.txt
.\run_pipeline.ps1 -urls https://www.example.com https://www.wikipedia.org https://httpbin.org/html

Write-Output "
Test 3: Verify output structure"
python -c "
import json
with open('output/final_report.json') as f:
    data = json.load(f)
    assert 'documents_processed' in data
    assert 'top_100_words' in data
    assert 'document_similarity' in data
    print('Output validation passed')
"