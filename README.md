# xcpc-sight

用于 ICPC/CCPC 竞赛前瞻与数据分析的轻量 Python 项目。项目未来可扩展 rating、前瞻报告和图片生成等能力；当前版本提供：

- 从 RankLand public v2 获取并解析 SRK 榜单；
- 获取并完整导出牛客赛时榜单；
- 定义 `icpc2025` + `ccpc2025` 的 2025–2026 赛季；
- 从空初始状态按比赛顺序计算个人 rating；
- 可复用的纯 Python API，不包含 CLI。

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
from rating import calculate_series_ratings

with RankLandClient() as client:
    season = load_2025_2026_season(client)

result = calculate_series_ratings(season.contests)
print(len(result.contests), len(result.ratings))
```

也可自行构造 `Contest`/`TeamResult` 后调用 `calculate_contest_ratings` 或 `calculate_series_ratings`，从而完全脱离网络运行。传入 `initial_ratings` 可从指定状态开始；默认新选手为 1400。

获取牛客比赛 `133876`、`133877` 的完整赛时榜单：

```bash
python scripts/fetch_nowcoder_leaderboards.py
```

结果写入 `results/nowcoder-<contest-id>-leaderboard.csv`。脚本也接受自定义比赛 ID 和 `--output-dir`；可复用代码可通过 `NowcoderClient.fetch_leaderboard` 直接获取不可变模型。牛客榜单仅提供成员 UID 而非成员姓名，因此当前不强行接入个人 rating 身份模型。

## 目录结构

```text
src/core/          RankLand/牛客数据获取、标准化、领域模型与赛季选择
src/rating/        Rating 模型与纯计算算法
scripts/           显式数据获取与结果导出脚本
doc/                    各功能设计文档
results/                Rating、报告、图片和快照等输出结果
```

`results/` 下生成物默认不提交 Git，仅保留目录说明；可丢弃的上游下载缓存应放在 `data-cache/`。当前库不会自动写结果，调用方应显式选择输出路径。发行名称仍为 `xcpc-sight`，安装后分别从 `core`、`rating` 导入，不提供 `xcpc_sight` facade。

## 赛季口径

2025–2026 赛季来自 RankLand official collection 中的 `icpc2025` 和 `ccpc2025`。邀请赛排除，区域赛包含；其余非邀请赛默认保留。比赛按上海本地日期排序，同日 CCPC 在 ICPC 前。

详细规则见：

- [设计文档索引](doc/README.md)
- [Rating 规则](doc/rating-rules.md)
- [RankLand 数据](doc/rankland-data.md)
- [牛客榜单数据](doc/nowcoder-data.md)
- [2025–2026 赛季](doc/season-2025-2026.md)

## 质量检查

```bash
ruff check .
pytest --cov=core --cov=rating
```

默认测试不访问公网。RankLand 是外部数据源，线上结果可能随上游数据更新；计算核心与网络适配保持分离，以便后续增加显式快照和缓存。
