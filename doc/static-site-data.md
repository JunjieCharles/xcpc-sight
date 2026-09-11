# 静态站点数据

选手 Rating 生成器发布四个 schema v1 Rating 系列（含 2026–2027），并把已提交的 2026–2027 schema v1 前瞻快照及对应赛后复盘一并登记到 schema v2 站点索引。独立的题目 Rating 生成器仍只发布三个已有系列的题目级聚合 JSON。项目不包含后端或数据库；`static/` 同时包含直接消费这些文件的零依赖前端。

## 文件与生成

```bash
python scripts/generate_static_data.py
```

默认写入：

- `static/data/index.json`
- `static/data/series/2025-2026.json`
- `static/data/series/2026-2027.json`
- `static/data/series/nowcoder-summer-2026.json`
- `static/data/series/hdu-summer-2026.json`
- `static/data/previews/2026-2027.json`
- `static/data/previews/icpc-2026-preliminary-2.json`
- `static/data/reviews/2026-2027.json`

XCPC 系列按 RankLand → 赛季选择 → rating 计算生成；牛客系列完整获取 133876 至 133885 榜单；HDU 系列通过认证会话完整获取固定 CID 1229 至 1238。各来源进入 Rating 前都过滤无提交队伍并重建含并列的比赛排名。`--output-dir` 可覆盖根目录。生成器先加载、计算并投影全部 Rating 系列，同时读取已提交的前瞻和对应复盘文件；成功后依次原子发布系列、前瞻与复盘文件，最后发布入口索引。它不会自行请求、刷新或扩展前瞻名单。

题目 Rating 数据在完成 `python -m problem_rating.predict_xcpc` 后离线生成：

```bash
python scripts/generate_problem_rating_static_data.py
```

默认写入 `static/data/problem-rating/index.json`、`static/data/problem-rating/series/2025-2026.json`、`static/data/problem-rating/series/nowcoder-summer-2026.json` 和 `static/data/problem-rating/series/hdu-summer-2026.json`。生成器读取已忽略的预测 CSV 以及现有选手 Rating series，准备好三个 series 后依次原子发布系列文件，最后发布入口索引；它不访问网络。

JSON 是紧凑 UTF-8（无 BOM），禁止 NaN，保留一个末尾换行，不包含生成时间；固定输入产生固定字节。生成命令访问实时 RankLand、牛客和 HDU，默认离线测试不会执行它。

## 索引契约

```json
{"schemaVersion":2,"defaultSeriesId":"2026-2027","series":[{"id":"2026-2027","title":"2026–2027 ICPC + CCPC","path":"series/2026-2027.json","previewPath":"previews/2026-2027.json"},{"id":"hdu-summer-2026","title":"2026“钉耙编程”中国大学生算法设计暑期联赛","path":"series/hdu-summer-2026.json"}]}
```

字段含义：

- `schemaVersion`：当前为 `2`；
- `defaultSeriesId`：静态站点默认打开的系列；
- `series[]`：可用系列的 `id`、显示 `title`，以及至少一个数据入口。`path` 指向选手 Rating series，`previewPath` 指向首个前瞻，可选 `previews: [{id, path}]` 提供完整多场次目录；可选 `reviewPath` 指向赛后复盘，2026–2027 同时提供选手榜、前瞻和复盘。

索引按每个 Rating 系列 `contests[].startAt` 的最大值或前瞻 `sortAt` 倒序排列，时间相同则按系列 ID 升序；同一系列同时存在两类数据时取两者中较新的时间。第一项成为默认系列。投影拒绝空输入、无内容系列、重复场次 ID 和重复路径；同一系列 ID 的 Rating 与前瞻合并为一项，并要求标题一致；多份前瞻通过 `previews` 登记且首项保留 `previewPath`。`project_static_data_index` 接受 `review_publications` 并验证复盘引用已发布前瞻。
2026–2027 的 `previews` 按第一场、第二场登记，`previewPath` 继续指向第一场；默认生成器复制两场已提交快照。已发布的 `index.json` 必须由同一批系列 JSON 投影得到；离线回归测试校验完整多场次目录的一致性，避免单独更新系列数据后目录顺序滞后。

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

