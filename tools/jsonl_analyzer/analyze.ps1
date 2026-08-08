param(
    [Parameter(Mandatory=$true, Position=0)]
    [string[]]$InputPath,

    [Parameter(Mandatory=$true)]
    [string]$OutputPath,

    [string]$Label = "analysis",

    [ValidateSet("redacted", "full", "hash-only", "none")]
    [string]$CommandText = "redacted"
)

$ErrorActionPreference = "Stop"
$script = Join-Path $PSScriptRoot "bbk_jsonl_analyzer.py"
& py -3 $script analyze @InputPath --output $OutputPath --label $Label --command-text $CommandText
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
