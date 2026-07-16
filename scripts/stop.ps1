$ErrorActionPreference = "Stop"
$Port = 3800
$Socket = & ss --numeric --tcp --listening --processes "sport = :$Port" 2>$null | Out-String

if (-not $Socket.Trim()) {
    Write-Host "SpeechShift is not listening on port $Port."
    exit 0
}
if ($Socket -notmatch 'pid=(\d+)') {
    throw "Port $Port is occupied, but its process could not be identified. No process was stopped.`n$Socket"
}

$ProcessId = [int]$Matches[1]
$CommandPath = "/proc/$ProcessId/cmdline"
$Command = if (Test-Path $CommandPath) { (Get-Content -Raw $CommandPath) -replace "`0", " " } else { "" }
if ($Command -notmatch "speechshift") {
    throw "Port $Port belongs to a process that does not identify as SpeechShift. No process was stopped.`n$Socket"
}

Stop-Process -Id $ProcessId
Write-Host "Stopped SpeechShift process $ProcessId. In-memory sessions will be cleared during shutdown."

