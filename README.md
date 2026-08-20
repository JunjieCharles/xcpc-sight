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

`collect_training_data` 获取最近 100 场已结束的常规 Codeforces 比赛。对于每一场比赛：

- 读取带官方 rating 的题目；
- 从 `contest.ratingChanges` 取得用户赛前 rating（`oldRating`）；
- 从 `contest.status` 取得提交，仅保留正式参赛者（`participantType == "CONTESTANT"`）；
- 为每个“用户-题目”对写入一条训练样本：`userRating`、`problemRating` 和 `timeConsumed`（秒）。

### 2. 解题用时计算

对于同一用户的提交，程序按提交时间正序处理，并只使用每题第一次 AC。对题目 $p$：

1. 记录该题第一次提交时刻 $t_{\text{first}}(p)$ 与第一次 AC 时刻 $t_{\text{AC}}(p)$。
2. 找到此前最近一次 AC 的不同题目时刻 $t_{\text{prev}}$。题号会忽略末尾数字比较，例如 `F1` 和 `F2` 视为同一题目族，避免把它们互相作为切换题目的边界。
3. 定义开始时刻和用时：

$$
t_{\text{start}} = \min(t_{\text{first}}(p), t_{\text{prev}}), \qquad
T = t_{\text{AC}}(p) - t_{\text{start}}
$$

这个定义将某题的尝试开始时间与上一次完成其他题目的时间结合起来，近似描述连续解题过程中的实际耗时。

### 3. 训练模型

`unified_model` 对训练数据执行以下筛选与拟合：

- 保留 $R \ge 1600$ 且 $0 < T \le 18000$ 秒的样本；
- 对 $\ln(T)$ 使用全局 IQR 规则移除离群值；
- 按题目 rating 分桶，对样本过多的 rating 随机下采样至 `max(该桶样本数中位数, 100)`，降低题目难度分布不均衡的影响；
- 使用 scikit-learn 的普通最小二乘 `LinearRegression` 拟合：

$$
\ln(T) = b_0 + b_1 R + b_2 D
$$

其中 $T$ 为秒，$R$ 为用户赛前 rating，$D$ 为题目官方 rating。脚本也会拟合并报告对照模型：

$$
\ln(T) = c_0 + c_1(D - R)
$$

### 4. 单场难度估计

`evaluate_contest_difficulty` 对指定比赛中的每道题，使用 rating 不低于 1600 的正式参赛者。为防止极短时间导致不稳定，先令 $T = \max(T, 60)$ 秒。

当前实现采用最近一次训练得到的固定参数：

$$
\ln(T) = 6.7271 - 0.000847R + 0.001354D
$$

对每个有效“用户-题目”记录反解：

$$
D = \frac{\ln(T) - 6.7271 + 0.000847R}{0.001354}
$$

某题的最终估计难度为全部有效用户估计值的中位数，并与 Codeforces 官方 rating 一起输出。

## 运行

从项目根目录执行，并确保 `src` 在模块搜索路径中：

```powershell
$env:PYTHONPATH = 'src'
python -m problem_rating.analyze_contest 2164
python -m problem_rating.collect_training_data
python -m problem_rating.unified_model
python -m problem_rating.evaluate_contest_difficulty 2164
python -m problem_rating.plot_results
```

`analyze_contest` 会将单场 CSV 写入 `outputs/analysis/`，并自动在 `outputs/plots/` 生成按题目的 rating-耗时图。