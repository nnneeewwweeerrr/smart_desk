import argparse
import os
import threading
import time

import cv2
import numpy as np

from communication.web_app import app
from control.buzzer import Buzzer
from control.oled_display import OLEDDisplay
from data.database import Database
from edge.posture_judge import PostureJudge
from edge.study_timer import StudyTimer
from perception.camera import Camera
from perception.posture import UpperBodyPose
from services.camera_worker import CameraWorker
from services.runtime import DeskRuntime
from services.state_manager import system_state
from services.video_stream import video_stream


ALERT_DURATION = PostureJudge.ALERT_DURATION


def read_camera_frame(camera):
    """Compatibility helper for existing manual scripts."""
    result = camera.read()
    if isinstance(result, tuple):
        if len(result) != 2 or not result[0]:
            return None
        result = result[1]
    return result if isinstance(result, np.ndarray) else None


def start_web_server():
    app.run(host="0.0.0.0", port=5000, debug=False,
            threaded=True, use_reloader=False)


def draw_status(frame, state):
    lines = [
        "Posture: " + state["posture"],
        "Study: %.1f min" % state["study_minutes"],
        "Status: " + state["study_status"],
        "Remaining: %02d:%02d" % divmod(state["remaining_seconds"], 60),
        "Session reminders: %d" % state["reminder_count"],
    ]
    for index, text in enumerate(lines):
        cv2.putText(frame, text, (10, 30 + index * 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 220, 255), 2)
    return frame


def main(headless=False, smoothing="one_euro", min_cutoff=1.0, beta=0.5, d_cutoff=1.0,
         buzzer_mode="mock"):
    detector = worker = runtime = buzzer = oled = None
    sequence = 0
    try:
        buzzer = Buzzer(mock=buzzer_mode == "mock", enabled=False)
        oled = OLEDDisplay(mock=True)
        system_state.update(buzzer_enabled=False, buzzer_active=False,
                            buzzer_mode=buzzer_mode, light_mode="mock",
                            device_mode="mock" if buzzer_mode == "mock" else "mixed")
        detector = UpperBodyPose()
        judge = PostureJudge(smoothing=smoothing, min_cutoff=min_cutoff, beta=beta, d_cutoff=d_cutoff)
        runtime = DeskRuntime(judge, StudyTimer(), Database(), system_state)
        worker = CameraWorker(Camera(camera_id=0))
        worker.start()
        threading.Thread(target=start_web_server, daemon=True).start()
        print("无窗口模式，请通过网页校准和控制" if headless else "C/R 校准，S/P/T 计时，Q 退出")
        while True:
            frame, next_sequence, online = worker.snapshot(sequence)
            if frame is None and online:
                time.sleep(0.01)
                continue
            sequence = next_sequence
            if frame is None:
                features = None
                annotated = np.zeros((480, 640, 3), np.uint8)
                cv2.putText(annotated, "CAMERA OFFLINE - retrying", (20, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            else:
                annotated, features = detector.process(frame)
            state, sound = runtime.step(features, online)
            buzzer.set_enabled(state["buzzer_enabled"])
            buzzer.start() if sound else buzzer.stop()
            system_state.update(buzzer_active=buzzer.is_active)
            oled.show_status(state["posture"], state["study_minutes"],
                             state["reminder_count"], state["study_status"].upper())
            video_stream.set_frame(draw_status(annotated, state))
            if not headless:
                cv2.imshow("Smart Desk Lamp", annotated)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                if key in (ord("c"), ord("r")):
                    system_state.set_posture_command(
                        "calibrate" if key == ord("c") else "reset_calibration")
                action = {ord("s"): "start", ord("p"): "pause", ord("t"): "reset"}.get(key)
                if action:
                    system_state.set_timer_command(action)
            if not online:
                time.sleep(0.05)
    except KeyboardInterrupt:
        print("收到退出指令，正在保存并释放资源")
    finally:
        if buzzer is not None:
            try:
                buzzer.close()
            except Exception as error:
                print("关闭蜂鸣器失败：", error)
        if runtime is not None:
            try:
                runtime.close()
            except Exception as error:
                print("退出时保存失败：", error)
        if worker is not None:
            worker.close()
        if detector is not None:
            detector.release()
        if oled is not None:
            oled.close()
        system_state.update(camera_online=False, person_detected=False, alert=False,
                            buzzer_active=False)
        video_stream.clear()
        if not headless:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="智学灯姿态监测与网页服务")
    parser.add_argument("--headless", action="store_true", help="通过网页查看画面和控制")
    parser.add_argument("--smoothing", choices=["one_euro", "moving_average"],
                        default=os.environ.get("SMART_DESK_SMOOTHING", "one_euro"))
    parser.add_argument("--filter-min-cutoff", type=float, default=1.0)
    parser.add_argument("--filter-beta", type=float, default=0.5)
    parser.add_argument("--filter-d-cutoff", type=float, default=1.0)
    parser.add_argument("--buzzer", choices=["mock", "gpio"],
                        default=os.environ.get("SMART_DESK_BUZZER", "mock"),
                        help="gpio: 已核实接线的 Pi 4 / MH-FMD / GPIO17")
    args = parser.parse_args()
    main(args.headless, args.smoothing, args.filter_min_cutoff, args.filter_beta,
         args.filter_d_cutoff, args.buzzer)
