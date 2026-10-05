$ErrorActionPreference = 'Stop'
$workspacePath = $PSScriptRoot
$rclonePath = (Get-Content -LiteralPath (Join-Path $workspacePath '.secrets/rclone-path.txt') -Raw).Trim()
$configPath = Join-Path $workspacePath '.secrets/rclone.conf'
$authOutputPath = Join-Path $workspacePath '.secrets/rclone-auth-output.log'
if (-not (Test-Path -LiteralPath $configPath)) {
    $tokenLine = Get-Content -LiteralPath $authOutputPath | Where-Object { $_.Trim().StartsWith('{') } | Select-Object -Last 1
    if (-not $tokenLine) { throw 'Complete the Google authorization in the browser first.' }
    $null = $tokenLine | ConvertFrom-Json
    Set-Content -LiteralPath $configPath -Value @('[ai-village-gcs]','type = google cloud storage',('token = ' + $tokenLine.Trim()))
}
if (Test-Path 'V:\') { throw 'Drive V: is already in use.' }
$mountLog = Join-Path $workspacePath '.secrets/rclone-mount.log'
$cachePath = Join-Path $env:LOCALAPPDATA 'Kairosity\ai-village-cache'
# IPv6 object reads time out on this laptop's network; keep TLS and use IPv4.
$mountArguments = @('mount','ai-village-gcs:kairosity-ai-village-504821/ai-village','V:','--config',('"'+$configPath+'"'),'--read-only','--bind','0.0.0.0','--vfs-cache-mode','full','--vfs-cache-max-size','10G','--cache-dir',('"'+$cachePath+'"'),'--volname','AI-Village','--log-file',('"'+$mountLog+'"'),'--log-level','INFO')
$mountProcess = Start-Process -FilePath $rclonePath -ArgumentList $mountArguments -WindowStyle Hidden -PassThru
$mountProcess.Id | Set-Content -LiteralPath (Join-Path $workspacePath '.secrets/rclone-mount.pid')
Write-Output ('Mount process started: '+$mountProcess.Id)

