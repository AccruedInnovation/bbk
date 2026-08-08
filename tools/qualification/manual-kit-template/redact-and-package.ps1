[CmdletBinding()]
param(
    [string]$QualificationRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) "bbk-alpha17-@BBK_RC_SLUG@-manual"),
    [string]$RawEvidenceDirectory = "",
    [string]$Python = ""
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$record = Get-Content -Raw -LiteralPath (Join-Path $QualificationRoot "evidence\install-record.json") | ConvertFrom-Json
if (-not $RawEvidenceDirectory) { $RawEvidenceDirectory = Join-Path $QualificationRoot "evidence-raw" }
if (-not $Python) { $Python = [string]$record.tools.python.path }
$redacted = Join-Path $QualificationRoot "evidence-redacted"
$report = Join-Path $QualificationRoot "redaction-report.json"
& $Python (Join-Path $PSScriptRoot "redact-evidence.py") --input $RawEvidenceDirectory --output $redacted --report $report
if ($LASTEXITCODE -ne 0) { throw "Redaction or secret-pattern scan failed. Inspect $report" }
Copy-Item -LiteralPath $report -Destination (Join-Path $redacted "redaction-report.json")
$zip = Join-Path $QualificationRoot "bbk-alpha17-@BBK_RC_SLUG@-redacted-evidence.zip"
if (Test-Path -LiteralPath $zip) { throw "Evidence ZIP already exists: $zip" }
Compress-Archive -Path (Join-Path $redacted "*") -DestinationPath $zip -CompressionLevel Optimal
$sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash.ToLowerInvariant()
"$sha  $([IO.Path]::GetFileName($zip))" | Set-Content -Encoding ASCII "$zip.sha256"
Write-Host "Redaction scan PASS. Manual inspection is still required."
Write-Host "Redacted directory: $redacted"
Write-Host "Evidence ZIP: $zip"
Write-Host "SHA-256: $sha"
