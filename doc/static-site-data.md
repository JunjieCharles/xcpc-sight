# 静态站点数据

选手 Rating 生成器发布三个 schema v1 系列：`2025-2026` ICPC + CCPC、`2026牛客暑期多校训练营`，以及 `2026“钉耙编程”中国大学生算法设计暑期联赛`。独立的题目 Rating 生成器从本地预测 CSV 发布这三个系列的题目级聚合 JSON。项目不包含后端或数据库，也不生成分块或重复的稠密数组；`static/` 同时包含直接消费这些文件的零依赖前端。

## 文件与生成

```bash
python scripts/generate_static_data.py
```

默认写入：

- `static/data/index.json`
- `static/data/series/2025-2026.json`
- `static/data/series/nowcoder-summer-2026.json`
- `static/data/series/hdu-summer-2026.json`

XCPC 系列按 RankLand → 赛季选择 → rating 计算生成；牛客系列完整获取 133876 至 133885 榜单；HDU 系列通过认证会话完整获取固定 CID 1229 至 1238，且当前均为 rated。各来源进入 Rating 前都过滤无提交队伍，并按 solved 降序、精确 penalty 升序重建含并列的比赛排名。各系列均按开始时间正序计算。`--output-dir` 可覆盖根目录。生成器先加载、计算并投影全部系列；任一来源失败时不发布任何文件。成功后依次原子发布系列文件，最后发布入口索引。

题目 Rating 数据在完成 `python -m problem_rating.predict_xcpc` 后离线生成：

```bash
python scripts/generate_problem_rating_static_data.py
```

默认写入 `static/data/problem-rating/index.json`、`static/data/problem-rating/series/2025-2026.json`、`static/data/problem-rating/series/nowcoder-summer-2026.json` 和 `static/data/problem-rating/series/hdu-summer-2026.json`。生成器读取已忽略的预测 CSV 以及现有选手 Rating series，准备好三个 series 后依次原子发布系列文件，最后发布入口索引；它不访问网络。

JSON 是紧凑 UTF-8（无 BOM），禁止 NaN，保留一个末尾换行，不包含生成时间；固定输入产生固定字节。生成命令访问实时 RankLand、牛客和 HDU，默认离线测试不会执行它。

## 索引契约

```json
{"schemaVersion":1,"defaultSeriesId":"hdu-summer-2026","series":[{"id":"hdu-summer-2026","title":"2026“钉耙编程”中国大学生算法设计暑期联赛","path":"series/hdu-summer-2026.json"},{"id":"nowcoder-summer-2026","title":"2026牛客暑期多校训练营","path":"series/nowcoder-summer-2026.json"},{"id":"2025-2026","title":"2025–2026 ICPC + CCPC","path":"series/2025-2026.json"}]}
```

字段含义：

- `schemaVersion`：当前为 `1`；
- `defaultSeriesId`：静态站点默认打开的系列；
- `series[]`：可用系列的 `id`、显示 `title` 和相对索引文件的 `path`。

索引按每个系列 `contests[].startAt` 的最大值倒序排列，时间相同则按系列 ID 升序；第一项成为默认系列。投影拒绝空输入、无比赛系列、重复 ID 和重复路径。
已发布的 `index.json` 必须由同一批系列 JSON 投影得到；离线回归测试会校验这一一致性，避免单独更新系列数据后目录顺序滞后。

## 系列契约

顶层字段：

- `schemaVersion`、`id`、`title`；
- `initialRating`：当前系列默认 `1400`；
- `contests[]`：rating 计算顺序中的比赛；
- `competitors[]`：最终 rating 排序后的参赛者。

`contests[]` 每项包含：

- `id`、`title`；
- `collection`：例如 `icpc2025`、`ccpc2025` 或 `nowcoder-summer-2026`；
- `startAt`：转换到 `Asia/Shanghai` 后的带偏移 ISO 8601 时间。无时区的上游时间按上海时间解释。
- unrated 场次额外包含 `"rated": false` 与非空 `unratedReason`；rated 场次省略这两个字段。

`competitors[]` 每项包含：

- `id`：`c_` 加 SHA-256(`identity_school + "\0" + identity_member`) 的完整小写十六进制值；
- `rank`：按最终 rating 的 competition ranking，同分同名次且后续名次跳号；
- `school`、`member`：最后一次实际参赛记录中的来源展示值；`school` 可应用来源适配器定义的展示清理，来源未提供学校时允许为空字符串；
- `finalRating`、`contestsParticipated`；
- `participations[]`：严格按 `contestIndex` 递增的实际参赛记录。

