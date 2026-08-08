[CmdletBinding()]
param(
    [string]$QualificationRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) "bbk-alpha17-@BBK_RC_SLUG@-manual"),
    [string]$Python = "python",
    [string]$Git = "git",
    [string]$Mise = "mise",
    [string]$Omp = "omp",
    [string]$SchemaWheelhouse = ""
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Resolve-Tool([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) {
        throw "Executable name or path must not be empty."
    }

    $expanded = [Environment]::ExpandEnvironmentVariables($Value)
    if (Test-Path -LiteralPath $expanded -PathType Leaf) {
        return (Resolve-Path -LiteralPath $expanded).Path
    }

    $command = Get-Command $expanded -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -ne $command) {
        $resolved = $null
        if ($command.PSObject.Properties.Name -contains "Path") {
            $resolved = [string]$command.Path
        }
        if ([string]::IsNullOrWhiteSpace($resolved) -and $command.PSObject.Properties.Name -contains "Source") {
            $resolved = [string]$command.Source
        }
        if (-not [string]::IsNullOrWhiteSpace($resolved) -and (Test-Path -LiteralPath $resolved -PathType Leaf)) {
            return (Resolve-Path -LiteralPath $resolved).Path
        }
    }

    throw "Cannot resolve executable path for '$Value'."
}
function Resolve-MiseTool([string]$Value) {
    try {
        return Resolve-Tool $Value
    } catch {
        # Continue with Windows install-location discovery. This is needed when
        # mise was installed correctly but the current PowerShell process has
        # not inherited/refreshed the corresponding PATH entry.
    }

    $candidates = New-Object System.Collections.Generic.List[string]
    foreach ($environmentCandidate in @($env:MISE_EXE, $env:MISE_PATH, $env:MISE_BIN, $env:MISE_INSTALL_PATH)) {
        if (-not [string]::IsNullOrWhiteSpace($environmentCandidate)) {
            $candidates.Add([Environment]::ExpandEnvironmentVariables($environmentCandidate))
        }
    }
    if (-not [string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        $candidates.Add((Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links\mise.exe"))
        $candidates.Add((Join-Path $env:LOCALAPPDATA "mise\bin\mise.exe"))
        $candidates.Add((Join-Path $env:LOCALAPPDATA "mise\mise.exe"))
        $candidates.Add((Join-Path $env:LOCALAPPDATA "mise\shims\mise.exe"))
        $candidates.Add((Join-Path $env:LOCALAPPDATA "Programs\mise\bin\mise.exe"))
        $candidates.Add((Join-Path $env:LOCALAPPDATA "Programs\mise\mise.exe"))
    }
    if (-not [string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
        $candidates.Add((Join-Path $env:USERPROFILE ".local\bin\mise.exe"))
        $candidates.Add((Join-Path $env:USERPROFILE ".cargo\bin\mise.exe"))
        $candidates.Add((Join-Path $env:USERPROFILE "scoop\shims\mise.exe"))
        $candidates.Add((Join-Path $env:USERPROFILE "bin\mise.exe"))
    }
    if (-not [string]::IsNullOrWhiteSpace($env:ChocolateyInstall)) {
        $candidates.Add((Join-Path $env:ChocolateyInstall "bin\mise.exe"))
    }
    if (-not [string]::IsNullOrWhiteSpace($env:ProgramFiles)) {
        $candidates.Add((Join-Path $env:ProgramFiles "mise\bin\mise.exe"))
        $candidates.Add((Join-Path $env:ProgramFiles "mise\mise.exe"))
    }

    $seen = @{}
    foreach ($candidate in $candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
        $key = $candidate.ToLowerInvariant()
        if ($seen.ContainsKey($key)) { continue }
        $seen[$key] = $true
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    # WinGet normally creates a link under Microsoft\WinGet\Links. Search
    # only its package root as a final bounded fallback when the current
    # PowerShell process has not inherited that link.
    if (-not [string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        $wingetPackages = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages"
        if (Test-Path -LiteralPath $wingetPackages -PathType Container) {
            $wingetMatch = Get-ChildItem -LiteralPath $wingetPackages -Filter "mise.exe" -File -Recurse -ErrorAction SilentlyContinue |
                Select-Object -First 1
            if ($null -ne $wingetMatch) {
                return (Resolve-Path -LiteralPath $wingetMatch.FullName).Path
            }
        }
    }

    $searched = ($seen.Keys | Sort-Object) -join "`n  - "
    if (-not [string]::IsNullOrWhiteSpace($searched)) {
        $searched = "`nSearched common locations:`n  - $searched"
    }
    throw @"
mise could not be resolved from '$Value', PATH, mise environment hints, or common Windows install locations.$searched
Pass its exact executable path explicitly, for example:
  .\install-isolated-rc.ps1 -Mise "C:\path\to\mise.exe"
"@
}
function Invoke-Captured([string]$File, [string[]]$Arguments, [string]$WorkingDirectory) {
    $oldLocation = Get-Location
    $oldErrorActionPreference = $ErrorActionPreference
    $nativeErrorPreference = Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue
    $oldNativeErrorPreference = $null

    try {
        Set-Location $WorkingDirectory

        # Windows PowerShell 5.1 represents redirected native stderr as ErrorRecord
        # objects. With the script-wide Stop preference, harmless progress output
        # from tools such as mise can otherwise terminate the script before their
        # actual process exit code is inspected.
        $ErrorActionPreference = "Continue"
        if ($null -ne $nativeErrorPreference) {
            $oldNativeErrorPreference = $nativeErrorPreference.Value
            Set-Variable -Name PSNativeCommandUseErrorActionPreference -Value $false -Scope Local
        }

        $captured = @(& $File @Arguments 2>&1)
        $exitCode = $LASTEXITCODE

        $outputLines = foreach ($item in $captured) {
            if ($item -is [System.Management.Automation.ErrorRecord]) {
                if ($null -ne $item.Exception -and -not [string]::IsNullOrWhiteSpace($item.Exception.Message)) {
                    [string]$item.Exception.Message
                } else {
                    [string]$item
                }
            } else {
                [string]$item
            }
        }
        $output = ($outputLines -join [Environment]::NewLine).Trim()

        if ($exitCode -ne 0) {
            throw "Command failed ($exitCode): $File $($Arguments -join ' ')`n$output"
        }
        return $output
    } finally {
        if ($null -ne $nativeErrorPreference) {
            Set-Variable -Name PSNativeCommandUseErrorActionPreference -Value $oldNativeErrorPreference -Scope Local
        }
        $ErrorActionPreference = $oldErrorActionPreference
        Set-Location $oldLocation
    }
}
function Resolve-Managed-Tool([string]$MisePath, [string]$Executable, [string]$ToolSpec, [string]$WorkingDirectory) {
    $managedPathText = Invoke-Captured $MisePath @("which",$Executable) $WorkingDirectory
    $managedPath = (Resolve-Path $managedPathText).Path
    $version = Invoke-Captured $MisePath @("exec",$ToolSpec,"--",$Executable,"--version") $WorkingDirectory
    return [ordered]@{
        execution_mode = "MISE_MANAGED"
        tool_spec = $ToolSpec
        executable = $Executable
        managed_path = $managedPath
        managed_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $managedPath).Hash.ToLowerInvariant()
        version = $version
        invocation_prefix = "mise exec $ToolSpec -- $Executable"
    }
}

function Get-JsonSchemaRuntime([string]$PythonPath, [string]$WorkingDirectory) {
    # Do not pass a multi-line Python program through `python -c` here.
    # Windows PowerShell 5.1 can rewrite native-command quoting, and merged
    # native stderr can corrupt a valid JSON probe. Write a temporary Python
    # source file and an exact structured result instead.
    $probeId = [Guid]::NewGuid().ToString("N")
    $probeScript = Join-Path $WorkingDirectory (".bbk-jsonschema-runtime-probe-{0}.py" -f $probeId)
    $probeResult = Join-Path $WorkingDirectory (".bbk-jsonschema-runtime-probe-{0}.json" -f $probeId)
    $probeSource = @'
import importlib.metadata
import json
import sys
import traceback
from pathlib import Path

output = Path(sys.argv[1])
try:
    import jsonschema  # noqa: F401
    import referencing  # noqa: F401
    value = {
        "status": "PASS",
        "python": sys.executable,
        "jsonschema_version": importlib.metadata.version("jsonschema"),
        "referencing_version": importlib.metadata.version("referencing"),
    }
except BaseException as exc:
    value = {
        "status": "FAIL",
        "python": sys.executable,
        "error_type": type(exc).__name__,
        "error": str(exc),
        "traceback": traceback.format_exc(),
    }
output.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
'@
    try {
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($probeScript, $probeSource, $utf8NoBom)
        $null = Invoke-Captured $PythonPath @("-I","-X","utf8",$probeScript,$probeResult) $WorkingDirectory
        if (-not (Test-Path -LiteralPath $probeResult -PathType Leaf)) {
            return [pscustomobject]@{
                status = "FAIL"
                python = $PythonPath
                error_type = "PROBE_OUTPUT_MISSING"
                error = "The runtime probe exited without creating its structured result."
            }
        }
        try {
            return ([System.IO.File]::ReadAllText($probeResult, [System.Text.Encoding]::UTF8) | ConvertFrom-Json)
        } catch {
            return [pscustomobject]@{
                status = "FAIL"
                python = $PythonPath
                error_type = "PROBE_OUTPUT_INVALID"
                error = $_.Exception.Message
            }
        }
    } catch {
        return [pscustomobject]@{
            status = "FAIL"
            python = $PythonPath
            error_type = "PROBE_PROCESS_FAILED"
            error = $_.Exception.Message
        }
    } finally {
        Remove-Item -LiteralPath $probeScript,$probeResult -Force -ErrorAction SilentlyContinue
    }
}
function Test-ExactJsonSchemaRuntime([object]$Runtime) {
    if ($null -eq $Runtime) { return $false }
    $statusProperty = $Runtime.PSObject.Properties["status"]
    $versionProperty = $Runtime.PSObject.Properties["jsonschema_version"]
    if ($null -eq $statusProperty -or $null -eq $versionProperty) { return $false }
    return ([string]$statusProperty.Value -eq "PASS" -and [string]$versionProperty.Value -eq "4.25.1")
}

function New-RoleReturnPythonRecord(
    [string]$ExecutionMode,
    [string]$PythonPath,
    [object]$Runtime,
    [AllowNull()][string]$ManagedEnvironment,
    [string]$WorkingDirectory
) {
    $resolvedPython = (Resolve-Path -LiteralPath $PythonPath).Path
    return [ordered]@{
        execution_mode = $ExecutionMode
        path = $resolvedPython
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $resolvedPython).Hash.ToLowerInvariant()
        version = (Invoke-Captured $resolvedPython @("--version") $WorkingDirectory)
        jsonschema_version = [string]$Runtime.jsonschema_version
        referencing_version = [string]$Runtime.referencing_version
        managed_environment = $ManagedEnvironment
    }
}

function Resolve-RoleReturnPython([string]$HostPython, [string]$QualificationRoot, [string]$EvidenceRoot, [string]$Wheelhouse) {
    # A direct interpreter is acceptable only when it already has the exact
    # pinned validator. The predecessor candidate previously accepted any direct jsonschema version.
    $direct = Get-JsonSchemaRuntime $HostPython $QualificationRoot
    $direct | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 (Join-Path $EvidenceRoot "role-return-python-direct-probe.json")
    if (Test-ExactJsonSchemaRuntime $direct) {
        return (New-RoleReturnPythonRecord "DIRECT_VALIDATED_RUNTIME" $HostPython $direct $null $QualificationRoot)
    }

    # Reuse a pre-existing BBK-managed validator when available. This includes
    # the standard user cache used by earlier BBK releases and avoids needless
    # network/package mutation while still requiring the exact pinned version.
    $candidatePaths = New-Object System.Collections.Generic.List[string]
    if (-not [string]::IsNullOrWhiteSpace($env:BBK_JSONSCHEMA_PYTHON)) {
        $candidatePaths.Add([Environment]::ExpandEnvironmentVariables($env:BBK_JSONSCHEMA_PYTHON))
    }
    foreach ($toolDirectory in @($env:BBK_JSONSCHEMA_TOOL_DIR, $env:BBK_SCHEMA_TOOL_DIR)) {
        if ([string]::IsNullOrWhiteSpace($toolDirectory)) { continue }
        $expandedToolDirectory = [Environment]::ExpandEnvironmentVariables($toolDirectory)
        if (Test-Path -LiteralPath $expandedToolDirectory -PathType Leaf) {
            $candidatePaths.Add($expandedToolDirectory)
        } else {
            $candidatePaths.Add((Join-Path $expandedToolDirectory "Scripts\python.exe"))
        }
    }
    if (-not [string]::IsNullOrWhiteSpace($env:BBK_TOOL_ROOT)) {
        $candidatePaths.Add((Join-Path ([Environment]::ExpandEnvironmentVariables($env:BBK_TOOL_ROOT)) "jsonschema-4.25.1\Scripts\python.exe"))
    }
    if (-not [string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
        $candidatePaths.Add((Join-Path $env:USERPROFILE ".cache\bbk\tooling\jsonschema-4.25.1\Scripts\python.exe"))
    }
    if (-not [string]::IsNullOrWhiteSpace($HOME)) {
        $candidatePaths.Add((Join-Path $HOME ".cache\bbk\tooling\jsonschema-4.25.1\Scripts\python.exe"))
    }
    if (-not [string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        $candidatePaths.Add((Join-Path $env:LOCALAPPDATA "BBK\tooling\jsonschema-4.25.1\Scripts\python.exe"))
    }

    $seenCandidates = @{}
    $candidateDiagnostics = New-Object System.Collections.Generic.List[object]
    foreach ($candidatePath in $candidatePaths) {
        if ([string]::IsNullOrWhiteSpace($candidatePath)) { continue }
        $candidateKey = $candidatePath.ToLowerInvariant()
        if ($seenCandidates.ContainsKey($candidateKey)) { continue }
        $seenCandidates[$candidateKey] = $true
        if (-not (Test-Path -LiteralPath $candidatePath -PathType Leaf)) { continue }

        $resolvedCandidate = (Resolve-Path -LiteralPath $candidatePath).Path
        $candidateRuntime = Get-JsonSchemaRuntime $resolvedCandidate $QualificationRoot
        $candidateDiagnostics.Add([ordered]@{ path=$resolvedCandidate; probe=$candidateRuntime })
        if (Test-ExactJsonSchemaRuntime $candidateRuntime) {
            $candidateParent = Split-Path -Parent $resolvedCandidate
            $managedEnvironment = if ((Split-Path -Leaf $candidateParent) -ieq "Scripts") {
                Split-Path -Parent $candidateParent
            } else {
                $candidateParent
            }
            $candidateDiagnostics | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 (Join-Path $EvidenceRoot "role-return-python-existing-probes.json")
            return (New-RoleReturnPythonRecord "EXISTING_VALIDATED_MANAGED_RUNTIME" $resolvedCandidate $candidateRuntime $managedEnvironment $QualificationRoot)
        }
    }
    $candidateDiagnostics | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 (Join-Path $EvidenceRoot "role-return-python-existing-probes.json")

    # No exact runtime was already available, so create an isolated one under
    # the qualification root. Normal Python warnings cannot corrupt the probe.
    $runtimeRoot = Join-Path $QualificationRoot "tooling\jsonschema-4.25.1"
    $runtimePython = Join-Path $runtimeRoot "Scripts\python.exe"
    Invoke-Captured $HostPython @("-X","utf8","-m","venv",$runtimeRoot) $QualificationRoot |
        Set-Content -Encoding UTF8 (Join-Path $EvidenceRoot "role-return-python-venv.txt")
    if (-not (Test-Path -LiteralPath $runtimePython -PathType Leaf)) {
        throw "Managed role-return Python was not created: $runtimePython"
    }

    $pipArguments = @(
        "-I","-X","utf8","-m","pip","install",
        "--disable-pip-version-check","--no-input"
    )
    if (-not [string]::IsNullOrWhiteSpace($Wheelhouse)) {
        $resolvedWheelhouse = (Resolve-Path -LiteralPath $Wheelhouse).Path
        $pipArguments += @("--no-index","--find-links",$resolvedWheelhouse)
    }
    $pipArguments += @("--upgrade","jsonschema==4.25.1")
    Invoke-Captured $runtimePython $pipArguments $QualificationRoot |
        Set-Content -Encoding UTF8 (Join-Path $EvidenceRoot "role-return-python-install.txt")

    $managed = Get-JsonSchemaRuntime $runtimePython $QualificationRoot
    $managed | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 (Join-Path $EvidenceRoot "role-return-python-managed-probe.json")
    if (-not (Test-ExactJsonSchemaRuntime $managed)) {
        $pipState = ""
        try {
            $pipState = Invoke-Captured $runtimePython @("-I","-X","utf8","-m","pip","show","jsonschema","referencing") $QualificationRoot
        } catch {
            $pipState = $_.Exception.Message
        }
        $pipState | Set-Content -Encoding UTF8 (Join-Path $EvidenceRoot "role-return-python-package-state.txt")
        $probeError = if ($null -ne $managed.PSObject.Properties["error"]) { [string]$managed.error } else { "unknown probe failure" }
        throw "Managed role-return validator is unavailable or not pinned to jsonschema 4.25.1. Probe: $probeError. See role-return-python-managed-probe.json and role-return-python-package-state.txt in the evidence directory."
    }
    $resolvedRuntimeRoot = (Resolve-Path -LiteralPath $runtimeRoot).Path
    return (New-RoleReturnPythonRecord "ISOLATED_MANAGED_RUNTIME" $runtimePython $managed $resolvedRuntimeRoot $QualificationRoot)
}
$Archive = Join-Path $PSScriptRoot "bbk-@BBK_VERSION@.zip"
$ExpectedArchiveSha256 = "@BBK_ARCHIVE_SHA256@"
$ExpectedPackageRootSha256 = "@BBK_PACKAGE_ROOT_SHA256@"
if (-not (Test-Path -LiteralPath $Archive -PathType Leaf)) { throw "RC archive is missing: $Archive" }
$Observed = (Get-FileHash -Algorithm SHA256 -LiteralPath $Archive).Hash.ToLowerInvariant()
if ($Observed -ne $ExpectedArchiveSha256) { throw "RC checksum mismatch: expected $ExpectedArchiveSha256 observed $Observed" }
if (Test-Path -LiteralPath $QualificationRoot) { throw "Qualification root already exists. Run rollback or choose a new -QualificationRoot: $QualificationRoot" }

$PythonPath = Resolve-Tool $Python
$GitPath = Resolve-Tool $Git
$MisePath = Resolve-MiseTool $Mise
$OmpPath = Resolve-Tool $Omp
$OmpVersion = Invoke-Captured $OmpPath @("--version") $PSScriptRoot
if ($OmpVersion -notmatch "16\.4\.8") { throw "This RC is qualified only for OMP 16.4.8; observed: $OmpVersion" }

New-Item -ItemType Directory -Path $QualificationRoot | Out-Null
$ExtractRoot = Join-Path $QualificationRoot "package"
$ProjectRoot = Join-Path $QualificationRoot "project"
$WorkspacesRoot = Join-Path $QualificationRoot "workspaces"
$EvidenceRoot = Join-Path $QualificationRoot "evidence"
$MiseRoot = Join-Path $QualificationRoot "mise"
$MiseData = Join-Path $MiseRoot "data"
$MiseCache = Join-Path $MiseRoot "cache"
$MiseConfig = Join-Path $MiseRoot "config"
New-Item -ItemType Directory -Path $ExtractRoot,$ProjectRoot,$WorkspacesRoot,$EvidenceRoot,$MiseData,$MiseCache,$MiseConfig | Out-Null
$env:MISE_DATA_DIR = $MiseData
$env:MISE_CACHE_DIR = $MiseCache
$env:MISE_CONFIG_DIR = $MiseConfig
$env:MISE_YES = "1"
$env:MISE_NO_DOTENV = "1"
$env:NO_COLOR = "1"
$env:CLICOLOR = "0"

Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($Archive)
try {
    $seen = @{}
    $roots = @{}
    foreach ($entry in $zip.Entries) {
        $name = $entry.FullName.Replace('\','/')
        if ([string]::IsNullOrWhiteSpace($name) -or $name.StartsWith('/') -or $name -match '^[A-Za-z]:' -or ($name.Split('/') -contains '..')) { throw "Unsafe ZIP entry: $name" }
        $key = $name.ToLowerInvariant()
        if ($seen.ContainsKey($key)) { throw "Duplicate/case-colliding ZIP entry: $name" }
        $seen[$key] = $true
        $roots[$name.Split('/')[0]] = $true
    }
    if ($roots.Count -ne 1 -or -not $roots.ContainsKey("bbk-@BBK_VERSION@")) { throw "Unexpected ZIP top-level root" }
} finally { $zip.Dispose() }
Expand-Archive -LiteralPath $Archive -DestinationPath $ExtractRoot
$PackageRoot = Join-Path $ExtractRoot "bbk-@BBK_VERSION@"
Invoke-Captured $PythonPath @((Join-Path $PackageRoot "tools\verify_package.py"), "--root", $PackageRoot, "--strict-mode") $QualificationRoot | Set-Content -Encoding UTF8 (Join-Path $EvidenceRoot "extracted-package-verify.txt")
$RoleReturnPython = Resolve-RoleReturnPython $PythonPath $QualificationRoot $EvidenceRoot $SchemaWheelhouse
$RoleReturnPython | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 (Join-Path $EvidenceRoot "role-return-python.json")

Copy-Item -LiteralPath (Join-Path $PSScriptRoot "qualification\verify_candidate.py") -Destination (New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot "qualification")).FullName
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "qualification\mise.toml") -Destination (Join-Path $ProjectRoot "mise.toml")
New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot "src\worker-a"),(Join-Path $ProjectRoot "src\worker-b") | Out-Null
New-Item -ItemType File -Path (Join-Path $ProjectRoot "src\worker-a\.gitkeep"),(Join-Path $ProjectRoot "src\worker-b\.gitkeep") | Out-Null
Set-Content -Encoding UTF8 -NoNewline -LiteralPath (Join-Path $ProjectRoot "README.md") -Value "# BBK Alpha.17 isolated manual qualification`n"
Set-Content -Encoding UTF8 -LiteralPath (Join-Path $ProjectRoot ".gitignore") -Value @(".bbk/", ".bbk-kit/", ".bbk-kit-install.json", ".omp/", ".agents/", ".beads/")

# mise owns installation and execution of jj and Beads for this qualification.
# The isolated MISE_* directories prevent reliance on or mutation of global tool installs.
$miseInstall = Invoke-Captured $MisePath @("install") $ProjectRoot
$miseInstall | Set-Content -Encoding UTF8 (Join-Path $EvidenceRoot "mise-install.txt")
$JjTool = Resolve-Managed-Tool $MisePath "jj" "jj@0.43.0" $ProjectRoot
$BdTool = Resolve-Managed-Tool $MisePath "bd" "github:gastownhall/beads@1.1.0" $ProjectRoot

Invoke-Captured $GitPath @("init") $ProjectRoot | Out-Null
Invoke-Captured $GitPath @("config","user.name","BBK Qualification") $ProjectRoot | Out-Null
Invoke-Captured $GitPath @("config","user.email","qualification@example.invalid") $ProjectRoot | Out-Null
$env:BD_NON_INTERACTIVE = "1"; $env:BEADS_DISABLE_METRICS = "1"
Invoke-Captured $MisePath @("exec","github:gastownhall/beads@1.1.0","--","bd","--sandbox","--json","init","--non-interactive","--skip-agents","--skip-hooks","--prefix","A17M") $ProjectRoot | Set-Content -Encoding UTF8 (Join-Path $EvidenceRoot "beads-setup.json")
Invoke-Captured $GitPath @("add",".") $ProjectRoot | Out-Null
$env:GIT_AUTHOR_DATE = "2026-08-04T00:00:00Z"; $env:GIT_COMMITTER_DATE = "2026-08-04T00:00:00Z"
Invoke-Captured $GitPath @("commit","-m","Alpha.17 manual qualification baseline") $ProjectRoot | Out-Null
Remove-Item Env:GIT_AUTHOR_DATE,Env:GIT_COMMITTER_DATE -ErrorAction SilentlyContinue
Invoke-Captured $MisePath @("exec","jj@0.43.0","--","jj","--no-pager","--color=never","git","init","--colocate",".") $ProjectRoot | Set-Content -Encoding UTF8 (Join-Path $EvidenceRoot "jj-setup.txt")

$InstallJson = Join-Path $EvidenceRoot "project-install.json"
$installOutput = Invoke-Captured $PythonPath @((Join-Path $PackageRoot "tools\setup.py"),"--install","--scope","project","--root",$ProjectRoot,"--omp","--no-language-profiles","--keep-existing","--json") $QualificationRoot
$installOutput | Set-Content -Encoding UTF8 $InstallJson
$InstalledPackage = Join-Path $ProjectRoot ".bbk-kit\versions\@BBK_VERSION@"
Invoke-Captured $PythonPath @((Join-Path $InstalledPackage "tools\bbk.py"),"init","--root",$ProjectRoot,"--title","Alpha.17 Manual Qualification","--project-id","BBK-A17-MANUAL","--no-examples") $ProjectRoot | Set-Content -Encoding UTF8 (Join-Path $EvidenceRoot "bbk-init.json")

$tools = [ordered]@{}
foreach ($spec in @(
    [pscustomobject]@{ Name="python"; Path=$PythonPath; VersionArgs=@("--version") },
    [pscustomobject]@{ Name="git"; Path=$GitPath; VersionArgs=@("--version") },
    [pscustomobject]@{ Name="mise"; Path=$MisePath; VersionArgs=@("--version") },
    [pscustomobject]@{ Name="omp"; Path=$OmpPath; VersionArgs=@("--version") }
)) {
    $name = [string]$spec.Name
    $path = [string]$spec.Path
    $args = [string[]]$spec.VersionArgs
    $tools[$name] = [ordered]@{ execution_mode="DIRECT_OPERATOR_TOOL"; path=$path; sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLowerInvariant(); version=(Invoke-Captured $path $args $ProjectRoot) }
}
$tools["jj"] = $JjTool
$tools["bd"] = $BdTool
$tools["role_return_python"] = $RoleReturnPython
$record = [ordered]@{
    schema="bbk.alpha17-manual-install-record.v1"
    status="PASS"
    rc_version="@BBK_VERSION@"
    rc_archive_sha256=$Observed
    package_root_sha256=$ExpectedPackageRootSha256
    qualification_root=(Resolve-Path $QualificationRoot).Path
    project_root=(Resolve-Path $ProjectRoot).Path
    workspaces_root=(Resolve-Path $WorkspacesRoot).Path
    package_root=(Resolve-Path $PackageRoot).Path
    installed_package_root=(Resolve-Path $InstalledPackage).Path
    tools=$tools
    mise_environment=[ordered]@{ data_dir=$MiseData; cache_dir=$MiseCache; config_dir=$MiseConfig; project_config=(Join-Path $ProjectRoot "mise.toml") }
    user_scope_bbk_modified=$false
    global_jj_or_bd_required=$false
    isolated_mise_tool_install_performed=$true
    mise_tool_bootstrap_network_access="PERMITTED_NOT_INSTRUMENTED"
}
$record | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 (Join-Path $EvidenceRoot "install-record.json")
Write-Host "Isolated Alpha.17 @BBK_RC_LABEL@ installation PASS"
Write-Host "jj and Beads were installed and bound through isolated mise state; global jj/bd were not used."
Write-Host "Role-return validation Python: $($RoleReturnPython.path) (jsonschema $($RoleReturnPython.jsonschema_version))"
Write-Host "Qualification root: $QualificationRoot"
Write-Host "Next: .\start-alpha17-qualification.ps1 -QualificationRoot `"$QualificationRoot`""
