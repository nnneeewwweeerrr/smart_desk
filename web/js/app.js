
"use strict";

// =====================================================
// 通用工具
// =====================================================

function getElement(id) {
    return document.getElementById(id);
}

function setText(id, value) {
    const element = getElement(id);

    if (element) {
        element.textContent = value;
    }
}

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[char]);
}

async function requestJSON(url, options = {}) {
    const response = await fetch(url, {
        cache: "no-store",
        ...options
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.message || "服务器请求失败");
    }

    return data;
}

function showMessage(message) {
    setText("message", message);
}


// =====================================================
// 顶部时间
// =====================================================

function updateClock() {

    const now = new Date();

    const pad = value => String(value).padStart(2, "0");

    setText(
        "liveClock",
        now.getFullYear() + "年" +
        (now.getMonth() + 1) + "月" +
        now.getDate() + "日 " +
        pad(now.getHours()) + ":" +
        pad(now.getMinutes()) + ":" +
        pad(now.getSeconds())
    );
}

updateClock();
setInterval(updateClock, 1000);


// =====================================================
// 侧边栏导航高亮
// =====================================================

document.querySelectorAll(".nav-item").forEach(item => {

    item.addEventListener("click", () => {

        document.querySelectorAll(".nav-item").forEach(other => {
            other.classList.remove("active");
        });

        item.classList.add("active");
    });
});


// =====================================================
// 姿态与学习状态文字
// =====================================================

function normalizePosture(value) {
    return String(value ?? "unknown")
        .trim()
        .toLowerCase();
}

function postureText(value) {

    const posture = normalizePosture(value);

    const map = {
        normal: "坐姿正常",

        "head down": "低头",

        "lean forward": "身体前倾",

        "tilt left": "向左倾斜",

        "tilt right": "向右倾斜",

        unknown: "等待识别",

        "keypoints not clear": "关键点不清晰",

        "no person": "未检测到人员",

        "wait calibration": "等待姿态校准"
    };

    return map[posture] || String(value || "等待识别");
}

function studyStatusText(value) {

    const status = String(value ?? "idle")
        .trim()
        .toLowerCase();

    const map = {
        idle: "等待开始",
        studying: "专注学习中",
        resting: "休息中",
        paused: "已暂停"
    };

    return map[status] || value || "等待开始";
}

function formatTime(seconds) {

    seconds = Math.max(0, Number(seconds) || 0);

    const minutes = Math.floor(seconds / 60);
    const remain = Math.floor(seconds % 60);

    return String(minutes).padStart(2, "0") + ":" +
        String(remain).padStart(2, "0");
}

function formatStudyDuration(seconds) {
    const total = Math.max(0, Math.floor(Number(seconds) || 0));
    return Math.floor(total / 60) + "分" + (total % 60) + "秒";
}


function formatUptime(seconds) {

    seconds = Math.max(0, Number(seconds) || 0);

    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (days > 0) {
        return days + " 天 " + hours + " 小时";
    }

    if (hours > 0) {
        return hours + " 小时 " + minutes + " 分钟";
    }

    return minutes + " 分钟";
}


// =====================================================
// 实时状态
// =====================================================

let statusRequesting = false;

let lightEnabled = false;
let buzzerEnabled = true;
let videoNeedsReconnect = false;
let lastTimerError = null;


