# Problem Rating

根据参赛者 rating、逐题通过结果和首次 AC 顺序估计程序设计竞赛题目的难度 rating。训练目标是 Codeforces 官方题目 rating；模型也可以应用于具有稳定参赛者 rating 和逐题榜单的其他比赛。

## 当前主线算法

当前主线是：

> 高斯核条件过题曲线 + prev1–prev3 AC 间隔特征 + 浅层 GradientBoostingRegressor

它不把全场总过题率直接等同于难度。不同比赛的参赛者水平构成不同，因此模型先按参赛者 rating 描述“什么水平的人通过了这道题”，再结合通过者的解题顺序和用时信息预测题目 rating。

### 1. 训练数据与 rating 口径

`collect_training_data` 默认收集最近 100 场已结束的常规 Codeforces rated 比赛，排除名称中标记为 `Div. 3` 或 `Div. 4` 的比赛。`build_problem_features` 将数据整理为“一道题一行”的 `data-cache/problem-rating/data/processed/problem_features.csv`。

- 训练目标为题目的官方 `problemRating`；
- Codeforces 参赛者使用 `contest.ratingChanges` 中的赛后 `newRating`，使训练时的 rating 尽量接近部署时可取得的最新水平；
- XCPC 测试使用对应 series 全部比赛结束后的 `finalRating`；
- 只保留正式参赛数据，不把练习、虚拟参赛等记录混入样本。

使用最新 rating 是有意选择：模型最终应用时通常只能取得选手当前 rating，而不一定能恢复每场比赛当时的精确赛前状态。

### 2. 有效参赛者与未通过样本

参赛池按“是否实际参加整场比赛”确定：

- 整场没有任何提交活动的报名选手或队伍排除，不进入任意题目的分母；
- 只要整场存在提交活动，就作为该场的有效参赛者；
- 对单道题，未提交和提交后未通过统一记为 `solved = false`；
- 不设置独立的 `attempted` 特征：没交题不代表没有思考，比赛结尾的试探性提交也不能稳定代表真实尝试；
- 没有通过某题的参赛者会影响该题的条件过题曲线，但不会贡献 AC 时间特征。

Codeforces 以正式 rating 记录定义参赛身份；RankLand、牛客和 HDU 适配显式过滤非正式队伍及整场无提交队伍。XCPC 预测还要求队伍能够映射到已发布的最新 rating。

### 3. 高斯核条件过题曲线

模型在 800–3500、步长 100 的参考 rating 上构造条件过题曲线。对参考点 $c$ 和参赛者 rating $R_i$，使用带宽 100 的高斯权重：

$$
w_i(c)=\exp\left(-\frac{1}{2}\left(\frac{R_i-c}{100}\right)^2\right)
$$

加权通过数和参赛权重为：

$$
S(c)=\sum_i w_i(c)y_i,\qquad N(c)=\sum_i w_i(c)
$$

其中 $y_i\in\{0,1\}$ 表示是否通过。使用 Jeffreys 平滑得到有限的 logit：

$$
\mathrm{logit}(c)=\log\frac{S(c)+0.5}{N(c)-S(c)+0.5}
$$

同时记录有效样本量：

$$
N_{\mathrm{eff}}(c)=\frac{(\sum_i w_i(c))^2}{\sum_i w_i(c)^2}
$$

因此，同为 10% 的总过题率，如果通过者集中在 1200 分段或 2400 分段，模型会看到不同的曲线。有效样本量还能区分“可靠的低通过率”和“只有少量参赛者覆盖该 rating 区间”。

### 4. prev1–prev3 AC 间隔

时间特征不使用首次提交时间 $t_{\text{first}}$，因为并非所有平台都能稳定取得该字段。程序只保留每题第一次 AC，并计算此前最近三个不同题目族的 AC 边界：

$$
\Delta_k(p)=t_{\mathrm{AC}}(p)-t_{\mathrm{prev},k}(p),\qquad k=1,2,3
$$

