import threading
import time


class CameraWorker:
    """Read/reopen the camera off the control thread; expire stale frames."""

    def __init__(self, camera, max_age=2.0):
        self.camera = camera
        self.max_age = max_age
        self.lock = threading.Lock()
        self.stopping = threading.Event()
        self.frame = None
        self.sequence = 0
        self.updated_at = None
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()

    def _run(self):
        while not self.stopping.is_set():
            try:
                self.camera.start()
                while not self.stopping.is_set():
                    ok, frame = self.camera.read()
                    if not ok or frame is None:
                        break
                    with self.lock:
                        self.frame = frame
                        self.sequence += 1
                        self.updated_at = time.monotonic()
            except Exception as error:
                print("摄像头暂不可用，稍后重试：", error)
            finally:
                with self.lock:
                    self.frame = None
                self.camera.release()
            self.stopping.wait(2.0)

    def snapshot(self, last_sequence):
        with self.lock:
            online = (self.frame is not None and self.updated_at is not None
                      and time.monotonic() - self.updated_at <= self.max_age)
            frame = (self.frame.copy() if online and self.sequence != last_sequence
                     else None)
            return frame, self.sequence, online

    def close(self):
        self.stopping.set()
        self.thread.join(timeout=3)
