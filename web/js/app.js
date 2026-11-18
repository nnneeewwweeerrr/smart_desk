
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
// 日期
// =====================================================

setText(
    "currentDate",
    new Date().toLocaleDateString("zh-CN", {
        year: "numeric",
        month: "long",
        day: "numeric"
    })
);


// =====================================================
// 姿态状态统一处理
// =====================================================

// 统一转成小写，解决 NORMAL / normal 大小写不一致问题
function normalizePosture(value) {
    return String(value ?? "unknown")
        .trim()
        .toLowerCase();
}


// =====================================================
// 状态文字转换
// =====================================================

function postureText(value) {

    const posture = normalizePosture(value);

    const map = {
        normal: "坐姿正常",

        head_down: "低头",

        leaning: "身体前倾",

        tilted_left: "向左倾斜",

        tilted_right: "向右倾斜",

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
        idle: "空闲",
        studying: "学习中",
        resting: "休息中",
        paused: "已暂停"
    };

    return map[status] || value || "空闲";
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


async function refreshStatus() {

    if (statusRequesting) return;

    statusRequesting = true;

    try {

        const data = await requestJSON("/api/status");


        // =================================================
        // 摄像头
        // =================================================

        const camera = getElement("cameraIndicator");

        if (camera) {

            if (data.camera_online) {

                camera.textContent = "● 摄像头在线";

                camera.style.background = "#E8F9F1";
                camera.style.color = "#38A77B";

                setText(
                    "videoMessage",
                    "摄像头已连接，正在实时识别上半身姿态"
                );

            } else {

                camera.textContent = "● 摄像头离线";

                camera.style.background = "#FFF0EE";
                camera.style.color = "#D66B61";

                setText(
                    "videoMessage",
                    "等待摄像头画面，请确认集成程序正在运行"
                );
            }
        }


        // =================================================
        // 人员状态
        // =================================================

        setText(
            "personStatus",
            data.person_detected
                ? "已检测到人员"
                : "未检测到人员"
        );


        // =================================================
        // 姿态状态
        // =================================================

        const posture = normalizePosture(data.posture);

        setText("posture", postureText(posture));


        // =================================================
        // 学习状态
        // =================================================

        const studyStatus = studyStatusText(data.study_status);

        setText("studyStatus", studyStatus);

        setText("timerControlStatus", studyStatus);


        // =================================================
        // 剩余时间
        // =================================================

        const remaining = formatTime(data.remaining_seconds);

        setText("studyCountdown", remaining);

        setText("timerControlCountdown", remaining);


        // =================================================
        // 本次学习时间
        // =================================================

        setText(
            "studyTime",
            (Number(data.study_minutes) || 0) + " 分钟"
        );


        // =================================================
        // 本次提醒次数
        // =================================================

        setText(
            "reminders",
            (Number(data.reminder_count) || 0) + " 次"
        );


        // =================================================
        // 坐姿异常判断
        // =================================================

        // 只有真正识别到人员，并且姿态不是正常、未知、
        // 等待校准或无法识别时，才判断为异常。

        // 正常状态和暂时无法判断的状态
        const normalPostures = [
            "normal",
            "unknown",
            "wait calibration",
            "keypoints not clear",
            "no_person"
        ];

        // 只要检测到人员，且姿态不属于正常或等待状态，
        // 就判断为异常姿势
        const abnormal =
            Boolean(data.person_detected) &&
            !normalPostures.includes(posture);


        const warningPanel = getElement("warningPanel");

        const normalPanel = getElement("normalPanel");


        // =================================================
        // 异常坐姿提醒
        // =================================================

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

            const remainingAlert = Math.max(
                0,
                Number(data.alert_remaining) || 0
            );


            if (data.alert) {

                setText(
                    "warningDescription",
                    "异常姿势持续时间已达到提醒阈值，请调整坐姿。"
                );

                setText(
                    "warningCountdown",
                    "已触发提醒"
                );

            } else {

                setText(
                    "warningDescription",
                    "请及时调整坐姿，持续异常达到 5 秒将触发提醒。"
                );

                setText(
                    "warningCountdown",
                    "已持续 " +
                    elapsed.toFixed(1) +
                    " 秒，距离提醒还有 " +
                    remainingAlert.toFixed(1) +
                    " 秒"
                );
            }

        } else {

            // =================================================
            // 正常状态 / 等待识别 / 等待校准
            // =================================================

            if (warningPanel) {
                warningPanel.classList.remove("show");
            }

            if (normalPanel) {
                normalPanel.style.display = "block";
            }


            if (!data.person_detected) {

                setText(
                    "normalPanel",
                    "当前未检测到人员，请进入摄像头识别范围。"
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
                    "尚未建立正常坐姿基准，请保持正常坐姿并点击姿态初始校准。"
                );

            } else {

                setText(
                    "normalPanel",
                    "当前坐姿状态正常，请继续保持。"
                );
            }
        }

    } catch (error) {

        console.error("实时状态加载失败：", error);

        showMessage("无法连接设备服务，请检查后台程序");

    } finally {

        statusRequesting = false;
    }
}


