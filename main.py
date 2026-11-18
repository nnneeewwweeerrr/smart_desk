
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


# 异常坐姿提醒持续时间
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
    try:
        app.run(
            host="0.0.0.0",
            port=5000,
            debug=False,
            threaded=True,
            use_reloader=False
        )
    except Exception as e:
        print("网页服务启动失败：", e)


def main():

    # =====================================================
    # 1. 初始化模块
    # =====================================================

    camera = None
    detector = None
    judge = None
    timer = None
    buzzer = None
    oled = None
    db = None
    web_thread = None

    session_start = None
    last_reminder_count = 0
    last_posture = "unknown"

    rest_alert_until = 0
    previous_timer_status = "idle"

    try:
        camera = Camera(camera_id=0)
        detector = UpperBodyPose()
        judge = PostureJudge()

        timer = StudyTimer(
            study_duration=25 * 60,
            rest_duration=5 * 60
        )

        # 电脑端测试阶段使用模拟模式
        buzzer = Buzzer(mock=True)
        oled = OLEDDisplay(mock=True)

        db = Database()

        print("所有模块初始化完成！")

        # =====================================================
        # 2. 保存当前学习记录
        # =====================================================

        def save_current_session():
            nonlocal session_start

            if session_start is None:
                return True

            try:
                timer_state = timer.get_state()

                total_seconds = timer_state.get(
                    "total_study_seconds", 0
                )

                if total_seconds <= 0:
                    session_start = None
                    return True

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

                session_start = None
                return True

            except Exception as e:
                print("保存学习记录失败：", e)
                return False

        # =====================================================
        # 3. 启动网页服务
        # =====================================================

        web_thread = threading.Thread(
            target=start_web_server,
            daemon=True
        )

        web_thread.start()

        print("网页服务启动线程已运行")
        print("浏览器访问：http://127.0.0.1:5000")

        # =====================================================
        # 4. 启动摄像头
        # =====================================================

        camera.start()

        print("\n========== 智能学习台灯 ==========")
        print("C：坐姿校准")
        print("R：重新校准坐姿")
        print("S：开始 / 继续学习")
        print("P：暂停计时")
        print("T：保存记录并重置计时")
        print("Q：退出程序")
        print("网页也可以控制学习计时和姿态校准")
        print("================================\n")

        # =====================================================
        # 5. 主循环
        # =====================================================

        while True:

            frame = read_camera_frame(camera)

            if frame is None:
                system_state.update(camera_online=False)

                # 避免摄像头读取失败时 CPU 空转
                time.sleep(0.05)
                continue

            # =================================================
            # 6. 姿态识别
            # =================================================

            annotated_frame, features = detector.process(frame)

            result = judge.judge(features)

            posture = result["posture"]
            reminder_count = result["alert_count"]
            alert = result["alert"]

            last_reminder_count = reminder_count

            if posture not in [
                "KEYPOINTS NOT CLEAR",
                "unknown"
            ]:
                last_posture = posture

            # =================================================
            # 7. 异常姿势持续时间
            # =================================================

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

            # =================================================
            # 8. 网页姿态控制
            # =================================================

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

                print(
                    "网页指令：姿态校准已重置，"
                    "等待重新校准"
                )

            # =================================================
            # 9. 网页计时控制
            # =================================================

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

                # 重置前先保存当前学习记录
                saved = save_current_session()

                if saved:
                    timer.reset()
                    rest_alert_until = 0
                    previous_timer_status = "idle"
                    buzzer.stop()

                    print("网页指令：学习计时已重置")
                else:
                    print(
                        "网页指令：记录保存失败，"
                        "本次暂不重置计时"
                    )

            # =================================================
            # 10. 更新计时器
            # =================================================

            timer_state = timer.update()

            study_status = timer_state["study_status"]
            study_minutes = timer_state["study_minutes"]
            remaining = timer_state["remaining_seconds"]

            total_study_seconds = timer_state.get(
                "total_study_seconds", 0
            )

            # 学习阶段结束，进入休息阶段
            if (
                study_status == "resting"
                and previous_timer_status != "resting"
            ):
                print("学习时间结束，请休息！")

                rest_alert_until = time.monotonic() + 3

            previous_timer_status = study_status

            # =================================================
            # 11. 蜂鸣器控制
            # =================================================

            web_state = system_state.get_state()

            buzzer.set_enabled(
                web_state["buzzer_enabled"]
            )

            if (
                alert
                or time.monotonic() < rest_alert_until
            ):
                buzzer.start()
            else:
                buzzer.stop()

            # =================================================
            # 12. 更新系统状态
            # =================================================

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

            # =================================================
            # 13. OLED 显示
            # =================================================

            oled.show_status(
                posture=posture,
                study_minutes=study_minutes,
                reminder_count=reminder_count,
                study_status=study_status.upper()
            )

            # =================================================
            # 14. 摄像头画面显示
            # =================================================

            cv2.putText(
                annotated_frame,
                f"Posture: {posture}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

            cv2.putText(
                annotated_frame,
                f"Study: {study_minutes} min",
                (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 0),
                2
            )

            cv2.putText(
                annotated_frame,
                f"Status: {study_status}",
                (10, 90),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 200, 255),
                2
            )

            cv2.putText(
                annotated_frame,
                f"Remaining: {remaining // 60:02d}:"
                f"{remaining % 60:02d}",
                (10, 120),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2
            )

            cv2.putText(
                annotated_frame,
                f"Reminders: {reminder_count}",
                (10, 150),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2
            )

            video_stream.set_frame(annotated_frame)

            cv2.imshow(
                "Smart Desk Lamp",
                annotated_frame
            )

            # =================================================
            # 15. 键盘控制
            # =================================================

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

                print(
                    "键盘 R：坐姿校准已重置，"
                    "等待重新校准"
                )

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

                # 重置前先保存当前学习记录
                saved = save_current_session()

                if saved:
                    timer.reset()
                    rest_alert_until = 0
                    previous_timer_status = "idle"
                    buzzer.stop()

                    print("学习计时已重置")
                else:
                    print(
                        "记录保存失败，"
                        "本次暂不重置计时"
                    )

    except KeyboardInterrupt:

        print("\n收到退出指令，正在关闭程序……")

    finally:

        print("\n正在释放系统资源……")

        # =====================================================
        # 16. 保存最后一次学习记录
        # =====================================================

        if timer is not None and db is not None:
            try:
                save_current_session()
            except Exception as e:
                print("退出时保存记录失败：", e)

        # =====================================================
        # 17. 关闭设备和资源
        # =====================================================

        try:
            system_state.update(camera_online=False)
        except Exception as e:
            print("更新设备状态失败：", e)

        try:
            video_stream.clear()
        except Exception as e:
            print("清理视频流失败：", e)

        if buzzer is not None:
            try:
                buzzer.close()
            except Exception as e:
                print("关闭蜂鸣器失败：", e)

        if oled is not None:
            try:
                oled.close()
            except Exception as e:
                print("关闭 OLED 失败：", e)

        if camera is not None:
            try:
                camera.release()
            except Exception as e:
                print("释放摄像头失败：", e)

        if detector is not None:
            try:
                detector.release()
            except Exception as e:
                print("释放姿态识别模块失败：", e)

        try:
            cv2.destroyAllWindows()
        except Exception as e:
            print("关闭图像窗口失败：", e)

        print("智能学习台灯程序已退出")


if __name__ == "__main__":
    main()
