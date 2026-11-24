
class Buzzer:
    """MH-FMD active-low buzzer on Pi 4 BCM17 (physical pin 11)."""

    def __init__(self, mock=True, enabled=True):
        self.mock = mock
        self.enabled = enabled
        self.is_active = False
        self._request = None
        self._closed = False
        if not mock:
            # Import only in hardware mode, so desktop/mock runs need no GPIO library.
            import gpiod
            from gpiod.line import Bias, Direction, Value

            self._values = Value
            with gpiod.Chip("/dev/gpiochip0") as chip:
                if chip.get_info().label != "pinctrl-bcm2711" or chip.get_line_info(17).name != "GPIO17":
                    raise RuntimeError("蜂鸣器配置仅适用于已核实接线的 Pi 4 GPIO17")
                self._request = chip.request_lines(
                    consumer="smart-desk-buzzer",
                    config={17: gpiod.LineSettings(
                        direction=Direction.OUTPUT, active_low=True,
                        bias=Bias.PULL_UP, output_value=Value.INACTIVE,
                    )},
                )

        print("蜂鸣器模块初始化成功")
        print("当前模式：软件模拟模式" if mock else "硬件模式：GPIO17，低电平触发，初始关闭")

    def start(self):
        """启动蜂鸣器"""
        if self._closed or not self.enabled or self.is_active:
            return

        if self._request is not None:
            self._request.set_value(17, self._values.ACTIVE)
        self.is_active = True

        if self.mock:
            print("[模拟蜂鸣器] 开始响铃！")

    def stop(self):
        """停止蜂鸣器"""
        if not self.is_active:
            return

        if self._request is not None:
            self._request.set_value(17, self._values.INACTIVE)
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
        if self._closed:
            return
        try:
            if self._request is not None:
                # Explicitly switch off even when our cached state already says off.
                self._request.set_value(17, self._values.INACTIVE)
            else:
                self.stop()
        finally:
            try:
                if self._request is not None:
                    self._request.release()
            finally:
                self._request = None
                self.is_active = False
                self.enabled = False
                self._closed = True
        print("蜂鸣器模块已关闭")
