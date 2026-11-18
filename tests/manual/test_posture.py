
import cv2
import mediapipe as mp
import numpy as np
import time
from collections import deque

# ==========================================
# 1. 初始化
# ==========================================

MODEL_PATH = "pose_landmarker_lite.task"

# 连续异常多少秒后触发提醒
ALERT_DURATION = 5.0

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

if not cap.isOpened():
    print("Camera open failed!")
    raise SystemExit

BaseOptions = mp.tasks.BaseOptions
PoseLandmarker = mp.tasks.vision.PoseLandmarker
Options = mp.tasks.vision.PoseLandmarkerOptions
RunningMode = mp.tasks.vision.RunningMode

options = Options(
    base_options=BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=RunningMode.IMAGE,
    num_poses=1
)

# 最近5帧：实时特征平滑
history = deque(maxlen=5)

# 最近30帧：正常坐姿校准
calibration_history = deque(maxlen=30)

# 正常坐姿基准
baseline = None

# 异常计时状态
abnormal_start_time = None
abnormal_posture = None
alert_triggered = False

# 累计提醒次数
alert_count = 0

# 当前提醒状态
alert_message = "NO ALERT"


# ==========================================
# 2. 提取人体姿态特征
# ==========================================

def get_features(landmarks):

    nose = landmarks[0]
    left_shoulder = landmarks[11]
    right_shoulder = landmarks[12]

    left_hip = landmarks[23]
    right_hip = landmarks[24]

    required = [
        nose,
        left_shoulder,
        right_shoulder
    ]

    if any(
        getattr(p, "visibility", 0) < 0.5
        for p in required
    ):
        return None

    # 肩膀中心坐标
    shoulder_x = (
        left_shoulder.x + right_shoulder.x
    ) / 2

    shoulder_y = (
        left_shoulder.y + right_shoulder.y
    ) / 2

    # 肩膀宽度
    shoulder_width = np.sqrt(
        (left_shoulder.x - right_shoulder.x) ** 2
        + (left_shoulder.y - right_shoulder.y) ** 2
    )

    if shoulder_width < 0.01:
        return None

    # 鼻子相对肩膀的位置
    head_drop = (
        nose.y - shoulder_y
    ) / shoulder_width

    # 左右肩膀高度差
    shoulder_tilt = (
        left_shoulder.y - right_shoulder.y
    ) / shoulder_width

    # 判断髋部是否可见
    hips_visible = (
        getattr(left_hip, "visibility", 0) > 0.5
        and getattr(right_hip, "visibility", 0) > 0.5
    )

    if hips_visible:

        hip_x = (
            left_hip.x + right_hip.x
        ) / 2

        body_lean = (
            shoulder_x - hip_x
        ) / shoulder_width

    else:

        body_lean = None

    return {
        "head_drop": float(head_drop),
        "shoulder_tilt": float(shoulder_tilt),
        "body_lean": body_lean,
        "hips_visible": hips_visible
    }


# ==========================================
# 3. 特征平滑
# ==========================================

def average_features(samples):

    result = {}

    for key in [
        "head_drop",
        "shoulder_tilt",
        "body_lean"
    ]:

        values = [
            item[key]
            for item in samples
            if item[key] is not None
        ]

        result[key] = (
            float(np.mean(values))
            if values else None
        )

    return result


# ==========================================
# 4. 坐姿判断
# ==========================================

def judge_posture(features, baseline):

    head_change = (
        features["head_drop"]
        - baseline["head_drop"]
    )

    tilt_change = (
        features["shoulder_tilt"]
        - baseline["shoulder_tilt"]
    )

    # 低头
    if head_change > 0.15:
        return "HEAD DOWN", head_change, tilt_change

    # 向左倾斜
    if tilt_change > 0.15:
        return "TILT LEFT", head_change, tilt_change

    # 向右倾斜
    if tilt_change < -0.15:
        return "TILT RIGHT", head_change, tilt_change

    # 身体前倾：需要髋部可见
    if (
        features["body_lean"] is not None
        and baseline["body_lean"] is not None
    ):

        lean_change = abs(
            features["body_lean"]
            - baseline["body_lean"]
        )

        if lean_change > 0.25:
            return "LEAN FORWARD", head_change, tilt_change

    return "NORMAL", head_change, tilt_change


# ==========================================
# 5. 异常姿势持续时间判断
# ==========================================

def update_alert(posture):

    global abnormal_start_time
    global abnormal_posture
    global alert_triggered
    global alert_count
    global alert_message

    abnormal_postures = [
        "HEAD DOWN",
        "TILT LEFT",
        "TILT RIGHT",
        "LEAN FORWARD"
    ]

    # 正常坐姿或无法有效检测
    if posture not in abnormal_postures:

        abnormal_start_time = None
        abnormal_posture = None
        alert_triggered = False

        alert_message = "NO ALERT"

        return 0.0

    # 第一次出现异常，或者异常类型发生变化
    if abnormal_posture != posture:

        abnormal_posture = posture
        abnormal_start_time = time.monotonic()
        alert_triggered = False

    # 计算异常持续时间
    elapsed = time.monotonic() - abnormal_start_time

    # 连续异常达到5秒
    if elapsed >= ALERT_DURATION and not alert_triggered:

        alert_triggered = True
        alert_count += 1

        alert_message = "ALERT TRIGGERED"

        print(
            f"WARNING! {posture} "
            f"has lasted {elapsed:.1f} seconds!"
        )

    elif alert_triggered:

        alert_message = "ALERT TRIGGERED"

    else:

        remaining = max(
            0,
            ALERT_DURATION - elapsed
        )

        alert_message = f"ALERT IN {remaining:.1f}s"

    return elapsed