async function refreshStatus() {

    if (statusRequesting) return;

    statusRequesting = true;

    try {

        const data = await requestJSON("/api/status");

        lightEnabled = Boolean(data.light);
        buzzerEnabled = Boolean(data.buzzer_enabled);
        if (data.timer_error && data.timer_error !== lastTimerError) showMessage(data.timer_error);
        lastTimerError = data.timer_error || null;
        const smoothing = data.posture_smoothing;
        setText("smoothingStatus", !smoothing ? "正在读取平滑配置" :
            "特征平滑：" + (smoothing.method === "one_euro" ? "1€ Filter" : "5帧均值"));
        setText("calibrationStatus",
            (data.calibration_message || "请坐正后校准") +
            " · 有效样本 " + (data.calibration_samples || 0) +
            "/" + (data.calibration_required || 10));
        const feed = getElement("cameraFeed");
        if (feed) {
            feed.style.visibility = data.camera_online ? "visible" : "hidden";
            if (data.camera_online && videoNeedsReconnect) {
                feed.src = "/video_feed?t=" + Date.now();
                videoNeedsReconnect = false;
            }
        }


        // 系统运行状态
        const runState = getElement("systemRunState");

        if (runState) {
            runState.classList.remove("offline");
        }

        const database = getElement("sysDatabase");

        if (database) {
            database.innerHTML =
                '<span class="info-dot"></span>正常';
            database.classList.add("ok");
        }

        setText(
            "sysUptime",
            formatUptime(data.uptime_seconds)
        );


        // 摄像头状态
        const camera = getElement("cameraIndicator");

        if (camera) {

            if (data.camera_online) {

                camera.textContent = "● 检测中...";
                camera.style.color = "#5aa38c";

                setText(
                    "videoMessage",
                    "摄像头已连接，正在实时识别上半身姿态"
                );

            } else {

                camera.textContent = "● 摄像头离线";
                camera.style.color = "#c17878";

                setText(
                    "videoMessage",
                    "等待摄像头画面，请确认集成程序正在运行"
                );
            }
        }


        // 姿态状态
        const posture = normalizePosture(data.posture);

        const abnormal =
            Boolean(data.person_detected) &&
            ![
                "normal",
                "unknown",
                "wait calibration",
                "keypoints not clear",
                "no person",
                "no_person"
            ].includes(posture);

        setText("statPostureText", postureText(posture));
        setText("ringPostureText", postureText(posture));

        updatePostureVisual(posture, abnormal, Boolean(data.alert));


        // 学习状态
        const studyStatus = studyStatusText(data.study_status);

        const stateText = getElement("studyStateText");
        const stateDot = getElement("studyStateDot");

        if (stateText && stateDot) {

            const dotClass = ["dot"];

            if (data.study_status === "studying") {
                dotClass.push("green");
            } else if (data.study_status === "resting") {
                dotClass.push("amber");
            }

            stateDot.className = dotClass.join(" ");
            stateDot.textContent = "";

            stateText.textContent = studyStatus;
            stateText.prepend(stateDot);
        }


        // 计时与学习时长
        const idle = String(data.study_status || "idle") === "idle";
        const status = String(data.study_status || "idle").toLowerCase();

        const totalSeconds = data.timer_phase === "resting" ? 5 * 60 : 25 * 60;
        const remainingSeconds = Math.max(
            0,
            Number(data.remaining_seconds) || 0
        );

        const displaySeconds =
            idle && remainingSeconds <= 0
                ? totalSeconds
                : remainingSeconds;

        setText("quickTimer", formatTime(displaySeconds));
        setText("ringTimer", formatTime(displaySeconds));

        updateTimerRing(status, displaySeconds, totalSeconds);

        setText(
            "statStudyMinutes",
            formatStudyDuration(data.total_study_seconds)
        );


        // 设备状态
        const lightBadge = getElement("lightBadge");

        if (lightBadge) {
            lightBadge.textContent = (data.light ? "已开启" : "已关闭") +
                ((data.light_mode || data.device_mode) === "mock" ? "（模拟）" : "");
            lightBadge.className =
                "badge " + (data.light ? "badge-on" : "badge-off");
        }

        const buzzerBadge = getElement("buzzerBadge");

        if (buzzerBadge) {
            buzzerBadge.textContent =
                (data.buzzer_enabled ? "已开启" : "已静音") +
                ((data.buzzer_mode || data.device_mode) === "mock" ? "（模拟）" : "（实体）");
            buzzerBadge.className =
                "badge " + (data.buzzer_enabled ? "badge-on" : "badge-off");
        }

        updateSwitch("lightToggle", Boolean(data.light));
        updateSwitch("buzzerToggle", Boolean(data.buzzer_enabled));


        // 坐姿提示面板
        updatePosturePanels(posture, abnormal, data);


    } catch (error) {

        console.error("实时状态加载失败：", error);

        const runState = getElement("systemRunState");

        if (runState) {
            runState.classList.add("offline");
        }

        const database = getElement("sysDatabase");

        if (database) {
            database.textContent = "无法连接";
            database.classList.remove("ok");
        }

        const feed = getElement("cameraFeed");
        if (feed) feed.style.visibility = "hidden";
        videoNeedsReconnect = true;
        showMessage("无法连接设备服务，请检查后台程序");

    } finally {

        statusRequesting = false;
    }
}


