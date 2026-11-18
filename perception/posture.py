
import os
import cv2
import mediapipe as mp
import numpy as np


class UpperBodyPose:
    """基于 MediaPipe Tasks 的上半身识别模块"""

    KEYPOINTS = [0, 11, 12, 13, 14, 15, 16, 23, 24]

    CONNECTIONS = [
        (11, 12), (11, 13), (13, 15),
        (12, 14), (14, 16),
        (11, 23), (12, 24), (23, 24)
    ]

    def __init__(self):
        model_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "pose_landmarker_lite.task"
        )

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"找不到模型文件：{model_path}"
            )

        options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(
                model_asset_path=model_path
            ),
            running_mode=mp.tasks.vision.RunningMode.IMAGE,
            num_poses=1
        )

        self.landmarker = (
            mp.tasks.vision.PoseLandmarker
            .create_from_options(options)
        )

    def process(self, frame):
        """输入摄像头画面，返回标注画面和姿态特征"""

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb
        )

        result = self.landmarker.detect(mp_image)

        annotated = frame.copy()

        if not result.pose_landmarks:
            return annotated, None

        landmarks = result.pose_landmarks[0]
        height, width = frame.shape[:2]

        def visible(index):
            return getattr(
                landmarks[index], "visibility", 0
            ) > 0.5

        # 绘制骨架
        for start, end in self.CONNECTIONS:
            if visible(start) and visible(end):
                p1 = landmarks[start]
                p2 = landmarks[end]

                cv2.line(
                    annotated,
                    (int(p1.x * width), int(p1.y * height)),
                    (int(p2.x * width), int(p2.y * height)),
                    (0, 255, 0), 2
                )

        # 绘制关键点
        for index in self.KEYPOINTS:
            if visible(index):
                p = landmarks[index]
                cv2.circle(
                    annotated,
                    (int(p.x * width), int(p.y * height)),
                    5, (0, 0, 255), -1
                )

        # 关键点有效性检查
        if not all(visible(i) for i in [0, 11, 12]):
            return annotated, None

        nose = landmarks[0]
        left_shoulder = landmarks[11]
        right_shoulder = landmarks[12]

        shoulder_x = (
            left_shoulder.x + right_shoulder.x
        ) / 2

        shoulder_y = (
            left_shoulder.y + right_shoulder.y
        ) / 2

        shoulder_width = np.sqrt(
            (left_shoulder.x - right_shoulder.x) ** 2
            + (left_shoulder.y - right_shoulder.y) ** 2
        )

        if shoulder_width < 0.01:
            return annotated, None

        head_drop = (
            nose.y - shoulder_y
        ) / shoulder_width

        shoulder_tilt = (
            left_shoulder.y - right_shoulder.y
        ) / shoulder_width

        hips_visible = visible(23) and visible(24)

        body_lean = None

        if hips_visible:
            hip_x = (
                landmarks[23].x + landmarks[24].x
            ) / 2

            body_lean = (
                shoulder_x - hip_x
            ) / shoulder_width

        features = {
            "head_drop": float(head_drop),
            "shoulder_tilt": float(shoulder_tilt),
            "body_lean": (
                float(body_lean)
                if body_lean is not None else None
            ),
            "hips_visible": hips_visible
        }

        return annotated, features

    def release(self):
        self.landmarker.close()
