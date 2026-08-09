param(
    [string]$TaskName = "GooayeStockUpdate",
    [string]$RepoDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"

$runBat = Join-Path $RepoDir "run_update.bat"
$configPath = Join-Path $RepoDir "config.json"

if (-not (Test-Path -LiteralPath $runBat)) {
    throw "Missing run_update.bat at $runBat"
}

if (-not (Test-Path -LiteralPath $configPath)) {
    throw "Missing config.json at $configPath. Copy your local config.json into the repo first."
}

if (-not [Environment]::GetEnvironmentVariable("GITHUB_PAT", "User")) {
    throw "Missing user environment variable GITHUB_PAT. Set it before enabling the scheduled task."
}

$action = "cmd.exe /c `"$runBat`""
schtasks /Change /TN $TaskName /TR $action | Out-Host
schtasks /Query /TN $TaskName /FO LIST /V | Select-String -Pattern "TaskName|Next Run Time|Task To Run|Start In|Days|Start Time|Last Result|Comment"