// =====================================================
// 姿势视觉反馈
// =====================================================

// 圆环倒计时：r = 63
const RING_LENGTH = 2 * Math.PI * 63;


function updateTimerRing(status, remaining, total) {

    const ringBox = getElement("postureRingBox");
    const ring = getElement("postureRing");

    if (ringBox) {

        ringBox.classList.remove("studying", "resting", "paused", "idle");

        if (status === "studying") {
            ringBox.classList.add("studying");
        } else if (status === "resting") {
            ringBox.classList.add("resting");
        } else if (status === "paused") {
            ringBox.classList.add("paused");
        } else {
            ringBox.classList.add("idle");
        }
    }

    if (ring) {

        const ratio = total > 0
            ? Math.min(1, Math.max(0, remaining / total))
            : 0;

        ring.style.strokeDasharray = RING_LENGTH.toFixed(1);
        ring.style.strokeDashoffset =
            (RING_LENGTH * (1 - ratio)).toFixed(1);
    }
}


function updatePostureVisual(posture, abnormal, alerting) {

    const ringBox = getElement("postureRingBox");
    const ringText = getElement("ringPostureText");
    const statCheck = getElement("postureCheck");

    if (ringText) {
        ringText.className = "ring-text";
    }

    if (statCheck) {
        statCheck.className = "stat-check";
    }

    let mark = "?";

    if (abnormal) {

        if (ringText) {
            ringText.classList.add(alerting ? "danger" : "warn");
        }

        if (statCheck) {
            statCheck.classList.add("warn");
        }

        mark = "!";

    } else if (posture === "normal") {

        mark = "✓";

    } else {

        if (ringText) {
            ringText.classList.add("idle");
        }

        if (statCheck) {
            statCheck.classList.add("idle");
        }
    }

    if (statCheck) {
        statCheck.textContent = mark;
    }

    if (ringBox) {
        ringBox.classList.toggle("alert", Boolean(abnormal && alerting));
    }
}


// =====================================================
// 坐姿提示面板
// =====================================================

function updatePosturePanels(posture, abnormal, data) {

    const warningPanel = getElement("warningPanel");

    if (!warningPanel) return;

    if (abnormal) {

        warningPanel.classList.add("show");

        setText(
            "warningTitle",
            "检测到坐姿异常：" + postureText(posture)
        );

        const elapsed = Number(data.alert_elapsed) || 0;
        const remaining = Math.max(0, Number(data.alert_remaining) || 0);

        if (data.alert) {

            setText(
                "warningDescription",
                "异常姿势持续时间已达到提醒阈值，请调整坐姿。"
            );

            setText("warningCountdown", "已触发提醒");

        } else {

            setText(
                "warningDescription",
                "请及时调整坐姿，持续异常达到 5 秒将触发提醒。"
            );

            setText(
                "warningCountdown",
                "已持续 " + elapsed.toFixed(1) +
                " 秒，距离提醒还有 " + remaining.toFixed(1) + " 秒"
            );
        }

        return;
    }

    warningPanel.classList.remove("show");
}


function updateSwitch(id, enabled) {

    const element = getElement(id);

    if (!element) return;

    element.classList.toggle("on", enabled);
}


// =====================================================
// 累计统计
// =====================================================

async function refreshSummary() {

    try {

        const data = await requestJSON("/api/summary");

        setText("totalSessions", data.total_sessions ?? 0);

        setText(
            "totalMinutes",
            formatStudyDuration(data.total_study_seconds ?? Number(data.total_study_minutes || 0) * 60)
        );

        setText(
            "totalReminders",
            (data.total_reminders ?? 0) + " 次"
        );

    } catch (error) {

        console.error("累计统计加载失败：", error);
    }
}


// =====================================================
// 学习趋势图表
// =====================================================

let trendRange = "today";


