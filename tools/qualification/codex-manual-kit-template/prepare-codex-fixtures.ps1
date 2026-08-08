param(
    [string]$QualificationRoot = (Join-Path $PSScriptRoot "bbk-alpha17-@BBK_RC_SLUG@-codex-manual"),
    [string]$Python = "python",
    [string]$Git = "git",
    [string]$Codex = "codex"
)
$ErrorActionPreference = "Stop"

function Resolve-Tool([string]$Value) {
    if ([System.IO.Path]::IsPathRooted($Value)) {
        if (-not (Test-Path -LiteralPath $Value -PathType Leaf)) { throw "Tool not found: $Value" }
        return (Resolve-Path -LiteralPath $Value).Path
    }
    return (Get-Command $Value -ErrorAction Stop).Source
}
function Quote-PS([string]$Value) { return "'" + $Value.Replace("'", "''") + "'" }
function Invoke-Native([string]$File, [string[]]$Arguments, [string]$Cwd) {
    $old = $ErrorActionPreference
    $hadNative = Test-Path variable:global:PSNativeCommandUseErrorActionPreference
    if ($hadNative) { $oldNative = $global:PSNativeCommandUseErrorActionPreference; $global:PSNativeCommandUseErrorActionPreference = $false }
    try {
        $ErrorActionPreference = 'Continue'
        Push-Location $Cwd
        try { $stream = & $File @Arguments 2>&1; $code = $LASTEXITCODE }
        finally { Pop-Location }
    } finally {
        $ErrorActionPreference = $old
        if ($hadNative) { $global:PSNativeCommandUseErrorActionPreference = $oldNative }
    }
    $text = ($stream | ForEach-Object { if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { [string]$_ } }) -join [Environment]::NewLine
    if ($code -ne 0) { throw "Command failed ($code): $File $($Arguments -join ' ')`n$text" }
    return $text
}

$PythonPath = Resolve-Tool $Python
$GitPath = Resolve-Tool $Git
$CodexPath = Resolve-Tool $Codex
$archive = Join-Path $PSScriptRoot "bbk-@BBK_VERSION@.zip"
if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) { throw "RC archive missing: $archive" }
$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant()
if ($actual -ne "@BBK_ARCHIVE_SHA256@") { throw "RC archive digest mismatch: $actual" }
if (Test-Path -LiteralPath $QualificationRoot) { throw "Qualification root already exists: $QualificationRoot" }
New-Item -ItemType Directory -Path $QualificationRoot | Out-Null
$packageRoot = Join-Path $QualificationRoot "package"
Expand-Archive -LiteralPath $archive -DestinationPath $packageRoot
$package = Get-ChildItem -LiteralPath $packageRoot -Directory | Select-Object -First 1
if (-not $package) { throw "Extracted package root not found" }

$projects = @{
    "MH-CODEX-01" = Join-Path $QualificationRoot "fixture-worker"
    "MH-CODEX-03" = Join-Path $QualificationRoot "fixture-rolling-wave"
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "fixtures\worker") -Destination $projects["MH-CODEX-01"] -Recurse
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "fixtures\rolling-wave") -Destination $projects["MH-CODEX-03"] -Recurse

foreach ($entry in $projects.GetEnumerator()) {
    $project = $entry.Value
    Invoke-Native $GitPath @("init") $project | Out-Null
    Invoke-Native $GitPath @("config", "user.email", "bbk-qualification@example.invalid") $project | Out-Null
    Invoke-Native $GitPath @("config", "user.name", "BBK Qualification") $project | Out-Null
    Invoke-Native $GitPath @("add", ".") $project | Out-Null
    Invoke-Native $GitPath @("commit", "-m", "qualification baseline") $project | Out-Null
    Invoke-Native $PythonPath @((Join-Path $package.FullName "tools\install.py"), "install", "--scope", "project", "--root", $project, "--codex", "--no-language-profiles", "--keep-existing") $project | Out-Null
    $status = Invoke-Native $PythonPath @((Join-Path $package.FullName "tools\install.py"), "status", "--scope", "project", "--root", $project) $project
    New-Item -ItemType Directory -Path (Join-Path $QualificationRoot "evidence") -Force | Out-Null
    $status | Set-Content -LiteralPath (Join-Path $QualificationRoot "evidence\$($entry.Key)-install-status.txt") -Encoding UTF8
}

$prompt1 = (Resolve-Path (Join-Path $PSScriptRoot "prompts\MH-CODEX-01-PRIMARY.md")).Path
$prompt3 = (Resolve-Path (Join-Path $PSScriptRoot "prompts\MH-CODEX-03-ROLLING-WAVE.md")).Path
$cmd1 = "& " + (Quote-PS $CodexPath) + " --cd " + (Quote-PS $projects["MH-CODEX-01"]) + " --ask-for-approval never (Get-Content -Raw -LiteralPath " + (Quote-PS $prompt1) + ")"
$cmd3 = "& " + (Quote-PS $CodexPath) + " --cd " + (Quote-PS $projects["MH-CODEX-03"]) + " --ask-for-approval never (Get-Content -Raw -LiteralPath " + (Quote-PS $prompt3) + ")"
@("# MH-CODEX-01", $cmd1, "", "# MH-CODEX-03", $cmd3) | Set-Content -LiteralPath (Join-Path $QualificationRoot "launch-codex-commands.ps1") -Encoding UTF8
@{
    schema = "bbk.alpha17-codex-manual-install.v1"
    version = "@BBK_VERSION@"
    package_root = $package.FullName
    qualification_root = $QualificationRoot
    worker_project = $projects["MH-CODEX-01"]
    rolling_wave_project = $projects["MH-CODEX-03"]
    codex = $CodexPath
    python = $PythonPath
    git = $GitPath
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $QualificationRoot "install-record.json") -Encoding UTF8

Write-Host "Prepared disposable Codex qualification fixtures. No Codex process was started."
Write-Host ""
Write-Host "MH-CODEX-01 command:"
Write-Host $cmd1
Write-Host ""
Write-Host "After MH-CODEX-01 completes, paste prompts\MH-CODEX-02-FOLLOWUP.md in the same conversation."
Write-Host ""
Write-Host "MH-CODEX-03 command:"
Write-Host $cmd3
Write-Host ""
Write-Host "Commands were also written to: $(Join-Path $QualificationRoot 'launch-codex-commands.ps1')"
