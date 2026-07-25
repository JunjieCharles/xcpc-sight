# xcpc-sight

用于 ICPC/CCPC 竞赛前瞻与数据分析的轻量 Python 项目。当前版本提供：

- 从 RankLand public v2 获取并解析 SRK 榜单；
- 获取并完整导出牛客赛时榜单；
- 定义 `icpc2025` + `ccpc2025` 的 2025–2026 赛季；
- 从空初始状态按比赛顺序计算个人 rating；
- 为静态站点生成确定、可复现的稀疏 JSON 数据；
- 提供零依赖、无需构建的静态 rating 浏览前端；
- 可复用的纯 Python API。

## 安装

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
```

需要 Python 3.11 或更高版本。

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

也可自行构造 `Contest`/`TeamResult` 后调用 `calculate_contest_ratings` 或 `calculate_series_ratings`，从而完全脱离网络运行。传入 `initial_ratings` 可从指定状态开始；默认新选手为 1400。

生成静态站点数据：

```bash
python scripts/generate_static_data.py
```

默认写入 `static/data/index.json` 和 `static/data/series/2025-2026.json`；可用 `--output-dir` 覆盖。系列 JSON 的稀疏参赛记录可派生系列宽表、单场变化表和选手完整 rating 曲线。生成过程访问实时 RankLand，不属于默认离线测试。

本地浏览静态站点（不能直接用 `file://`，因为浏览器需要通过 HTTP 加载 ES module 和 JSON）：

```bash
python -m http.server 8000 --directory static
```

然后打开 `http://localhost:8000/`。站点没有 npm 依赖、构建步骤或 `package.json`；可直接部署整个 `static/` 目录到任意子路径。页面提供系列选择、搜索与虚拟滚动宽表、单场参赛者表、选手 rating 曲线和参赛记录；当前视图会写入查询参数，链接可以直接分享。前端纯数据工具测试使用 Node 内置测试运行器：

```bash
node --test tests/test_frontend_data.mjs
```

获取牛客比赛 `133876`、`133877` 的完整赛时榜单：

```bash
python scripts/fetch_nowcoder_leaderboards.py
```

结果写入已忽略的 `data-cache/nowcoder/nowcoder-<contest-id>-leaderboard.csv`，属于可丢弃上游下载缓存，不是静态站点发布数据。脚本接受自定义比赛 ID 和 `--output-dir`；可复用代码可通过 `NowcoderClient.fetch_leaderboard` 获取不可变模型。牛客榜单仅提供成员 UID 而非成员姓名，因此当前不强行接入个人 rating 身份模型。

## 目录结构

```text
src/core/          RankLand/牛客数据获取、标准化、领域模型与赛季选择
src/rating/        Rating 模型、纯计算算法与静态 JSON 投影
scripts/           显式数据获取与静态数据生成脚本
static/             零构建静态前端
static/js/          浏览器 ES modules 与数据辅助函数
static/data/        静态站点发布 JSON
data-cache/        已忽略、可丢弃的上游下载缓存
doc/               各功能设计文档
```

库 API 不隐式写文件；脚本负责显式输出。发行名称为 `xcpc-sight`，安装后分别从 `core`、`rating` 导入，不提供 `xcpc_sight` facade。

## 赛季口径

2025–2026 赛季来自 RankLand official collection 中的 `icpc2025` 和 `ccpc2025`。邀请赛排除，区域赛包含；其余非邀请赛默认保留。比赛按上海本地日期排序，同日 CCPC 在 ICPC 前。

详细规则见：

- [设计文档索引](doc/README.md)
- [Rating 规则](doc/rating-rules.md)
- [静态站点数据](doc/static-site-data.md)
- [RankLand 数据](doc/rankland-data.md)
- [牛客榜单数据](doc/nowcoder-data.md)
- [2025–2026 赛季](doc/season-2025-2026.md)

## 质量检查

```bash
ruff check .
pytest --cov=core --cov=rating
node --test tests/test_frontend_data.mjs
```

默认测试不访问公网。RankLand 是外部数据源，线上结果可能随上游数据更新；计算核心、JSON 投影与网络适配保持分离。
