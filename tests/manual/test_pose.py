import cv2
import mediapipe as mp
import traceback

print("1. 打开摄像头", flush=True)

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("摄像头打开失败")
    exit()

print("2. 摄像头打开成功", flush=True)

print("3. 初始化 MediaPipe", flush=True)

pose = mp.solutions.pose.Pose(
    static_image_mode=True,
    model_complexity=0,
    min_detection_confidence=0.5
)

print("4. MediaPipe 初始化成功", flush=True)

try:
    ret, frame = cap.read()

    if not ret:
        print("读取画面失败")
        exit()

    print("5. 原始画面尺寸：", frame.shape, flush=True)

    # 降低分辨率，减轻处理负担
    frame = cv2.resize(frame, (640, 480))

    print("6. 图片缩放成功", flush=True)

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    print("7. 开始姿态识别", flush=True)

    results = pose.process(rgb)

    print("8. 姿态识别完成", flush=True)

    if results.pose_landmarks:
        print("检测到了人体！", flush=True)

        mp.solutions.drawing_utils.draw_landmarks(
            frame,
            results.pose_landmarks,
            mp.solutions.pose.POSE_CONNECTIONS
        )
    else:
        print("没有检测到人体", flush=True)

    cv2.imshow("MediaPipe Test", frame)
    cv2.waitKey(0)

except Exception:
    traceback.print_exc()

finally:
    cap.release()
    pose.close()
    cv2.destroyAllWindows()

print("9. 测试结束", flush=True)