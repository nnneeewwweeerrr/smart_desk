
import sqlite3
import os
from datetime import datetime


# 数据库文件放在项目 data 文件夹中
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "smart_desk.db")


class Database:

    def __init__(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        self.init_database()

    def get_connection(self):
        return sqlite3.connect(DB_PATH)

    def init_database(self):
        """初始化数据库和数据表"""

        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS study_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT NOT NULL,
                end_time TEXT,
                study_minutes INTEGER DEFAULT 0,
                reminder_count INTEGER DEFAULT 0,
                posture_status TEXT DEFAULT 'normal'
            )
        """)

        conn.commit()
        conn.close()

        print("数据库初始化成功！")

    def add_record(
        self,
        start_time,
        end_time,
        study_minutes,
        reminder_count,
        posture_status="normal"
    ):
        """添加一条学习记录"""

        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO study_records (
                start_time,
                end_time,
                study_minutes,
                reminder_count,
                posture_status
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            start_time,
            end_time,
            study_minutes,
            reminder_count,
            posture_status
        ))

        conn.commit()
        conn.close()

        print("学习记录保存成功！")

    def get_records(self, limit=20):
        """查询最近的学习记录"""

        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM study_records
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))

        records = cursor.fetchall()
        conn.close()

        return records

    def get_summary(self):
        """获取学习统计数据"""

        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*),
                COALESCE(SUM(study_minutes), 0),
                COALESCE(SUM(reminder_count), 0)
            FROM study_records
        """)

        result = cursor.fetchone()
        conn.close()

        return {
            "total_sessions": result[0],
            "total_study_minutes": result[1],
            "total_reminders": result[2]
        }

    def get_daily_stats(self, days=7):
        """获取最近几天的每日学习时长"""

        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                DATE(start_time) AS study_date,
                COALESCE(SUM(study_minutes), 0) AS total_minutes
            FROM study_records
            WHERE DATE(start_time) >= DATE('now', ?)
            GROUP BY DATE(start_time)
            ORDER BY study_date ASC
        """, (f"-{days - 1} days",))

        records = cursor.fetchall()
        conn.close()

        # 整理为日期和时长的对应关系
        stats_map = {
            row[0]: row[1]
            for row in records
        }

        from datetime import date, timedelta

        result = []

        today = date.today()

        for i in range(days - 1, -1, -1):
            current_date = today - timedelta(days=i)
            date_str = current_date.strftime("%Y-%m-%d")

            result.append({
                "date": date_str,
                "minutes": stats_map.get(date_str, 0)
            })

        return result


if __name__ == "__main__":

    db = Database()

    print("\n数据库测试：")
    print("学习统计：", db.get_summary())
    print("学习记录：", db.get_records())
    print("最近7天学习统计：", db.get_daily_stats(7))
