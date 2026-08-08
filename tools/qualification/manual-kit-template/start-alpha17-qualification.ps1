[CmdletBinding()]
param(
    [string]$QualificationRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) "bbk-alpha17-@BBK_RC_SLUG@-manual"),
    [string]$Model = "",
    [string]$OmpProfile = ""
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Quote-PowerShellLiteral([string]$Value) {
    if ($null -eq $Value) { return "''" }
    return "'" + $Value.Replace("'", "''") + "'"
}

function Require-File([string]$Path,[string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "$Label missing: $Path" }
    return (Resolve-Path -LiteralPath $Path).Path
}

$recordPath = Join-Path $QualificationRoot "evidence\install-record.json"
$recordPath = Require-File $recordPath "Install record; run install-isolated-rc.ps1 first"
$record = Get-Content -Raw -LiteralPath $recordPath | ConvertFrom-Json
if ([string]$record.rc_version -ne "@BBK_VERSION@") {
    throw "Install record package version mismatch: expected @BBK_VERSION@, observed $($record.rc_version)"
}
$project = (Resolve-Path -LiteralPath ([string]$record.project_root)).Path
$omp = Require-File ([string]$record.tools.omp.path) "OMP executable"
$python = Require-File ([string]$record.tools.python.path) "Python executable"
$roleReturnPython = Require-File ([string]$record.tools.role_return_python.path) "Role-return validation Python"
$git = Require-File ([string]$record.tools.git.path) "Git executable"
$mise = Require-File ([string]$record.tools.mise.path) "mise executable"
$extension = Require-File (Join-Path $project ".omp\extensions\bbk\index.js") "Installed BBK extension"
$helper = Require-File (Join-Path $PSScriptRoot "manual-bootstrap-extension.mjs") "Manual qualification helper"
$overlay = Require-File (Join-Path $PSScriptRoot "omp-qualification-overlay.yml") "OMP qualification overlay"
if ([string]$record.tools.omp.version -notmatch "16\.4\.8") {
    throw "Install record is not bound to OMP 16.4.8: $($record.tools.omp.version)"
}

$environment = [ordered]@{
    MISE_DATA_DIR = [string]$record.mise_environment.data_dir
    MISE_CACHE_DIR = [string]$record.mise_environment.cache_dir
    MISE_CONFIG_DIR = [string]$record.mise_environment.config_dir
    MISE_YES = "1"
    MISE_NO_DOTENV = "1"
    NO_COLOR = "1"
    CLICOLOR = "0"
    BD_NON_INTERACTIVE = "1"
    BEADS_DISABLE_METRICS = "1"
    BBK_GOVERNED_PROFILE = "governed-software"
    BBK_PROJECT_ROOT = $project
    BBK_OMP_HOST_VERSION = "omp/16.4.8"
    BBK_EXPECTED_PACKAGE_VERSION = "@BBK_VERSION@"
    BBK_PYTHON = $roleReturnPython
    BBK_OPERATOR_PYTHON = $python
    BBK_GIT = $git
    BBK_MISE = $mise
    BBK_MANUAL_HARNESS_ROOT = $PSScriptRoot
}
$arguments = @(
    '--cwd', $project,
    '--config', $overlay,
    '--no-skills',
    '--no-rules',
    '--extension', $extension,
    '--extension', $helper
)
if (-not [string]::IsNullOrWhiteSpace($Model)) { $arguments += @('--model', $Model) }
if (-not [string]::IsNullOrWhiteSpace($OmpProfile)) { $arguments += @('--profile', $OmpProfile) }

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add('$ErrorActionPreference = ''Stop''')
foreach ($entry in $environment.GetEnumerator()) {
    $lines.Add('$env:' + $entry.Key + ' = ' + (Quote-PowerShellLiteral ([string]$entry.Value)))
}
$lines.Add('Set-Location -LiteralPath ' + (Quote-PowerShellLiteral $project))
$quotedArguments = @($arguments | ForEach-Object { Quote-PowerShellLiteral ([string]$_) })
$lines.Add('& ' + (Quote-PowerShellLiteral $omp) + ' ' + ($quotedArguments -join ' '))
$commandBlock = ($lines -join [Environment]::NewLine) + [Environment]::NewLine

$outputPath = Join-Path $QualificationRoot "evidence\launch-alpha17-qualification-command.ps1"
[System.IO.File]::WriteAllText($outputPath, $commandBlock, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "Validated the @BBK_RC_LABEL@ isolated install. No OMP process was started."
Write-Host "Copy the command block below into a PowerShell terminal and run it manually."
Write-Host "The same block was written to: $outputPath"
Write-Host ""
Write-Output $commandBlock
