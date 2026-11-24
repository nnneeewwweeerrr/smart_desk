
class OLEDDisplay:
    """OLED显示模块，当前使用软件模拟模式"""

    def __init__(self, mock=True):
        self.mock = mock
        self.is_open = True
        self._last_status = None

        print("OLED模块初始化成功")
        print("当前模式：软件模拟模式")

    def show_status(
        self,
        posture="UNKNOWN",
        study_minutes=0,
        reminder_count=0,
        study_status="STUDYING"
    ):
        """更新OLED显示内容"""

        if not self.is_open:
            return

        if self.mock:
            status = (posture, study_minutes, reminder_count, study_status)
            if status == self._last_status:
                return
            self._last_status = status
            print("\n========== SMART DESK ==========")
            print(f"当前坐姿：{posture}")
            print(f"学习时间：{study_minutes} 分钟")
            print(f"提醒次数：{reminder_count}")
            print(f"学习状态：{study_status}")
            print("================================")

    def close(self):
        self.is_open = False
        print("OLED模块已关闭")
