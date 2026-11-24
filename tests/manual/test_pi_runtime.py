"""Bounded camera/model smoke check. Run from the repository root on the Pi."""

import argparse
import json
import platform
import time
from importlib.metadata import version

import cv2
import numpy as np

from perception.camera import Camera
from perception.posture import UpperBodyPose


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=30)
    args = parser.parse_args()
    if args.frames < 1:
        parser.error("--frames must be positive")

    detector = None
    camera = Camera(camera_id=0)
    started = time.monotonic()
    try:
        detector = UpperBodyPose()
        initialized = time.monotonic()

        # A no-person input must still pass through the actual native model.
        _, blank_features = detector.process(np.zeros((480, 640, 3), np.uint8))
        if blank_features is not None:
            raise RuntimeError("Unexpected pose features from an empty image")

        camera.start()
        capture_started = time.monotonic()
        detected = 0
        inference_seconds = 0.0
        for _ in range(args.frames):
            ok, frame = camera.read()
            if not ok or frame is None:
                raise RuntimeError("Camera frame read failed")
            before = time.monotonic()
            annotated, features = detector.process(frame)
            inference_seconds += time.monotonic() - before
            if annotated.shape != frame.shape:
                raise RuntimeError("Annotated frame shape changed")
            detected += features is not None

        duration = time.monotonic() - capture_started
        print(json.dumps({
            "python": platform.python_version(),
            "architecture": platform.machine(),
            "mediapipe": version("mediapipe"),
            "opencv": cv2.__version__,
            "model_init_seconds": round(initialized - started, 3),
            "frames": args.frames,
            "frames_with_features": detected,
            "capture_and_inference_fps": round(args.frames / duration, 2),
            "mean_inference_ms": round(inference_seconds * 1000 / args.frames, 1),
        }, ensure_ascii=False), flush=True)
    finally:
        camera.release()
        if detector is not None:
            detector.release()


if __name__ == "__main__":
    main()
