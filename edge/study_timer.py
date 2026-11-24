import time


class StudyTimer:
    """Monotonic study/rest timer preserving time across pause and phase changes."""

    def __init__(self, study_duration=25 * 60, rest_duration=5 * 60):
        if study_duration <= 0 or rest_duration <= 0:
            raise ValueError("Timer durations must be positive")
        self.study_duration = study_duration
        self.rest_duration = rest_duration
        self.previous_status = "studying"
        self.reset()

    def start(self):
        if self.status in ("studying", "resting"):
            self.update()
            return
        self.status = self.previous_status if self.status == "paused" else "studying"
        self.last_update = time.monotonic()

    def pause(self):
        if self.status in ("studying", "resting"):
            self.update()
            self.previous_status = self.status
            self.status = "paused"
            self.last_update = None

    def reset(self):
        self.status = "idle"
        self.remaining = self.study_duration
        self.total_study_seconds = 0.0
        self.last_update = None

    def update(self):
        if self.status not in ("studying", "resting"):
            return self.get_state()
        now = time.monotonic()
        elapsed = max(0.0, now - self.last_update) if self.last_update is not None else 0.0
        self.last_update = now
        while elapsed > 0:
            consumed = min(elapsed, self.remaining)
            if self.status == "studying":
                self.total_study_seconds += consumed
            self.remaining -= consumed
            elapsed -= consumed
            if self.remaining <= 0:
                self.status = "resting" if self.status == "studying" else "studying"
                self.remaining = (self.rest_duration if self.status == "resting"
                                  else self.study_duration)
        return self.get_state()

    def get_state(self):
        return {
            "study_status": self.status,
            "timer_phase": self.previous_status if self.status == "paused" else self.status,
            "remaining_seconds": max(0, int(self.remaining)),
            "study_minutes": int(self.total_study_seconds) / 60,
            "total_study_seconds": int(self.total_study_seconds),
        }
