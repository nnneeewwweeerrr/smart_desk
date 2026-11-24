"""Replay identical raw features through both smoothers; no camera or DB writes.

--demo uses generated signals, not human measurements. Recorded CSV labels are
operator intentions and do not establish per-frame ground truth or accuracy.
"""

import argparse
import csv
import json
import math
import random
from pathlib import Path

from edge.posture_judge import PostureJudge


def demo_rows():
    rng = random.Random(20261122)
    rows = []
    for index in range(1, 201):
        timestamp = index / 10
        truth = .4 if 5 <= timestamp < 13 else 0.0
        rows.append({
            "run_id": "synthetic-step", "sample_time_s": timestamp, "valid": 1,
            "label": "HEAD DOWN" if truth else "NORMAL",
            "head_drop": truth + rng.gauss(0, .025),
            "shoulder_tilt": rng.gauss(0, .015), "body_lean": "", "hips_visible": 0,
            "baseline_time_s": 0, "baseline_head_drop": 0,
            "baseline_shoulder_tilt": 0, "baseline_body_lean": "", "truth_head": truth,
        })
    return rows


def optional_number(value):
    return None if value in (None, "", "None") else float(value)


def replay(rows, min_cutoff=1.0, beta=.5, d_cutoff=1.0, synthetic=False):
    judges = {}
    last_times = {}
    output = []
    for row in rows:
        run_id, timestamp = row["run_id"], float(row["sample_time_s"])
        if not math.isfinite(timestamp) or timestamp <= last_times.get(run_id, -math.inf):
            raise ValueError("Each run requires finite, strictly increasing sample timestamps")
        last_times[run_id] = timestamp
        if run_id not in judges:
            baseline = {key: optional_number(row["baseline_" + key])
                        for key in ("head_drop", "shoulder_tilt", "body_lean")}
            judges[run_id] = {}
            for method in ("moving_average", "one_euro"):
                judge = PostureJudge(method, min_cutoff, beta, d_cutoff)
                judge.baseline = baseline.copy()
                judge.baseline_timestamp = float(row["baseline_time_s"])
                judge.last_timestamp = judge.baseline_timestamp
                judge.reset_smoothing(baseline, judge.baseline_timestamp)
                judges[run_id][method] = judge
        valid = str(row["valid"]) == "1"
        features = ({key: optional_number(row[key]) for key in
                     ("head_drop", "shoulder_tilt", "body_lean")} if valid else None)
        if features:
            features["hips_visible"] = str(row["hips_visible"]) == "1"
        record = {"run_id": run_id, "sample_time_s": timestamp,
                  "label": row["label"], "valid": int(valid),
                  "raw_head_drop": row["head_drop"], "raw_shoulder_tilt": row["shoulder_tilt"]}
        if synthetic:
            record["truth_head"] = row["truth_head"]
        for method, judge in judges[run_id].items():
            result = judge.judge(features, timestamp=timestamp)
            record[method + "_head"] = result.get("filtered_features", {}).get("head_drop", "")
            record[method + "_tilt"] = result.get("filtered_features", {}).get("shoulder_tilt", "")
            record[method + "_head_change"] = result["head_change"] if valid else ""
            record[method + "_tilt_change"] = result["tilt_change"] if valid else ""
            record[method + "_posture"] = result["posture"]
            record[method + "_alert"] = int(result["alert"])
            record[method + "_alert_elapsed"] = result["elapsed"]
        output.append(record)
    summary = {"source": "synthetic_demo" if synthetic else "recorded_raw_features",
               "samples": len(output), "runs": len(judges),
               "one_euro_parameters": dict(min_cutoff=min_cutoff, beta=beta, d_cutoff=d_cutoff),
               "note": "No claim of human accuracy; labels in recorded data are operator intentions."}
    if synthetic:
        # Fixed generated signal: stationary samples before the step, excluding startup.
        steady = [r for r in output if 1 <= r["sample_time_s"] < 5]
        summary["synthetic_metrics"] = {}
        for method in ("moving_average", "one_euro"):
            values = [float(r[method + "_head"]) for r in steady]
            onset = next((r["sample_time_s"] - 5 for r in output
                          if 5 <= r["sample_time_s"] < 13 and r[method + "_posture"] == "HEAD DOWN"), None)
            summary["synthetic_metrics"][method] = {
                "stationary_head_rms": math.sqrt(sum(v*v for v in values) / len(values)),
                "step_classification_delay_s": onset,
            }
    return output, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo", action="store_true")
    source.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, default=Path("docs/test-results/filter_comparison.csv"))
    parser.add_argument("--summary", type=Path, default=Path("docs/test-results/filter_comparison.json"))
    parser.add_argument("--min-cutoff", type=float, default=1.0)
    parser.add_argument("--beta", type=float, default=.5)
    parser.add_argument("--d-cutoff", type=float, default=1.0)
    args = parser.parse_args()
    if args.input and args.input.resolve() in (args.output.resolve(), args.summary.resolve()):
        parser.error("Output must not overwrite the input")
    if args.output.resolve() == args.summary.resolve():
        parser.error("CSV and JSON output paths must differ")
    if args.demo:
        rows = demo_rows()
    else:
        with args.input.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
    if not rows:
        parser.error("No rows to replay")
    records, summary = replay(rows, args.min_cutoff, args.beta, args.d_cutoff, args.demo)
    for path in (args.output, args.summary):
        path.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
