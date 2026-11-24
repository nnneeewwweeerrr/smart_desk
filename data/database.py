import os
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.abspath(os.environ.get(
    "SMART_DESK_DB_PATH", os.path.join(BASE_DIR, "data", "smart_desk.db")
))


class Database:
    """Second-precision records; daily totals belong to the session start date."""

    def __init__(self, path=None):
        self.path = os.path.abspath(path or DB_PATH)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.init_database()

    def get_connection(self):
        return sqlite3.connect(self.path, timeout=10)

    @contextmanager
    def connection(self):
        conn = self.get_connection()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def init_database(self):
        with self.connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS study_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time TEXT NOT NULL, end_time TEXT,
                    study_minutes INTEGER DEFAULT 0,
                    reminder_count INTEGER DEFAULT 0,
                    posture_status TEXT DEFAULT 'normal',
                    study_seconds INTEGER
                )
            """)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(study_records)")}
            if "study_seconds" not in columns:
                conn.execute("ALTER TABLE study_records ADD COLUMN study_seconds INTEGER")
            # Historical sub-minute precision was never stored and cannot be recovered.
            conn.execute("""UPDATE study_records
                SET study_seconds = CAST(ROUND(COALESCE(study_minutes, 0) * 60) AS INTEGER)
                WHERE study_seconds IS NULL""")

    def add_record(self, start_time, end_time, study_minutes=0, reminder_count=0,
                   posture_status="normal", study_seconds=None):
        seconds = max(0, int(round(study_minutes * 60) if study_seconds is None
                             else study_seconds))
        with self.connection() as conn:
            conn.execute("""INSERT INTO study_records
                (start_time, end_time, study_minutes, reminder_count, posture_status, study_seconds)
                VALUES (?, ?, ?, ?, ?, ?)""",
                         (start_time, end_time, seconds / 60, reminder_count,
                          posture_status, seconds))

    def get_records(self, limit=20):
        with self.connection() as conn:
            return conn.execute("""SELECT id, start_time, end_time,
                study_seconds / 60.0, reminder_count, posture_status, study_seconds
                FROM study_records ORDER BY id DESC LIMIT ?""", (limit,)).fetchall()

    def get_summary(self):
        with self.connection() as conn:
            count, seconds, reminders = conn.execute("""SELECT COUNT(*),
                COALESCE(SUM(study_seconds), 0), COALESCE(SUM(reminder_count), 0)
                FROM study_records""").fetchone()
        return {"total_sessions": count, "total_study_seconds": seconds,
                "total_study_minutes": round(seconds / 60, 2), "total_reminders": reminders}

    def get_day_summary(self, day):
        with self.connection() as conn:
            seconds, reminders = conn.execute("""SELECT
                COALESCE(SUM(study_seconds), 0), COALESCE(SUM(reminder_count), 0)
                FROM study_records WHERE DATE(start_time) = ?""", (str(day),)).fetchone()
        return {"seconds": seconds, "reminders": reminders}

    def get_daily_stats(self, days=7):
        today = date.today()
        first = today - timedelta(days=days - 1)
        with self.connection() as conn:
            rows = conn.execute("""SELECT DATE(start_time), SUM(study_seconds),
                SUM(reminder_count) FROM study_records
                WHERE DATE(start_time) BETWEEN ? AND ?
                GROUP BY DATE(start_time)""", (str(first), str(today))).fetchall()
        by_date = {row[0]: row[1:] for row in rows}
        result = []
        for offset in range(days):
            day = str(first + timedelta(days=offset))
            seconds, reminders = by_date.get(day, (0, 0))
            result.append({"date": day, "seconds": seconds,
                           "minutes": round(seconds / 60, 2), "reminders": reminders})
        return result
