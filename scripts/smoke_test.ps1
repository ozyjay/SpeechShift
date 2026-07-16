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
$Config = Invoke-RestMethod -Uri "$BaseUrl/api/config" -TimeoutSec 5
if ($Config.audio_sample_rate -ne 16000 -or $Config.max_input_seconds -gt 8) {
    throw "SpeechShift audio capture configuration is unsafe or unexpected."
}
$Worklet = Invoke-WebRequest -Uri "$BaseUrl/audio-worklet.js" -TimeoutSec 5
if ($Worklet.StatusCode -ne 200 -or $Worklet.Content -notmatch "speechshift-capture") {
    throw "SpeechShift audio capture worklet is unavailable."
}
& .venv/bin/python scripts/smoke_mock.py
Write-Host "SpeechShift smoke test passed: replay ready, audio bounded, and mock binary streaming complete."
