
import threading


class StateManager:
    def __init__(self):
        self.lock = threading.RLock()

        self.state = {
            "camera_online": False,
            "person_detected": False,
            "posture": "unknown",

            "study_minutes": 0,
            "total_study_seconds": 0,
            "remaining_seconds": 0,
            "study_status": "idle",

            "reminder_count": 0,
            "alert": False,
            "alert_elapsed": 0.0,
            "alert_remaining": 5.0,

            "light": False,
            "buzzer_enabled": False,
            "buzzer_active": False,
            "buzzer_mode": "mock",
            "light_mode": "mock",
        }
        self.state.update(
            calibrated=False, calibration_samples=0, calibration_required=10,
            calibration_result="waiting", calibration_message="请坐正并积累有效样本后校准",
            posture_command_id=0, session_start=None,
            reminder_scope="current_session", device_mode="mock",
        )

        # 网页发给主程序的学习计时指令
        self.timer_command = None

        # 网页发给主程序的姿态校准指令
        self.posture_command = None

    def update(self, **kwargs):
        """更新系统共享状态"""
        with self.lock:
            self.state.update(kwargs)

    def get_state(self):
        """获取当前系统状态"""
        with self.lock:
            return self.state.copy()

    def set_light(self, enabled):
        """设置台灯状态"""
        with self.lock:
            self.state["light"] = bool(enabled)

    def set_buzzer(self, enabled):
        """设置蜂鸣器状态"""
        with self.lock:
            self.state["buzzer_enabled"] = bool(enabled)

    def set_timer_command(self, command):
        """接收网页计时指令"""
        allowed_commands = ["start", "pause", "reset"]

        if command not in allowed_commands:
            return False

        with self.lock:
            if self.timer_command is not None:
                return False
            self.timer_command = command

        return True

    def get_timer_command(self):
        """读取计时指令，读取后清空"""
        with self.lock:
            command = self.timer_command
            self.timer_command = None

        return command

    def set_posture_command(self, command):
        """接收网页姿态校准指令"""
        allowed_commands = [
            "calibrate",
            "reset_calibration"
        ]

        if command not in allowed_commands:
            return False

        with self.lock:
            if self.posture_command is not None:
                return False
            self.posture_command = command
            self.state["posture_command_id"] += 1
            self.state["calibration_result"] = "pending"
            self.state["calibration_message"] = "校准指令等待执行"

        return True

    def get_posture_command(self):
        """读取姿态指令，读取后清空"""
        with self.lock:
            command = self.posture_command
            self.posture_command = None

        return command


system_state = StateManager()
