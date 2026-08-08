param(
    [Parameter(Mandatory=$true)][ValidateSet("MH-CODEX-01","MH-CODEX-02","MH-CODEX-03","MH-CODEX-04","MH-CODEX-05","MH-CODEX-06")][string]$TestId,
    [Parameter(Mandatory=$true)][string]$LogPath,
    [string]$OutputRoot = (Join-Path $PSScriptRoot "analysis"),
    [string]$Python = "python"
)
$ErrorActionPreference = "Stop"
$pythonPath = (Get-Command $Python -ErrorAction Stop).Source
$log = (Resolve-Path -LiteralPath $LogPath).Path
$out = Join-Path $OutputRoot $TestId
New-Item -ItemType Directory -Path $out -Force | Out-Null
& $pythonPath (Join-Path $PSScriptRoot "jsonl-analyzer\bbk_jsonl_analyzer.py") analyze $log --output $out --label $TestId --config (Join-Path $PSScriptRoot "jsonl-analyzer\alpha17-config.json")
if ($LASTEXITCODE -ne 0) { throw "JSONL analyzer failed: $LASTEXITCODE" }
if ($TestId -in @("MH-CODEX-01","MH-CODEX-02","MH-CODEX-03")) {
    & $pythonPath (Join-Path $PSScriptRoot "jsonl-analyzer\evaluate_alpha17_gates.py") `
      --analysis-dir $out `
      --compiled-manifest (Join-Path $PSScriptRoot "gate-inputs\bbk-worker-codex-compiled-manifest.json") `
      --effective-catalog (Join-Path $PSScriptRoot "gate-inputs\bbk-worker-codex-effective-catalog.json") `
      --planning-readiness (Join-Path $PSScriptRoot "gate-inputs\planning-readiness.valid.json") `
      --prompt (Join-Path $PSScriptRoot "gate-inputs\bbk_worker.toml") `
      --output (Join-Path $out "alpha17-gate-report.json")
    if ($LASTEXITCODE -ne 0) { Write-Warning "One or more Alpha.17 hard gates did not pass; preserve the report." }
}
Write-Host "Analysis written to: $out"