# ==========================================
# 6. 绘制人体关键点
# ==========================================

connections = [
    (11, 12),
    (11, 13), (13, 15),
    (12, 14), (14, 16),
    (11, 23), (12, 24),
    (23, 24)
]


# ==========================================
# 7. 程序启动
# ==========================================

print("=" * 45)
print("Smart Desk Posture Detection Started")
print("=" * 45)

print("Please sit normally and press C to calibrate.")
print("Press R to recalibrate.")
print("Press Q to quit.")
print(f"Alert duration: {ALERT_DURATION} seconds.")


# ==========================================
# 8. 主程序循环
# ==========================================

try:

    with PoseLandmarker.create_from_options(options) as landmarker:

        while True:

            ret, frame = cap.read()

            if not ret:
                print("Camera read failed!")
                break

            frame = cv2.resize(frame, (640, 480))

            rgb = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB
            )

            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=rgb
            )

            result = landmarker.detect(mp_image)

            posture = "NO PERSON"

            head_change = 0.0
            tilt_change = 0.0

            features = None

            # ==================================
            # 人体检测
            # ==================================

            if result.pose_landmarks:

                landmarks = result.pose_landmarks[0]

                features = get_features(landmarks)

                if features is not None:

                    history.append(features)

                    calibration_history.append(features)

                    current = average_features(history)

                    if baseline is None:

                        posture = "WAIT CALIBRATION"

                    else:

                        posture, head_change, tilt_change = (
                            judge_posture(
                                current,
                                baseline
                            )
                        )

                else:

                    posture = "KEYPOINTS NOT CLEAR"

                # 绘制人体连接线
                for start, end in connections:

                    p1 = landmarks[start]
                    p2 = landmarks[end]

                    x1 = int(p1.x * 640)
                    y1 = int(p1.y * 480)

                    x2 = int(p2.x * 640)
                    y2 = int(p2.y * 480)

                    cv2.line(
                        frame,
                        (x1, y1),
                        (x2, y2),
                        (0, 255, 0),
                        2
                    )

                # 绘制关键点
                for index in [
                    0, 11, 12, 13, 14, 15, 16, 23, 24
                ]:

                    p = landmarks[index]

                    if getattr(p, "visibility", 0) > 0.5:

                        x = int(p.x * 640)
                        y = int(p.y * 480)

                        cv2.circle(
                            frame,
                            (x, y),
                            5,
                            (0, 0, 255),
                            -1
                        )

            # ==================================
            # 异常计时
            # ==================================

            elapsed = update_alert(posture)

            # ==================================
            # 显示检测结果
            # ==================================

            cv2.putText(
                frame,
                "Posture: " + posture,
                (15, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

            calibration_text = (
                "CALIBRATED: YES"
                if baseline is not None
                else "CALIBRATED: NO - Press C"
            )

            cv2.putText(
                frame,
                calibration_text,
                (15, 70),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 0),
                1
            )

            cv2.putText(
                frame,
                f"Head change: {head_change:.3f}",
                (15, 105),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )

            cv2.putText(
                frame,
                f"Shoulder tilt: {tilt_change:.3f}",
                (15, 135),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )

            # 显示髋部状态
            if features is not None and not features["hips_visible"]:

                cv2.putText(
                    frame,
                    "HIPS NOT VISIBLE",
                    (15, 165),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 165, 255),
                    1
                )

            # 显示提醒倒计时
            cv2.putText(
                frame,
                alert_message,
                (15, 195),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 255) if alert_triggered else (255, 255, 0),
                2
            )

            # 显示累计提醒次数
            cv2.putText(
                frame,
                f"Reminder count: {alert_count}",
                (15, 225),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )

            # 显示提醒持续时间
            if abnormal_start_time is not None:

                cv2.putText(
                    frame,
                    f"Abnormal time: {elapsed:.1f}s",
                    (15, 255),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 0, 255),
                    1
                )

            # ==================================
            # 显示画面
            # ==================================

            cv2.imshow(
                "Smart Desk - Posture Detection",
                frame
            )

            # ==================================
            # 键盘操作
            # ==================================

            key = cv2.waitKey(10) & 0xFF

            # C：正常坐姿校准
            if key == ord("c") or key == ord("C"):

                if len(calibration_history) >= 10:

                    baseline = average_features(
                        list(calibration_history)
                    )

                    abnormal_start_time = None
                    abnormal_posture = None
                    alert_triggered = False

                    print("\nCalibration completed!")
                    print("Baseline:", baseline)

                else:

                    print(
                        "Not enough valid frames. "
                        "Please wait."
                    )

            # R：重新校准
            elif key == ord("r") or key == ord("R"):

                baseline = None

                history.clear()
                calibration_history.clear()

                abnormal_start_time = None
                abnormal_posture = None
                alert_triggered = False

                alert_message = "NO ALERT"

                print("Calibration reset.")

            # Q：退出
            elif key == ord("q") or key == ord("Q"):

                break

finally:

    cap.release()
    cv2.destroyAllWindows()

print("Posture detection stopped.")
