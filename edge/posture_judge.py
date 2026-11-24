
import time
import numpy as np
from collections import deque
from edge.one_euro import OneEuroFilter


class PostureJudge:
    """坐姿判断、正常坐姿校准和异常计时"""

    ALERT_DURATION = 5.0
    MIN_CALIBRATION_SAMPLES = 10

    def __init__(self, smoothing="moving_average", min_cutoff=1.0, beta=0.5, d_cutoff=1.0):
        if smoothing not in ("moving_average", "one_euro"):
            raise ValueError("Unknown smoothing method")
        self.smoothing = smoothing
        self.filters = {key: OneEuroFilter(min_cutoff, beta, d_cutoff)
                        for key in ("head_drop", "shoulder_tilt", "body_lean")}
        self.last_timestamp = None
        self.baseline_timestamp = None
        self.history = deque(maxlen=5)
        self.calibration_history = deque(maxlen=30)

        self.baseline = None

        self.abnormal_start_time = None
        self.abnormal_posture = None
        self.alert_triggered = False
        self.alert_count = 0

    def average_features(self, samples):
        result = {}

        for key in ["head_drop", "shoulder_tilt", "body_lean"]:
            values = [
                item[key] for item in samples
                if item[key] is not None
            ]

            result[key] = (
                float(np.mean(values)) if values else None
            )

        return result

    def calibrate(self):
        """使用最近有效样本建立正常坐姿基准"""
        if len(self.calibration_history) < self.MIN_CALIBRATION_SAMPLES:
            return False

        self.baseline = self.average_features(
            list(self.calibration_history)
        )
        self.baseline_timestamp = self.last_timestamp
        self.reset_smoothing(self.baseline, self.baseline_timestamp)
        self.reset_alert()
        return True

    def reset_calibration(self):
        """清除校准数据"""
        self.baseline = None
        self.history.clear()
        self.calibration_history.clear()
        self.baseline_timestamp = None
        self.last_timestamp = None
        self.reset_smoothing()
        self.reset_alert()

    def reset_smoothing(self, seed=None, timestamp=None):
        self.history.clear()
        if seed is not None:
            self.history.extend(dict(seed) for _ in range(5))
        for key, filter_ in self.filters.items():
            if seed is not None and seed.get(key) is not None and timestamp is not None:
                filter_.reset(seed[key], timestamp)
            else:
                filter_.reset()

    def filter_settings(self):
        filter_ = self.filters["head_drop"]
        return {"method": self.smoothing, "window": 5 if self.smoothing == "moving_average" else None,
                "min_cutoff": filter_.min_cutoff, "beta": filter_.beta,
                "d_cutoff": filter_.d_cutoff, "max_gap": filter_.max_gap}

    def reset_alert(self):
        self.abnormal_start_time = None
        self.abnormal_posture = None
        self.alert_triggered = False

    def judge(self, features, timestamp=None):
        """输入姿态特征，返回当前坐姿状态"""

        if features is None:
            self.reset_smoothing()
            self.last_timestamp = None
            self.calibration_history.clear()
            self.reset_alert()
            return self.result("KEYPOINTS NOT CLEAR")

        timestamp = time.monotonic() if timestamp is None else timestamp
        if (self.last_timestamp is not None and
                timestamp - self.last_timestamp > self.filters["head_drop"].max_gap):
            self.reset_smoothing()
            self.calibration_history.clear()
        self.last_timestamp = timestamp
        self.history.append(features)
        self.calibration_history.append(features)

        if self.baseline is None:
            self.reset_alert()
            return self.result("WAIT CALIBRATION")

        if self.smoothing == "moving_average":
            current = self.average_features(self.history)
        else:
            current = {}
            for key, filter_ in self.filters.items():
                if features[key] is None:
                    filter_.reset()
                    current[key] = None
                else:
                    current[key] = float(filter_(features[key], timestamp))

        head_change = (
            current["head_drop"] - self.baseline["head_drop"]
        )

        tilt_change = (
            current["shoulder_tilt"]
            - self.baseline["shoulder_tilt"]
        )

        posture = "NORMAL"

        if head_change > 0.15:
            posture = "HEAD DOWN"

        elif tilt_change > 0.15:
            posture = "TILT LEFT"

        elif tilt_change < -0.15:
            posture = "TILT RIGHT"

        elif (
            current["body_lean"] is not None
            and self.baseline["body_lean"] is not None
        ):
            lean_change = abs(
                current["body_lean"]
                - self.baseline["body_lean"]
            )

            if lean_change > 0.25:
                posture = "LEAN FORWARD"

        elapsed = self.update_alert(posture, now=timestamp)

        return {
            "posture": posture,
            "head_change": head_change,
            "tilt_change": tilt_change,
            "hips_visible": features["hips_visible"],
            "elapsed": elapsed,
            "alert": self.alert_triggered,
            "alert_count": self.alert_count,
            "alert_message": self.alert_message,
            "filtered_features": current,
        }

    def update_alert(self, posture, now=None):
        now = time.monotonic() if now is None else now
        self._alert_now = now
        abnormal = [
            "HEAD DOWN",
            "TILT LEFT",
            "TILT RIGHT",
            "LEAN FORWARD"
        ]

        if posture not in abnormal:
            self.reset_alert()
            return 0.0

        if self.abnormal_posture != posture:
            self.abnormal_posture = posture
            self.abnormal_start_time = now
            self.alert_triggered = False

        elapsed = max(0.0, now - self.abnormal_start_time)

        if elapsed >= self.ALERT_DURATION and not self.alert_triggered:
            self.alert_triggered = True
            self.alert_count += 1
            print(f"WARNING: {posture} lasted {elapsed:.1f}s")

        return elapsed

    @property
    def alert_message(self):
        if self.alert_triggered:
            return "ALERT TRIGGERED"

        if self.abnormal_start_time is None:
            return "NO ALERT"

        remaining = max(
            0,
            self.ALERT_DURATION
            - (self._alert_now - self.abnormal_start_time)
        )

        return f"ALERT IN {remaining:.1f}s"

    def result(self, posture):
        return {
            "posture": posture,
            "head_change": 0.0,
            "tilt_change": 0.0,
            "hips_visible": False,
            "elapsed": 0.0,
            "alert": False,
            "alert_count": self.alert_count,
            "alert_message": self.alert_message
        }
