# SpeechShift contributor instructions

SpeechShift is a standalone, local-first Open Day speech demonstration. Fedora 44 is the primary target.

## Non-negotiable boundaries

- Keep visitor audio and transcripts in memory only and clear them on reset, cancellation, timeout and shutdown.
- Never log visitor audio or transcript text.
- Keep `replay`, `local` and `modeldeck` providers explicit. Never silently change provider.
- Call ModelDeck only through its gateway. Never call management or worker ports.
- Do not download models in Open Day mode.
- Keep replay visibly labelled and usable without ModelDeck or internet access.
- Do not add identity cloning, identifiable-person voices or visitor-supplied target voices.
- Use Australian English in prose, comments and interface copy.
- Make focused changes and add tests when behaviour changes.

## Verification

Run:

```powershell
pwsh -NoProfile -File scripts/verify.ps1
```

