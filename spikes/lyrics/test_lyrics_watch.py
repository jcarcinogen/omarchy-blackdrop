import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import lyrics_watch


class LyricsWatchTests(unittest.TestCase):
    def test_parse_lrc_orders_timestamps_and_ignores_metadata(self):
        raw = "[ar:Artist]\n[00:12.50]Second line\n[00:03.00][00:06.00]First line\n"
        self.assertEqual(
            lyrics_watch.parse_lrc(raw),
            [(3000, "First line"), (6000, "First line"), (12500, "Second line")],
        )
    def test_lines_at_position_returns_previous_current_and_next(self):
        entries = [(1000, "One"), (2500, "Two"), (4000, "Three")]
        self.assertEqual(lyrics_watch.lines_at_position(entries, 3000), ("One", "Two", "Three"))
        self.assertEqual(lyrics_watch.lines_at_position(entries, 500), ("", "", "One"))
    def test_parse_busctl_metadata_extracts_track_signature(self):
        payload = {
            "type": "a{sv}",
            "data": {
                "mpris:trackid": {"type": "o", "data": "/track/1"},
                "mpris:length": {"type": "x", "data": 275000000},
                "xesam:title": {"type": "s", "data": "Let It All Out"},
                "xesam:artist": {"type": "as", "data": ["The Elovaters", "Pepper"]},
                "xesam:album": {"type": "s", "data": "Double Vision"},
            },
        }
        self.assertEqual(
            lyrics_watch.parse_busctl_metadata(payload),
            {
                "track_id": "/track/1",
                "duration": 275,
                "title": "Let It All Out",
                "artist": "The Elovaters, Pepper",
                "search_artist": "The Elovaters",
                "album": "Double Vision",
            },
        )
    def test_choose_synced_result_prefers_duration_match(self):
        results = [
            {"id": 1, "duration": 240, "syncedLyrics": "[00:01.00]Wrong"},
            {"id": 2, "duration": 274.5, "syncedLyrics": "[00:01.00]Right"},
            {"id": 3, "duration": 275, "syncedLyrics": None},
        ]
        self.assertEqual(lyrics_watch.choose_synced_result(results, 275)["id"], 2)
        self.assertIsNone(lyrics_watch.choose_synced_result(results, 200))


if __name__ == "__main__":
    unittest.main()
