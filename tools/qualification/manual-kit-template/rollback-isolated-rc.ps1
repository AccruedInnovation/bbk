[CmdletBinding()]
param(
    [string]$QualificationRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) "bbk-alpha17-@BBK_RC_SLUG@-manual"),
    [switch]$RemoveQualificationDirectory
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$recordPath = Join-Path $QualificationRoot "evidence\install-record.json"
if (-not (Test-Path -LiteralPath $recordPath -PathType Leaf)) { throw "Install record missing: $recordPath" }
$record = Get-Content -Raw -LiteralPath $recordPath | ConvertFrom-Json
$project = [string]$record.project_root
$python = [string]$record.tools.python.path
$package = [string]$record.package_root
$rollback = & $python (Join-Path $package "tools\install.py") --json uninstall --scope project --root $project 2>&1 | Out-String
$code = $LASTEXITCODE
$rollback | Set-Content -Encoding UTF8 (Join-Path $QualificationRoot "evidence\rollback.json")
if ($code -ne 0) { throw "Project-scope rollback failed ($code): $rollback" }
if (Test-Path -LiteralPath (Join-Path $project ".bbk-kit-install.json")) { throw "Project install manifest remains after rollback" }
Write-Host "Project-scope manifest-owned rollback PASS. User-scope BBK was not targeted."
if ($RemoveQualificationDirectory) {
    $resolved = (Resolve-Path $QualificationRoot).Path
    if ((Split-Path -Leaf $resolved) -ne "bbk-alpha17-@BBK_RC_SLUG@-manual") { throw "Refusing recursive removal for non-default qualification directory: $resolved" }
    Remove-Item -LiteralPath $resolved -Recurse -Force
    Write-Host "Removed qualification directory: $resolved"
}
