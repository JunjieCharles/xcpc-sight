# 设计文档索引

| 功能 | 文档 |
| --- | --- |
| 本地学校别名、更名维护与加载 | [school-aliases.md](school-aliases.md) |
| 个人与报名实体 rating 规则、系列计算及队伍归一化 LSE 聚合 | [rating-rules.md](rating-rules.md) |
| 题目难度 rating 的特征、训练、验证、XCPC 预测与静态展示 | [problem-rating.md](problem-rating.md) |
| 多系列静态站点 JSON 数据契约、生成与零构建前端 | [static-site-data.md](static-site-data.md) |
| 赛后复盘、指标符合度、队伍结果关联与排名对比 | [post-contest-review.md](post-contest-review.md) |
| 首场网络赛 max、LSE 与混合聚合的离线对比实验 | [team-aggregation-first-preliminary.md](team-aggregation-first-preliminary.md) |
| RankLand 数据获取与 SRK 转换 | [rankland-data.md](rankland-data.md) |
| 牛客榜单数据获取、报名实体 Rating 与 CSV 导出 | [nowcoder-data.md](nowcoder-data.md) |
| HDU 认证榜单、CSV 契约与 team token Rating | [hdu-data.md](hdu-data.md) |
| IOI 中国选手成绩快照与校验 | [ioi-data.md](ioi-data.md) |
| NOI 获奖名单缓存与标准化数据集 | [noi-data.md](noi-data.md) |
| 2025–2026 赛季范围与排序 | [season-2025-2026.md](season-2025-2026.md) |
| 2026–2027 赛季范围、外部名单前瞻与匹配口径 | [season-2026-2027-preview.md](season-2026-2027-preview.md) |

开发已有功能前应先阅读对应文档；实现完成后必须回到文档同步行为、API、假设、限制与测试。

代码按职责分为 `src/core/`（数据获取、标准化、赛季）、`src/rating/`（选手/报名实体 rating 模型、算法与纯 JSON 投影）和 `src/problem_rating/`（题目难度特征与模型）。静态站点发布数据放在 `static/data/`；选手 rating 上游缓存位于 `data-cache/nowcoder/`、`data-cache/hdu/`，题目 rating 的训练数据、API 缓存与本地输出统一隔离在 `data-cache/problem-rating/`，均不进入 Git。
