$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
$RepoRoot = Split-Path -Parent $PSScriptRoot
$CataloguePath = Join-Path $RepoRoot "assets/replay/catalogue.json"

if (-not (Get-Command espeak-ng -ErrorAction SilentlyContinue)) {
    throw "espeak-ng is required to regenerate the prepared replay assets."
}

$Catalogue = Get-Content -Raw $CataloguePath | ConvertFrom-Json
foreach ($Sentence in $Catalogue.sentences) {
    $Directory = Join-Path $RepoRoot ("assets/replay/" + (Split-Path -Parent $Sentence.original_audio))
    New-Item -ItemType Directory -Force -Path $Directory | Out-Null
    & espeak-ng -v en-au -s 155 -p 48 -w (Join-Path $RepoRoot ("assets/replay/" + $Sentence.original_audio)) $Sentence.source_text
    & espeak-ng -v en-au -s 132 -p 36 -w (Join-Path $Directory "voice-calm.wav") $Sentence.source_text
    & espeak-ng -v en-au -s 188 -p 68 -a 155 -w (Join-Path $Directory "voice-energetic.wav") $Sentence.source_text
    & espeak-ng -v en -s 145 -p 18 -a 130 -w (Join-Path $Directory "voice-robot.wav") $Sentence.source_text
    foreach ($Language in $Sentence.languages) {
        & espeak-ng -v $Language.id -s 150 -p 48 -w (Join-Path $RepoRoot ("assets/replay/" + $Language.audio)) $Language.text
    }
}

Write-Host "Prepared replay WAV assets regenerated. Review them before public use."