1. **系列宽表**：按比赛顺序扫描；未参加时从系列初始 Rating `1400` 开始沿用，实际参赛时更新为 `after`。前四列依次为排名、参赛者/学校、最终 Rating、参赛次数；当滚动容器宽于 `924px` 时冻结这四列，否则只冻结排名和参赛者/学校，使横向滚动后仍能看到比赛列。`600px` 以下进一步隐藏独立排名列，把排名以 `#x 学校` 的形式放到参赛者单元格的学校副行中，只冻结这一列复合身份信息；身份列宽为 `clamp(150px, 42cqw, 176px)`，右侧阴影提示仍可横向滚动。单场参赛者表使用相同策略，把比赛排名放在学校前并合入参赛者/学校副行。每场比赛在数据结构中为独立的 rating 与 delta 两列，确保两类数值分别全列右对齐。页面视觉上将它们合并在同一比赛标题下，不显示子列名或内部边框。实际参赛时显示 rating 与 delta，未参赛时只显示沿用 rating。
2. **单场参赛者表**：筛选 `contestIndex`，按比赛排名、参赛者/学校、`before`、`after`、`delta` 的顺序展示。
3. **参赛者完整曲线**：覆盖系列所有比赛；从初始 Rating 开始，参赛点更新为 `after`，未参赛点水平延续，只有实际参赛点显示 marker。

Rating 文本采用 Codeforces 风格等级色：`<1200` 灰、`1200` 绿、`1400` 青、`1600` 蓝、`1900` 紫、`2100` 橙、`2400` 红；`>=3000` 为黑色文字且首个数字为红色。曲线线段和 marker 使用对应等级色，悬浮提示采用精简的 `比赛名 #排名，before → after (delta)` 或 `比赛名 · 未参赛`。

系列文件不输出 seed、performance、修正项等计算诊断，不生成缺席记录、稠密 rating 数组或重复的单场 JSON。

## 题目 Rating 数据契约

`static/data/problem-rating/index.json` 使用独立 schema v1：

```json
{"schemaVersion":1,"series":[{"id":"hdu-summer-2026","title":"2026…","path":"series/hdu-summer-2026.json"},{"id":"nowcoder-summer-2026","title":"2026…","path":"series/nowcoder-summer-2026.json"}]}
```

series 文件顶层包含 `schemaVersion`、`seriesId`、`title`、`modelId` 和 `contests[]`。当前 `modelId` 为 `gaussian-prev1-3-shallow-gbr-no-order-no-team-size`；模型不输入题号、题目位置或队伍规模，同场中其他模型输入相同的题目必须得到相同预测。场次沿用对应选手 Rating series 的 `id`、`title`、`startAt` 与顺序，每场包含非空 `problems[]`；可选的非空 `shortTitle` 仅用于图例和曲线提示，2025–2026 ICPC + CCPC 的 16 场均提供该字段。题目字段为：

- `index`：非空题号；`name` 为字符串，RankLand 或 HDU 无法取得题名时发布为空字符串；当前系列的题名全部为空时，前端隐藏整列题名；
- `rating`：有限非负整数预测值；
- `solvedCount`、`participantCount`、`timeSampleCount`：非负整数，并满足 `timeSampleCount <= solvedCount <= participantCount`。

投影拒绝跨 series、缺场、额外场次、重复题目和非法计数。发布文件不包含选手/队伍名称、Codeforces handle、team token、逐人提交或本地路径；浏览器不会请求 `data-cache/`。

2025–2026 ICPC + CCPC 的题目特征以正式且有提交活动的队伍为样本。后续预测每队 Rating 是已匹配非教练队员 `finalRating` 的归一化 LSE（尺度 400）；成员使用与选手 Rating 相同的学校/姓名规范化和稳定 ID。缺失成员不计入求和和人数，全员缺失才排除。现有题目结果按用户要求保留原全员匹配、取 max 的产物，新规则仅用于后续重新预测。RankLand SRK 原始成员和逐题记录仅缓存在被 Git 忽略的本地目录，发布投影只保留题目级计数。

## 前瞻数据契约

`static/data/previews/2026-2027.json` 使用独立 schema v1。顶层包含 `seriesId`、`seriesTitle`、场次 `id`/`title`、用于索引排序的 `sortAt`、`snapshotDate`、`teamSource`、`metricSources[]`、来源快照信息、匹配政策/统计与 `teams[]`。

`teams[]` 每项包含学校、中文队名、来源顺序、稳定 ID、成员明细、四项队伍评分和金银铜牌总数。每位成员有同样四项评分与个人奖牌数。评分允许 `null`，但非空值必须有限；顶层可选 `ratingAggregation` 支持 `max` 和 `normalized-lse`，省略时兼容旧快照的 max。第一场保持原样，第二场使用 normalized-lse：除 CPC Finder 仍取 max 外，队伍分为已匹配成员的归一化 LSE（固定尺度 400，缺失成员不计入求和与人数，全缺失为 null，0 是有效评分）。保存完整浮点值，浏览器聚合校验允许 1e-9 绝对误差，显示固定两位小数，排名按保存值计算；队伍奖牌必须严格等于成员奖牌之和。详细来源、匹配与人工更新边界见 [2026–2027 赛季与前瞻](season-2026-2027-preview.md)。

