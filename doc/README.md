# 设计文档索引

| 功能 | 文档 |
| --- | --- |
| 个人 rating 规则与系列计算 | [rating-rules.md](rating-rules.md) |
| 静态站点 JSON 数据契约与生成 | [static-site-data.md](static-site-data.md) |
| RankLand 数据获取与 SRK 转换 | [rankland-data.md](rankland-data.md) |
| 牛客榜单数据获取与 CSV 导出 | [nowcoder-data.md](nowcoder-data.md) |
| 2025–2026 赛季范围与排序 | [season-2025-2026.md](season-2025-2026.md) |

开发已有功能前应先阅读对应文档；实现完成后必须回到文档同步行为、API、假设、限制与测试。

代码按职责分为 `src/core/`（数据获取、标准化、赛季）和 `src/rating/`（rating 模型、算法与纯 JSON 投影）。静态站点发布数据放在 `static/data/`，可丢弃的上游下载缓存放在已忽略的 `data-cache/`。
