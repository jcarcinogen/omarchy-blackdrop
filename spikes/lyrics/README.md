# Synced lyrics spike

## Verdict: PARTIAL

The data path is validated but intentionally not active in Blackdrop.

### What worked

- Sidra exposes title, artists, album, duration, track ID, playback status, and position through MPRIS.
- LRCLIB returned timestamped lyrics for live Sidra tracks without an API key.
- `lyrics_watch.py` parses LRC timestamps, selects duration-matched synced results, follows MPRIS position, caches successful results, and emits bounded JSONL line updates.
- Unit tests cover LRC parsing, timeline selection, MPRIS metadata parsing, and duration-matched result selection.

### What was deferred

- QML presentation and the `L`/`Shift+L` toggle were removed from the active plugin at Scott's request.
- Provider coverage, seek handling, visual styling, and longer live playback need another QA pass before activation.

### Resume path

Copy the helper into the active `scripts/` directory, add a service-owned `Process` with JSONL parsing, then add overlay shortcuts for `L` and `Shift+L`. LRCLIB requests must keep the identifying User-Agent, cache results, remain sequential, and honor 429 responses.

## Test

```bash
python -m unittest discover -s spikes/lyrics -p 'test_lyrics_watch.py' -v
```
