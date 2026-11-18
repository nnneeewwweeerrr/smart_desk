import cv2
import mediapipe as mp
import numpy as np

print("正在初始化摄像头和姿态识别模型……", flush=True)

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("摄像头打开失败！")
    raise SystemExit

BaseOptions = mp.tasks.BaseOptions
PoseLandmarker = mp.tasks.vision.PoseLandmarker
Options = mp.tasks.vision.PoseLandmarkerOptions
RunningMode = mp.tasks.vision.RunningMode

options = Options(
    base_options=BaseOptions(
        model_asset_path="pose_landmarker_lite.task"
    ),
    running_mode=RunningMode.IMAGE,
    num_poses=1
)

# 上半身关键点连接
connections = [
    (11, 12),
    (11, 13), (13, 15),
    (12, 14), (14, 16),
    (11, 23), (12, 24),
    (23, 24),
]

print("模型初始化成功！", flush=True)
print("摄像头启动成功！", flush=True)

try:
    with PoseLandmarker.create_from_options(options) as landmarker:

        while True:
            ret, frame = cap.read()

            if not ret:
                print("摄像头读取失败")
                break

            frame = cv2.resize(frame, (640, 480))

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=rgb
            )

            result = landmarker.detect(mp_image)

            if result.pose_landmarks:
                landmarks = result.pose_landmarks[0]

                # 绘制上半身骨架
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

                # 绘制鼻子、肩膀、手肘、手腕和髋部
                for index in [0, 11, 12, 13, 14, 15, 16, 23, 24]:
                    point = landmarks[index]

                    x = int(point.x * 640)
                    y = int(point.y * 480)

                    cv2.circle(
                        frame,
                        (x, y),
                        5,
                        (0, 0, 255),
                        -1
                    )

                cv2.putText(
                    frame,
                    "Person Detected",
                    (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2
                )

            else:
                cv2.putText(
                    frame,
                    "No Person",
                    (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    2
                )

            cv2.imshow("Smart Desk - Pose Detection", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

finally:
    cap.release()
    cv2.destroyAllWindows()

print("测试结束")