- 不足 $k$ 个历史 AC 时，以比赛开始时刻为边界，并记录 `hasPrevK = false`；
- `F1`、`F2` 等末尾数字不同的拆分题视为同一题目族，不互相充当前序边界；
- 时间间隔最小截为 60 秒后取对数，减弱同时开题、连续提交等极短记录的影响；
- 只汇总 rating 不低于 1600 的通过者时间，降低低水平选手随机行为带来的噪声；
- 每个 $k$ 使用对数时间中位数、IQR 和边界存在率，而不是依赖单个选手记录；
- 额外记录通过者 rating 的中位数、IQR，以及 prev1 小于 60/120 秒的比例。

时间样本很少时，这些统计量仍可能跳动。例如少数通过者的 `solverRatingIqr` 跨过树分裂阈值，可能产生十几分的预测差异。因此原始预测中的小差值不应被解释为严格的题目次序。

### 5. 其他主线特征

除条件过题曲线和 prev 特征外，模型还使用：

- 有效参赛者总数及各 rating 中心的有效样本量；
- 该场题目总数；题号和题目在比赛中的位置不进入模型，避免把 Codeforces 题号顺序的难度先验迁移到 XCPC；
- 比赛时长；
- 极短 prev1 间隔比例。

离线特征表仍保留 `problemOrder` 作为审计字段，但 `prepare_features` 不把它加入任何模型特征族。因而题号、字母顺序或出题人排列不能改变预测；同场比赛中其他模型输入完全相同的题目会得到相同结果。

`teamSizeMedian` 不进入模型，训练特征和 XCPC 预测特征也不再生成该字段。部分比赛无法可靠取得完整队伍规模，不能让该上游字段成为训练或部署依赖；已有旧版 `problem_features.csv` 即使仍保留该列，`prepare_features` 也会忽略它。

移除前后的同切分对比表明该字段没有稳定收益：

| 版本 | 输入列数 | 分组交叉验证 MAE | 最新 20 场 MAE |
|---|---:|---:|---:|
| 包含 `teamSizeMedian` | 73 | 54.539 | 61.545 |
| 移除 `teamSizeMedian` | 72 | 54.557 | 61.395 |

交叉验证变化为 +0.018 rating，时间留出反而改善 0.150 rating，均远小于模型本身的误差和切分波动。

当前主线不直接输入原始 `solvedCount` 或全场总过题率，也没有施加“通过人数越多，预测必须越简单”的单调约束。总通过人数仍会通过各 rating 区间的条件过题曲线间接影响预测，但它不是唯一依据。

### 6. 浅层梯度提升模型

缺失值先使用训练集特征中位数填充，并增加缺失指示变量。回归器配置为：

```python
GradientBoostingRegressor(
    n_estimators=200,
    learning_rate=0.03,
    max_depth=2,
    min_samples_leaf=8,
    loss="huber",
    random_state=42,
)
```

浅层树可以学习条件过题曲线、时间和比赛元数据之间的非线性交互，同时通过深度和叶节点样本数控制复杂度。模型输出连续 rating，不强制取整到 100；实际阅读时，十几分的差异通常没有显著意义。

### 7. 验证方式与当前结果

验证必须按整场比赛切分，避免同一场不同题目的参赛者构成泄漏到训练折和测试折。当前同时报告：

- 5 折 contest-grouped cross-validation；
- 最新 20 场比赛的时间留出验证；
- 低/中/高难度以及稀疏时间样本切片。

当前浅层树结果：

| 验证范围 | MAE |
|---|---:|
| 按比赛分组交叉验证 | 54.5 |
| 最新 20 场时间留出 | 61.4 |
| Contest 2180 整场留出 | 53.0 |

这些误差意味着输出更适合解释为一个难度区间，而不是精确到个位的绝对值。

### 8. 特征重要性排行榜

2026-08-22 移除 `teamSizeMedian` 后，使用当前 `problem_features.csv` 的 718 道题、100 场比赛和主线模型的 72 列输入重新分析。所有切分继续以整场比赛为单位。这里同时使用两种口径：

- **分组打乱**：在每个测试折内把一组特征整体按行打乱，重复 20 次；MAE 增量表示当前已训练模型对该组的依赖程度。同组列使用同一个排列，以保留曲线内部形状。
- **删除重训**：删除整组特征后，用相同配置重新做 5 折训练；MAE 增量表示该组包含多少无法由其他特征替代的信息。最新 20 场也单独复核。