RankLand 系列中 `member` 为个人姓名。牛客系列以报名实体计算，`member` 通常是队伍名，身份来自命名空间化 standing UID；学校和显示名变化不改变身份。

每条 participation 包含：

```json
{"contestIndex":0,"contestRank":1,"before":1400,"delta":25,"after":1425}
```

参赛者按 `finalRating` 降序；同 rating 按最后一次实际参赛记录中的展示学校名升序；学校相同再按稳定 `id` 升序排列。投影验证稳定 ID 唯一、比赛引用范围、同场身份唯一、`before + delta == after`、跨参赛场次 rating 连续、最终 rating 和参赛次数一致。

## 从稀疏记录派生页面数据

`participations` 记录实际参赛的场次：

- 某场没有记录表示未参加；
- 有记录且 `delta == 0` 表示参加但 rating 未变化；可能是 rated 计算恰好为 0，也可能是比赛被标记为 unrated，后者可由对应 contest 的 `rated` 字段区分。

因此可以派生：

1. **系列宽表**：按比赛顺序扫描；未参加时从系列初始 Rating `1400` 开始沿用，实际参赛时更新为 `after`。前四列依次为排名、参赛者/学校、最终 Rating、参赛次数；宽屏冻结这四列，视口不超过 `700px` 时仅冻结排名和参赛者/学校，使窄屏横向滚动后仍能看到比赛列。竖屏时参赛者/学校列在原始 `220px` 与 `50vw - 62px` 中取较小值，因而与固定 `62px` 的排名列合计不超过页面宽度的 50%。每场比赛在数据结构中为独立的 rating 与 delta 两列，确保两类数值分别全列右对齐。页面视觉上将它们合并在同一比赛标题下，不显示子列名或内部边框。实际参赛时显示 rating 与 delta，未参赛时只显示沿用 rating。
2. **单场参赛者表**：筛选 `contestIndex`，按比赛排名、参赛者/学校、`before`、`after`、`delta` 的顺序展示。
3. **参赛者完整曲线**：覆盖系列所有比赛；从初始 Rating 开始，参赛点更新为 `after`，未参赛点水平延续，只有实际参赛点显示 marker。

Rating 文本采用 Codeforces 风格等级色：`<1200` 灰、`1200` 绿、`1400` 青、`1600` 蓝、`1900` 紫、`2100` 橙、`2400` 红；`>=3000` 为黑色文字且首个数字为红色。曲线线段和 marker 使用对应等级色，悬浮提示采用精简的 `比赛名 #排名，before → after (delta)` 或 `比赛名 · 未参赛`。

系列文件不输出 seed、performance、修正项等计算诊断，不生成缺席记录、稠密 rating 数组或重复的单场 JSON。

## 题目 Rating 数据契约

`static/data/problem-rating/index.json` 使用独立 schema v1：

```json
{"schemaVersion":1,"series":[{"id":"hdu-summer-2026","title":"2026…","path":"series/hdu-summer-2026.json"},{"id":"nowcoder-summer-2026","title":"2026…","path":"series/nowcoder-summer-2026.json"}]}
```

series 文件顶层包含 `schemaVersion`、`seriesId`、`title`、`modelId` 和 `contests[]`。场次沿用对应选手 Rating series 的 `id`、`title`、`startAt` 与顺序，每场包含非空 `problems[]`；可选的非空 `shortTitle` 仅用于图例和曲线提示，2025–2026 ICPC + CCPC 的 16 场均提供该字段。题目字段为：

- `index`：非空题号；`name` 为字符串，RankLand 或 HDU 无法取得题名时发布为空字符串；当前系列的题名全部为空时，前端隐藏整列题名；
- `rating`：有限非负整数预测值；
- `solvedCount`、`participantCount`、`timeSampleCount`：非负整数，并满足 `timeSampleCount <= solvedCount <= participantCount`。

投影拒绝跨 series、缺场、额外场次、重复题目和非法计数。发布文件不包含选手/队伍名称、Codeforces handle、team token、逐人提交或本地路径；浏览器不会请求 `data-cache/`。

2025–2026 ICPC + CCPC 的题目特征以正式且有提交活动的队伍为样本。每队 Rating 是全部非教练队员 `finalRating` 的最大值；成员使用与选手 Rating 相同的学校/姓名规范化和稳定 ID。只有全部成员均可映射时才纳入该队，避免把部分成员最大值误当成完整队伍 Rating。RankLand SRK 原始成员和逐题记录仅缓存在被 Git 忽略的本地目录，发布投影只保留题目级计数。

