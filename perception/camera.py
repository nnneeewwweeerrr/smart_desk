
import cv2


class Camera:
    """摄像头采集模块"""

    def __init__(self, camera_id=0):
        self.camera_id = camera_id
        self.cap = None

    def start(self):
        """打开摄像头"""
        self.cap = cv2.VideoCapture(self.camera_id)

        if not self.cap.isOpened():
            raise RuntimeError(
                "摄像头打开失败，请检查摄像头连接或编号"
            )

        print("摄像头启动成功！")

    def read(self):
        """读取一帧画面"""
        if self.cap is None or not self.cap.isOpened():
            return False, None

        return self.cap.read()

    def release(self):
        """释放摄像头"""
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def show(self):
        """实时显示摄像头画面"""
        self.start()

        try:
            while True:
                success, frame = self.read()

                if not success:
                    print("读取摄像头画面失败")
                    break

                cv2.imshow("Smart Desk - Camera", frame)

                # 按 q 键退出
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

        finally:
            self.release()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    camera = Camera(camera_id=0)
    camera.show()