## 赛后复盘数据契约

`reviewPath` 指向 schema v1 复盘系列，含 `seriesId` 和 `contests[]`。每场以实际 `id` 及 `previewId` 明确关联前瞻，包含标题、时间、结果来源和所有前瞻队伍的 `previewTeamId/resultTeamId/hasActivity/actualRank`。无活动名次为 `null`，有活动名次为正整数。浏览器验证完整一对一关联、唯一 ID 及活动/名次一致性。首场固定来源版本，不从个人 Rating 反推队伍成绩。完整字段、生成命令、纯 API、匹配政策和测试见 [赛后复盘](post-contest-review.md)。

## 静态前端

前端入口为 `static/index.html`，样式和原生 ES modules 位于 `static/styles.css`、`static/js/data.mjs`、`static/js/problem-rating.mjs`、`static/js/preview.mjs` 和 `static/js/review.mjs` 和 `static/js/app.mjs`。入口 CSS、应用模块及其依赖使用同一查询版本标识；数据 JSON 继续由 `cache: "no-cache"` 请求并重新验证。它不使用第三方依赖、包管理器或构建步骤，所有数据 URL 均相对于入口索引或模块解析。

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
- 三个已发布题目数据的 series 均提供“选手 Rating / 题目难度”切换；题目页默认选择全部场次，图例只显示场次短名，支持点击逐场筛选和快捷全选/全不选；2025–2026 ICPC + CCPC 另有“仅 ICPC”和“仅 CCPC”按钮，用对应组织的全部场次替换当前选择；表头点击完成“场次 + 题号”或 Rating 的正序/逆序切换；通过队伍/有效队伍在同一列分别对齐，界面不展示时间样本；
- 每场题目按预测 Rating 从易到难排列的多曲线 SVG；Rating 相同按自然题号稳定排序，图表适配页面可用宽度，曲线长度与题目数量成正比，并使用不越过相邻点范围的单调三次插值，圆点和提示保留真实预测值；颜色按场次索引以黄金角色相和交替明度确定性生成，筛选不改变颜色，已发布系列内不重复；曲线宽命中带和题目点悬停均显示正式场次名，题目点另外显示题号、题名和 Rating；
- `view=problem-rating`、`problemContests`、`problemSort`、`problemOrder` 查询状态。缺少 `problemContests` 表示全选，`none` 表示取消全部，其他值为逗号分隔的场次 ID。
- 只有前瞻数据的系列直接打开“赛前前瞻”页；2026–2027 已有选手 Rating，默认打开选手榜；“赛前前瞻”作为独立 tab 始终显示，不显示不存在的选手 Rating/题目难度 tab。标题区保留比赛选择下拉框，当前只有网络赛第一场。页面不展示静态说明、匹配政策和快照日期，名单来源与数据来源分行显示，并批注校排随当前排序方式变化。前瞻支持学校、中文队名和成员多词搜索、学校多选，以及学校/队名/成员/综合战力/四项评分/奖牌全部居中表头双向排序；除学校、队名、成员排序外，每种当前排序均基于未筛选结果按学校首次出现顺序独立生成校排，只在该校排名最高的队伍校名前以预留槽显示 `#x`，筛选不重算校排。评分缺失值始终置后，CPC Finder 的 `0` 在队伍单元格及队员明细中显示为 `0.00`，缺失评分显示 `—`；零分参与该列排名和数值排序，同分并列，缺失值无名次且始终置后；仅综合战力中两者同为该维度最弱值且互不超过，奖牌依次比较金、银、铜。Rating 不显示千分位，队伍分统一固定两位小数；个人明细中 XCPC Elo、上赛季和本赛季 Rating 的整数值按整数显示，XCPC Rating 与 CPC Finder 固定两位小数；除 CPC Finder 外分别使用对应来源的颜色体系。除综合战力外，每个数据单元格在主值后以 `#x` 单行显示该项在全部队伍中的竞赛名次，排名使用小号等宽数字并占用固定的 `1.9rem` 左对齐窄槽；同值并列且缺失评分不显示名次，筛选不改变这些全局名次。奖牌表头只显示“奖牌”，展示省略点号分隔，以避免窄列溢出。评分和奖牌单元格无需提示图标，正常悬浮或聚焦即显示全员明细；综合战力单元格悬浮或聚焦只显示五维雷达图。两类悬浮窗按视口空间显示在单元格上方或下方，不被表格滚动容器裁切。
- `view=preview`、`previewContest`、`previewSort`、`previewOrder` 查询状态；默认按 `power` 综合战力降序。

