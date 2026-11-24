"""Contract checks for classification and alert timing, without a camera."""

import unittest
from unittest.mock import patch

from edge.posture_judge import PostureJudge


def features(head=0.0, tilt=0.0):
    return {"head_drop": head, "shoulder_tilt": tilt,
            "body_lean": None, "hips_visible": False}


class PostureLogicTests(unittest.TestCase):
    def setUp(self):
        self.clock = patch("edge.posture_judge.time.monotonic", return_value=0.0)
        self.now = self.clock.start()
        self.addCleanup(self.clock.stop)
        self.judge = PostureJudge()

    def calibrate(self):
        for _ in range(10):
            self.judge.judge(features())
        self.assertTrue(self.judge.calibrate())

    def settle(self, sample):
        for _ in range(5):
            result = self.judge.judge(sample)
        return result

    def test_calibration_requires_ten_valid_samples(self):
        self.assertEqual(self.judge.judge(None)["posture"], "KEYPOINTS NOT CLEAR")
        self.assertEqual(self.judge.judge(features())["posture"], "WAIT CALIBRATION")
        self.assertFalse(self.judge.calibrate())
        for _ in range(9):
            self.judge.judge(features())
        self.assertTrue(self.judge.calibrate())
        self.assertEqual(self.judge.judge(features())["posture"], "NORMAL")

    def test_head_and_tilt_classification(self):
        self.calibrate()
        for sample, expected in [
            (features(), "NORMAL"),
            (features(head=0.3), "HEAD DOWN"),
            (features(tilt=0.3), "TILT LEFT"),
            (features(tilt=-0.3), "TILT RIGHT"),
        ]:
            with self.subTest(expected=expected):
                self.assertEqual(self.settle(sample)["posture"], expected)

    def test_head_down_has_priority_when_two_thresholds_are_exceeded(self):
        self.calibrate()
        result = self.settle(features(head=0.3, tilt=0.3))
        self.assertEqual(result["posture"], "HEAD DOWN")

    def test_five_seconds_one_alert_and_recovery_rearms(self):
        self.calibrate()
        self.settle(features(head=0.3))
        self.now.return_value = 4.9
        self.assertFalse(self.judge.judge(features(head=0.3))["alert"])
        self.now.return_value = 5.0
        self.assertEqual(self.judge.judge(features(head=0.3))["alert_count"], 1)
        self.now.return_value = 8.0
        self.assertEqual(self.judge.judge(features(head=0.3))["alert_count"], 1)
        self.assertFalse(self.settle(features())["alert"])
        self.settle(features(head=0.3))
        self.now.return_value = 13.0
        self.assertEqual(self.judge.judge(features(head=0.3))["alert_count"], 2)

    def test_missing_points_clear_alert_and_samples_but_keep_baseline(self):
        self.calibrate()
        self.settle(features(head=0.3))
        self.now.return_value = 6.0
        self.assertTrue(self.judge.judge(features(head=0.3))["alert"])
        result = self.judge.judge(None)
        self.assertFalse(result["alert"])
        self.assertEqual(result["posture"], "KEYPOINTS NOT CLEAR")
        self.assertEqual(len(self.judge.history), 0)
        self.assertEqual(len(self.judge.calibration_history), 0)
        self.assertIsNotNone(self.judge.baseline)

    def test_switching_abnormal_category_restarts_clock(self):
        self.judge.update_alert("HEAD DOWN")
        self.now.return_value = 4.0
        self.assertEqual(self.judge.update_alert("TILT LEFT"), 0.0)
        self.now.return_value = 5.0
        self.assertEqual(self.judge.update_alert("TILT LEFT"), 1.0)
        self.assertFalse(self.judge.alert_triggered)

    def test_reset_calibration_clears_samples_but_not_lifetime_count(self):
        self.calibrate()
        self.judge.alert_count = 2
        self.judge.reset_calibration()
        self.assertIsNone(self.judge.baseline)
        self.assertFalse(self.judge.history)
        self.assertFalse(self.judge.calibration_history)
        self.assertEqual(self.judge.alert_count, 2)


if __name__ == "__main__":
    unittest.main()
