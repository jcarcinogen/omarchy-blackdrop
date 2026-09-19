import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReactivePresetTests(unittest.TestCase):
    def test_every_preset_uses_transient_drum_and_voice_modulation(self):
        presets = sorted((ROOT / "presets").glob("*.milk"))
        self.assertEqual(len(presets), 12)
        for preset in presets:
            text = preset.read_text(errors="ignore")
            with self.subTest(preset=preset.name):
                self.assertIn("bd_kick=max(0,min(2,bass/(bass_att+0.01)-1))", text)
                self.assertIn("bd_voice=max(0,min(2,0.65*(mid/(mid_att+0.01)-1)+0.35*(treb/(treb_att+0.01)-1)))", text)
                self.assertIn("zoom=zoom*(1+0.10*bd_kick)", text)
                self.assertIn("warp=warp+0.32*bd_voice", text)
                self.assertNotIn("bd_bass=", text)


if __name__ == "__main__":
    unittest.main()