特征族按分组打乱的 MAE 增量排名如下：

| 排名 | 特征族 | 分组打乱 ΔMAE | 删除重训 ΔMAE | 最新 20 场删除重训 ΔMAE |
|---:|---|---:|---:|---:|
| 1 | 高斯条件过题曲线 logit（800–3500） | +845.82 ± 19.54 | +74.10 | +57.88 |
| 2 | prev3 AC 间隔（中位数、IQR、边界存在率） | +13.37 ± 0.69 | +0.14 | +0.60 |
| 3 | prev1 AC 间隔（中位数、IQR、边界存在率） | +11.11 ± 0.50 | +0.19 | -0.41 |
| 4 | prev2 AC 间隔（中位数、IQR、边界存在率） | +6.35 ± 0.38 | +0.07 | +0.12 |
| 5 | 通过者 Rating 分布（中位数、IQR） | +3.13 ± 0.40 | +0.22 | +0.38 |
| 6 | 极短 prev1 间隔比例 | +0.01 ± 0.02 | +0.07 | +0.01 |
| 7 | 曲线有效样本量及总参赛人数 | -0.00 ± 0.06 | -0.08 | -0.13 |
| 8 | 比赛结构元数据（题数、时长） | -0.01 ± 0.01 | +0.04 | +0.12 |

结论分为两个层次：

1. **条件过题曲线是唯一稳定且不可替代的核心特征。** 删除它后，分组交叉验证 MAE 从 54.56 上升到 128.66，最新 20 场从 61.39 上升到 119.28。
2. **时间特征是当前模型实际使用的局部修正项，但独立增益很小。** 打乱 prev1–prev3 会明显破坏已学习的交互；重新训练后，过题曲线可以替代其中大部分信息。除过题曲线外，各组删除重训的变化都小于 1 rating，并且在不同折或时间留出上可能变号，因此第 2–8 名不应解释为稳定的精确优劣。

若把曲线拆成单列，分组打乱的重要性前十名全部是条件过题 logit：

| 排名 | 单列特征 | 打乱 ΔMAE |
|---:|---|---:|
| 1 | `gaussianSolveLogitR2000` | +112.84 |
| 2 | `gaussianSolveLogitR1900` | +107.74 |
| 3 | `gaussianSolveLogitR1700` | +74.87 |
| 4 | `gaussianSolveLogitR2100` | +74.06 |
| 5 | `gaussianSolveLogitR1800` | +52.63 |
| 6 | `gaussianSolveLogitR1600` | +50.30 |
| 7 | `gaussianSolveLogitR2200` | +33.74 |
| 8 | `gaussianSolveLogitR1300` | +19.66 |
| 9 | `gaussianSolveLogitR1000` | +19.47 |
| 10 | `gaussianSolveLogitR2700` | +15.59 |

非曲线单列中前三名是 `logTimePrev1Median`（+8.76）、`logTimePrev3Median`（+7.58）和 `logTimePrev2Median`（+6.17）。相邻 rating 中心的曲线点高度相关，树还会在它们之间替换分裂，因此单列名次只用于定位模型最常利用的区间，不能解释为因果贡献或稳定的精确顺序。分组打乱还会制造“时间统计来自一道题、过题曲线来自另一道题”的分布外组合，所以判断特征是否真正不可替代时，应以删除重训列为准。

完整结果已导出到：

- `data-cache/problem-rating/outputs/analysis/problem_rating_feature_importance.md`：完整 Markdown 报告，包含运行元数据、全部特征族、删除重训逐折结果和全部 72 个单特征排名；
- `data-cache/problem-rating/outputs/analysis/problem_rating_feature_importance_groups.csv`：8 个特征族的机器可读结果；
- `data-cache/problem-rating/outputs/analysis/problem_rating_feature_importance_features.csv`：全部 72 个单特征的机器可读结果；
- `data-cache/problem-rating/outputs/analysis/problem_rating_feature_importance_folds.csv`：8 个特征族在 5 个测试折上的 40 条删除重训明细。

