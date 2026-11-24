
import os
import time
from datetime import datetime

from flask import (
    Flask,
    jsonify,
    request,
    Response,
    stream_with_context,
    send_from_directory
)

from services.state_manager import system_state
from services.video_stream import video_stream
from data.database import Database


# =====================================================
# 路径配置
# =====================================================

# 当前文件位于 communication 文件夹内
# 向上一级就是 smart_desk 项目根目录
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

# 前端文件夹
WEB_DIR = os.path.join(PROJECT_ROOT, "web")

# 服务启动时间，用于计算系统运行时长
WEB_START_TIME = time.time()


# =====================================================
# Flask 初始化
# =====================================================

# 将 web 文件夹设置为静态文件目录
# 这样 /css/style.css 和 /js/app.js 可以直接访问
app = Flask(
    __name__,
    static_folder=WEB_DIR,
    static_url_path=""
)

db = Database()


# =====================================================
# 首页
# =====================================================

@app.route("/")
def index():

    return send_from_directory(
        WEB_DIR,
        "index.html"
    )


# =====================================================
# 实时视频流接口
# =====================================================

@app.route("/video_feed")
def video_feed():

    def generate():

        while True:

            frame = video_stream.get_frame()

            if frame is None:
                time.sleep(0.1)
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + frame
                + b"\r\n"
            )

            time.sleep(0.03)

    return Response(
        stream_with_context(generate()),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


# =====================================================
# 实时状态接口
# =====================================================

@app.route("/api/status", methods=["GET"])
def get_status():

    state = system_state.get_state()

    state["uptime_seconds"] = int(
        max(0, time.time() - WEB_START_TIME)
    )

    return jsonify(state)


# =====================================================
# 累计学习统计接口
# =====================================================

@app.route("/api/summary", methods=["GET"])
def get_summary():

    return jsonify(
        db.get_summary()
    )


# =====================================================
# 今日学习统计接口
# =====================================================

@app.route("/api/today_stats", methods=["GET"])
def get_today_stats():

    today = datetime.now().strftime("%Y-%m-%d")
    with system_state.lock:
        saved = db.get_day_summary(today)
        current = system_state.get_state()
        # Archive whole sessions by local start date, including midnight crossings.
        belongs_today = str(current.get("session_start") or "")[:10] == today
        seconds = saved["seconds"] + (current.get("total_study_seconds", 0) if belongs_today else 0)
        reminders = saved["reminders"] + (current.get("reminder_count", 0) if belongs_today else 0)
    return jsonify({
        "date": today, "date_policy": "session_start_date",
        "today_study_seconds": seconds,
        "today_study_minutes": round(seconds / 60, 2),
        "today_reminders": reminders,
    })


# =====================================================
# 最近七天学习趋势接口
# =====================================================

@app.route("/api/daily_stats", methods=["GET"])
def get_daily_stats():

    try:
        days = int(request.args.get("days", 7))
    except (TypeError, ValueError):
        days = 7

    days = max(1, min(days, 365))

    return jsonify(
        db.get_daily_stats(days)
    )


# =====================================================
# 学习历史接口
# =====================================================

@app.route("/api/records", methods=["GET"])
def get_records():

    records = db.get_records(limit=50)

    result = []

    for record in records:

        result.append({
            "id": record[0],
            "start_time": record[1],
            "end_time": record[2],
            "study_minutes": round(record[3], 2),
            "study_seconds": record[6],
            "reminder_count": record[4],
            "posture_status": record[5]
        })

    return jsonify(result)


# =====================================================
# 台灯控制接口
# =====================================================

@app.route("/api/device/light", methods=["POST"])
def control_light():

    data = request.get_json(silent=True) or {}

    if not isinstance(data, dict) or not isinstance(data.get("enabled"), bool):

        return jsonify({
            "success": False,
            "message": "请提供 true 或 false"
        }), 400

    system_state.set_light(
        data["enabled"]
    )

    return jsonify({
        "success": True,
        "message": "台灯状态已更新"
    })


# =====================================================
# 蜂鸣器控制接口
# =====================================================

@app.route("/api/device/buzzer", methods=["POST"])
def control_buzzer():

    data = request.get_json(silent=True) or {}

    if not isinstance(data, dict) or not isinstance(data.get("enabled"), bool):

        return jsonify({
            "success": False,
            "message": "请提供 true 或 false"
        }), 400

    system_state.set_buzzer(
        data["enabled"]
    )

    return jsonify({
        "success": True,
        "message": "蜂鸣器设置已更新"
    })


# =====================================================
# 学习计时控制接口
# S：开始 / 继续
# P：暂停
# T：重置
# =====================================================

@app.route("/api/timer/<action>", methods=["POST"])
def control_timer(action):

    allowed_actions = [
        "start",
        "pause",
        "reset"
    ]

    if action not in allowed_actions:

        return jsonify({
            "success": False,
            "message": "不支持的计时操作"
        }), 400

    accepted = system_state.set_timer_command(
        action
    )

    if not accepted:

        return jsonify({
            "success": False,
            "message": "上一条计时指令正在处理中，请稍后重试"
        }), 400

    messages = {
        "start": "开始 / 继续指令已发送",
        "pause": "暂停指令已发送",
        "reset": "重置指令已发送"
    }

    return jsonify({
        "success": True,
        "message": messages[action]
    })


# =====================================================
# 姿态校准控制接口
# C：正常坐姿初始校准
# R：重新等待姿态校准
# =====================================================

@app.route("/api/posture/<action>", methods=["POST"])
def control_posture(action):

    allowed_actions = [
        "calibrate",
        "reset_calibration"
    ]

    if action not in allowed_actions:

        return jsonify({
            "success": False,
            "message": "不支持的姿态控制操作"
        }), 400

    with system_state.lock:
        if not system_state.set_posture_command(action):
            return jsonify(success=False, message="上一条姿态指令正在处理中，请稍后重试"), 409
        command_id = system_state.get_state()["posture_command_id"]
    return jsonify(success=True, command_id=command_id,
                   message="指令已接收，等待实际执行结果")


# =====================================================
# 服务检测接口
# =====================================================

@app.route("/api/health", methods=["GET"])
def health():

    return jsonify({
        "success": True,
        "message": "Web服务运行正常"
    })


# =====================================================
# 程序入口
# =====================================================

if __name__ == "__main__":

    print("智学灯 Web 服务启动中……")
    print("前端目录：", WEB_DIR)
    print("访问地址：http://127.0.0.1:5000")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        threaded=True
    )
