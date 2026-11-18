
import time
import numpy as np
from collections import deque


class PostureJudge:
    """坐姿判断、正常坐姿校准和异常计时"""

    ALERT_DURATION = 5.0

    def __init__(self):
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
        if len(self.calibration_history) < 10:
            return False

        self.baseline = self.average_features(
            list(self.calibration_history)
        )

        self.reset_alert()
        return True

    def reset_calibration(self):
        """清除校准数据"""
        self.baseline = None
        self.history.clear()
        self.calibration_history.clear()
        self.reset_alert()

    def reset_alert(self):
        self.abnormal_start_time = None
        self.abnormal_posture = None
        self.alert_triggered = False

    def judge(self, features):
        """输入姿态特征，返回当前坐姿状态"""

        if features is None:
            self.reset_alert()
            return self.result("KEYPOINTS NOT CLEAR")

        self.history.append(features)
        self.calibration_history.append(features)

        if self.baseline is None:
            self.reset_alert()
            return self.result("WAIT CALIBRATION")

        current = self.average_features(self.history)

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

        elapsed = self.update_alert(posture)

        return {
            "posture": posture,
            "head_change": head_change,
            "tilt_change": tilt_change,
            "hips_visible": features["hips_visible"],
            "elapsed": elapsed,
            "alert": self.alert_triggered,
            "alert_count": self.alert_count,
            "alert_message": self.alert_message
        }

    def update_alert(self, posture):
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
            self.abnormal_start_time = time.monotonic()
            self.alert_triggered = False

        elapsed = time.monotonic() - self.abnormal_start_time

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
            - (time.monotonic() - self.abnormal_start_time)
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
