# 设计文档索引

| 功能 | 文档 |
| --- | --- |
| 个人 rating 规则与系列计算 | [rating-rules.md](rating-rules.md) |
| RankLand 数据获取与 SRK 转换 | [rankland-data.md](rankland-data.md) |
| 2025–2026 赛季范围与排序 | [season-2025-2026.md](season-2025-2026.md) |

开发已有功能前应先阅读对应文档；实现完成后必须回到文档同步行为、API、假设、限制与测试。

代码按职责分为 `src/core/`（数据获取、标准化、赛季）和 `src/rating/`（rating 模型与算法）。面向用户的生成结果放在仓库根目录 `results/`，可丢弃缓存放在 `data-cache/`。
