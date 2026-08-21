# Problem Rating

使用 Codeforces 比赛提交记录，研究用户 rating、题目官方 rating 与解题耗时的关系，并据此估计题目难度。

## 目录结构

- `src/problem_rating/`: Python 源代码。
- `data/raw/api_cache/`: Codeforces API 响应缓存。
- `data/processed/`: 清洗和汇总后的训练数据集。
- `outputs/analysis/`: 单场比赛分析生成的 CSV 文件。
- `outputs/plots/`: 图表等可视化结果。
- `docs/`: 补充文档；[Codeforces API 参考](docs/api.md) 位于此目录。

## 当前算法

### 1. 数据采集

`collect_training_data` 获取最近 100 场已结束的常规 Codeforces 比赛，明确排除名称中标记为 `Div. 3` 或 `Div. 4` 的比赛，以及 `contest.ratingChanges` 没有有效赛后 rating（`newRating`）记录的 unrated 比赛。对于每一场比赛：

- 读取带官方 rating 的题目；
- 从 `contest.ratingChanges` 取得用户赛后 rating（`newRating`）；
- 从 `contest.status` 取得提交，仅保留正式参赛者（`participantType == "CONTESTANT"`）；
- 为每个“用户-题目”对写入一条训练样本：`userRating`、`problemRating`、`timeConsumed`（秒）和该场比赛的 `contestDurationSeconds`。

### 2. 解题用时计算

对于同一用户的提交，程序按提交时间正序处理，并只使用每题第一次 AC。当前实现不再依赖第一次提交时刻，而是记录此前最近三次不同题目族的 AC 边界：

$$
\Delta_k(p) = t_{\text{AC}}(p) - t_{\text{prev},k}(p), \qquad k=1,2,3
$$

不足 $k$ 个边界时使用比赛开始时刻，并额外记录边界是否存在。题号会忽略末尾数字比较，例如 `F1` 和 `F2` 视为同一题目族。兼容接口 `calculate_problem_times` 返回 $\Delta_1$；实验特征同时保留 $\Delta_1,\Delta_2,\Delta_3$。

### 3. 训练模型

`unified_model` 对训练数据执行以下筛选与拟合：

- 保留 $R \ge 1600$ 且 $0 < T \le L$ 的样本，其中 $L$ 为该条样本所属比赛的 `contestDurationSeconds`；
- 对 $\ln(T)$ 使用全局 IQR 规则移除离群值；
- 可选：按题目 rating 分桶，对样本过多的 rating 随机下采样至 `max(该桶样本数中位数, 100)`，降低题目难度分布不均衡的影响；默认关闭，使用 `--balance-difficulties` 开启。
- 使用 scikit-learn 的普通最小二乘 `LinearRegression` 拟合：

$$
\ln(T) = b_0 + b_1 R + b_2 D
$$

其中 $T$ 为秒，$R$ 为用户赛后 rating，$D$ 为题目官方 rating。训练完成后，模型系数会写入 `outputs/models/time_model.json`，供单场难度估计使用。脚本也会拟合并报告对照模型：

$$
\ln(T) = c_0 + c_1(D - R)
$$

### 4. 单场难度估计

`evaluate_contest_difficulty` 对指定比赛中的每道题，使用 rating 不低于 1600 的正式参赛者。为防止极短时间导致不稳定，先令 $T = \max(T, 60)$ 秒。

当前实现加载 `unified_model` 最近一次训练写入的模型系数：

$$
\ln(T) = b_0 + b_1R + b_2D
$$

对每个有效“用户-题目”记录反解：

$$
D = \frac{\ln(T) - b_0 - b_1R}{b_2}
$$

某题的最终估计难度为全部有效用户估计值的中位数，并与 Codeforces 官方 rating 一起输出。

## 运行

从项目根目录执行，并确保 `src` 在模块搜索路径中：

```powershell
$env:PYTHONPATH = 'src'
python -m problem_rating.analyze_contest 2164
python -m problem_rating.collect_training_data
python -m problem_rating.unified_model
python -m problem_rating.unified_model --balance-difficulties
python -m problem_rating.evaluate_contest_difficulty 2164
python -m problem_rating.plot_results
python -m problem_rating.build_problem_features
python -m problem_rating.experiment_models
python -m problem_rating.experiment_models --suite advanced
```

`analyze_contest` 会将单场 CSV 写入 `outputs/analysis/`，并自动在 `outputs/plots/` 生成按题目的 rating-耗时图。

切换为赛后 rating 或比赛时长过滤后，需要依次重新运行 `collect_training_data` 和 `unified_model`，再执行 `evaluate_contest_difficulty`。

## 实验模型

`build_problem_features` 从 API 缓存生成一题一行的 `data/processed/problem_features.csv`。主要特征包括：

- 所有正式 rated 参赛者的二元 `solved` 结果；没有 AC 的记录统一作为未通过，不区分是否提交；
- 从 800 到 3500 的参考 rating，以每个参考值为中心上下 100 分计算重叠滑动窗口过题率；
- 每个窗口的参赛人数、过题人数、Jeffreys 平滑过题率及 logit；
- 同一组参考 rating 上的三角核、高斯核条件过题曲线，以及两参数单调 IRT 曲线；
- 不使用首次提交的 prev1–prev3 用时中位数、IQR、边界覆盖率和低尾异常率；
- 比赛时长、题目顺序、题目数量与队伍人数。

`experiment_models` 比较 Ridge、加性样条 GAM、浅层梯度提升、HistGradientBoosting 和 RBF-SVR；安装可选的 `catboost` 后还会加入 CatBoost。`--suite advanced` 只运行耗时较短的高级模型对比。实验同时报告按 contest 分组的交叉验证、最新 20 场的时间留出结果、训练耗时和稀疏样本切片。Ridge/GAM/SVR 的参数在每个训练折内部继续按 contest 分组选择；较慢的树模型大网格不纳入日常入口。该实验不会覆盖现有 `unified_model` 模型文件。
