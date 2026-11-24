import importlib
import sqlite3
import tempfile
import threading
import time
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import numpy as np

from data.database import Database
from edge.posture_judge import PostureJudge
from edge.study_timer import StudyTimer
from services.camera_worker import CameraWorker
from services.runtime import DeskRuntime
from services.state_manager import StateManager


NORMAL = dict(head_drop=0.0, shoulder_tilt=0.0, body_lean=None, hips_visible=False)
DOWN = dict(NORMAL, head_drop=0.4)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.clock = patch("time.monotonic", return_value=0.0)
        self.now = self.clock.start()
        self.addCleanup(self.clock.stop)
        self.db = Database(Path(self.tmp.name) / "test.db")
        self.state = StateManager()
        self.runtime = DeskRuntime(PostureJudge(), StudyTimer(), self.db, self.state)

    def command(self, action):
        self.assertTrue(self.state.set_timer_command(action))
        return self.runtime.step(NORMAL, True)[0]

    def settle(self, sample):
        for _ in range(5):
            state, sound = self.runtime.step(sample, True)
        return state, sound

    def calibrate(self):
        for _ in range(10):
            self.runtime.step(NORMAL, True)
        self.state.set_posture_command("calibrate")
        state, _ = self.runtime.step(NORMAL, True)
        self.assertEqual(state["calibration_result"], "succeeded")

    def test_calibration_receipt_and_fresh_samples(self):
        self.state.set_posture_command("calibrate")
        self.assertEqual(self.state.get_state()["calibration_result"], "pending")
        state, _ = self.runtime.step(None, False)
        self.assertEqual(state["calibration_result"], "failed")
        self.assertFalse(state["calibrated"])
        self.calibrate()
        self.runtime.step(None, True)
        self.state.set_posture_command("calibrate")
        state, _ = self.runtime.step(NORMAL, True)
        self.assertEqual(state["calibration_result"], "failed")
        self.assertTrue(state["calibrated"])

    def test_camera_offline_still_pauses_saves_and_disables_sound(self):
        self.command("start")
        self.now.return_value = 30
        self.state.set_timer_command("pause")
        state, sound = self.runtime.step(None, False)
        self.assertEqual(state["study_status"], "paused")
        self.assertEqual(state["total_study_seconds"], 30)
        self.assertFalse(sound)
        self.state.set_timer_command("reset")
        state, _ = self.runtime.step(None, False)
        self.assertEqual(state["study_status"], "idle")
        self.assertEqual(self.db.get_records()[0][6], 30)

    def test_session_reminders_two_plus_one_not_cumulative(self):
        self.calibrate()
        self.command("start")
        for timestamp in (5, 10):
            self.settle(DOWN)
            self.now.return_value = timestamp
            self.runtime.step(DOWN, True)
            self.settle(NORMAL)
        self.assertEqual(self.state.get_state()["reminder_count"], 2)
        self.command("reset")
        self.assertEqual(self.state.get_state()["reminder_count"], 0)
        self.command("start")
        self.settle(DOWN)
        self.now.return_value = 15
        self.runtime.step(DOWN, True)
        self.assertEqual(self.state.get_state()["reminder_count"], 1)
        self.command("reset")
        self.assertEqual(self.db.get_summary()["total_reminders"], 3)
        self.assertEqual([r[4] for r in self.db.get_records()], [1, 2])

    def test_save_failure_preserves_session_until_retry(self):
        self.command("start")
        self.now.return_value = 30
        with patch.object(self.db, "add_record", side_effect=OSError("disk unavailable")):
            state = self.command("reset")
        self.assertIsNotNone(state["session_start"])
        self.assertEqual(state["total_study_seconds"], 30)
        self.assertIsNotNone(state["timer_error"])
        self.command("reset")
        self.assertEqual(self.db.get_summary()["total_sessions"], 1)
        self.assertEqual(self.db.get_summary()["total_study_seconds"], 30)

    def test_api_today_does_not_double_count_saved_session(self):
        with patch("data.database.DB_PATH", str(Path(self.tmp.name) / "import.db")):
            web = importlib.import_module("communication.web_app")
        with patch.object(web, "db", self.db), patch.object(web, "system_state", self.state):
            client = web.app.test_client()
            self.command("start")
            self.now.return_value = 30
            self.runtime.step(NORMAL, True)
            before = client.get("/api/today_stats").json
            self.command("reset")
            after = client.get("/api/today_stats").json
            self.assertEqual(before["today_study_seconds"], 30)
            self.assertEqual(before, after)
            records = client.get("/api/records").json
            self.assertEqual(records[0]["study_seconds"], 30)
            self.assertEqual(records[0]["study_minutes"], 0.5)
            self.state.set_posture_command("calibrate")
            self.assertEqual(client.post("/api/posture/calibrate").status_code, 409)
            for value in (True, [1], {"enabled": "yes"}):
                self.assertEqual(client.post("/api/device/light", json=value).status_code, 400)


