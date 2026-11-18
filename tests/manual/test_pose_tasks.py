import mediapipe as mp
import numpy as np
import time
import os

print("步骤1：导入成功", flush=True)

model_path = "pose_landmarker_lite.task"

if not os.path.exists(model_path):
    print("模型文件不存在！")
    raise SystemExit

print("步骤2：开始初始化 Pose Landmarker", flush=True)

BaseOptions = mp.tasks.BaseOptions
PoseLandmarker = mp.tasks.vision.PoseLandmarker
PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode

options = PoseLandmarkerOptions(
    base_options=BaseOptions(
        model_asset_path=model_path
    ),
    running_mode=VisionRunningMode.IMAGE,
    num_poses=1
)

print("步骤3：创建模型", flush=True)

with PoseLandmarker.create_from_options(options) as landmarker:

    print("步骤4：模型初始化成功", flush=True)

    image = np.zeros((480, 640, 3), dtype=np.uint8)

    mp_image = mp.Image(
        image_format=mp.ImageFormat.SRGB,
        data=image
    )

    print("步骤5：开始执行姿态识别", flush=True)

    start = time.time()

    result = landmarker.detect(mp_image)

    print("步骤6：姿态识别完成", flush=True)

    print("检测到的人数：", len(result.pose_landmarks))
    print("耗时：", round(time.time() - start, 3), "秒")

print("步骤7：测试结束", flush=True)