这些文件属于本地分析产物，随 `data-cache/problem-rating/` 一起被 Git 忽略，不进入静态站点发布数据。

## 运行主线流程

从项目根目录执行，并确保 `src` 在模块搜索路径中：

```powershell
$env:PYTHONPATH = 'src'

# 获取/更新 Codeforces 训练数据与缓存
python -m problem_rating.collect_training_data

# 从缓存生成一题一行的主线特征
python -m problem_rating.build_problem_features

# 运行基线、主线和挑战模型验证
python -m problem_rating.experiment_models
python -m problem_rating.experiment_models --suite advanced
```

实验入口不会覆盖旧 `unified_model` 的模型文件。

### XCPC series 预测

`predict_xcpc` 读取 `xcpc-sight` 发布的三个 series，以选手 `finalRating` 作为最新 rating，生成 2025–2026 ICPC + CCPC 16 场、牛客 10 场和 HDU 10 场的逐题预测。ICPC + CCPC 的队伍 Rating 定义为队内所有非教练选手 Rating 的最大值；适配器读取完整成员名单，并按 RankLand 的 `role=coach` 或姓名教练后缀排除教练，不依赖成员顺序。必须能映射全部队员，缺少任一成员时整队排除，不使用部分成员最大值：

```powershell
python -m problem_rating.predict_xcpc
```

默认输出：

- `data-cache/problem-rating/outputs/analysis/xcpc_problem_ratings.xlsx`：ICPC+CCPC、牛客、HDU 三个 sheet；
- `data-cache/problem-rating/outputs/analysis/xcpc_problem_ratings.md`：三个独立 Markdown 表格；
- `data-cache/problem-rating/outputs/analysis/xcpc_problem_ratings.csv`：包含 series 标识的完整数据。

牛客题名从公开 `contest/problem-list` 接口取得。RankLand SRK 与 HDU guest 榜单目前只提供题号；原始预测结果使用缺失说明，静态发布时将该说明规范化为空题名，不影响通过数和 rating 预测。RankLand 原始 SRK 缓存在 `data-cache/problem-rating/outputs/analysis/xcpc_cache/rankland/`，包含公开队员和逐题记录，不进入 Git。

### 静态站点发布

完成预测后，从默认 CSV 离线生成三个系列的题目 Rating 静态数据：

```powershell
python scripts/generate_problem_rating_static_data.py
```

默认发布：

- `static/data/problem-rating/index.json`：当前支持的 series 及相对路径；
- `static/data/problem-rating/series/2025-2026.json`；
- `static/data/problem-rating/series/nowcoder-summer-2026.json`；
- `static/data/problem-rating/series/hdu-summer-2026.json`。

`MODEL_ID`、`ProblemRatingRecord`、`project_problem_rating_series` 和 `project_problem_rating_index` 是 `problem_rating` 的公开纯 Python API。当前 `MODEL_ID` 为 `gaussian-prev1-3-shallow-gbr-no-order-no-team-size`，在发布文件中标识不使用题目位置和队伍规模的 72 列模型。投影以现有选手 Rating series 为比赛 ID、标题、时间和顺序的唯一规范来源，拒绝缺场、额外场次、重复题目、非法计数和跨 series 数据。文件仅包含场次元数据以及题号、题名、预测 Rating、通过队伍数、有效队伍数和时间样本数，不包含选手/队伍身份、team token 或逐人提交。

