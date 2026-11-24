"""Collect labelled posture features without saving images or driving devices.

Run from the project root with the camera service stopped. Sit normally during
calibration, then perform the requested action when SAMPLE_START is printed.
"""

import argparse
import csv
import json
import time
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path

from edge.posture_judge import PostureJudge
from perception.camera import Camera
from perception.posture import UpperBodyPose


FIELDS = [
    "run_id", "smoothing", "min_cutoff", "beta", "d_cutoff",
    "baseline_time_s", "baseline_head_drop", "baseline_shoulder_tilt", "baseline_body_lean",
    "timestamp", "elapsed_s", "label", "valid", "posture",
    "sample_time_s", "head_drop", "shoulder_tilt", "body_lean", "hips_visible",
    "filtered_head_drop", "filtered_shoulder_tilt", "head_change", "tilt_change",
    "alert_elapsed_s", "alert", "alert_count",
]


def positive_seconds(value):
    seconds = float(value)
    if not 0 < seconds < float("inf"):
        raise argparse.ArgumentTypeError("must be a finite positive number")
    return seconds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True, choices=[
        "NORMAL", "HEAD DOWN", "TILT LEFT", "TILT RIGHT", "NO PERSON",
    ])
    parser.add_argument("--seconds", type=positive_seconds, default=20.0)
    parser.add_argument("--calibration-seconds", type=positive_seconds, default=5.0)
    parser.add_argument("--smoothing", choices=["one_euro", "moving_average"], default="one_euro")
    parser.add_argument("--min-cutoff", type=float, default=1.0)
    parser.add_argument("--beta", type=float, default=0.5)
    parser.add_argument("--d-cutoff", type=float, default=1.0)
    parser.add_argument("--output", type=Path,
                        default=Path("docs/test-results/posture_filter_samples.csv"))
    args = parser.parse_args()

    # Refuse incompatible files rather than mixing different CSV schemas.
    if args.output.exists() and args.output.stat().st_size:
        with args.output.open(encoding="utf-8", newline="") as stream:
            if next(csv.reader(stream)) != FIELDS:
                parser.error("output CSV has a different header; choose another file")

    camera = Camera(camera_id=0)
    detector = None
    judge = PostureJudge(smoothing=args.smoothing, min_cutoff=args.min_cutoff,
                         beta=args.beta, d_cutoff=args.d_cutoff)
    run_id = uuid.uuid4().hex
    counts = Counter()
    try:
        detector = UpperBodyPose()
        camera.start()
        print("CALIBRATION: sit normally with nose and both shoulders visible.", flush=True)
        deadline = time.monotonic() + args.calibration_seconds
        latest_features = None
        while time.monotonic() < deadline:
            ok, frame = camera.read()
            if not ok or frame is None:
                raise RuntimeError("Camera read failed during calibration")
            _, latest_features = detector.process(frame)
            judge.judge(latest_features)

        if latest_features is None or not judge.calibrate():
            raise RuntimeError("Calibration failed: keep head and both shoulders visible; retry")
        print("BASELINE " + json.dumps(judge.baseline), flush=True)
        print("SAMPLE_START: perform " + args.label, flush=True)

        args.output.parent.mkdir(parents=True, exist_ok=True)
        needs_header = not args.output.exists() or args.output.stat().st_size == 0
        started = time.monotonic()
        last_print = -1.0
        with args.output.open("a", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            if needs_header:
                writer.writeheader()
            while time.monotonic() - started < args.seconds:
                ok, frame = camera.read()
                if not ok or frame is None:
                    raise RuntimeError("Camera read failed during sampling")
                _, features = detector.process(frame)
                result = judge.judge(features)
                elapsed = time.monotonic() - started
                row = {
                    "run_id": run_id, "smoothing": args.smoothing,
                    "min_cutoff": args.min_cutoff, "beta": args.beta, "d_cutoff": args.d_cutoff,
                    "baseline_time_s": judge.baseline_timestamp,
                    "baseline_head_drop": judge.baseline["head_drop"],
                    "baseline_shoulder_tilt": judge.baseline["shoulder_tilt"],
                    "baseline_body_lean": judge.baseline["body_lean"],
                    "timestamp": datetime.now().isoformat(timespec="milliseconds"),
                    "elapsed_s": round(elapsed, 3),
                    "label": args.label,
                    "valid": int(features is not None),
                    "posture": result["posture"],
                    "head_drop": features["head_drop"] if features else "",
                    "shoulder_tilt": features["shoulder_tilt"] if features else "",
                    "sample_time_s": judge.last_timestamp if features else time.monotonic(),
                    "body_lean": features["body_lean"] if features else "",
                    "hips_visible": int(features["hips_visible"]) if features else 0,
                    "filtered_head_drop": result.get("filtered_features", {}).get("head_drop", ""),
                    "filtered_shoulder_tilt": result.get("filtered_features", {}).get("shoulder_tilt", ""),
                    "head_change": result["head_change"] if features else "",
                    "tilt_change": result["tilt_change"] if features else "",
                    "alert_elapsed_s": round(result["elapsed"], 3),
                    "alert": int(result["alert"]),
                    "alert_count": result["alert_count"],
                }
                writer.writerow(row)
                counts[result["posture"]] += 1
                if elapsed - last_print >= 1:
                    print(json.dumps(row), flush=True)
                    stream.flush()
                    last_print = elapsed
        print("SUMMARY " + json.dumps({
            "label": args.label, "samples": sum(counts.values()),
            "posture_counts": dict(counts), "baseline": judge.baseline,
            "alert_count": judge.alert_count, "output": str(args.output),
        }), flush=True)
    finally:
        camera.release()
        if detector is not None:
            detector.release()


if __name__ == "__main__":
    main()
