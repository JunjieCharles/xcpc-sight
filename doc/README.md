# 设计文档索引

| 功能 | 文档 |
| --- | --- |
| 个人与报名实体 rating 规则及系列计算 | [rating-rules.md](rating-rules.md) |
| 题目难度 rating 的特征、训练、验证、XCPC 预测与静态展示 | [problem-rating.md](problem-rating.md) |
| 多系列静态站点 JSON 数据契约、生成与零构建前端 | [static-site-data.md](static-site-data.md) |
| RankLand 数据获取与 SRK 转换 | [rankland-data.md](rankland-data.md) |
| 牛客榜单数据获取、报名实体 Rating 与 CSV 导出 | [nowcoder-data.md](nowcoder-data.md) |
| HDU 认证榜单、CSV 契约与 team token Rating | [hdu-data.md](hdu-data.md) |
| 2025–2026 赛季范围与排序 | [season-2025-2026.md](season-2025-2026.md) |

开发已有功能前应先阅读对应文档；实现完成后必须回到文档同步行为、API、假设、限制与测试。

代码按职责分为 `src/core/`（数据获取、标准化、赛季）、`src/rating/`（选手/报名实体 rating 模型、算法与纯 JSON 投影）和 `src/problem_rating/`（题目难度特征与模型）。静态站点发布数据放在 `static/data/`；选手 rating 上游缓存位于 `data-cache/nowcoder/`、`data-cache/hdu/`，题目 rating 的训练数据、API 缓存与本地输出统一隔离在 `data-cache/problem-rating/`，均不进入 Git。