// =====================================================
// 累计统计
// =====================================================

async function refreshSummary() {

    try {

        const data = await requestJSON("/api/summary");

        setText(
            "totalSessions",
            data.total_sessions ?? 0
        );

        setText(
            "totalMinutes",
            (data.total_study_minutes ?? 0) + " 分钟"
        );

        setText(
            "totalReminders",
            data.total_reminders ?? 0
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
            (data.today_reminders ?? 0) + " 次"
        );

    } catch (error) {

        console.error("今日统计加载失败：", error);
    }
}


// =====================================================
// 最近七天趋势
// =====================================================

async function refreshDailyStats() {

    const chart = getElement("dailyChart");

    if (!chart) return;

    try {

        const records = await requestJSON("/api/daily_stats");

        if (!Array.isArray(records) || records.length === 0) {

            chart.innerHTML =
                '<div class="empty">暂无学习趋势数据</div>';

            return;
        }


        const maxMinutes = Math.max(
            ...records.map(item => Number(item.minutes) || 0),
            1
        );


        chart.innerHTML = records.map(item => {

            const minutes = Number(item.minutes) || 0;

            const height = minutes > 0
                ? Math.max(minutes / maxMinutes * 100, 3)
                : 0;

            const dateLabel = escapeHTML(
                String(item.date || "").slice(5)
            );


            return `
                <div class="bar-item">

                    <div class="bar-value">
                        ${minutes}
                    </div>

                    <div class="bar-track">

                        <div
                            class="bar-fill"
                            style="height:${height}%"
                            title="${dateLabel}：${minutes} 分钟">
                        </div>

                    </div>

                    <div class="bar-date">
                        ${dateLabel}
                    </div>

                </div>
            `;

        }).join("");


        const total = records.reduce(
            (sum, item) => sum + (Number(item.minutes) || 0),
            0
        );


        setText(
            "chartTip",
            "最近7天累计学习：" + total + " 分钟"
        );

    } catch (error) {

        console.error("学习趋势加载失败：", error);

        chart.innerHTML =
            '<div class="empty">学习趋势加载失败，请检查服务</div>';
    }
}


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


    showMessage(
        messages[action] || "正在发送计时指令……"
    );


    try {

        const result = await requestJSON(
            "/api/timer/" + action,
            {
                method: "POST"
            }
        );


        if (!result.success) {

            throw new Error(
                result.message || "计时控制失败"
            );
        }


        showMessage(
            result.message || "计时指令已发送"
        );

        await refreshStatus();

    } catch (error) {

        showMessage(
            error.message || "计时控制失败"
        );
    }
}


// =====================================================
// 姿态校准控制
// =====================================================

async function postureControl(action) {

    const messages = {

        calibrate: "正在发送姿态初始校准指令……",

        reset_calibration: "正在发送重新等待校准指令……"
    };


    showMessage(
        messages[action] || "正在发送姿态指令……"
    );


    try {

        const result = await requestJSON(
            "/api/posture/" + action,
            {
                method: "POST"
            }
        );


        if (!result.success) {

            throw new Error(
                result.message || "姿态控制失败"
            );
        }


        showMessage(
            result.message || "姿态指令已发送"
        );

        await refreshStatus();

    } catch (error) {

        showMessage(
            error.message || "姿态控制失败"
        );
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

                body: JSON.stringify({
                    enabled: enabled
                })
            }
        );


        if (!result.success) {

            throw new Error(
                result.message || "设备控制失败"
            );
        }


        showMessage(
            result.message || "设备设置已更新"
        );

        await refreshStatus();

    } catch (error) {

        showMessage(
            error.message || "设备控制失败"
        );
    }
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

    refreshDailyStats();

    refreshRecords();
}


refreshAll();


setInterval(refreshStatus, 1000);

setInterval(refreshSummary, 5000);

setInterval(refreshTodayStats, 5000);

setInterval(refreshDailyStats, 30000);

setInterval(refreshRecords, 10000);
