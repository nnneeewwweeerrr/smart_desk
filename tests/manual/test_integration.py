
import cv2
import time
import numpy as np
import threading
from datetime import datetime

from perception.camera import Camera
from perception.posture import UpperBodyPose
from edge.posture_judge import PostureJudge
from edge.study_timer import StudyTimer
from control.buzzer import Buzzer
from control.oled_display import OLEDDisplay
from data.database import Database

from services.state_manager import system_state
from services.video_stream import video_stream
from communication.web_app import app


ALERT_DURATION = 5.0


def read_camera_frame(camera):
    """兼容不同的摄像头返回格式"""
    result = camera.read()

    if isinstance(result, tuple):
        if len(result) != 2:
            return None

        ret, frame = result

        if not ret:
            return None
    else:
        frame = result

    if frame is None or not isinstance(frame, np.ndarray):
        return None

    return frame


def start_web_server():
    """在后台线程启动网页服务"""
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        threaded=True,
        use_reloader=False
    )


def main():

    # =========================
    # 1. 初始化模块
    # =========================

    camera = Camera(camera_id=0)
    detector = UpperBodyPose()
    judge = PostureJudge()

    timer = StudyTimer(
        study_duration=25 * 60,
        rest_duration=5 * 60
    )

    buzzer = Buzzer(mock=True)
    oled = OLEDDisplay(mock=True)
    db = Database()

    session_start = None
    last_reminder_count = 0
    last_posture = "unknown"

    rest_alert_until = 0
    previous_timer_status = "idle"

    # =========================
    # 2. 启动网页服务
    # =========================

    web_thread = threading.Thread(
        target=start_web_server,
        daemon=True
    )
    web_thread.start()

    print("网页服务已在后台启动")
    print("浏览器访问：http://127.0.0.1:5000")

    try:

        # =========================
        # 3. 启动摄像头
        # =========================

        camera.start()

        print("\n========== 智能学习台灯 ==========")
        print("C：坐姿校准")
        print("R：重新校准坐姿")
        print("S：开始 / 继续学习")
        print("P：暂停计时")
        print("T：重置计时")
        print("Q：退出程序")
        print("网页也可以控制学习计时和姿态校准")
        print("================================\n")

        # =========================
        # 4. 主循环
        # =========================

        while True:

            frame = read_camera_frame(camera)

            if frame is None:
                system_state.update(camera_online=False)
                continue

            # =========================
            # 5. 姿态识别
            # =========================

            annotated_frame, features = detector.process(frame)

            result = judge.judge(features)

            posture = result["posture"]
            reminder_count = result["alert_count"]
            alert = result["alert"]

            last_reminder_count = reminder_count

            if posture not in ["KEYPOINTS NOT CLEAR", "unknown"]:
                last_posture = posture

            # =========================
            # 6. 异常姿势持续时间
            # =========================

            try:
                alert_elapsed = max(
                    0.0,
                    float(result.get("elapsed", 0) or 0)
                )
            except (TypeError, ValueError):
                alert_elapsed = 0.0

            alert_remaining = max(
                0.0,
                ALERT_DURATION - alert_elapsed
            )

            # =========================
            # 7. 接收网页姿态控制指令
            # =========================

            posture_command = system_state.get_posture_command()

            if posture_command == "calibrate":

                success = judge.calibrate()

                if success:
                    print("网页指令：正常坐姿校准成功")
                else:
                    print(
                        "网页指令：有效姿态样本不足，"
                        "请继续保持正常坐姿"
                    )

            elif posture_command == "reset_calibration":

                judge.reset_calibration()
                buzzer.stop()

                print("网页指令：姿态校准已重置，等待重新校准")

            # =========================
            # 8. 接收网页计时指令
            # =========================

            command = system_state.get_timer_command()

            if command == "start":

                if session_start is None:
                    session_start = datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )

                timer.start()

                print("网页指令：学习计时开始 / 继续")

            elif command == "pause":

                timer.pause()

                print("网页指令：学习计时暂停")

            elif command == "reset":

                timer.reset()
                session_start = None

                rest_alert_until = 0
                previous_timer_status = "idle"

                buzzer.stop()

                print("网页指令：学习计时重置")

            # =========================
            # 9. 更新学习计时器
            # =========================

            timer_state = timer.update()

            study_status = timer_state["study_status"]
            study_minutes = timer_state["study_minutes"]
            remaining = timer_state["remaining_seconds"]

            total_study_seconds = timer_state.get(
                "total_study_seconds", 0
            )

            if (
                study_status == "resting"
                and previous_timer_status != "resting"
            ):
                print("学习时间结束，请休息！")
                rest_alert_until = time.monotonic() + 3

            previous_timer_status = study_status

            # =========================
            # 10. 蜂鸣器控制
            # =========================

            web_state = system_state.get_state()

            buzzer.set_enabled(web_state["buzzer_enabled"])

            if alert or time.monotonic() < rest_alert_until:
                buzzer.start()
            else:
                buzzer.stop()

            # =========================
            # 11. 更新共享状态
            # =========================

            system_state.update(
                camera_online=True,
                person_detected=(features is not None),
                posture=posture,

                study_minutes=study_minutes,
                total_study_seconds=total_study_seconds,
                remaining_seconds=remaining,
                study_status=study_status,

                reminder_count=reminder_count,
                alert=bool(alert),
                alert_elapsed=round(alert_elapsed, 1),
                alert_remaining=round(alert_remaining, 1)
            )

            # =========================
            # 12. OLED 模拟显示
            # =========================

            oled.show_status(
                posture=posture,
                study_minutes=study_minutes,
                reminder_count=reminder_count,
                study_status=study_status.upper()
            )

            # =========================
            # 13. 摄像头画面显示
            # =========================

            cv2.putText(
                annotated_frame,
                f"Posture: {posture}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7, (0, 255, 0), 2
            )

            cv2.putText(
                annotated_frame,
                f"Study: {study_minutes} min",
                (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7, (255, 255, 0), 2
            )

            cv2.putText(
                annotated_frame,
                f"Status: {study_status}",
                (10, 90),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7, (0, 200, 255), 2
            )

            cv2.putText(
                annotated_frame,
                f"Remaining: {remaining // 60:02d}:{remaining % 60:02d}",
                (10, 120),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7, (255, 255, 255), 2
            )

            cv2.putText(
                annotated_frame,
                f"Reminders: {reminder_count}",
                (10, 150),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7, (0, 0, 255), 2
            )

            video_stream.set_frame(annotated_frame)

            cv2.imshow("Smart Desk Lamp", annotated_frame)

            # =========================
            # 14. 键盘控制（保留原功能）
            # =========================

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

            elif key == ord("c"):

                success = judge.calibrate()

                if success:
                    print("键盘 C：正常坐姿校准成功")
                else:
                    print(
                        "键盘 C：有效姿态样本不足，"
                        "请继续保持正常坐姿"
                    )

            elif key == ord("r"):

                judge.reset_calibration()
                buzzer.stop()

                print("键盘 R：坐姿校准已重置，等待重新校准")

            elif key == ord("s"):

                if session_start is None:
                    session_start = datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )

                timer.start()
                print("学习计时已开始 / 继续")

            elif key == ord("p"):

                timer.pause()
                print("学习计时已暂停")

            elif key == ord("t"):

                timer.reset()
                session_start = None

                rest_alert_until = 0
                previous_timer_status = "idle"

                buzzer.stop()

                print("学习计时已重置")

    finally:

        # =========================
        # 15. 保存学习记录
        # =========================

        try:
            timer_state = timer.get_state()

            if (
                session_start is not None
                and timer_state["total_study_seconds"] > 0
            ):
                end_time = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

                db.add_record(
                    start_time=session_start,
                    end_time=end_time,
                    study_minutes=timer_state["study_minutes"],
                    reminder_count=last_reminder_count,
                    posture_status=last_posture
                )

                print("本次学习记录已保存！")

        except Exception as e:
            print("保存学习记录失败：", e)

        # =========================
        # 16. 释放资源
        # =========================

        system_state.update(camera_online=False)
        video_stream.clear()

        buzzer.close()
        oled.close()
        camera.release()
        detector.release()

        cv2.destroyAllWindows()

        print("智能学习台灯程序已退出")


if __name__ == "__main__":
    main()