class StorageTests(unittest.TestCase):
    def test_old_database_migrates_twice_without_losing_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "old.db"
            with sqlite3.connect(path) as conn:
                conn.execute("""CREATE TABLE study_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, start_time TEXT NOT NULL,
                    end_time TEXT, study_minutes INTEGER, reminder_count INTEGER,
                    posture_status TEXT)""")
                conn.execute("INSERT INTO study_records VALUES (1, ?, ?, 2, 3, 'NORMAL')",
                             ("2026-11-21 23:59:00", "2026-11-22 00:01:00"))
            conn.close()
            db = Database(path)
            db.add_record("2026-11-22 10:00:00", "2026-11-22 10:00:30", study_seconds=30)
            again = Database(path)
            self.assertEqual(again.get_summary()["total_study_seconds"], 150)
            self.assertEqual(again.get_summary()["total_reminders"], 3)
            self.assertEqual(again.get_records()[1][0], 1)
            self.assertEqual(db.get_day_summary("2026-11-21")["seconds"], 120)
            self.assertEqual(db.get_day_summary("2026-11-22")["seconds"], 30)

    def test_day_window_uses_local_dates_and_excludes_future(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(Path(tmp) / "dates.db")
            for delta, seconds in [(-1, 60), (0, 30), (1, 999)]:
                day = str(date.today() + timedelta(days=delta))
                db.add_record(day + " 10:00:00", day + " 10:01:00", study_seconds=seconds)
            rows = db.get_daily_stats(2)
            self.assertEqual([r["seconds"] for r in rows], [60, 30])


class TimerAndCameraTests(unittest.TestCase):
    def test_main_runs_controls_without_any_camera_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "offline.db"
            with patch("data.database.DB_PATH", str(path)):
                main = importlib.import_module("main")
            state = StateManager()
            db = Database(path)
            with patch("time.monotonic", return_value=0.0) as now:
                worker = unittest.mock.Mock()
                calls = iter(["start", "pause", "reset"])

                def snapshot(_):
                    try:
                        action = next(calls)
                    except StopIteration:
                        raise KeyboardInterrupt
                    if action == "pause":
                        now.return_value = 30
                    state.set_timer_command(action)
                    return None, 0, False

                worker.snapshot.side_effect = snapshot
                with patch.object(main, "system_state", state), \
                     patch.object(main, "Database", return_value=db), \
                     patch.object(main, "CameraWorker", return_value=worker), \
                     patch.object(main, "UpperBodyPose") as detector, \
                     patch.object(main, "start_web_server"), \
                     patch.object(main, "video_stream"), \
                     patch.object(main.time, "sleep"):
                    main.main(headless=True)
                    detector.return_value.process.assert_not_called()
                worker.close.assert_called_once()
                self.assertEqual(db.get_summary()["total_study_seconds"], 30)
                self.assertEqual(state.get_state()["study_status"], "idle")

    def test_pause_and_multiple_phase_crossings_preserve_study_seconds(self):
        with patch("time.monotonic", return_value=0.0) as now:
            timer = StudyTimer(study_duration=10, rest_duration=5)
            timer.start()
            now.return_value = 4
            timer.start()  # repeated start must account for elapsed time
            now.return_value = 6
            timer.pause()
            self.assertEqual(timer.get_state()["total_study_seconds"], 6)
            now.return_value = 100
            timer.start()
            now.return_value = 120
            state = timer.update()
            self.assertEqual(state["total_study_seconds"], 20)
            self.assertEqual(state["study_status"], "resting")
            self.assertEqual(state["remaining_seconds"], 4)

    def test_stalled_camera_does_not_block_snapshot_and_control(self):
        entered, release = threading.Event(), threading.Event()

        class StalledCamera:
            def start(self):
                pass

            def read(self):
                entered.set()
                release.wait(3)
                return False, None

            def release(self):
                pass

        worker = CameraWorker(StalledCamera())
        worker.start()
        try:
            self.assertTrue(entered.wait(1))
            frame, _, online = worker.snapshot(0)
            self.assertIsNone(frame)
            self.assertFalse(online)
        finally:
            worker.stopping.set()
            release.set()
            worker.close()

    def test_stale_frame_expires_even_if_read_thread_is_stuck(self):
        worker = CameraWorker(None, max_age=2)
        worker.frame = np.zeros((2, 2, 3), np.uint8)
        worker.updated_at, worker.sequence = 0.0, 1
        with patch("time.monotonic", return_value=1):
            self.assertTrue(worker.snapshot(0)[2])
        with patch("time.monotonic", return_value=3):
            self.assertFalse(worker.snapshot(0)[2])
            self.assertIsNone(worker.snapshot(0)[0])


if __name__ == "__main__":
    unittest.main()
