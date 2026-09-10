# xcpc-sight

[在线页面](https://junjiecharles.github.io/xcpc-sight/)

用于 ICPC/CCPC 竞赛前瞻与数据分析的轻量 Python 项目。当前版本提供：

- 从 RankLand public v2 获取并解析 SRK 榜单；
- 获取并完整导出牛客赛时榜单，并将完赛榜单按报名实体接入 rating；
- 通过登录会话获取 HDU 榜单元数据与 UTF-8 CSV，并按稳定 team token 接入 rating；
- 对所有来源统一过滤无提交队伍，并按题数、罚时重建含并列的比赛排名；
- 定义 `icpc2025` + `ccpc2025` 的 2025–2026 赛季；
- 定义 `icpc2026` + `ccpc2026` 的 2026–2027 赛季，并提供独立的“赛前前瞻”和“赛后复盘”；
- 前瞻队名悬浮展示上赛季区域赛/总决赛、排名、历史队名及队员重合比例，支持键盘聚焦；离线补充命令与 `--history-srk-root` 参数见 [前瞻设计文档](doc/season-2026-2027-preview.md#队名悬浮比赛记录)；
- 发布 `2026牛客暑期多校训练营` 第一至第十场；
- 发布固定 CID `1229` 至 `1238` 的 `2026“钉耙编程”中国大学生算法设计暑期联赛`；
- 从空初始状态按比赛顺序计算个人或报名实体 rating；
- 以独立的 `problem_rating` 包训练、验证和预测题目难度 rating；
- 为静态站点生成确定、可复现的稀疏 JSON 数据；
- 提供零依赖、无需构建的选手 Rating、题目难度、赛前前瞻与赛后复盘浏览前端；
- 可复用的纯 Python API。

## 安装

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
```

需要 Python 3.11 或更高版本。

题目难度模型依赖 NumPy、pandas、SciPy 和 scikit-learn 等科学计算包；只使用原有选手 rating 功能时无需安装。运行完整题目 rating 流程前安装对应 extra：

```bash
.venv/Scripts/python -m pip install -e ".[problem-rating]"
```

## 使用

在线加载赛季并计算：

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

学校别名与更名直接维护在 [config/school-aliases.json](config/school-aliases.json)，已完整纳入 658 个学校条目、730 个别名。前瞻和复盘生成器默认读取该文件，不依赖线上列表；`--school-aliases` 可指定其他本地文件。程序中通过 `core.load_school_aliases(path)` 加载后传给 `DefaultNormalizer(school_aliases=...)`。格式、歧义处理和维护方法见 [学校别名设计](doc/school-aliases.md)。

生成静态站点数据：

```bash
python scripts/generate_static_data.py
```

默认写入 `static/data/index.json`、四个 Rating series（含 2026–2027），并复制已提交的 `static/data/previews/2026-2027.json` 前瞻快照及已提交的复盘快照；可用 `--output-dir` 覆盖。系列按最新比赛或前瞻场次时间倒序排列，最新系列成为默认系列。前瞻不会在该命令中联网刷新。Rating 生成过程访问实时 RankLand、牛客和 HDU，不属于默认离线测试。

在完成 2025–2026 ICPC + CCPC、牛客和 HDU 题目预测后，可以从本地预测 CSV 离线发布独立的题目 Rating JSON：

```bash
python scripts/generate_problem_rating_static_data.py
```

默认写入 `static/data/problem-rating/index.json` 以及三个 series 文件。当前发布模型标识为 `gaussian-prev1-3-shallow-gbr-no-order-no-team-size`。该命令不访问网络，不修改选手 Rating JSON，也不会发布账号、队伍或逐人提交数据。ICPC + CCPC 队伍 Rating 定义为队内所有非教练选手最终 Rating 的最大值。

本地浏览静态站点（不能直接用 `file://`，因为浏览器需要通过 HTTP 加载 ES module 和 JSON）：

```bash
python -m http.server 8000 --directory static
```

然后打开 `http://localhost:8000/`。站点没有 npm 依赖、构建步骤或 `package.json`；可直接部署整个 `static/` 目录。2026–2027 系列已发布 ICPC 网络赛第一场的 7380 名选手 Rating，并提供两场赛前前瞻：第一场 2535 支、第二场 2636 支公开报名队伍，展示学校、中文队名、非教练成员、XCPC Rating、XCPC Elo、本仓库上赛季 Rating、CPC Finder 评分及队员奖牌总数；第二场在上赛季 Rating 后增加本赛季 Rating，标题区提供比赛选择下拉框，支持通过索引扩展多场次。评分列取队内最高值且不使用千分位，XCPC Rating 与 CPC Finder 固定两位小数（队伍值与队员明细一致），除 CPC Finder 外沿用各来源配色；各项 Rating 与奖牌值后以 `#x` 单行显示该项在全部队伍中的并列名次，各列为名次保留相同的窄槽，筛选不重新计算。无需提示图标，正常悬浮或键盘聚焦即可查看全员明细。CPC Finder 的零分显示为 `0.00`、缺失值显示为 `—`；零分参与该列排名与数值排序，缺失值无名次且始终置后；综合战力中两者仍同档、互不超过。综合战力统计每队在各项 Rating 和奖牌上分别严格超过的队伍数，将计数降序后按元组排序；第一场五维、第二场六维，该列显示全局名次并在悬浮时展示对应五边形或六边形雷达图，页面默认按此排序。所有表头均可双向排序，奖牌按金、银、铜依次捆绑排序。名单来源与数据来源分开显示，前瞻始终有独立 tab；桌面冻结紧凑的学校、队名和成员列，手机冻结进一步压缩的学校和队名、取消成员冻结。悬浮窗会根据视口空间显示在格子上方或下方，不被表格底部裁切。前瞻名单是外部静态快照，不来自 Pintia 比赛榜单，也不随比赛自动更新；后续只按用户明确指定的场次或名单更新。完整口径见 [2026–2027 赛季与前瞻](doc/season-2026-2027-preview.md)。

```bash
node --test tests/test_frontend_data.mjs tests/test_problem_rating_frontend_data.mjs tests/test_preview_frontend_data.mjs tests/test_review_frontend_data.mjs
```

“赛后复盘”同时展示六项指标的 Spearman ρ、有效队伍数和覆盖率，点击指标卡片切换队伍表。先排除无提交队伍，再排除当前指标缺失队伍；CPC Finder 和奖牌保留零值记录。综合战力保留原前瞻顺序，排除五维计数全零队伍。两侧名次在有效队伍中重新编号并保留并列，显示箭头名次变化及 `log10(前瞻排名 / 实际排名)`；搜索和学校筛选只影响显示。网络赛第一场综合战力有效队伍为 1950 支，符合度 0.736。详见 [赛后复盘设计](doc/post-contest-review.md)。

```bash
python scripts/generate_review_data.py
```

该命令只下载文档指定版本的首场 SRK，核对 SHA-256 后生成 `static/data/reviews/2026-2027.json`，不刷新赛前评分或索引；使用 `--srk` 可完全离线生成，其他场次参数见设计文档。纯 API `core.project_review_contest(preview, contest, *, normalizer=None, overrides=None)` 负责队伍关联与结果投影，不访问网络或文件。`rating.project_static_data_index(..., preview_publications=..., review_publications=...)` 负责生成包含复盘入口的索引；同系列多份前瞻会生成 `previews: [{id, path}]`，保留首项 `previewPath` 兼容入口。

获取牛客比赛 `133876` 至 `133885` 的完整赛时榜单：

```bash
python scripts/fetch_nowcoder_leaderboards.py
```

结果写入已忽略的 `data-cache/nowcoder/nowcoder-<contest-id>-leaderboard.csv`，属于可丢弃上游下载缓存，不是静态站点发布数据。脚本接受自定义比赛 ID 和 `--output-dir`；可复用代码可通过 `NowcoderClient.fetch_leaderboard` 获取不可变模型。静态系列不伪造成个人身份，而以命名空间化的榜单 standing UID 作为报名实体身份，显示名称通常为队伍名。

将已缓存的官方 NOI 获奖名单标准化为逐年离线数据集：

```bash
python scripts/normalize_noi_awards.py
```

该命令从 `data-cache/noi/` 的官方表格缓存读取数据，输出 `data-cache/noi/normalized/index.json` 和逐年文件。每条记录只包含年份、姓名、省份、学校、年级、加分后的总分和金/银/铜牌；不会发布至静态站点。完整字段和校验规则见 [NOI 获奖名单数据](doc/noi-data.md)。

用户提供的 IOI 中国选手成绩快照位于 `data-cache/ioi/`，按年份保存排名、姓名、年级、得分、奖牌和学校；它不声称覆盖当届完整成绩。字段契约和校验 API 见 [IOI 成绩数据](doc/ioi-data.md)。

- 牛客比赛列表与榜单数据契约见 [牛客榜单数据](doc/nowcoder-data.md)
- HDU 榜单数据与认证契约见 [HDU 榜单数据](doc/hdu-data.md)
- IOI 中国选手成绩快照与校验见 [IOI 成绩数据](doc/ioi-data.md)
- NOI 获奖名单缓存与标准化数据集见 [NOI 获奖名单数据](doc/noi-data.md)

## 目录结构

```text
src/core/          RankLand/牛客/HDU 数据获取、标准化、领域模型与赛季选择
src/rating/        Rating 模型、纯计算算法与静态 JSON 投影
src/problem_rating/ 题目难度特征、模型、预测与静态 JSON 投影
scripts/           显式数据获取与静态数据生成脚本
static/             零构建静态前端
static/js/          浏览器 ES modules 与数据辅助函数
static/data/        静态站点发布 JSON
static/data/problem-rating/  ICPC+CCPC/牛客/HDU 题目 Rating 发布 JSON
static/data/previews/  人工指定更新的赛前队伍静态快照
data-cache/        已忽略、可丢弃的上游下载缓存
doc/               各功能设计文档
```

选手/报名实体 rating 位于 `src/rating/`，题目难度 rating 位于独立的 `src/problem_rating/`，两者不共享模型或状态。题目难度模型不使用题号或题目在比赛中的位置，避免把 Codeforces 的题号难度先验迁移到 XCPC。后者的 Codeforces API 缓存、训练数据和本地输出都位于已忽略的 `data-cache/problem-rating/`；静态前端只发布经过严格投影的题目级聚合数据。详细算法和命令见 [题目难度 Rating](doc/problem-rating.md)。

库 API 不隐式写文件；脚本负责显式输出。发行名称为 `xcpc-sight`，安装后分别从 `core`、`rating`、`problem_rating` 导入，不提供 `xcpc_sight` facade。

## 赛季口径

2025–2026 赛季来自 `icpc2025` 和 `ccpc2025`；2026–2027 赛季对应 `icpc2026` 和 `ccpc2026`，当前已发布网络赛第一场选手 Rating，并保留指定的赛前前瞻，尚未发布本赛季题目难度；新赛季 Rating 从 1400 独立起算。两个正式赛季都按统一规则排除邀请赛、保留区域赛，并按上海本地日期排序。

详细规则见：

- [设计文档索引](doc/README.md)
- [Rating 规则](doc/rating-rules.md)
- [题目难度 Rating](doc/problem-rating.md)
- [静态站点数据](doc/static-site-data.md)
- [RankLand 数据](doc/rankland-data.md)
- [牛客榜单数据](doc/nowcoder-data.md)
- [HDU 榜单数据](doc/hdu-data.md)
- [IOI 成绩数据](doc/ioi-data.md)
- [NOI 获奖名单数据](doc/noi-data.md)
- [2025–2026 赛季](doc/season-2025-2026.md)
- [2026–2027 赛季与前瞻](doc/season-2026-2027-preview.md)

## 质量检查

```bash
ruff check .
pytest --cov=core --cov=rating --cov=problem_rating
node --test tests/test_frontend_data.mjs tests/test_problem_rating_frontend_data.mjs tests/test_preview_frontend_data.mjs tests/test_review_frontend_data.mjs
```

默认测试不访问公网。RankLand、牛客和 HDU 都是外部数据源，线上结果可能随上游数据更新；计算核心、JSON 投影与网络适配保持分离。
