# HDU 榜单数据适配

实现位于 `core.hdu`。网络客户端维护同一 `httpx.Client` 会话，只返回不可变源模型或纯转换后的 `Contest`，不隐式写文件。

## 登录与导出契约

固定比赛 CID 为 `1229`、`1230`、`1231`、`1232`。每场先 GET `/contest/problems?cid=<cid>` 读取比赛元数据，再提交登录表单：

```text
POST /contest/login?cid=<cid>&redirect=<percent-encoded /contest/rank?cid=<cid>&export=csv>
```

POST 字段严格为 `username`、`password`。默认凭据为 `guest`/`guest`，可在构造 `HduClient` 时注入；凭据只进入表单 body，不写入 URL、错误消息或模型。客户端跟随重定向；若 POST 成功但尚未返回 CSV，则在同一认证会话中 GET `/contest/rank?cid=<cid>&export=csv` 一次。最终响应必须为 `text/csv`，登录 HTML 或其他非 CSV 响应均会被拒绝。

HTTP 408、429、5xx 与网络错误有限重试。HTTP/认证/导出失败抛出 `HduError`；已成功读取但违反数据契约的内容抛出 `DataValidationError`。

## 元数据

problems 页面必须包含 `.contest-info` 内的非空 `<h2>`（浏览器 `<title>` 实际为 `Contest Login`，不能作为比赛标题）和严格 JSON：

```javascript
const contest={id,now,start,end,isCodeSharing};
```

解析器严格要求这五个字段且类型正确，核对 `id` 与请求 CID，拒绝结束早于开始的比赛。时间支持 ISO 8601 或秒/毫秒 Unix 时间戳，统一转换为 `Asia/Shanghai`。`now >= end` 才视为完赛；未完赛数据可以解析，但在转换到 Rating `Contest` 时拒绝。

## CSV 与完整性

CSV 必须是严格 UTF-8，允许开头 UTF-8 BOM。前四列严格为 `Rank,Author,Solved,Penalty`，后续列均为动态题目列；题目列名须为唯一的 ASCII 数字 problem ID。每行列数必须与 header 一致：

- `Rank` 为正整数且全表单调不降；
- `Author` 不区分大小写地匹配 `teamNNNN <team> <school>`，team token 统一 casefold 后在一场内唯一；当前 1229、1230、1231、1232 CSV 的队名和学校均不含 ASCII 空格，因此按最后一个空白拆分队名与学校；文本中的 HTML character reference 只解码一次；
- `Solved` 为不超过题目数的非负整数；
- `Penalty` 严格使用合法 `HH:MM:SS`；
- 任一题目单元格非空即表示该队有比赛活动，不能只依据 solved 判断。

## Rating 边界与公开 API

公共模型为 `HduContestMetadata`、`HduStanding`、`HduLeaderboard`，公开入口包括 `HduClient.fetch_leaderboard`、`HduClient.fetch_contest`、`parse_hdu_metadata`、`parse_hdu_csv` 和 `hdu_leaderboard_to_contest`。

Rating 身份为 `CompetitorId("hdu", team_token)`；队名与学校分别映射到展示 member/school，team token 是跨场身份依据，展示字段变化不会改变身份。CSV 的源排名保留在 `HduStanding` 中用于校验，但转换为标准 `Contest` 时不采用它：先排除无提交活动的队伍，再按 solved 降序、精确罚时升序重建 `1, 2, 2, 4` 式排名，同题同罚时即并列。罚时总秒数无损转换为 `TeamResult` 使用的毫秒；无提交队伍保留供审计但 rank 为 0。比赛 ID 为 `hdu:<cid>`，系列 ID 为 `hdu-summer-2026`。

## 静态生成与测试

`scripts/generate_static_data.py` 注册 CID `1229`、`1230`、`1231`、`1232`，按比赛开始时间排序后生成 `static/data/series/hdu-summer-2026.json`。完整静态生成会访问公网，本次集成不运行线上全量生成。

默认测试全部离线，使用 `httpx.MockTransport` 覆盖登录 URL/redirect/form、默认与注入凭据、重试、错误 Content-Type、严格元数据、UTF-8/CSV/header/行校验、team token 身份、题目活动语义、成绩并列重排名、无提交过滤和完赛边界。真实站点 HTML 或 CSV 契约变化时，应先更新本设计文档和固定测试，再运行人工线上抽样；不得静默放宽解析。
