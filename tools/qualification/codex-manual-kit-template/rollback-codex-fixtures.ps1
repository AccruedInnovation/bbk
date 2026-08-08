param([string]$QualificationRoot = (Join-Path $PSScriptRoot "bbk-alpha17-@BBK_RC_SLUG@-codex-manual"), [string]$Python = "python")
$ErrorActionPreference = "Stop"
$recordPath = Join-Path $QualificationRoot "install-record.json"
if (-not (Test-Path -LiteralPath $recordPath -PathType Leaf)) { throw "Install record missing: $recordPath" }
$record = Get-Content -Raw -LiteralPath $recordPath | ConvertFrom-Json
$pythonPath = (Get-Command $Python -ErrorAction Stop).Source
foreach ($project in @($record.worker_project, $record.rolling_wave_project)) {
    & $pythonPath (Join-Path $record.package_root "tools\install.py") uninstall --scope project --root $project
    if ($LASTEXITCODE -ne 0) { throw "BBK uninstall failed for $project" }
}
Write-Host "Managed BBK files were removed from both disposable fixtures. Project files and evidence were preserved."
