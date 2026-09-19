#!/usr/bin/env python3
"""Synchronized lyrics helper for Blackdrop."""

from __future__ import annotations

import bisect
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

_TIMESTAMP = re.compile(r"\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]")


def parse_lrc(raw: str) -> list[tuple[int, str]]:
    entries: list[tuple[int, str]] = []
    for source_line in raw.splitlines():
        matches = list(_TIMESTAMP.finditer(source_line))
        if not matches:
            continue
        text = _TIMESTAMP.sub("", source_line).strip()
        if not text:
            continue
        for match in matches:
            minutes = int(match.group(1))
            seconds = int(match.group(2))
            fraction = match.group(3) or "0"
            millis = int((fraction + "00")[:3])
            entries.append(((minutes * 60 + seconds) * 1000 + millis, text))
    return sorted(entries, key=lambda entry: entry[0])


def parse_busctl_metadata(payload: dict) -> dict:
    data = payload.get("data", {})

    def value(key: str, fallback=None):
        item = data.get(key, {})
        return item.get("data", fallback) if isinstance(item, dict) else fallback

    artists = value("xesam:artist", []) or []
    if isinstance(artists, str):
        artists = [artists]
    artist_names = [str(artist).strip() for artist in artists if str(artist).strip()]
    length_us = int(value("mpris:length", 0) or 0)
    return {
        "track_id": str(value("mpris:trackid", "") or ""),
        "duration": int(round(length_us / 1_000_000)),
        "title": str(value("xesam:title", "") or "").strip(),
        "artist": ", ".join(artist_names),
        "search_artist": artist_names[0] if artist_names else "",
        "album": str(value("xesam:album", "") or "").strip(),
    }


def choose_synced_result(results: list[dict], duration: int) -> Optional[dict]:
    candidates = []
    for result in results:
        if not result.get("syncedLyrics"):
            continue
        difference = abs(float(result.get("duration", 0)) - duration)
        if difference <= 2:
            candidates.append((difference, result))
    return min(candidates, key=lambda item: item[0])[1] if candidates else None


def lines_at_position(entries: list[tuple[int, str]], position_ms: int) -> tuple[str, str, str]:
    if not entries:
        return "", "", ""
    times = [entry[0] for entry in entries]
    index = bisect.bisect_right(times, position_ms) - 1
    if index < 0:
        return "", "", entries[0][1]
    previous = entries[index - 1][1] if index > 0 else ""
    current = entries[index][1]
    following = entries[index + 1][1] if index + 1 < len(entries) else ""
    return previous, current, following


CLIENT_ID = "Blackdrop/0.1.0 (https://omarchy.org/)"
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "blackdrop" / "lyrics"


def busctl_property(player: str, name: str) -> dict:
    output = subprocess.check_output(
        [
            "busctl", "--user", "--json=short", "get-property", player,
            "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Player", name,
        ],
        text=True,
        timeout=3,
    )
    return json.loads(output)


def player_names() -> list[str]:
    output = subprocess.check_output(
        ["busctl", "--user", "--list", "--no-legend", "--no-pager"],
        text=True,
        timeout=3,
    )
    return [line.split()[0] for line in output.splitlines()
            if line.startswith("org.mpris.MediaPlayer2.")]


def active_player() -> Optional[str]:
    players = player_names()
    for player in players:
        try:
            if busctl_property(player, "PlaybackStatus").get("data") == "Playing":
                return player
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            continue
    return players[0] if players else None


def track_metadata(player: str) -> dict:
    return parse_busctl_metadata(busctl_property(player, "Metadata"))


def playback_position_ms(player: str) -> int:
    payload = busctl_property(player, "Position")
    return max(0, int(payload.get("data", 0) or 0) // 1000)


def cache_path(metadata: dict) -> Path:
    signature = "\0".join([
        metadata.get("title", ""), metadata.get("search_artist", ""),
        metadata.get("album", ""), str(metadata.get("duration", 0)),
    ])
    return CACHE_DIR / (hashlib.sha256(signature.encode()).hexdigest() + ".json")


def fetch_synced_lyrics(metadata: dict) -> tuple[list[tuple[int, str]], str]:
    path = cache_path(metadata)
    if path.exists():
        try:
            cached = json.loads(path.read_text())
            return [(int(item[0]), str(item[1])) for item in cached.get("entries", [])], "cached"
        except (OSError, ValueError, TypeError):
            pass

    query = urllib.parse.urlencode({
        "track_name": metadata["title"],
        "artist_name": metadata["search_artist"],
    })
    request = urllib.request.Request(
        "https://lrclib.net/api/search?" + query,
        headers={"User-Agent": CLIENT_ID, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            results = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            return [], "rate-limited"
        return [], "unavailable"
    except (OSError, ValueError):
        return [], "unavailable"

    match = choose_synced_result(results if isinstance(results, list) else [], metadata["duration"])
    entries = parse_lrc(match.get("syncedLyrics", "")) if match else []
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"entries": entries}, ensure_ascii=False))
        temporary.replace(path)
    except OSError:
        pass
    return entries, "ok" if entries else "unavailable"


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), flush=True)


def main() -> int:
    player: Optional[str] = None
    metadata: dict = {}
    entries: list[tuple[int, str]] = []
    fetched_track = ""
    last_display = None
    next_metadata_check = 0.0

    emit({"status": "starting", "message": "Finding synced lyrics…"})
    while True:
        now = time.monotonic()
        try:
            if now >= next_metadata_check:
                next_metadata_check = now + 1.0
                player = active_player()
                if not player:
                    payload = {"status": "no-player", "message": "No MPRIS player found"}
                    if payload != last_display:
                        emit(payload); last_display = payload
                    time.sleep(0.25)
                    continue
                current_metadata = track_metadata(player)
                track_key = current_metadata.get("track_id") or "\0".join([
                    current_metadata.get("title", ""), current_metadata.get("artist", ""),
                    str(current_metadata.get("duration", 0)),
                ])
                if track_key != fetched_track:
                    metadata = current_metadata
                    fetched_track = track_key
                    emit({
                        "status": "loading", "title": metadata.get("title", ""),
                        "artist": metadata.get("artist", ""),
                        "message": "Finding synced lyrics…",
                    })
                    if metadata.get("title") and metadata.get("search_artist") and metadata.get("duration"):
                        entries, source_status = fetch_synced_lyrics(metadata)
                    else:
                        entries, source_status = [], "unavailable"
                    if not entries:
                        last_display = None
                        emit({
                            "status": source_status,
                            "title": metadata.get("title", ""),
                            "artist": metadata.get("artist", ""),
                            "message": "Synced lyrics unavailable",
                        })

            if player and entries:
                previous, current, following = lines_at_position(entries, playback_position_ms(player))
                payload = {
                    "status": "ok", "title": metadata.get("title", ""),
                    "artist": metadata.get("artist", ""), "previous": previous,
                    "current": current, "next": following,
                }
                if payload != last_display:
                    emit(payload)
                    last_display = payload
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError, ValueError) as exc:
            payload = {"status": "error", "message": str(exc)[:160]}
            if payload != last_display:
                emit(payload); last_display = payload
            player = None
            next_metadata_check = 0.0
        time.sleep(0.18)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(0)
