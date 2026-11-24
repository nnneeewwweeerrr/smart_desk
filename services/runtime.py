"""Control/session lifecycle, independent of camera reads and native inference."""

import time
from datetime import datetime


class DeskRuntime:
    def __init__(self, judge, timer, db, state):
        self.judge, self.timer, self.db, self.state = judge, timer, db, state
        self.session_start = None
        self.session_reminders = 0
        self.last_alert_count = judge.alert_count
        self.last_posture = "unknown"
        self.rest_alert_until = 0.0
        self.previous_status = "idle"

    def save_session(self):
        """Caller holds the state lock through save and publication/reset."""
        self.timer.update()
        seconds = self.timer.get_state()["total_study_seconds"]
        if self.session_start and (seconds or self.session_reminders):
            self.db.add_record(
                self.session_start, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                study_seconds=seconds, reminder_count=self.session_reminders,
                posture_status=self.last_posture,
            )
        self.session_start = None
        self.session_reminders = 0

    def _posture_command(self, features, online):
        command = self.state.get_posture_command()
        if command is None:
            return
        if command == "reset_calibration":
            self.judge.reset_calibration()
            result, message = "waiting", "校准已重置，请坐正并保持头肩清晰可见"
        elif not online or features is None:
            result, message = "failed", "校准失败：摄像头离线或头肩关键点不清晰"
        elif not self.judge.calibrate():
            result, message = "failed", "校准失败：连续有效样本不足，请坐正后重试"
        else:
            result, message = "succeeded", "正常坐姿校准成功"
        if result == "failed" and self.judge.baseline is not None:
            message += "；原校准基准保留"
        self.state.update(calibration_result=result, calibration_message=message)

    def step(self, features, camera_online):
        # /api/today_stats takes the same lock: saved and live contributions
        # cannot be read on opposite sides of a session save/reset.
        with self.state.lock:
            self.timer.update()
            if not camera_online or features is None:
                features = None
                self.judge.judge(None)
            self._posture_command(features, camera_online)
            command = self.state.get_timer_command()
            if command == "start":
                if self.session_start is None:
                    self.session_start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.session_reminders = 0
                    self.last_posture = "unknown"
                self.timer.start()
            elif command == "pause":
                self.timer.pause()
            elif command == "reset":
                try:
                    self.save_session()
                except Exception as error:
                    self.state.update(timer_error="记录保存失败，请重试")
                    print("保存学习记录失败：", error)
                else:
                    self.timer.reset()
                    self.rest_alert_until = 0.0
                    self.state.update(timer_error=None)

            result = self.judge.judge(features)
            new_alerts = max(0, result["alert_count"] - self.last_alert_count)
            self.last_alert_count = result["alert_count"]
            if self.session_start:
                self.session_reminders += new_alerts
            if result["posture"] in ("NORMAL", "HEAD DOWN", "TILT LEFT", "TILT RIGHT", "LEAN FORWARD"):
                self.last_posture = result["posture"]
            timer_state = self.timer.get_state()
            if timer_state["study_status"] == "resting" and self.previous_status != "resting":
                self.rest_alert_until = time.monotonic() + 3
            self.previous_status = timer_state["study_status"]
            if not camera_online:
                self.rest_alert_until = 0.0
            self.state.update(
                **timer_state, session_start=self.session_start,
                reminder_count=self.session_reminders,
                total_reminder_count=self.judge.alert_count,
                camera_online=camera_online, person_detected=features is not None,
                posture=result["posture"], alert=result["alert"],
                alert_elapsed=round(result["elapsed"], 1),
                alert_remaining=round(max(0, self.judge.ALERT_DURATION - result["elapsed"]), 1),
                calibrated=self.judge.baseline is not None,
                calibration_samples=len(self.judge.calibration_history),
                calibration_required=self.judge.MIN_CALIBRATION_SAMPLES,
                posture_smoothing=self.judge.filter_settings(),
                posture_features={"raw": features, "filtered": result.get("filtered_features"),
                                  "head_change": result["head_change"],
                                  "tilt_change": result["tilt_change"]},
            )
            return self.state.get_state(), bool(camera_online and (
                result["alert"] or time.monotonic() < self.rest_alert_until))

    def close(self):
        with self.state.lock:
            self.save_session()
            self.timer.reset()
            self.state.update(**self.timer.get_state(), session_start=None,
                              reminder_count=0, camera_online=False, person_detected=False,
                              alert=False)
