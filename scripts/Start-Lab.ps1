param([int]$Port = 8765, [int]$MaxCalls = 2000)
$ErrorActionPreference = 'Stop'
$labRoot = Split-Path -Parent $PSScriptRoot
$runtimeDir = Join-Path $labRoot '.runtime'
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
$recordPath = Join-Path $runtimeDir 'server-process.json'
if (Test-Path -LiteralPath $recordPath) {
    $existing = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
    $existingProcess = Get-Process -Id $existing.pid -ErrorAction SilentlyContinue
    if ($existingProcess -and $existingProcess.StartTime.ToUniversalTime() -eq ([datetimeoffset]$existing.started_utc).UtcDateTime) {
        Write-Output "Society Lab is already running at http://127.0.0.1:$($existing.port)"
        exit 0
    }
}
$listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
if ($listeners.Count -gt 0) {
    throw "Port $Port already has a listener. Inspect that process before starting another Society Lab server."
}
$pythonExe = (Get-Command python -ErrorAction Stop).Source
$labProcess = Start-Process -FilePath $pythonExe -ArgumentList @('-m', 'swarm_lab.cli', '--max-calls', "$MaxCalls", 'serve', '--port', "$Port") -WorkingDirectory $labRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimeDir 'server.stdout.log') -RedirectStandardError (Join-Path $runtimeDir 'server.stderr.log') -PassThru
@{ pid = $labProcess.Id; started_utc = $labProcess.StartTime.ToUniversalTime().ToString('o'); port = $Port; root = $labRoot } | ConvertTo-Json | Set-Content -LiteralPath $recordPath -Encoding utf8
Write-Output "Society Lab starting at http://127.0.0.1:$Port"