“赛后复盘”通过比赛下拉框选择场次，并同时显示六项指标的符合度卡片；点击卡片选择表格指标，默认综合战力。显示筛选后的两侧排名、箭头涨跌和对数上涨程度。搜索不重算统计，虚拟表在宽屏铺满容器、窄屏横向滚动。`view=review`、`reviewContest`、`reviewMetric`、`reviewSort`、`reviewOrder` 支持 URL 恢复与前进后退。

数据层以 URL 为键缓存正在进行和已完成的 JSON Promise；失败会从缓存移除以允许重试。索引和系列对象分别只验证一次，系列验证后只建立一次参赛者 ID 与单场参赛者索引。验证包括 schema 版本、必需字段与类型、唯一 ID、比赛引用范围、参赛顺序、rating 算术与连续性，以及最终 rating/参赛次数一致性。未知 schema 版本或不合法文档会显示错误面板，不静默渲染部分数据。

宽表、单场表和前瞻表仅在 DOM 中保留视口附近的行；筛选仍在已加载数据上执行。虚拟表使用显式 `colgroup`、固定 table layout 和固定 44px 行高。所有横向滚动表的冻结区均以不超过其滚动容器宽度的 50% 为硬条件。前瞻表总宽由实际列数组计算；学校、队名、成员和奖牌列的桌面上限分别为 `200px`、`170px`、`190px` 和 `150px`。容器宽于 `1120px` 时冻结学校、队名和成员三列，`600px` 到 `1120px` 冻结学校和队名；`600px` 以下只隐藏独立学校列，把队名、学校和校排合为 `clamp(150px, 42cqw, 176px)` 的单一冻结身份列，成员列保留但不冻结，点击或聚焦身份列也可查看成员。题目 Rating 表在相同断点把题号、题名和场次合为单一冻结身份列。各移动身份列保持两行紧凑排版及右侧阴影，桌面列结构与排序入口不变。系列与前瞻 JSON 当前仍一次性加载和解析；本版不引入服务端搜索或分块。

## 前端测试

### 站点标志

`static/assets/xcpc-sight.svg` 是页头和浏览器标签栏共用的可编辑矢量标志，
由三面立方体、顶部思考气泡、左侧气球和右侧灯泡组成。外轮廓、分面线和图案均为白色；
立方体保留不透明底色 `#17202a`，与标题栏的 `--ink` 背景一致，在页头融为白色线稿，
在标签栏仍有深色底块；立方体外部透明。修改标题栏背景时需同步 SVG 的 `cube` 填色。
三个图案各有独立命名的 SVG 分组，线宽随整体缩放，禁止固定屏幕像素的描边以免小尺寸糊成一团。
页头图标随标题字号缩放并预留尺寸，旁边已有站名，因此图片使用空 `alt` 避免重复朗读。
标签栏通过相对路径声明 `image/svg+xml`，支持子目录部署；当前没有为不支持 SVG favicon 的旧浏览器提供 ICO 回退。
16px 下以立方体轮廓为主要识别元素，细节以页头尺寸为准。
前端回归覆盖两处资源引用一致、文件可读、底色与页头一致、外轮廓描边和三个图案分组。

### 执行方式

四个前端测试文件使用 Node 内置测试运行器，不需要 `package.json`：

```bash
node --test tests/test_frontend_data.mjs tests/test_problem_rating_frontend_data.mjs tests/test_preview_frontend_data.mjs tests/test_review_frontend_data.mjs
```

覆盖选手、题目与前瞻 schema，真实 2535 队快照，索引两类入口，稀疏 rating、搜索/学校筛选、前瞻各列与奖牌复合排序、缺失值、三类页面 URL 状态、子路径解析、Promise 缓存、题目筛选与难度曲线。DOM 虚拟滚动、悬浮详情和浏览器交互继续通过本地 HTTP 与桌面/移动端浏览器检查。

移动端隐藏首列时只匹配普通数据行，必须排除 `.virtual-spacer`；占位单元格保留完整高度，使系列、单场和前瞻虚拟列表均可滚动至末行。2026-09-06 修复了占位单元格误隐藏导致手机选手榜停在第 37 名的问题。回归检查覆盖三种表的占位单元格可见性；在 390px 手机视口中实测从首屏滚动至 7380 名选手和 2535 支前瞻队伍的末行。

金、银、铜牌在赛前前瞻、赛后复盘及成员悬浮明细中共用固定网格：每种奖牌的图标占 1em、数量占 2ch，三组依次排列。图标居中、数字右对齐并使用等宽数字，不随一位或两位数移动；当前快照的最大数量分别为 35、24、17。奖牌顺序和排序规则保持不变，浏览器回归检查两页及移动端的各组位置一致。
