
import cv2
import threading


class VideoStream:
    """在线程之间共享最新的摄像头画面"""

    def __init__(self):
        self.lock = threading.Lock()
        self.frame = None

    def set_frame(self, frame):
        """将处理后的画面编码为 JPEG 并保存"""
        if frame is None:
            return

        success, encoded = cv2.imencode(
            ".jpg",
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), 80]
        )

        if success:
            with self.lock:
                self.frame = encoded.tobytes()

    def get_frame(self):
        """获取最新 JPEG 画面"""
        with self.lock:
            return self.frame

    def clear(self):
        """清除共享画面"""
        with self.lock:
            self.frame = None


video_stream = VideoStream()
