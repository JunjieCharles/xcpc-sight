# xcpc-sight

[在线页面](https://junjiecharles.github.io/xcpc-sight/)

用于 ICPC/CCPC 竞赛前瞻与数据分析的轻量 Python 项目，提供选手与报名实体 Rating、题目难度预测、赛前前瞻和赛后复盘，也可通过纯 Python API 使用。

## 浏览站点

在线页面无需安装。选择系列后，可以查看 Rating 与参赛记录、搜索选手或学校，并在有数据的系列中切换题目难度、赛前前瞻和赛后复盘。

| 系列 | 已发布内容 |
| --- | --- |
| 2025–2026 ICPC + CCPC | 选手 Rating、题目难度 |
| 2026–2027 ICPC + CCPC | 三场网络赛选手 Rating、赛前前瞻和赛后复盘，以及西安站前瞻 |
| 2026 牛客暑期多校训练营 | 第一至第十场报名实体 Rating、题目难度 |
| 2026 HDU 暑期联赛 | CID 1229 至 1238 报名实体 Rating、题目难度 |

2026–2027 的三场网络赛为 ICPC 网络赛第一、第二场及 CCPC 网络预选赛。新增 [CCPC 长春站前瞻](https://junjiecharles.github.io/xcpc-sight/?series=2026-2027&view=preview&previewContest=ccpc-2026-changchun)，含 336 支队伍，正式赛时间为北京时间 2026 年 10 月 18 日 09:00–14:00（邀请函日程草案）。西安站前瞻不在主站比赛选择器中展示，请使用[直达链接](https://junjiecharles.github.io/xcpc-sight/?series=2026-2027&view=preview&previewContest=icpc-2026-xian)。本赛季尚未发布题目难度。

前瞻支持排序、学校筛选，以及悬浮或键盘聚焦查看成员评分和历史战绩；复盘可切换指标查看预测与实际排名的符合度。前瞻为赛前静态快照，不会随赛后结果自动更新。不同场次的聚合口径见[前瞻说明](doc/season-2026-2027-preview.md)，复盘统计口径见[复盘说明](doc/post-contest-review.md)。

Rating 仅适合在同一系列内比较，不与 Codeforces 等平台 Rating 对标。两个 ICPC + CCPC 赛季分别来自 RankLand 的 icpc2025 / ccpc2025 和 icpc2026 / ccpc2026，排除邀请赛、保留区域赛，按上海本地日期排序；每个赛季从 1400 独立起算。牛客和 HDU 以报名实体计分，不视为个人身份。

## 本地安装与浏览

需要 Python 3.11 或更高版本。在仓库根目录执行：

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e .
```

以上使用 Windows 虚拟环境路径；macOS / Linux 对应为 `.venv/bin/python`。后续命令中的 python 应使用该虚拟环境解释器。

仅浏览仓库已有的静态数据，无需重新获取榜单或训练模型：

```bash
python -m http.server 8000 --directory static
```

打开 http://localhost:8000/。浏览器通过 HTTP 加载 ES modules 和 JSON，不能直接用 `file://` 打开。站点没有 npm 依赖或构建步骤，可直接部署整个 `static/` 目录。

按需安装额外依赖：

```bash
# 题目难度训练、验证与预测
python -m pip install -e ".[problem-rating]"

# 从 XLSX 导入前瞻名单
python -m pip install -e ".[preview]"
```

## 生成与更新数据

### 选手与报名实体 Rating

```bash
python scripts/generate_static_data.py
```

默认生成 `static/data/index.json` 与四个 Rating 系列，并复制已提交的前瞻、名单和复盘快照；可用 `--output-dir` 指定输出目录。该命令访问实时 RankLand、牛客和 HDU，结果可能随上游更新；HDU 需要登录会话，准备方式见 [HDU 数据说明](doc/hdu-data.md)。该命令不会联网刷新前瞻名单。

### 题目难度

先按[题目难度文档](doc/problem-rating.md)完成训练与预测，再从本地预测 CSV 离线生成站点数据：

```bash
python scripts/generate_problem_rating_static_data.py
```

默认写入 `static/data/problem-rating/` 下的索引及三个系列文件，不修改选手 Rating 数据。发布内容仅包含题目级聚合数据，不包含账号、队伍或逐人提交记录。现有预测结果保留原产物；后续预测使用新的队伍归一化 LSE 聚合，详见设计文档中的模型与数据口径。

### 赛前前瞻与赛后复盘

前瞻按指定场次和名单更新。名单导入、评分来源、历史战绩补充以及西安站参数见[前瞻生成说明](doc/season-2026-2027-preview.md)。学校别名和更名维护在 [config/school-aliases.json](config/school-aliases.json)，生成器默认读取该文件，`--school-aliases` 可指定其他本地文件；格式见[学校别名说明](doc/school-aliases.md)。

```bash
python scripts/generate_review_data.py
```

默认下载指定版本的首场 SRK，校验 SHA-256 后生成 `static/data/reviews/2026-2027.json`，不刷新赛前评分或索引。使用 `--srk` 可离线生成；其他场次参数、官方移除队伍的映射与匹配规则见[复盘生成说明](doc/post-contest-review.md)。

### 其他数据工具

```bash
# 获取牛客 133876 至 133885 的完整赛时榜单
python scripts/fetch_nowcoder_leaderboards.py

# 从已缓存的官方 NOI 表格生成逐年标准化数据
python scripts/normalize_noi_awards.py
```

牛客榜单默认写入 `data-cache/nowcoder/`，脚本支持自定义比赛 ID 和 `--output-dir`。NOI 工具读取 `data-cache/noi/`，输出其 `normalized/` 子目录；这些本地数据不发布到静态站点。IOI 中国选手成绩快照位于 `data-cache/ioi/`，只覆盖提供的名单，不代表当届完整成绩。

数据契约与参数见[牛客榜单](doc/nowcoder-data.md)、[NOI 获奖名单](doc/noi-data.md)和 [IOI 成绩快照](doc/ioi-data.md)。`data-cache/` 由 Git 忽略，本地缓存和输入文件不会随仓库提供。

## Python API

发行名称为 `xcpc-sight`，安装后从 `core`、`rating`、`problem_rating` 导入，不提供 `xcpc_sight` facade。在线加载赛季并计算：

```python
from core import RankLandClient, load_2025_2026_season
from rating import calculate_series_ratings, project_series_rating_data

with RankLandClient() as client:
    season = load_2025_2026_season(client)

result = calculate_series_ratings(season.contests)
document = project_series_rating_data(
    result,
    series_id="2025-2026",
    title="2025–2026 ICPC + CCPC",
)
print(len(document["contests"]), len(document["competitors"]))
```

也可自行构造 `Contest`/`TeamResult` 后调用 `calculate_contest_ratings` 或 `calculate_series_ratings`，从而完全脱离网络运行。`TeamResult.penalty` 使用非负毫秒；Rating 会忽略调用方提供的 `rank`，过滤非正式或无提交活动的队伍，并按 `solved` 降序、`penalty` 升序重建名次。需要单独标准化比赛时可调用 `rebuild_competition_ranks`。传入 `initial_ratings` 可从指定状态开始；默认新选手为 1400。为 `Contest.unrated_reason` 提供非空原因可只记录本场排名，所有参赛者的 rating 变化均为 0。

队伍聚合可使用 `rating.normalized_lse_rating`，计算 `400 * log10(mean(10 ** (R / 400)))`；空输入返回 `None`，调用方需过滤缺失成员。完整计算规则见 [Rating 规则](doc/rating-rules.md)。

学校别名可通过 `core.load_school_aliases(path)` 加载，再传给 `DefaultNormalizer(school_aliases=...)`。复盘纯 API `core.project_review_contest(preview, contest, *, normalizer=None, overrides=None, removed_results=None)` 负责队伍关联与结果投影；官方移除的队伍须通过 `removed_results` 显式提供映射。

静态索引 API `rating.project_static_data_index` 支持 `p`review_publications`` 和 review_publications，可登记同系列多份前瞻与复盘入口。库 API 不隐式写文件；输出由脚本显式完成。数据获取、模型和字段契约见[设计文档索引](doc/README.md)。

## 项目导航

| 路径 | 内容 |
| --- | --- |
| `src/core/` | 数据获取、标准化、领域模型与赛季选择 |
| `src/rating/` | 选手与报名实体 Rating、静态 JSON 投影 |
| `src/problem_rating/` | 独立的题目难度模型、预测与静态 JSON 投影 |
| `scripts/` | 数据获取与生成命令 |
| `static/` | 无需构建的前端与发布数据 |
| `config/` | 学校别名等本地配置 |
| `data-cache/` | Git 忽略的上游缓存和本地数据 |
| `doc/` | 功能设计、详细规则和数据契约 |
| `tests/` | 离线回归测试与精简样例 |

开发代理的工作约束、测试命令与文档同步要求集中在 [AGENTS.md](AGENTS.md)。
