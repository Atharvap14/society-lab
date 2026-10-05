$ErrorActionPreference = 'Stop'
$labRoot = Split-Path -Parent $PSScriptRoot
$recordPath = Join-Path $labRoot '.runtime/server-process.json'
if (-not (Test-Path -LiteralPath $recordPath)) { Write-Output 'No recorded server process.'; exit 0 }
$record = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
$labProcess = Get-Process -Id $record.pid -ErrorAction SilentlyContinue
if ($labProcess -and $labProcess.StartTime.ToUniversalTime() -eq ([datetimeoffset]$record.started_utc).UtcDateTime) {
    $command = (Get-CimInstance Win32_Process -Filter "ProcessId=$($record.pid)").CommandLine
    if ($command -notlike '*swarm_lab.cli*serve*') { throw 'Recorded process is not the Society Lab server.' }
    Stop-Process -Id $record.pid
}
elseif ($labProcess) { throw 'Recorded process start time differs; preserve the record and inspect the process.' }
Remove-Item -LiteralPath $recordPath
Write-Output 'Society Lab stopped.'
