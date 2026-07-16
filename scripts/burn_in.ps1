param([int]$Sessions = 50)
$ErrorActionPreference = "Stop"
$BaseUrl = "http://127.0.0.1:3800"

for ($Index = 1; $Index -le $Sessions; $Index++) {
    $Session = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/sessions" -TimeoutSec 5
    Invoke-RestMethod -Method Delete -Uri "$BaseUrl/api/sessions/$($Session.session_id)" -TimeoutSec 5
    if (($Index % 10) -eq 0) { Write-Host "$Index session resets passed." }
}
Write-Host "Replay reset burn-in passed for $Sessions sessions."