## 静态前端

前端入口为 `static/index.html`，样式和原生 ES modules 分别位于 `static/styles.css`、`static/js/data.mjs`、`static/js/problem-rating.mjs` 和 `static/js/app.mjs`。入口 CSS、应用模块及其依赖使用同一查询版本标识；发布前端改动时必须一并更新该标识，使浏览器和 CDN 请求新的资源 URL，而数据 JSON 则继续由 `cache: "no-cache"` 请求并重新验证。它不使用第三方依赖、包管理器或构建步骤，部署时保留 `static/` 内的相对目录即可；所有数据 URL 均相对于入口索引或模块解析，因此部署在域名子路径下也能工作。

本地必须通过 HTTP 访问，而不是直接打开 `file://`：

```bash
python -m http.server 8000 --directory static
```

页面包含：

- 站点标题旁的 Rating 口径批注：数值仅在同一系列比赛范围内有效，不与 Codeforces 等平台 Rating 对标；
- 页面左侧的系列目录和按参赛者名称/学校的多词搜索；学校下拉框支持搜索和多选，所选学校以可移除标签显示在原搜索框内，学校之间为 OR、并与关键词条件按 AND 组合，学校名采用精确匹配；搜索框末尾按钮同时清空关键词和全部学校筛选；
- 按最终排名排列的虚拟滚动宽表；比赛列头可打开只含实际参赛者的虚拟滚动表；
- 参赛者详情、可键盘访问且带悬停/聚焦提示的单系列 SVG rating 曲线，以及排列在曲线下方、提供同一数据的参赛记录表；
- `series`、`q`、可重复的 `school`、`contest`、`competitor` 查询参数状态及浏览器前进/后退支持。比赛或参赛者详情页除“返回系列”按钮外，也可点击左侧当前系列名回到系列总览。
- 三个已发布题目数据的 series 均提供“选手 Rating / 题目难度”切换；题目页默认选择全部场次，图例支持点击逐场筛选和快捷全选/全不选；2025–2026 ICPC + CCPC 另有“仅 ICPC”和“仅 CCPC”按钮，用对应组织的全部场次替换当前选择；表头点击完成“场次 + 题号”或 Rating 的正序/逆序切换；通过队伍/有效队伍在同一列分别对齐，界面不展示时间样本；
- 每场题目按预测 Rating 从易到难排列的多曲线 SVG；Rating 相同按自然题号稳定排序，图表适配页面可用宽度，曲线长度与题目数量成正比，并使用不越过相邻点范围的单调三次插值，圆点和提示保留真实预测值；
- `view=problem-rating`、`problemContests`、`problemSort`、`problemOrder` 查询状态。缺少 `problemContests` 表示全选，`none` 表示取消全部，其他值为逗号分隔的场次 ID。

数据层以 URL 为键缓存正在进行和已完成的 JSON Promise；失败会从缓存移除以允许重试。索引和系列对象分别只验证一次，系列验证后只建立一次参赛者 ID 与单场参赛者索引。验证包括 schema 版本、必需字段与类型、唯一 ID、比赛引用范围、参赛顺序、rating 算术与连续性，以及最终 rating/参赛次数一致性。未知 schema 版本或不合法文档会显示错误面板，不静默渲染部分数据。

宽表和单场表仅在 DOM 中保留视口附近的行；筛选仍在已加载数据上执行。两个虚拟表都使用显式 `colgroup`、固定 table layout 和固定 44px 行高，列宽不依赖当前挂载的可见行，因此纵向滚动不会触发表格列宽突变。系列 JSON 当前仍一次性加载和解析，因此内存规模取决于整个系列文件；本版不引入服务端搜索、分块或单场文件。

## 前端测试

`tests/test_frontend_data.mjs` 与 `tests/test_problem_rating_frontend_data.mjs` 使用 Node 内置测试运行器，不需要 `package.json`：

```bash
node --test tests/test_frontend_data.mjs tests/test_problem_rating_frontend_data.mjs
```

覆盖选手与题目 schema 校验失败和空题名、一次性索引、稀疏记录的 carried rating、关键词与学校精确多选筛选、组合清空控件、零变化量强调、signed delta、含重复学校参数的查询状态、子路径 URL 解析、Promise 缓存失败重试、多系列索引顺序、题目场次筛选、两类双向排序、自然题号、难度曲线顺序/题量比例、单调路径、题目 URL 状态，以及按 ID 独立加载题目数据。DOM 虚拟滚动和浏览器交互继续通过本地 HTTP 与桌面/移动端浏览器检查。
