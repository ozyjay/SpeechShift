# Replay assets

The replay set contains three curated English source sentences. Every sentence has a neutral prepared source, three synthetic voice treatments, and French and German synthetic speech. `catalogue.json` is the authoritative asset index.

The WAV files are generated locally with eSpeak NG and contain no visitor or identifiable-person recordings. Regenerate them with:

```powershell
pwsh -NoProfile -File scripts/generate_replay_assets.ps1
```

Regeneration is a development action, not an Open Day start-up step. Staff must listen to every regenerated file for intelligibility, pronunciation, clipping and appropriate volume before public use. The interface describes these as prepared examples, not output from a live AI model.

