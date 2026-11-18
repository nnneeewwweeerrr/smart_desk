
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

        no_person: "未检测到人员",

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


// =====================================================
// 实时状态
// =====================================================

let statusRequesting = false;

let lightEnabled = false;
let buzzerEnabled = true;


async function refreshStatus() {

    if (statusRequesting) return;

    statusRequesting = true;

    try {

        const data = await requestJSON("/api/status");

        lightEnabled = Boolean(data.light);
        buzzerEnabled = Boolean(data.buzzer_enabled);


        // 系统运行状态
        const runState = getElement("systemRunState");

        if (runState) {
            runState.classList.remove("offline");
        }

        const database = getElement("sysDatabase");

        if (database) {
            database.textContent = "正常";
            database.classList.add("ok");
        }


        // 摄像头状态
        const camera = getElement("cameraIndicator");

        if (camera) {

            if (data.camera_online) {

                camera.textContent = "● 检测中...";
                camera.style.color = "#63a98b";

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

        setText(
            "sysCamera",
            data.camera_online ? "在线" : "离线"
        );


        // 姿态状态
        const posture = normalizePosture(data.posture);

        const abnormal =
            Boolean(data.person_detected) &&
            ![
                "normal",
                "unknown",
                "wait calibration",
                "keypoints not clear",
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

            stateText.textContent = studyStatus;
            stateText.prepend(stateDot);

            stateDot.className = "dot";

            if (data.study_status === "studying") {
                stateDot.classList.add("green");
            } else if (data.study_status === "resting") {
                stateDot.classList.add("amber");
            }
        }

        const timerStatus = getElement("timerStatus");

        if (timerStatus) {

            timerStatus.textContent = studyStatus;

            timerStatus.className = "badge";

            if (data.study_status === "studying") {
                timerStatus.classList.add("on");
            } else if (data.study_status === "idle") {
                timerStatus.classList.add("off");
            }
        }


        // 计时与学习时长
        const remaining = formatTime(data.remaining_seconds);

        const idle = String(data.study_status || "idle") === "idle";

        setText(
            "timerControlCountdown",
            idle && Number(data.remaining_seconds) === 0
                ? "25:00"
                : remaining
        );

        setText(
            "statStudyMinutes",
            (Number(data.study_minutes) || 0) + " 分钟"
        );


        // 设备状态
        setText(
            "lightBadge",
            data.light ? "已开启" : "已关闭"
        );

        setText(
            "buzzerBadge",
            data.buzzer_enabled ? "已开启" : "已静音"
        );

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

        showMessage("无法连接设备服务，请检查后台程序");

    } finally {

        statusRequesting = false;
    }
}


// =====================================================
// 姿势视觉反馈
// =====================================================

function updatePostureVisual(posture, abnormal, alerting) {

    const ringBox = getElement("postureRingBox");
    const ringText = getElement("ringPostureText");
    const statCheck = getElement("postureCheck");
    const ringCheck = getElement("ringCheck");

    if (ringBox) {
        ringBox.className = "ring";
    }

    if (ringText) {
        ringText.className = "ring-text";
    }

    if (statCheck) {
        statCheck.className = "stat-check";
    }

    let mark = "?";

    if (abnormal) {

        const danger = alerting;

        if (ringBox) {
            ringBox.classList.add(danger ? "danger" : "warn");
        }

        if (ringText) {
            ringText.classList.add(danger ? "danger" : "warn");
        }

        if (statCheck) {
            statCheck.classList.add("warn");
        }

        mark = "!";

    } else if (posture === "normal") {

        mark = "✓";

    } else {

        if (ringBox) {
            ringBox.classList.add("idle");
        }

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

    if (ringCheck) {
        ringCheck.textContent = mark;
        ringCheck.className = "ring-check";

        if (mark !== "✓") {
            ringCheck.classList.add("hide");
        }
    }
}


// =====================================================
// 坐姿提示面板
// =====================================================

function updatePosturePanels(posture, abnormal, data) {

    const warningPanel = getElement("warningPanel");
    const normalPanel = getElement("normalPanel");

    if (abnormal) {

        if (warningPanel) {
            warningPanel.classList.add("show");
        }

        if (normalPanel) {
            normalPanel.style.display = "none";
        }

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

    if (warningPanel) {
        warningPanel.classList.remove("show");
    }

    if (normalPanel) {
        normalPanel.style.display = "block";
    }

    if (!data.person_detected) {

        setText(
            "normalPanel",
            "当前未检测到人员或关键点不清晰，" +
            "请进入识别范围并保持上半身完整可见。"
        );

    } else if (
        posture === "keypoints not clear" ||
        posture === "unknown"
    ) {

        setText(
            "normalPanel",
            "暂时无法清晰识别坐姿，请调整摄像头范围或坐姿。"
        );

    } else if (posture === "wait calibration") {

        setText(
            "normalPanel",
            "尚未建立正常坐姿基准，请保持正常坐姿并点击姿态校准。"
        );

    } else {

        setText(
            "normalPanel",
            "当前坐姿状态正常，请继续保持。"
        );
    }
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
            (data.total_study_minutes ?? 0) + " 分钟"
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
// 今日统计
// =====================================================

async function refreshTodayStats() {

    try {

        const data = await requestJSON("/api/today_stats");

        setText(
            "todayStudy",
            (data.today_study_minutes ?? 0) + " 分钟"
        );

        setText(
            "todayReminders",
            (data.today_reminders ?? 0) + " 次提醒"
        );

    } catch (error) {

        console.error("今日统计加载失败：", error);
    }
}


// =====================================================
// 学习趋势图表
// =====================================================

let trendDays = 7;


function niceMax(value, defaultValue) {

    if (!value || value <= 0) return defaultValue;

    const steps = [10, 20, 30, 60, 90, 120, 180, 240, 300, 360, 480, 600];

    for (const step of steps) {
        if (value <= step) return step;
    }

    return Math.ceil(value / 60) * 60;
}


function buildChart(records) {

    const width = 640;
    const height = 232;

    const padLeft = 30;
    const padRight = 42;
    const padTop = 16;
    const padBottom = 28;

    const plotWidth = width - padLeft - padRight;
    const plotHeight = height - padTop - padBottom;

    const count = records.length;

    const maxMinutes = niceMax(
        Math.max(...records.map(item => Number(item.minutes) || 0)),
        30
    );

    const maxReminders = niceMax(
        Math.max(...records.map(item => Number(item.reminders) || 0)),
        5
    );

    const x = index => count <= 1
        ? padLeft + plotWidth / 2
        : padLeft + index * plotWidth / (count - 1);

    const yMinutes = value =>
        padTop + plotHeight * (1 - value / maxMinutes);

    const yReminders = value =>
        padTop + plotHeight * (1 - value / maxReminders);

    const formatDate = value => escapeHTML(String(value || "").slice(5));


    // 横向网格与左右纵轴
    let grid = "";
    let leftAxis = "";
    let rightAxis = "";

    for (let i = 0; i <= 3; i += 1) {

        const y = padTop + plotHeight * i / 3;

        grid += `<line x1="${padLeft}" y1="${y}" x2="${width - padRight}" y2="${y}" stroke="#eef3f8" stroke-width="1" />`;

        leftAxis += `<text x="${padLeft - 8}" y="${y + 3}" text-anchor="end" font-size="9" fill="#9aa8b8">${Math.round(maxMinutes * (3 - i) / 3)}</text>`;

        rightAxis += `<text x="${width - padRight + 8}" y="${y + 3}" font-size="9" fill="#9dbba9">${Math.round(maxReminders * (3 - i) / 3)}</text>`;
    }


    // 横轴日期标签
    let xAxis = "";

    const labelStep = Math.max(1, Math.ceil(count / 7));

    records.forEach((item, index) => {

        if (
            index % labelStep !== 0 &&
            index !== count - 1
        ) {
            return;
        }

        xAxis += `<text x="${x(index)}" y="${height - 8}" text-anchor="middle" font-size="9" fill="#9aa8b8">${formatDate(item.date)}</text>`;
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

    const toPolyline = points =>
        points.map(point => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");

    const areaPath =
        `M ${minutePoints[0].x.toFixed(1)} ${padTop + plotHeight} ` +
        minutePoints.map(point => `L ${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(" ") +
        ` L ${minutePoints[count - 1].x.toFixed(1)} ${padTop + plotHeight} Z`;

    const showDots = count <= 14;

    const dots = showDots
        ? minutePoints.map((point, index) => (
            `<circle cx="${point.x}" cy="${point.y}" r="3" fill="#ffffff" stroke="#6e9fd8" stroke-width="2"><title>${formatDate(records[index].date)}：${Number(records[index].minutes) || 0} 分钟</title></circle>`
        )).join("") +
        reminderPoints.map((point, index) => (
            `<circle cx="${point.x}" cy="${point.y}" r="2.5" fill="#ffffff" stroke="#6fb795" stroke-width="2"><title>${formatDate(records[index].date)}：${Number(records[index].reminders) || 0} 次提醒</title></circle>`
        )).join("")
        : "";


    return `
        <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="学习趋势图">
            <defs></defs>

            ${grid}

            <path d="${areaPath}" fill="#6e9fd8" opacity="0.08"></path>

            <polyline
                points="${toPolyline(minutePoints)}"
                fill="none"
                stroke="#6e9fd8"
                stroke-width="2.4"
                stroke-linecap="round"
                stroke-linejoin="round">
            </polyline>

            <polyline
                points="${toPolyline(reminderPoints)}"
                fill="none"
                stroke="#6fb795"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round">
            </polyline>

            ${dots}

            ${leftAxis}
            ${rightAxis}
            ${xAxis}

            <text x="${padLeft - 8}" y="${padTop - 5}" text-anchor="end" font-size="8" fill="#b0bdcb">分钟</text>
            <text x="${width - padRight + 8}" y="${padTop - 5}" font-size="8" fill="#b0c8b9">次</text>
        </svg>
    `;
}


async function refreshDailyStats(days = trendDays) {

    const chart = getElement("dailyChart");

    if (!chart) return;

    try {

        const records = await requestJSON(
            "/api/daily_stats?days=" + days
        );

        if (!Array.isArray(records) || records.length === 0) {

            chart.innerHTML =
                '<div class="empty">暂无学习趋势数据</div>';

            return;
        }

        chart.innerHTML = buildChart(records);


        const totalMinutes = records.reduce(
            (sum, item) => sum + (Number(item.minutes) || 0),
            0
        );

        const totalReminders = records.reduce(
            (sum, item) => sum + (Number(item.reminders) || 0),
            0
        );

        setText(
            "chartTip",
            "近 " + days + " 天累计学习 " + totalMinutes +
            " 分钟 · 坐姿提醒 " + totalReminders +
            " 次 · 蓝线为学习时长，绿线为提醒次数"
        );

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

        trendDays = Number(button.dataset.days) || 7;

        refreshDailyStats(trendDays);
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

                <td>${escapeHTML(record.study_minutes ?? 0)} 分钟</td>

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


        showMessage(result.message || "姿态指令已发送");

        await refreshStatus();

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

    refreshTodayStats();

    refreshDailyStats(trendDays);

    refreshRecords();
}


refreshAll();


setInterval(refreshStatus, 1000);

setInterval(refreshSummary, 5000);

setInterval(refreshTodayStats, 5000);

setInterval(() => refreshDailyStats(trendDays), 30000);

setInterval(refreshRecords, 10000);
