Write-Output "=== Test 1: Machine Learning papers ==="
.\run.ps1 "cat:cs.LG" 5 "output_ml"

Write-Output "=== Test 2: Search by author ==="
.\run.ps1 "au:LeCun" 3 "output_author"

Write-Output "=== Test 3: Search by title keyword ==="
.\run.ps1 "ti:transformer" 10 "output_title"

Write-Output "=== Test 4: Complex query (ML papers about transformers from 2023) ==="
.\run.ps1 "cat:cs.LG AND ti:transformer AND submittedDate:[202301010000 TO 202312312359]" 5 "output_complex"

Write-Output "=== Tests completed. Check output directories for results. ==="
