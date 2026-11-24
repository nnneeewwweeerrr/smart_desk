# 智学灯 —— 基于树莓派的智能学习姿势监测与提醒系统

利用摄像头采集学习者上半身画面，通过 MediaPipe 在本地完成人体关键点识别与坐姿判断，发现不良坐姿时通过蜂鸣器、OLED 和网页进行提醒，同时记录学习时长与提醒次数。

## 系统架构

```text
摄像头感知 → 边缘计算（坐姿判断 / 学习计时） → 设备反馈（蜂鸣器 / OLED）
                         ↓
                   SQLite 数据存储
                         ↓
                  Flask 网页管理界面
```

## 目录结构

```text
smart_desk/
├── main.py                     # 系统唯一启动入口
├── pose_landmarker_lite.task   # MediaPipe 姿势识别模型
├── requirements.txt            # PC 端运行依赖
├── perception/                 # 感知层：摄像头、关键点提取
│   ├── camera.py
│   └── posture.py
├── edge/                       # 边缘计算层：坐姿判断、学习计时
│   ├── posture_judge.py
│   └── study_timer.py
├── control/                    # 控制层：蜂鸣器、OLED（当前为模拟模式）
│   ├── buzzer.py
│   └── oled_display.py
├── services/                   # 公共服务：全局状态、视频帧缓存
│   ├── state_manager.py
│   └── video_stream.py
├── communication/web_app.py    # Flask 服务与 HTTP API
├── data/                       # SQLite 数据库
│   ├── database.py
│   └── smart_desk.db
├── web/                        # 前端页面
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
├── tests/
│   ├── manual/                 # 开发阶段的手工测试脚本
│   └── assets/                 # 测试用图片
└── docs/archive/               # 历史目录树导出（仅存档，不参与运行）
```

## 运行方式

Windows PowerShell：

```powershell
cd D:\workspace\smart_desk
.\.venv\Scripts\Activate.ps1
python -m main
```

启动后在浏览器打开 <http://127.0.0.1:5000>。

注意：

- 启动 `main.py` 后不要再单独运行 `communication/web_app.py`，否则会重复启动服务并争用摄像头。
- 退出请使用键盘 `q` 或 `Ctrl+C`，让摄像头、数据库等资源正常释放。

### 键盘快捷键

| 按键 | 功能 |
|---|---|
| C | 正常坐姿校准 |
| R | 重置校准，重新等待校准 |
| S | 开始 / 继续学习 |
| P | 暂停计时 |
| T | 保存记录并重置计时 |
| Q | 退出程序 |

## HTTP API

| 接口 | 方法 | 用途 |
|---|---|---|
| `/` | GET | 网页首页 |
| `/video_feed` | GET | MJPEG 实时视频流 |
| `/api/status` | GET | 系统实时状态 |
| `/api/summary` | GET | 累计学习统计 |
| `/api/today_stats` | GET | 今日学习统计 |
| `/api/daily_stats` | GET | 最近 7 天学习趋势 |
| `/api/records` | GET | 历史学习记录 |
| `/api/device/light` | POST | 台灯开关，body：`{"enabled": true}` |
| `/api/device/buzzer` | POST | 蜂鸣器开关，body：`{"enabled": true}` |
| `/api/timer/<start\|pause\|reset>` | POST | 学习计时控制 |
| `/api/posture/<calibrate\|reset_calibration>` | POST | 坐姿校准控制 |
| `/api/health` | GET | 服务健康检查 |

## 坐姿状态取值

后端 `posture` 字段可能取值：

| 取值 | 含义 |
|---|---|
| `NORMAL` | 坐姿正常 |
| `HEAD DOWN` | 低头 |
| `TILT LEFT` | 身体向左倾斜 |
| `TILT RIGHT` | 身体向右倾斜 |
| `LEAN FORWARD` | 身体前倾（需要髋部关键点可见） |
| `WAIT CALIBRATION` | 尚未建立正常坐姿基准 |
| `KEYPOINTS NOT CLEAR` | 关键点不清晰或未检测到人员 |
| `unknown` | 初始状态 |

异常姿势连续保持 5 秒后触发提醒，触发一次后需恢复再重新计时。

## 手工测试脚本

当前主程序默认启用论文 1€ Filter 特征平滑；`--smoothing moving_average` 可切回 5 帧均值对照。算法、参数、真人采样与同输入回放说明见 [OneEuro 算法接入与对照实验](docs/OneEuro算法接入与对照实验.md)。初始参数尚未通过真人数据选优。

控制与数据修复、校准执行回执及最新验证结果见 [代码补全执行记录](docs/代码补全执行记录.md)。逻辑回归可以执行 `python -m unittest discover -s tests -p "test_*.py" -v`，不占用真实摄像头；前端行为检查为 `node tests/test_web_ui.cjs`。

新记录保存 `study_seconds`，`reminder_count` 为当前学习会话提醒次数，进程累计值为 `total_reminder_count`。每日统计按会话开始日期归档，跨午夜不拆分自然日。旧库会自动增加秒数字段，历史上未保存的秒数无法恢复。

`tests/manual/` 下是开发阶段用于排查摄像头、MediaPipe 和姿态判断的脚本，不参与正式运行。需要在项目根目录执行，例如：

```powershell
python -m tests.manual.test_camera_again
python -m tests.manual.test_posture
```

## 树莓派部署提醒

树莓派 4 已补充独立环境与无窗口运行方案，详见 [树莓派部署与运行](docs/树莓派部署与运行.md)。该设备使用 `.venv-pi`（Python 3.11 / MediaPipe 0.10.18），依赖由 `requirements-pi.lock` 锁定；原有 `.venv` 保留。运行入口为：

```bash
.venv-pi/bin/python -u main.py --headless
```

已有后台服务时请先停止服务，再手动启动，避免争用摄像头。`SMART_DESK_DB_PATH` 可指定独立测试数据库，默认仍使用 `data/smart_desk.db`。

- `Buzzer`、`OLEDDisplay` 目前仅实现软件模拟；真实 GPIO / I2C 驱动仍需编写和实机联调，仅改 `mock=False` 不会驱动外设。
- MediaPipe 在 ARM 上的可用版本与 PC 不同，请按树莓派系统实际支持版本安装。
- 若帧率偏低，可优先降低摄像头分辨率，再考虑降低识别频率。
