import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import set_projectm_fps


class RefreshRateTests(unittest.TestCase):
    def test_matches_the_monitor_current_refresh_rate(self):
        self.assertEqual(set_projectm_fps.refresh_for_monitor({"refreshRate": 59.94}), 60)
        self.assertEqual(set_projectm_fps.refresh_for_monitor({"refreshRate": 119.88}), 120)
        self.assertEqual(set_projectm_fps.refresh_for_monitor({"refreshRate": 144.001}), 144)

    def test_falls_back_to_sixty_when_refresh_is_missing(self):
        self.assertEqual(set_projectm_fps.refresh_for_monitor({}), 60)

    def test_clamps_unreasonable_values(self):
        self.assertEqual(set_projectm_fps.refresh_for_monitor({"refreshRate": 500}), 360)
        self.assertEqual(set_projectm_fps.refresh_for_monitor({"refreshRate": 10}), 30)


if __name__ == "__main__":
    unittest.main()
