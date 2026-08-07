# 牛客榜单数据适配

实现位于 `core.nowcoder`；显式 CSV 获取脚本位于 `scripts/fetch_nowcoder_leaderboards.py`。网络客户端只返回不可变的牛客源数据模型，不隐式写缓存或结果文件。

## 数据接口

榜单页面通过以下动态接口读取：

```text
GET https://ac.nowcoder.com/acm-heavy/acm/contest/real-time-rank-data
```

每页必须显式发送：

- `id`：比赛 ID；
- `page`：从 1 开始的页码；
- `limit`：牛客将其解释为“最多纳入榜单的总名次数”，而不是单页大小；
- `onlyContestRank=true`：仅获取赛时榜单。

客户端先以 `limit=50` 探测；若正好返回 50 名，会以足够大的 limit 重新获取第一页以取得真实 `rankCount`，再在后续页面保持该总量上限。不能固定使用 `limit=50`，否则接口会把榜单截断成 50 名并错误报告 `pageCount=1`。

请求还发送比赛页面 Referer、稳定 User-Agent 和 `X-Requested-With`。响应业务 envelope 要求 `code=0` 且存在 `data`。

## 分页与完整性

`NowcoderClient.fetch_leaderboard` 首先读取第一页，再根据 `basicInfo.pageCount` 获取所有页面。合并时检查：

- page size 为 50，页数与 `rankCount` 匹配；
- contest ID、比赛起止时间、rank type、题目定义等元数据在各页一致；
- `onlyContestRankApplied=true`；
- 每页行数以及合并总行数正确；
- UID 唯一，源 ranking 单调不降；
- 每行 `scoreList` 与 `problemData` 的题目 ID 一一对应。

上游 ranking 和所有时间值均原样保留在牛客来源模型与 CSV 导出中；`penaltyTime`、`acceptedTime` 和比赛时间戳使用毫秒。转换为标准 `Contest` 时不采用上游 ranking，而统一按有效参赛队伍的成绩重建排名。

## 模型与 Rating 边界

公共模型包括 `NowcoderProblem`、`NowcoderProblemScore`、`NowcoderStanding` 与 `NowcoderLeaderboard`。`nowcoder_leaderboard_to_contest` 将已结束榜单纯转换为 `Contest`：

- 每行按牛客报名实体计算，不把队伍名伪造成个人姓名；
- 稳定身份为 `CompetitorId("nowcoder", "standing:<uid>")`；相同 standing UID 跨场延续 rating，不同 UID 即使名称相同也保持独立；
- `member` 展示 `userName`（通常是队伍名），`school` 展示榜单学校，缺失时留空；展示字段不参与身份计算；
- 使用 `acceptedCount` 和原始毫秒罚时，对正式且有提交活动的队伍按题数降序、罚时升序重建 `1, 2, 2, 4` 式排名；
- 同题数、同毫秒罚时视为并列；源 `ranking` 不进入标准 `Contest` 的排名；
- 有通过或任一题存在提交才视为实际参赛；
- 比赛开始毫秒时间戳转换为 `Asia/Shanghai` 带偏移时间；
- 未结束榜单和空显示名会被拒绝。

`teamMemberUids` 可为 0–3 个，但其稳定性和人员含义不足以支持个人 rating，因此不会用于自动拆分或跨 UID 合并。未来如需合并报名实体，只接受显式 alias 配置。

## CSV 输出

运行：

```bash
python scripts/fetch_nowcoder_leaderboards.py
```

默认获取以下比赛：

- `133876`：<https://ac.nowcoder.com/acm/contest/133876>
- `133877`：<https://ac.nowcoder.com/acm/contest/133877>
- `133878`：<https://ac.nowcoder.com/acm/contest/133878>
- `133879`：<https://ac.nowcoder.com/acm/contest/133879>
- `133880`：<https://ac.nowcoder.com/acm/contest/133880>
- `133881`：<https://ac.nowcoder.com/acm/contest/133881>
- `133882`：<https://ac.nowcoder.com/acm/contest/133882>

并写入：

- `data-cache/nowcoder/nowcoder-133876-leaderboard.csv`
- `data-cache/nowcoder/nowcoder-133877-leaderboard.csv`
- `data-cache/nowcoder/nowcoder-133878-leaderboard.csv`
- `data-cache/nowcoder/nowcoder-133879-leaderboard.csv`
- `data-cache/nowcoder/nowcoder-133880-leaderboard.csv`
- `data-cache/nowcoder/nowcoder-133881-leaderboard.csv`
- `data-cache/nowcoder/nowcoder-133882-leaderboard.csv`

这些 CSV 是已忽略、可随时重新下载的上游缓存，不属于 `static/data/` 的静态站点发布数据。

可传入比赛 ID，并使用 `--output-dir` 指定目录。CSV 使用 UTF-8 with BOM，通过临时文件完成后原子替换。基础列保存排名、UID、名称、学校、成员 UID JSON、题数、毫秒罚时和分数；随后按题目顺序保存每题全部状态字段。

## 错误、限制与测试

HTTP 408、429、5xx 和网络错误有限重试；HTTP/业务失败抛出 `NowcoderError`，成功响应的结构错误抛出带比赛、页码和字段路径的 `DataValidationError`。离线测试覆盖源 ranking 单调性，以及转换后忽略不同源 ranking、按相同成绩并列并过滤无提交队伍。

牛客接口属于网页前端使用的外部契约，路径和字段可能变化；实时榜单也可能在分页期间变化。默认测试使用 `httpx.MockTransport`，覆盖请求契约、分页、完整性失败、重试和 CSV 投影，不访问公网。适配器调整后应手工获取真实榜单并重新检查行数与题目 ID。
