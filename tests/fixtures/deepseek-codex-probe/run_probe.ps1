$ErrorActionPreference = 'Continue'
$tmp = (Resolve-Path '.bbk/tmp/PKG-BBK-CODEX-DEEPSEEK-001/PH-DS-01').Path
$home = Join-Path $tmp 'codex-home'
New-Item -ItemType Directory -Force $home | Out-Null
$out = Join-Path $tmp 'mock2.out'; $err = Join-Path $tmp 'mock2.err'
$p = Start-Process -FilePath 'C:\Python313\python.exe' -ArgumentList 'tests/fixtures/deepseek-codex-probe/mock_responses.py' -WorkingDirectory (Get-Location) -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
Start-Sleep -Milliseconds 300
$port = Get-Content $out -TotalCount 1
@("model_provider = 'deepseek'", "model = 'deepseek-v4-flash'", '[model_providers.deepseek]', "name = 'DeepSeek'", "base_url = 'http://127.0.0.1:$port/v1'", "wire_api = 'responses'") | Set-Content (Join-Path $home 'config.toml') -Encoding utf8
$codex = 'C:\Users\Tombstone\AppData\Local\Programs\Pen\resources\app.asar.unpacked\node_modules\@openai\codex-win32-x64\vendor\x86_64-pc-windows-msvc\bin\codex.exe'
$env:CODEX_HOME = $home
$o = Join-Path $tmp 'codex.out'; $e = Join-Path $tmp 'codex.err'
$cp = Start-Process -FilePath $codex -ArgumentList @('exec','--ephemeral','--skip-git-repo-check','--json','-m','deepseek-v4-flash','Respond with probe marker.') -RedirectStandardOutput $o -RedirectStandardError $e -PassThru
Wait-Process -Id $cp.Id -Timeout 15 -ErrorAction SilentlyContinue
if (!$cp.HasExited) { Stop-Process -Id $cp.Id -Force }
Write-Output "PORT=$port"; Write-Output 'CODEX_OUT'; Get-Content $o; Write-Output 'CODEX_ERR'; Get-Content $e; Write-Output 'MOCK'; Get-Content $out; Get-Content $err
