[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$SessionHtml,
    [string]$QualificationRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) "bbk-alpha17-@BBK_RC_SLUG@-manual"),
    [string]$OutputDirectory = ""
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $SessionHtml -PathType Leaf)) { throw "Session export missing: $SessionHtml" }
$recordPath = Join-Path $QualificationRoot "evidence\install-record.json"
$record = Get-Content -Raw -LiteralPath $recordPath | ConvertFrom-Json
$project = [string]$record.project_root
$mise = [string]$record.tools.mise.path
$roleReturnPython = [string]$record.tools.role_return_python.path
$env:MISE_DATA_DIR = [string]$record.mise_environment.data_dir
$env:MISE_CACHE_DIR = [string]$record.mise_environment.cache_dir
$env:MISE_CONFIG_DIR = [string]$record.mise_environment.config_dir
$env:MISE_YES = "1"; $env:MISE_NO_DOTENV = "1"; $env:NO_COLOR = "1"; $env:CLICOLOR = "0"
$env:BD_NON_INTERACTIVE = "1"; $env:BEADS_DISABLE_METRICS = "1"
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $QualificationRoot "evidence-raw" }
if (Test-Path -LiteralPath $OutputDirectory) { throw "Evidence output already exists: $OutputDirectory" }
New-Item -ItemType Directory -Path $OutputDirectory | Out-Null
New-Item -ItemType Directory -Path (Join-Path $OutputDirectory "session"),(Join-Path $OutputDirectory "project"),(Join-Path $OutputDirectory "commands"),(Join-Path $OutputDirectory "kit") | Out-Null
Copy-Item -LiteralPath $SessionHtml -Destination (Join-Path $OutputDirectory "session\omp-session.html")
Copy-Item -LiteralPath $recordPath -Destination (Join-Path $OutputDirectory "project\install-record.json")
Copy-Item -LiteralPath (Join-Path $QualificationRoot "evidence\mise-install.txt") -Destination (Join-Path $OutputDirectory "project\mise-install.txt")
$launchCommand = Join-Path $QualificationRoot "evidence\launch-alpha17-qualification-command.ps1"
if (Test-Path -LiteralPath $launchCommand -PathType Leaf) { Copy-Item -LiteralPath $launchCommand -Destination (Join-Path $OutputDirectory "project\launch-alpha17-qualification-command.ps1") }
foreach ($name in @('install-isolated-rc.ps1','start-alpha17-qualification.ps1','collect-evidence.ps1','expected-invariants.json','RESULT-TEMPLATE.md','RESULT-RECORD-TEMPLATE.json','KNOWN-BOUNDARIES.md','manual-bootstrap-extension.mjs','omp-qualification-overlay.yml','bootstrap-binding.py','manual-integration.py','manual-qualification-kit.json','KIT-MANIFEST.json','analyze-session.py')) {
    $source = Join-Path $PSScriptRoot $name
    if (Test-Path -LiteralPath $source -PathType Leaf) {
        if ($name -in @('RESULT-TEMPLATE.md','RESULT-RECORD-TEMPLATE.json')) { Copy-Item -LiteralPath $source -Destination (Join-Path $OutputDirectory $name) }
        else { Copy-Item -LiteralPath $source -Destination (Join-Path $OutputDirectory "kit\$name") }
    }
}
if (Test-Path -LiteralPath (Join-Path $project ".bbk")) { Copy-Item -LiteralPath (Join-Path $project ".bbk") -Destination (Join-Path $OutputDirectory "project\.bbk") -Recurse }
if (Test-Path -LiteralPath (Join-Path $project ".bbk-kit-install.json")) { Copy-Item -LiteralPath (Join-Path $project ".bbk-kit-install.json") -Destination (Join-Path $OutputDirectory "project\.bbk-kit-install.json") }
foreach ($rel in @('README.md','mise.toml','qualification','src')) { $p=Join-Path $project $rel; if (Test-Path -LiteralPath $p) { Copy-Item -LiteralPath $p -Destination (Join-Path $OutputDirectory "project\$rel") -Recurse } }