前端在三个 series 内提供“选手 Rating / 题目难度”切换，系列导航保持在页面左侧。题目页默认选择全部场次，图例始终列出所有场次，支持点击逐场切换以及快捷全选/全不选；2025–2026 ICPC + CCPC 额外提供“仅 ICPC”和“仅 CCPC”快捷筛选，点击后以对应组织的全部比赛替换当前选择。该系列的 16 场比赛发布独立短名供图例使用，例如 `ICPC 网络赛1`、`CCPC 哈尔滨`、`ICPC EC-Final` 和 `CCPC 总决赛`；图例只显示短名，不重复附加题目数量。曲线颜色按场次索引使用黄金角色相和交替明度确定性生成，筛选前后保持不变，并避免固定短色板循环造成重复。曲线本体使用透明宽命中带：悬停在两题之间时显示正式比赛场次名，悬停题目圆点时显示正式比赛场次名、题号和 Rating。表格通过“场次 + 题号”和 Rating 表头切换排序字段，再次点击同一表头切换正序/逆序。当前系列所有题名均为空时，表格隐藏整列题名；只要系列内存在题名则保留该列。通过队伍与有效队伍合并显示，时间样本不在界面展示。每场曲线先按预测 Rating 从易到难排序，Rating 相同按自然题号稳定排序；最长的已选曲线适配可用页面宽度，其他曲线按题目数量比例缩短。曲线使用保持单调的三次插值，圆点才是实际预测值，插值不代表新增模型数据。筛选和排序状态写入 URL。

## 其他模型与旧流程

- **GAM/Ridge**：作为平滑、较易解释的基线；高斯曲线 + prev1 GAM 的近期留出 MAE 为 64.8。
- **HistGradientBoosting**：整体 MAE 更低，但预测容易贴近训练标签的整百平台；当前作为挑战模型，不替换主线。
- **CatBoost、RBF-SVR、模型融合**：已纳入快速对比，当前没有稳定超过浅层树或 HistGradientBoosting。
- **三角核、滑动方窗、IRT**：用于比较条件过题曲线的表达方式，不是当前主线输入。
- **`unified_model` 线性时间模型**：早期兼容流程，通过 $\ln(T)$、用户 rating 和题目 rating 建模；`evaluate_contest_difficulty` 仍可读取其模型文件，但它不再代表当前主线。

旧流程和单场分析仍可运行：

```powershell
python -m problem_rating.unified_model
python -m problem_rating.evaluate_contest_difficulty 2164
python -m problem_rating.analyze_contest 2164
python -m problem_rating.plot_results
```

## 目录结构

- `src/problem_rating/`：特征、模型、验证和预测代码；
- `data-cache/problem-rating/data/raw/api_cache/`：Codeforces API 响应缓存；
- `data-cache/problem-rating/data/processed/`：训练数据与题目级特征；
- `data-cache/problem-rating/outputs/analysis/`：分析结果、CSV、Markdown 和 Excel；
- `data-cache/problem-rating/outputs/plots/`：图表；
- `data-cache/problem-rating/outputs/models/`：旧线性模型文件；
- `static/data/problem-rating/`：可发布的 ICPC+CCPC/牛客/HDU 题目级聚合 JSON；
- `doc/problem-rating-api.md`：Codeforces API 参考。

`data-cache/problem-rating/` 整体被 Git 忽略，不属于可发布数据。缓存来自 Codeforces 公共 API，可能包含公开账号 handle、比赛提交和榜单信息；不得在其中混入登录 Cookie、API 密钥或其他凭据。代码不会读取 `.env` 或把认证信息写入缓存。静态前端只读取 `static/data/problem-rating/` 下的聚合文件，不读取或复制本地缓存。

## 迁移与提交历史

该功能从本地 `problem-rating` 仓库迁入。源仓库 `master` 的 7 个提交作为当前仓库合并提交的第二父链保留，随后按本项目布局移动到 `src/problem_rating/`、`tests/problem_rating/` 和 `doc/`。源仓库的编辑器配置及重复的顶层抓取脚本未纳入最终工作树；可执行实现以 `python -m problem_rating.fetch_data` 及上文各模块入口为准。

## 测试覆盖与限制

聚焦测试覆盖 AC 顺序与拆分题族、滑窗/核/IRT 特征、未提交样本口径、题目位置和 `teamSizeMedian` 特征排除、预测特征不依赖队伍规模、模型集成门控、XCPC 标识稳定性、本地路径隔离、静态投影、缺失题名规范化和离线生成。Node 测试覆盖 schema（含空题名）、场次筛选、两类双向排序、自然题号、曲线难度顺序、题量比例、单调路径、URL 状态和独立数据加载。默认测试只读取构造数据，不访问网络，也不依赖已同步的本地缓存。模型精度数字来自当前离线训练特征的重新验证；静态发布不会重新训练模型。