// 平滑曲线：三次贝塞尔（控制点限制在绘图区内，避免曲线冲出坐标轴）
function smoothPath(points, top, bottom) {

    if (points.length === 0) return "";

    if (points.length === 1) {
        return `M ${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)}`;
    }

    const clampY = value => Math.min(bottom, Math.max(top, value));

    let path = `M ${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)}`;

    for (let i = 0; i < points.length - 1; i += 1) {

        const p0 = points[i - 1] || points[i];
        const p1 = points[i];
        const p2 = points[i + 1];
        const p3 = points[i + 2] || p2;

        const c1x = p1.x + (p2.x - p0.x) / 6;
        const c1y = clampY(p1.y + (p2.y - p0.y) / 6);
        const c2x = p2.x - (p3.x - p1.x) / 6;
        const c2y = clampY(p2.y - (p3.y - p1.y) / 6);

        path +=
            ` C ${c1x.toFixed(1)} ${c1y.toFixed(1)},` +
            ` ${c2x.toFixed(1)} ${c2y.toFixed(1)},` +
            ` ${p2.x.toFixed(1)} ${p2.y.toFixed(1)}`;
    }

    return path;
}


function buildChart(records) {

    const width = 640;
    const height = 214;

    const padLeft = 32;
    const padRight = 16;
    const padTop = 30;
    const padBottom = 26;

    const plotWidth = width - padLeft - padRight;
    const plotHeight = height - padTop - padBottom;

    const count = records.length;

    const maxMinutes = Math.max(
        90,
        Math.ceil(
            Math.max(...records.map(item => Number(item.minutes) || 0)) / 30
        ) * 30
    );

    const maxReminders = Math.max(
        4,
        Math.max(...records.map(item => Number(item.reminders) || 0))
    );

    const x = index => count <= 1
        ? padLeft + plotWidth / 2
        : padLeft + index * plotWidth / (count - 1);

    const yMinutes = value =>
        padTop + plotHeight * (1 - value / maxMinutes);

    const yReminders = value =>
        padTop + plotHeight * (1 - value / maxReminders);


    // 横向网格与左侧刻度
    let grid = "";
    let leftAxis = "";

    for (let i = 0; i <= 3; i += 1) {

        const y = padTop + plotHeight * i / 3;

        grid += `<line x1="${padLeft}" y1="${y}" x2="${width - padRight}" y2="${y}" stroke="#eef3f8" stroke-width="1" />`;

        leftAxis += `<text x="${padLeft - 8}" y="${y + 3}" text-anchor="end" font-size="9" fill="#a6b4c4">${Math.round(maxMinutes * (3 - i) / 3)}</text>`;
    }


    // 横轴标签
    let xAxis = "";

    const labelStep = Math.max(1, Math.ceil(count / 7));

    records.forEach((item, index) => {

        if (index % labelStep !== 0 && index !== count - 1) {
            return;
        }

        xAxis += `<text x="${x(index).toFixed(1)}" y="${height - 7}" text-anchor="middle" font-size="9" fill="#a6b4c4">${escapeHTML(item.label)}</text>`;
    });


    // 折线数据
    const minutePoints = records.map((item, index) => ({
        x: x(index),
        y: yMinutes(Number(item.minutes) || 0)
    }));

    const reminderPoints = records.map((item, index) => ({
        x: x(index),
        y: yReminders(Number(item.reminders) || 0)
    }));

    const areaPath =
        smoothPath(minutePoints, padTop, padTop + plotHeight) +
        ` L ${minutePoints[count - 1].x.toFixed(1)} ${padTop + plotHeight}` +
        ` L ${minutePoints[0].x.toFixed(1)} ${padTop + plotHeight} Z`;

    const showDots = count <= 14;

    const minuteDots = showDots
        ? minutePoints.map((point, index) => (
            `<circle cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="2.8" fill="#ffffff" stroke="#6d97c8" stroke-width="2"><title>${escapeHTML(records[index].label)}：${Number(records[index].minutes) || 0} 分钟</title></circle>`
        )).join("")
        : "";

    const reminderDots = showDots
        ? reminderPoints.map((point, index) => (
            `<circle cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="2.4" fill="#ffffff" stroke="#6fb795" stroke-width="2"><title>${escapeHTML(records[index].label)}：${Number(records[index].reminders) || 0} 次提醒</title></circle>`
        )).join("")
        : "";


    return `
        <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="学习趋势图">

            <circle cx="${width - padRight - 148}" cy="12" r="3.2" fill="#6d97c8"></circle>
            <text x="${width - padRight - 139}" y="15.5" font-size="9.5" fill="#8395a8">学习时长</text>

            <circle cx="${width - padRight - 60}" cy="12" r="3.2" fill="#6fb795"></circle>
            <text x="${width - padRight - 51}" y="15.5" font-size="9.5" fill="#8395a8">提醒次数</text>

            ${grid}

            <defs>
                <linearGradient id="areaBlue" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="#6d97c8" stop-opacity="0.16"></stop>
                    <stop offset="100%" stop-color="#6d97c8" stop-opacity="0"></stop>
                </linearGradient>
            </defs>

            <path d="${areaPath}" fill="url(#areaBlue)"></path>

            <path
                d="${smoothPath(minutePoints, padTop, padTop + plotHeight)}"
                fill="none"
                stroke="#6d97c8"
                stroke-width="2.4"
                stroke-linecap="round"
                stroke-linejoin="round">
            </path>

            <path
                d="${smoothPath(reminderPoints, padTop, padTop + plotHeight)}"
                fill="none"
                stroke="#6fb795"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round">
            </path>

            ${minuteDots}
            ${reminderDots}

            ${leftAxis}
            ${xAxis}

        </svg>
    `;
}


