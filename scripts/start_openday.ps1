$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if ($env:PORT_ALLOCATION_CONFIRMED -ne "true") {
    throw "SpeechShift does not yet have a confirmed exact OpenDayOps port allocation. Update the registry and set PORT_ALLOCATION_CONFIRMED=true."
}
& $PSScriptRoot/check_ports.ps1 -Port 3800
$env:DEMO_MODE = "openday"
$env:APP_PORT = "3800"
$env:SPEECH_PROVIDER = "replay"
& .venv/bin/python -m speechshift
