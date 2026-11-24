import math
import unittest
import csv
import io

from edge.one_euro import OneEuroFilter
from edge.posture_judge import PostureJudge


def sample(head=0.0, tilt=0.0, lean=None):
    return dict(head_drop=head, shoulder_tilt=tilt, body_lean=lean,
                hips_visible=lean is not None)


class OneEuroTests(unittest.TestCase):
    def test_first_sample_and_constant_are_exact(self):
        filter_ = OneEuroFilter()
        for timestamp in (0, .1, .35, .5, .7):
            self.assertEqual(filter_(2.5, timestamp), 2.5)

    def test_fixed_cutoff_matches_hand_computed_low_pass(self):
        filter_ = OneEuroFilter(min_cutoff=1, beta=0)
        self.assertEqual(filter_(0, 0), 0)
        alpha = 1 / (1 + 1 / (2 * math.pi * .1))
        self.assertAlmostEqual(filter_(1, .1), alpha)
        alpha2 = 1 / (1 + 1 / (2 * math.pi * .2))
        self.assertAlmostEqual(filter_(1, .3), alpha2 + (1 - alpha2) * alpha)

    def test_adaptation_matches_appendix_derivative_formula(self):
        filter_ = OneEuroFilter(min_cutoff=1, beta=.5, d_cutoff=1)
        filter_(0, 0)
        ad = 1 / (1 + 1 / (2 * math.pi * .1))
        derivative = ad * 10
        cutoff = 1 + .5 * derivative
        expected = 1 / (1 + 1 / (2 * math.pi * cutoff * .1))
        self.assertAlmostEqual(filter_(1, .1), expected)
        self.assertGreater(expected, ad)

    def test_repeated_backward_time_and_tracking_gap(self):
        filter_ = OneEuroFilter()
        self.assertEqual(filter_(1, 10), 1)
        self.assertEqual(filter_(99, 10), 1)
        self.assertEqual(filter_(99, 9), 1)
        self.assertEqual(filter_(3, 13), 3)
        filter_.reset()
        self.assertEqual(filter_(7, 0), 7)

    def test_invalid_values_do_not_poison_filter(self):
        for parameters in [dict(min_cutoff=0), dict(beta=-1), dict(d_cutoff=-1),
                           dict(beta=math.nan), dict(max_gap=math.inf)]:
            with self.subTest(parameters=parameters), self.assertRaises(ValueError):
                OneEuroFilter(**parameters)
        filter_ = OneEuroFilter()
        filter_(0, 0)
        with self.assertRaises(ValueError):
            filter_(math.nan, .1)
        self.assertTrue(math.isfinite(filter_(1, .2)))


class OneEuroPostureTests(unittest.TestCase):
    def calibrated(self, method="one_euro"):
        judge = PostureJudge(smoothing=method)
        for index in range(10):
            judge.judge(sample(), timestamp=index / 10)
        self.assertTrue(judge.calibrate())
        return judge

    def test_classification_and_five_second_alert_use_sample_time(self):
        judge = self.calibrated()
        first = None
        counts = []
        for index in range(10, 90):
            timestamp = index / 10
            result = judge.judge(sample(head=.4), timestamp=timestamp)
            if result["posture"] == "HEAD DOWN" and first is None:
                first = timestamp
            if result["alert"]:
                self.assertGreaterEqual(timestamp - first, 5)
                counts.append(result["alert_count"])
        self.assertIsNotNone(first)
        self.assertEqual(set(counts), {1})

    def test_loss_reset_and_optional_hips_do_not_reuse_old_signal(self):
        judge = self.calibrated()
        judge.judge(sample(head=.4, lean=.3), timestamp=1)
        judge.judge(None, timestamp=1.1)
        result = judge.judge(sample(), timestamp=1.2)
        self.assertEqual(result["posture"], "NORMAL")
        self.assertIsNone(result["filtered_features"]["body_lean"])
        self.assertIsNone(judge.filters["body_lean"].timestamp)
        judge.reset_calibration()
        self.assertIsNone(judge.baseline)
        self.assertTrue(all(f.timestamp is None for f in judge.filters.values()))

    def test_mean_mode_and_recalibration_remain_available(self):
        for method in ("moving_average", "one_euro"):
            judge = self.calibrated(method)
            for index in range(10, 20):
                judge.judge(sample(head=.03), timestamp=index / 10)
            self.assertTrue(judge.calibrate())
            self.assertEqual(judge.filter_settings()["method"], method)
            self.assertEqual(judge.filter_settings()["window"], 5 if method == "moving_average" else None)
            self.assertEqual(len(judge.history), 5)
            self.assertEqual(judge.judge(sample(head=.03), timestamp=2)["posture"], "NORMAL")

    def test_exported_raw_csv_replays_to_identical_live_decisions(self):
        from tests.manual.compare_posture_filters import replay
        for method in ("moving_average", "one_euro"):
            judge = self.calibrated(method)
            rows, expected = [], []
            for index in range(10, 90):
                timestamp = index / 10
                features = sample(head=.4 if index < 70 else 0)
                if index in (30, 31):
                    features = None
                result = judge.judge(features, timestamp=timestamp)
                expected.append(result)
                rows.append({"run_id": "test", "sample_time_s": timestamp,
                             "valid": int(features is not None), "label": "NORMAL",
                             "head_drop": features["head_drop"] if features else "",
                             "shoulder_tilt": features["shoulder_tilt"] if features else "",
                             "body_lean": "", "hips_visible": 0,
                             "baseline_time_s": judge.baseline_timestamp,
                             "baseline_head_drop": 0, "baseline_shoulder_tilt": 0,
                             "baseline_body_lean": ""})
            stream = io.StringIO()
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
            stream.seek(0)
            actual, summary = replay(list(csv.DictReader(stream)))
            self.assertEqual(summary["source"], "recorded_raw_features")
            for observed, wanted in zip(actual, expected):
                self.assertEqual(observed[method + "_posture"], wanted["posture"])
                self.assertEqual(observed[method + "_alert"], wanted["alert"])
                if wanted.get("filtered_features"):
                    self.assertAlmostEqual(observed[method + "_head"], wanted["filtered_features"]["head_drop"])


if __name__ == "__main__":
    unittest.main()