function Capture([string]$Name,[string]$File,[string[]]$Arguments,[string]$Cwd) {
    $oldLocation = Get-Location
    $oldPreference = $ErrorActionPreference
    $nativePreference = Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue
    $oldNativePreference = $null
    try {
        Set-Location $Cwd
        # Native tools routinely emit progress and warnings on stderr. In
        # Windows PowerShell 5.1 those lines become ErrorRecord objects; they
        # are evidence, not a terminating condition. The process exit code is
        # the command result.
        $ErrorActionPreference = 'Continue'
        if ($null -ne $nativePreference) {
            $oldNativePreference = $nativePreference.Value
            Set-Variable -Name PSNativeCommandUseErrorActionPreference -Value $false -Scope Local
        }
        $captured = @(& $File @Arguments 2>&1)
        $code = $LASTEXITCODE
        $lines = foreach ($item in $captured) {
            if ($item -is [System.Management.Automation.ErrorRecord] -and $null -ne $item.Exception -and -not [string]::IsNullOrWhiteSpace($item.Exception.Message)) { [string]$item.Exception.Message }
            else { [string]$item }
        }
        $text = ($lines -join [Environment]::NewLine).Trim()
    } finally {
        if ($null -ne $nativePreference) { Set-Variable -Name PSNativeCommandUseErrorActionPreference -Value $oldNativePreference -Scope Local }
        $ErrorActionPreference = $oldPreference
        Set-Location $oldLocation
    }
    [ordered]@{ command=$Name; executable=$File; arguments=$Arguments; exit_code=$code; output=$text } | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 (Join-Path $OutputDirectory "commands\$Name.json")
}
Capture "git-status" ([string]$record.tools.git.path) @('status','--short','--branch') $project
Capture "git-head" ([string]$record.tools.git.path) @('rev-parse','HEAD') $project
Capture "git-log" ([string]$record.tools.git.path) @('log','-n','10','--format=%H %P %s') $project
Capture "jj-workspaces" $mise @('exec','jj@0.43.0','--','jj','--no-pager','--color=never','workspace','list') $project
Capture "jj-log" $mise @('exec','jj@0.43.0','--','jj','--no-pager','--color=never','log','-r','all()','--no-graph') $project
Capture "bd-list" $mise @('exec','github:gastownhall/beads@1.1.0','--','bd','--sandbox','--json','list') $project
Capture "mise-version" $mise @('--version') $project
Capture "mise-tools" $mise @('ls','--current') $project
Capture "mise-tasks" $mise @('tasks','ls') $project
Capture "mise-which-jj" $mise @('which','jj') $project
Capture "mise-which-bd" $mise @('which','bd') $project
Capture "omp-version" ([string]$record.tools.omp.path) @('--version') $project
Capture "role-return-python-version" $roleReturnPython @('--version') $project
$jsonschemaProbe = Join-Path ([IO.Path]::GetTempPath()) ("bbk-jsonschema-version-" + [Guid]::NewGuid().ToString("N") + ".py")
try {
    @'
import importlib.metadata
print(importlib.metadata.version("jsonschema"))
'@ | Set-Content -LiteralPath $jsonschemaProbe -Encoding ASCII
    Capture "role-return-jsonschema-version" $roleReturnPython @('-I','-X','utf8',$jsonschemaProbe) $project
} finally {
    if (Test-Path -LiteralPath $jsonschemaProbe) { Remove-Item -LiteralPath $jsonschemaProbe -Force }
}
Capture "package-status" ([string]$record.tools.python.path) @((Join-Path ([string]$record.package_root) 'tools\install.py'),'--json','status','--scope','project','--root',$project) $project
Capture "package-verify" ([string]$record.tools.python.path) @((Join-Path ([string]$record.installed_package_root) 'tools\verify_package.py'),'--root',([string]$record.installed_package_root),'--strict-mode') $project

$analysisPath = Join-Path $OutputDirectory 'session\session-admission.json'
$resultRecordPath = Join-Path $OutputDirectory 'RESULT-RECORD.json'
$analysisArguments = @(
    (Join-Path $PSScriptRoot 'analyze-session.py'),
    '--session-html', $SessionHtml,
    '--expected-version', '@BBK_VERSION@',
    '--output', $analysisPath,
    '--full-gate',
    '--result-record-template', (Join-Path $PSScriptRoot 'RESULT-RECORD-TEMPLATE.json'),
    '--result-record-output', $resultRecordPath
)
$oldPreference = $ErrorActionPreference
$nativePreference = Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue
$oldNativePreference = $null
try {
    $ErrorActionPreference = 'Continue'
    if ($null -ne $nativePreference) {
        $oldNativePreference = $nativePreference.Value
        Set-Variable -Name PSNativeCommandUseErrorActionPreference -Value $false -Scope Local
    }
    $analysisCaptured = @(& $roleReturnPython @analysisArguments 2>&1)
    $analysisExit = $LASTEXITCODE
    $analysisLines = foreach ($item in $analysisCaptured) {
        if ($item -is [System.Management.Automation.ErrorRecord] -and $null -ne $item.Exception -and -not [string]::IsNullOrWhiteSpace($item.Exception.Message)) { [string]$item.Exception.Message }
        else { [string]$item }
    }
    $analysisOutput = ($analysisLines -join [Environment]::NewLine).Trim()
} finally {
    if ($null -ne $nativePreference) { Set-Variable -Name PSNativeCommandUseErrorActionPreference -Value $oldNativePreference -Scope Local }
    $ErrorActionPreference = $oldPreference
}
[ordered]@{ command='manual-qualification-analysis'; exit_code=$analysisExit; output=$analysisOutput; result_path=$analysisPath; populated_result_record=$resultRecordPath } | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 (Join-Path $OutputDirectory 'commands\session-admission.json')

$manifest = [ordered]@{ schema="bbk.alpha17-manual-raw-evidence.v3"; rc_version=$record.rc_version; rc_archive_sha256=$record.rc_archive_sha256; package_root_sha256=$record.package_root_sha256; collected_at=(Get-Date).ToUniversalTime().ToString("o"); project_root=$project; session_file=(Resolve-Path $SessionHtml).Path; manual_qualification_analysis_exit_code=$analysisExit; populated_result_record=(Test-Path -LiteralPath $resultRecordPath -PathType Leaf); managed_tools=@('jj@0.43.0','github:gastownhall/beads@1.1.0'); global_jj_or_bd_used=$false; environment_dump_collected=$false; credential_files_collected=$false }
$manifest | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 (Join-Path $OutputDirectory "RAW-EVIDENCE-MANIFEST.json")
Write-Host "Raw evidence collected: $OutputDirectory"
if ($analysisExit -ne 0) { Write-Warning "The full manual-qualification analyzer classified this run as a nonpass. Evidence was preserved, including the analyzer-populated RESULT-RECORD.json; inspect session\session-admission.json." }
else { Write-Host "Analyzer PASS. Complete only the manual redaction_attestation fields in RESULT-RECORD.json after inspecting the redacted archive." }
Write-Host "Next: .\redact-and-package.ps1 -QualificationRoot `"$QualificationRoot`" -RawEvidenceDirectory `"$OutputDirectory`""
