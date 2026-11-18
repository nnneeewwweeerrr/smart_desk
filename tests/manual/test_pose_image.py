import cv2
import mediapipe as mp
import time

print("1. 正在打开摄像头", flush=True)

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("摄像头打开失败")
    exit()

ret, frame = cap.read()

# 先释放摄像头
cap.release()

if not ret:
    print("照片读取失败")
    exit()

print("2. 已经拍摄照片，摄像头已关闭", flush=True)

frame = cv2.resize(frame, (640, 480))
cv2.imwrite("test_frame.jpg", frame)

print("3. 正在初始化 MediaPipe", flush=True)

pose = mp.solutions.pose.Pose(
    static_image_mode=True,
    model_complexity=0,
    min_detection_confidence=0.5
)

print("4. MediaPipe 初始化成功", flush=True)

rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

print("5. 开始识别静态照片", flush=True)

start = time.time()
results = pose.process(rgb)

print("6. 识别完成，耗时：", time.time() - start, "秒", flush=True)

if results.pose_landmarks:
    print("成功检测到人体！", flush=True)
else:
    print("没有检测到人体", flush=True)

pose.close()

print("7. 测试结束", flush=True)