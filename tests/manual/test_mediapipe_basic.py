import mediapipe as mp
import numpy as np
import time

print("步骤1：导入成功", flush=True)

print("步骤2：初始化姿态模型", flush=True)

pose = mp.solutions.pose.Pose(
    static_image_mode=True,
    model_complexity=0,
    min_detection_confidence=0.5
)

print("步骤3：模型初始化成功", flush=True)

# 生成一张 640×480 的空白 RGB 图片
image = np.zeros((480, 640, 3), dtype=np.uint8)

print("步骤4：准备空白图片成功", flush=True)

start = time.time()

print("步骤5：开始执行 MediaPipe 推理", flush=True)

result = pose.process(image)

print("步骤6：推理完成", flush=True)
print("耗时：", round(time.time() - start, 3), "秒")

print("是否检测到人体：", result.pose_landmarks is not None)

pose.close()

print("步骤7：测试结束", flush=True)