
import time


class StudyTimer:
    """学习计时与休息提醒模块"""

    def __init__(
        self,
        study_duration=25 * 60,
        rest_duration=5 * 60
    ):
        self.study_duration = study_duration
        self.rest_duration = rest_duration

        self.status = "idle"
        self.remaining = study_duration

        self.total_study_seconds = 0
        self.last_update = None

    def start(self):
        """开始或继续计时"""
        if self.status == "idle":
            self.status = "studying"

        if self.status == "paused":
            self.status = self.previous_status

        self.last_update = time.monotonic()

    def pause(self):
        """暂停计时"""
        if self.status in ["studying", "resting"]:
            self.previous_status = self.status
            self.status = "paused"
            self.last_update = None

    def reset(self):
        """重置计时"""
        self.status = "idle"
        self.remaining = self.study_duration
        self.total_study_seconds = 0
        self.last_update = None

    def update(self):
        """更新计时状态"""

        if self.status not in ["studying", "resting"]:
            return self.get_state()

        now = time.monotonic()

        if self.last_update is None:
            self.last_update = now
            return self.get_state()

        elapsed = now - self.last_update
        self.last_update = now

        self.remaining -= elapsed

        if self.status == "studying":
            self.total_study_seconds += elapsed

        # 当前阶段结束
        if self.remaining <= 0:

            if self.status == "studying":
                self.status = "resting"
                self.remaining = self.rest_duration
                print("学习时间结束，请休息！")

            else:
                self.status = "studying"
                self.remaining = self.study_duration
                print("休息结束，开始下一轮学习！")

        return self.get_state()

    def get_state(self):
        """返回当前计时信息"""

        return {
            "study_status": self.status,
            "remaining_seconds": max(0, int(self.remaining)),
            "study_minutes": int(self.total_study_seconds // 60),
            "total_study_seconds": int(self.total_study_seconds)
        }