function buildTodayRecords(records) {

    // 今日按 2 小时分桶：8/10/12/14/16/18 点
    const buckets = [
        { hour: 8, label: "8时" },
        { hour: 10, label: "10时" },
        { hour: 12, label: "12时" },
        { hour: 14, label: "14时" },
        { hour: 16, label: "16时" },
        { hour: 18, label: "18时" }
    ];

    const today = new Date();

    const todayKey =
        today.getFullYear() + "-" +
        String(today.getMonth() + 1).padStart(2, "0") + "-" +
        String(today.getDate()).padStart(2, "0");

    const result = buckets.map(item => ({
        label: item.label,
        minutes: 0,
        reminders: 0
    }));

    records.forEach(record => {

        const startTime = String(record.start_time || "");

        if (startTime.slice(0, 10) !== todayKey) {
            return;
        }

        const hour = Number(startTime.slice(11, 13));

        if (!Number.isFinite(hour)) {
            return;
        }

        let index = 0;

        for (let i = 0; i < buckets.length; i += 1) {
            if (hour >= buckets[i].hour) {
                index = i;
            }
        }

        result[index].minutes += Number(record.study_minutes) || 0;
        result[index].reminders += Number(record.reminder_count) || 0;
    });

    return result;
}


async function refreshDailyStats() {

    const chart = getElement("dailyChart");

    if (!chart) return;

    try {

        let records = [];

        if (trendRange === "today") {

            const raw = await requestJSON("/api/records");

            records = buildTodayRecords(
                Array.isArray(raw) ? raw : []
            );

        } else {

            const days = trendRange === "week" ? 7 : 30;

            const raw = await requestJSON(
                "/api/daily_stats?days=" + days
            );

            records = (Array.isArray(raw) ? raw : []).map(item => ({
                label: String(item.date || "").slice(5),
                minutes: Number(item.minutes) || 0,
                reminders: Number(item.reminders) || 0
            }));
        }

        chart.innerHTML = buildChart(records);

    } catch (error) {

        console.error("学习趋势加载失败：", error);

        chart.innerHTML =
            '<div class="empty">学习趋势加载失败，请检查服务</div>';
    }
}


document.querySelectorAll("#trendTabs button").forEach(button => {

    button.addEventListener("click", () => {

        document.querySelectorAll("#trendTabs button").forEach(other => {
            other.classList.remove("active");
        });

        button.classList.add("active");

        trendRange = button.dataset.range || "today";

        refreshDailyStats();
    });
});


// =====================================================
// 学习历史
// =====================================================

