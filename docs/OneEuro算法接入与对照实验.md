# 1€ Filter 算法接入与对照实验

实施日期：2026-11-22。当前树莓派程序默认使用 `one_euro`，原有 `moving_average` 方案保留作为对照。本次只更换特征平滑步骤，未改变 MediaPipe 模型、0.15 判定阈值、个人校准与同类异常连续 5 秒提醒的规则。

## 1. 论文依据与实现边界

依据 Casiez、Roussel、Vogel 的 CHI 2012 论文 **1€ Filter: A Simple Speed-based Low-pass Filter for Noisy Input in Interactive Systems**，DOI：10.1145/2207676.2208639。

[论文原文](https://gery.casiez.net/publications/CHI2012-casiez.pdf) · [作者算法与实现页面](https://gery.casiez.net/1euro/)

项目在 `edge/one_euro.py` 中独立实现论文附录 A 的标量滤波形式：平滑速度估计，速度越大则提高截止频率，再对输入作一阶低通滤波。导数采用附录算法的“当前输入减上次滤波输出”，并按实际时间间隔计算。

重复/倒退时间戳处理、跟踪间断重置、校准初始化与样本记录属于本项目工程处理，不是新增算法理论。当前参数尚未通过真人数据选优，不应宣称坐姿识别准确率已经提升。

## 2. 算法放在哪里

```text
摄像头 → MediaPipe关键点 → 原始坐姿特征
                              ↓
                 1€ Filter 或 5帧均值（二选一）
                              ↓
                 与个人基准比较 → 分类 → 持续提醒
```

三个标量 `head_drop`、`shoulder_tilt`、可选 `body_lean` 分别拥有自己的滤波状态。不会在 1€ Filter 后再套一层 5 帧均值。髋部不可见时，`body_lean` 滤波器单独重置并返回空值，不使用旧髋部信息。

## 3. 计算逻辑与初始参数

设实际采样间隔为 `dt`，上次滤波结果为 `x_prev`：

```python
alpha = 1 / (1 + 1 / (2 * pi * cutoff * dt))
speed = (x - x_prev) / dt
filtered_speed = alpha_d * speed + (1 - alpha_d) * previous_speed
cutoff = min_cutoff + beta * abs(filtered_speed)
filtered_x = alpha * x + (1 - alpha) * x_prev
```

其中 `alpha_d` 用 `d_cutoff` 计算，最终 `alpha` 用自适应的 `cutoff` 计算。这里是公式说明，实际实现会验证参数与时间间隔。

| 参数 | 当前初始值 | 含义 |
| --- | --- | --- |
| `min_cutoff` | 1.0 Hz | 低速时的最低截止频率；降低通常更平滑，但延迟更大 |
| `beta` | 0.5 | 速度对截止频率的影响；增大通常让快速变化响应更积极 |
| `d_cutoff` | 1.0 Hz | 速度估计本身的平滑截止频率 |
| `max_gap` | 2.0 秒 | 超过此间隔重新初始化，避免跨跟踪间断插值 |

这些数值是针对本项目相对特征尺度的初始设置，不是论文对本项目给出的最佳参数。调参时应在开发数据上选择，再用独立人员或会话验证。

工程边界：

- 首个样本直接初始化，不从 0 缓慢漂移到实际值。
- 重复或倒退时间戳不会再次推进滤波状态。
- 非有限数值和无效参数会被拒绝，避免污染滤波状态。
- 关键点丢失、校准重置或跟踪间隔过长会清除相关平滑状态。
- 正常校准成功后，用同一个基准和时间初始化两种方案，便于可重复对照。
- 样本可显式提供时间戳，使离线回放的滤波、分类和 5 秒提醒按记录时间运行，而不是按回放执行速度运行。

## 4. 主要代码

| 文件 | 内容 |
| --- | --- |
| [edge/one_euro.py](../edge/one_euro.py) | 标量 1€ Filter、参数验证、初始化及间断处理 |
| [edge/posture_judge.py](../edge/posture_judge.py) | 两种平滑方式选择、校准后初始化、分类与时间戳接入 |
| [main.py](../main.py) | 默认启用及启动参数 |
| [services/runtime.py](../services/runtime.py) | 发布当前平滑配置、原始/滤波特征与差值 |
| [采样工具](../tests/manual/collect_posture_samples.py) | 采集带基准、时间戳和参数的原始特征 |
| [回放工具](../tests/manual/compare_posture_filters.py) | 将同一组原始数据输入两种平滑方案 |
| [算法测试](../tests/test_one_euro.py) | 手算结果、时序、缺失、分类、提醒与 CSV 回放一致性 |

`GET /api/status` 新增 `posture_smoothing` 和 `posture_features`。前者记录方法、参数和适用窗口；`one_euro` 的 `window` 为空，`moving_average` 为 5。后者包含原始特征、滤波结果及用于分类的差值。网页显示当前方法。

## 5. 运行、调整与切回对照

手动运行前先停止后台服务，避免争用摄像头：

```bash
cd /home/hyz/smart_desk
systemctl --user stop smart-desk.service

# 当前默认方案；这组参数尚待真人调优。
.venv-pi/bin/python -u main.py --headless --smoothing one_euro --filter-min-cutoff 1.0 --filter-beta 0.5 --filter-d-cutoff 1.0

# 前台按 Ctrl+C 退出后，可用下面的命令测试均值方案。
.venv-pi/bin/python -u main.py --headless --smoothing moving_average

# 前台退出后恢复默认后台服务。
systemctl --user start smart-desk.service
```

每次更换方法或重启后重新校准。不要同时运行这两条前台命令。也可用 `SMART_DESK_SMOOTHING=moving_average` 设置进程默认方法；命令行 `--smoothing` 优先于环境变量，后台服务需通过自己的配置设置环境，不能仅在交互终端 export 后就认为已改变后台进程。

## 6. 真人采样与同输入回放

采样脚本需要独占摄像头，暂停网页服务后操作；每次运行先自然坐正，看到 `SAMPLE_START` 后才执行目标动作。

```bash
cd /home/hyz/smart_desk
systemctl --user stop smart-desk.service
.venv-pi/bin/python -u -m tests.manual.collect_posture_samples --label NORMAL --seconds 20
.venv-pi/bin/python -u -m tests.manual.collect_posture_samples --label "HEAD DOWN" --seconds 20
systemctl --user start smart-desk.service

# 回放不占用摄像头，可在后台服务运行时执行。
.venv-pi/bin/python -m tests.manual.compare_posture_filters --input docs/test-results/posture_filter_samples.csv --output docs/test-results/recorded_comparison.csv --summary docs/test-results/recorded_comparison.json
```

默认 CSV 现为 `posture_filter_samples.csv`，与旧格式分开。新增 `run_id`、基准与基准时间、逐帧时间、原始肩髋特征、滤波输出和参数，不能把旧的平滑后差值文件直接当作原始信号回放。

回放为两个方法使用同一组输入、时间、基准和分类阈值；输出两组滤波结果、类别及提醒。它不会把操作者声明的动作当作逐帧真实标签，也不会自动给出真人准确率；需要人工标记实际动作区间再评估。

## 7. 合成对照结果

可以不占用摄像头，直接运行可重复的合成示例：

```bash
.venv-pi/bin/python -m tests.manual.compare_posture_filters --demo --output docs/test-results/one_euro_demo.csv --summary docs/test-results/one_euro_demo.json
```

本次示例固定随机种子、10 Hz 采样、200 个点，使用带噪声的正常/低头阶跃信号；它不是人体或医学实验。

| 指标 | 5 帧均值 | 1€ Filter |
| --- | --- | --- |
| 静止区间头部特征 RMS，越小越好 | 约 0.00749 | 约 0.00809 |
| 阶跃后首次分类为低头的延迟 | 约 0.10 秒 | 此采样网格上为 0.00 秒 |

这组初始参数响应较快，但静止抖动略高，不能由此得出整体优于均值平滑。0.00 秒只表示在阶跃发生的那个采样点超过阈值，不是物理系统零延迟；真实摄像头、推理、网页刷新和 5 秒提醒仍有耗时。

[合成结果 JSON](test-results/one_euro_demo.json) · [逐点对比 CSV](test-results/one_euro_demo.csv)

## 8. 已执行验证与尚缺证据

- 本地与树莓派各 27 项 Python 回归通过，包括公式手算、固定/自适应截止、重复/倒退时间戳、间断、校准、缺失髋部、5 秒提醒及 CSV 回放与在线决策一致性。
- 前端行为检查通过，包含当前算法名称显示。
- 真实模型从仓库图片提取有效特征后，完成 1€ Filter 校准与正常分类联调。
- 摄像头、模型和判断器连续处理 30 帧完成；该次画面没有有效人员特征，不能据此认定真人准确率或有人场景性能。
- 后台接口确认 `posture_smoothing.method=one_euro`，连续网页视频可读，原有 15 条记录、240 秒和 13 次提醒保持不变。
- 尚未完成多人的受控坐姿测试、真人滤波参数选择、长时间稳定性与算法加分验收；蜂鸣器、灯及 OLED 仍为模拟状态。

[部署验证记录](test-results/one_euro_deployment.json)。旧代码及数据库备份在树莓派 `/home/hyz/.local/share/smart-desk/backups/one-euro-20261122-221846/`。
