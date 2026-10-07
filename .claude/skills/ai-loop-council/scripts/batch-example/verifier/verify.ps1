# Example verifier for batch-example/batch.json: accepts a candidate that contains the word GOOD (capital letters).
# It lives in a folder of its own because delegate.ps1 freezes the verifier's whole folder (V2-02).
param([string] $Script)
$text = if (Test-Path -LiteralPath $Script -PathType Leaf) { Get-Content -Raw -LiteralPath $Script } else { '' }
if ("$text" -cmatch '\bGOOD\b') { Write-Output '1/1 passed'; exit 0 }
Write-Output 'FAIL the candidate does not contain the word GOOD'
Write-Output '0/1 passed'
exit 1
