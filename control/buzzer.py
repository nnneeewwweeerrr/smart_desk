
class Buzzer:
    """蜂鸣器控制模块，当前使用软件模拟模式"""

    def __init__(self, mock=True):
        self.mock = mock
        self.enabled = True
        self.is_active = False

        print("蜂鸣器模块初始化成功")
        print("当前模式：软件模拟模式" if mock else "硬件模式")

    def start(self):
        """启动蜂鸣器"""
        if not self.enabled or self.is_active:
            return

        self.is_active = True

        if self.mock:
            print("🔔 [模拟蜂鸣器] 开始响铃！")

    def stop(self):
        """停止蜂鸣器"""
        if not self.is_active:
            return

        self.is_active = False

        if self.mock:
            print("[模拟蜂鸣器] 已停止")

    def set_enabled(self, enabled):
        """开启或关闭蜂鸣器提醒"""
        self.enabled = enabled

        if not enabled:
            self.stop()

    def close(self):
        """释放蜂鸣器"""
        self.stop()
        print("蜂鸣器模块已关闭")
