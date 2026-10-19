# Opens the dashboard from the latest daily check on GitHub Actions, so the PC shows
# the same reading the phone alerts are based on. If GitHub can't be reached, it builds
# the dashboard locally instead.

$ErrorActionPreference = "Stop"
$repo = "dvlrsn/ai-bubble-monitor"
$root = Split-Path -Parent $PSScriptRoot
$dest = Join-Path $env:LOCALAPPDATA "ai-bubble-monitor\latest"

try {
    Write-Host "Fetching the latest daily check from GitHub..."
    $run = gh run list -R $repo -w daily.yml -s success -L 1 --json "databaseId,createdAt" | ConvertFrom-Json
    if (-not $run) { throw "no finished run yet" }
    if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
    gh run download $run[0].databaseId -R $repo -n dashboard -D $dest
    if ($LASTEXITCODE -ne 0) { throw "download failed" }
    $when = ([datetime]$run[0].createdAt).ToLocalTime().ToString("yyyy-MM-dd HH:mm")
    Write-Host "Checked on GitHub at $when."
    Start-Process (Join-Path $dest "dashboard.html")
}
catch {
    Write-Host "Couldn't get it from GitHub ($_). Building it on this PC instead (about 30 seconds)..."
    Push-Location $root
    try { python monitor.py run --open } finally { Pop-Location }
    Read-Host "Press Enter to close"
}
