# RankLand 数据适配

实现位于 `core.rankland`，其输出使用 `core.models` 中的标准化竞赛模型；身份标准化位于 `core.normalization`。`rating` 包不直接访问 RankLand。

## 数据流

`RankLandClient` 使用同步 RankLand public v2：

1. `GET /api/v2/public/collections/official`：从 official collection 树定位系列节点并读取叶子 contest UK。
2. `GET /api/v2/public/contests/{uk}`：取得比赛元数据和 `srkFileID`。
3. `GET /api/v2/public/files/{srkFileID}`：取得 CDN URL 和 SHA-256。
4. `GET {file.url}`：下载 SRK JSON。

API envelope 必须为 `success=true`、`code=0` 且存在 `data`。HTTP 408、429、5xx 和网络错误进行有限重试；404 直接报告资源不存在。

## SRK 字段

当前读取：

- `contest.title`、`contest.startAt`；
- `rows[].user.id/name/organization/official/teamMembers`；
- `rows[].score.value/time`；
- `rows[].statuses[].result/tries`；
- 可选 `rows[].rank`。

本地化文本优先级为 `zh-CN`、`texts.zh-CN`、`fallback`、`texts.en`、`en`。时间支持 ms、s、min 和 h。结构类型错误包含 JSON path 和 contest UK。

学校展示名在 RankLand 适配边界移除全角或半角括号中的 `非独立法人` / `非獨立法人` 注记；其余上游文字保持不变。身份标准化原本也会移除该注记，因此显示清理不会改变参赛者稳定 ID。

## 排名

参考项目的旧适配器用 `rowIndex + 1`，会让非正式队伍占位且无法表达并列，本项目不使用该行为。

- 若所有正式队伍都有正的显式 rank，则保留上游排名。
- 否则只对正式队伍按 solved 降序、penalty 升序重建 `1, 2, 2, 4` 式排名。
- 非正式队伍保留在 `Contest.teams` 中供审计，但 rank 为 0 且不参与 rating。
- 提交活动由 status 的 result/tries 或 solved 值判断；0 题但有失败提交仍为活跃。

## Provenance 与限制

`ContestProvenance` 保存 contest UK、file ID、CDN URL 和上游 SHA-256。首版不隐式写磁盘缓存；纯算法只依赖标准化 `Contest`，因此未来可以增加内容寻址快照而无需修改 rating 核心。

已知限制：RankLand/SRK 是外部契约，字段可能变化；默认测试通过 `httpx.MockTransport` 固定协议，不访问网络。更新适配器时应先更新本文档和 fixture，并手工执行一次线上 smoke test。
