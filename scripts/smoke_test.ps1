$ErrorActionPreference = "Stop"
$BaseUrl = "http://127.0.0.1:3800"
$Health = Invoke-RestMethod -Uri "$BaseUrl/api/health" -TimeoutSec 5
if ($Health.status -ne "ready" -or -not $Health.replay_ready) {
    throw "SpeechShift replay provider is not ready."
}
$Catalogue = Invoke-RestMethod -Uri "$BaseUrl/api/replay/catalogue" -TimeoutSec 5
if ($Catalogue.sentences.Count -lt 3) {
    throw "SpeechShift replay catalogue is incomplete."
}
Write-Host "SpeechShift smoke test passed: replay ready with $($Catalogue.sentences.Count) sentences."