async function refreshRecords() {

    const tbody = getElement("recordTable");

    if (!tbody) return;

    try {

        const records = await requestJSON("/api/records");

        if (!Array.isArray(records) || records.length === 0) {

            tbody.innerHTML =
                '<tr><td colspan="6" class="empty">暂时没有学习记录</td></tr>';

            return;
        }


        tbody.innerHTML = records.map(record => `

            <tr>

                <td>${escapeHTML(record.id ?? "-")}</td>

                <td>${escapeHTML(record.start_time || "-")}</td>

                <td>${escapeHTML(record.end_time || "-")}</td>

                <td>${escapeHTML(formatStudyDuration(record.study_seconds ?? Number(record.study_minutes || 0) * 60))}</td>

                <td>${escapeHTML(record.reminder_count ?? 0)}</td>

                <td>${escapeHTML(postureText(record.posture_status))}</td>

            </tr>

        `).join("");

    } catch (error) {

        console.error("历史记录加载失败：", error);

        tbody.innerHTML =
            '<tr><td colspan="6" class="empty">历史记录加载失败</td></tr>';
    }
}


// =====================================================
// 学习计时控制
// =====================================================

async function timerControl(action) {

    const messages = {

        start: "正在发送开始 / 继续指令……",

        pause: "正在发送暂停指令……",

        reset: "正在发送重置指令……"
    };


    showMessage(messages[action] || "正在发送计时指令……");


    try {

        const result = await requestJSON(
            "/api/timer/" + action,
            { method: "POST" }
        );


        if (!result.success) {

            throw new Error(result.message || "计时控制失败");
        }


        showMessage(result.message || "计时指令已发送");

        await refreshStatus();

        if (action === "reset") {
            await refreshRecords();
            await refreshSummary();
            await refreshDailyStats();
        }

    } catch (error) {

        showMessage(error.message || "计时控制失败");
    }
}


// =====================================================
// 姿态校准控制
// =====================================================

async function postureControl(action) {

    const messages = {

        calibrate: "正在发送姿态校准指令……",

        reset_calibration: "正在发送重新等待校准指令……"
    };


    showMessage(messages[action] || "正在发送姿态指令……");


    try {

        const result = await requestJSON(
            "/api/posture/" + action,
            { method: "POST" }
        );


        if (!result.success) {

            throw new Error(result.message || "姿态控制失败");
        }


        showMessage("指令已接收，正在等待校准结果……");
        const deadline = Date.now() + 10000;
        while (Date.now() < deadline) {
            const state = await requestJSON("/api/status");
            if (state.posture_command_id !== result.command_id) {
                showMessage("已提交更新的校准指令，请查看当前校准状态");
                return;
            }
            if (state.calibration_result !== "pending") {
                showMessage(state.calibration_message);
                await refreshStatus();
                return;
            }
            await new Promise(resolve => setTimeout(resolve, 250));
        }
        showMessage("指令仍在处理中，请查看校准状态或设备连接");

    } catch (error) {

        showMessage(error.message || "姿态控制失败");
    }
}


// =====================================================
// 台灯与蜂鸣器控制
// =====================================================

async function control(device, enabled) {

    if (!["light", "buzzer"].includes(device)) {

        showMessage("不支持的设备");

        return;
    }


    showMessage(
        device === "light"
            ? "正在发送台灯控制指令……"
            : "正在发送蜂鸣器控制指令……"
    );


    try {

        const result = await requestJSON(
            "/api/device/" + device,
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({ enabled: enabled })
            }
        );


        if (!result.success) {

            throw new Error(result.message || "设备控制失败");
        }


        showMessage(result.message || "设备设置已更新");

        await refreshStatus();

    } catch (error) {

        showMessage(error.message || "设备控制失败");
    }
}


function toggleLight() {
    control("light", !lightEnabled);
}


function toggleBuzzer() {
    control("buzzer", !buzzerEnabled);
}


// =====================================================
// 摄像头错误处理
// =====================================================

const cameraFeed = getElement("cameraFeed");

if (cameraFeed) {

    cameraFeed.onerror = function () {
        videoNeedsReconnect = true;

        setText(
            "videoMessage",
            "暂时无法获取摄像头画面，请确认集成程序正在运行"
        );
    };
}


// =====================================================
// 页面初始化
// =====================================================

function refreshAll() {

    refreshStatus();

    refreshSummary();

    refreshDailyStats();

    refreshRecords();
}


refreshAll();


setInterval(refreshStatus, 1000);

setInterval(refreshSummary, 5000);

setInterval(refreshDailyStats, 30000);

setInterval(refreshRecords, 10000);
