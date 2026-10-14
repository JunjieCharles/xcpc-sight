# 2026–2027 赛季与前瞻

## 正式名单来源与姓名截断

长春名单图片本身链接到对应原图，支持鼠标点击与键盘聚焦打开，图注只保留页序，不另设“查看原图”文字入口。

前瞻表格上方提供“所有队伍 / 正式队伍 / 打星队伍”三个互斥按钮，默认所有队伍；`excluded: true` 视为打星，false 或缺省视为正式。资格筛选与搜索、学校选择取交集，计数与空结果沿用表格现有展示；切换资格重置表格纵向滚动。完整名单仍先计算排名、校排、综合战力及牌线，再筛选展示，筛选不重算全局值。URL 可选 `previewTeamType=official|starred`，默认或非法值为所有队伍，默认不写参数；刷新、浏览器前进后退恢复选择，切换比赛保留选择。仅影响前瞻，其他 tab 不使用该筛选且移除该 URL 参数。纯函数测试覆盖三种资格、旧快照缺省资格、交集/空结果、输入不变及 URL；浏览器覆盖桌面/手机的切换、计数、排名保持、历史恢复与图片点击。

2026-10-14 按用户要求，在前瞻数据来源上方显示独立的“名单来源”链接，使用当前场次 `teamSource`，切换场次同步更新。西安链接到 `static/sources/icpc-2026-xian-manual.pdf`，保留正式参赛手册原文件；长春链接到 `static/sources/ccpc-2026-changchun/index.html`，按图片中的队伍序号 1–336 排序展示 10 张正式名单原图（`statusSources` 的原始记录顺序不是页序），可打开原图放大，以图片为正式名单，不发布 Excel。所有原图逐一核对既有 SHA-256，文件名与字节不变；原始本地路径不写入网页。这些附件是静态站点资源，部署时与 `static/` 一起复制，名单 JSON 仍供离线重建使用。来源标题和 URL 的更改不刷新名单、评分或快照时间；西安以后重建时也应保留正式 PDF URL，长春保留图片来源页 URL。

队员姓名及其奖项提示触发器改为普通行内元素，让单元格按字符截断，避免第二个长名字作为整块被省略；例如显示“名字 / 较长的…”而非“名字 / …”。完整姓名仍保留在单元格 title 与 DOM 中，NOI/IOI 标记、聚焦及悬浮提示保留。浏览器回归覆盖桌面 1440px/手机 390px、普通和带提示的长名字、前缀可见、溢出和来源切换；离线校验来源链接与附件哈希。

## 2026-10-14 西安正式手册名单校对

以用户提供的 `西安赛站参赛手册（发布）.pdf` 印刷页码第 6–24 页为依据，逐项核对学校、中文队名、队员与参赛资格，并目视复核跨页队名及外文姓名。PDF SHA-256 为 `ff2aa3a8c14d60c4bd5204d9763e65709521fd3f7ea86d6459b96f22a1599d7a`。原有 403 支正式队伍身份一致；手册序号 404–418 的 15 支打星队原先未收录，现补入 `static/data/rosters/icpc-2026-xian.json` 与对应前瞻，均设 `excluded: true`。保留原正式队伍顺序，打星队按手册顺序追加。总计 418 队、238 个学校/单位名称、1253 个成员条目；正式队仍为 403 队、227 校、1208 个成员条目。佛山大学“我的刀盾”在手册中仅两名队员，保持原样；备注“女队”不视为打星。

名单快照日期改为 2026-10-14，来源标题改为正式手册；身份摘录记录 PDF 哈希，随后按用户要求发布正式手册附件（含原有座位信息），见上节。评分沿用 10 月 10 日已下载的外部缓存及原有本地赛季、NOI/IOI、历史榜单，不联网刷新。定向离线生成后，原 403 队的全部前瞻记录（含评分、奖项、网络赛排名、历史战绩和 ID）逐项与修订前一致。新打星队增加 11 个 XCPC Elo 和 11 个 CPC Finder 成员匹配；未匹配值保持 null。打星不计正式排名与牌线，捧杯/金/银/铜仍为 `11 / 117 / 288 / 658`。

重建使用下文西安生成命令，将 `--teams` 改为 `static/data/rosters/icpc-2026-xian.json`、`--team-format` 改为 `roster`、`--snapshot-date` 改为 `2026-10-14`；评分来源路径及 `--cpcfinder-snapshot-date 2026-10-10` 保持不变。生成器默认以 JSON 文件名为标题，发布时将 `teamSource.title` 设置为身份摘录中的 `source`（正式手册文件名）。未修改其他场次、个人 Rating 或数据契约。

离线回归覆盖 418 队身份与评分一致性、全部 15 支打星队名单及资格、唯一 ID 与来源顺序、两人队、匹配计数、静态复制、前端 schema、403 队正式基数与既有牌线。

## 2026-10-13 武汉、成都仅牌线摘要

按用户要求，两站只加入赛站牌线汇总表，不生成完整前瞻、队伍评分或前瞻跳转。发布文件为 `static/data/regional-cutoffs/2026-2027.json`，schema v1 包含 `seriesId` 与 `contests`；每条包含 ID、标题、区域赛阶段、正式赛时间、承办学校、四条 `cutoffs`（正整数或 null）、总队数/正式队数/打星队数/至少匹配一场的正式队数，以及来源文件名、工作表名、名单/网络赛系列/学校别名文件 SHA-256 和官方公告附件 URL。不发布成员和逐队匹配明细；本地审计文件保留边界队伍和匹配明细。

站点索引该系列新增可选 `regionalCutoffsPath`，由静态生成脚本复制已提交摘要并登记，不联网、不刷新名单。未配置该路径的系列无需额外请求。`createPreviewStore.getRegionalCutoffs` 独立加载并校验摘要，与完整前瞻列表分离；`previewNavigationGroups` 合并后沿用日期排序，摘要行无按钮、链接、点击处理或选中状态，也不影响默认比赛和 URL 前瞻选择。若以后发布同 ID 的完整前瞻，完整前瞻优先且不重复展示。公开 Python 包 API 不变。

输入只使用学校、中文队名、正式/打星、队员及用于重复检查的队伍 ID；所有工作簿内网络赛名次、评分、奖牌和公式均忽略。武汉第一页是“强度分布”，明确读取“武汉报名强度表”工作表；成都读取“成都报名强度表”。按学校别名与规范化姓名重新匹配 `static/data/series/2026-2027.json` 的三场正式队伍排名，重组队伍逐场取当前成员最好值。缺失保持 null；同校同名仍无法区分。名单按给定表中的正式/打星资格纳入，不以原表评分或审核状态再筛选。捧杯按规范化学校取最强队伍后第三校，奖牌边界沿用本页既有逐档独立向上取整规则，不改变既有赛站口径。

| 赛站 | 全部 / 正式 / 打星 | 匹配正式队 | 金银铜边界队排 | 捧杯 / 金 / 银 / 铜 |
| --- | --- | --- | --- | --- |
| ICPC 成都 | 307 / 305 / 2 | 297 | 31 / 92 / 184 | 4 / 76 / 258 / 574 |
| ICPC 武汉 | 412 / 368 / 44 | 357 | 37 / 111 / 222 | 13 / 113 / 279 / 673 |

武汉工作簿 SHA-256：`c1bea19761508b1d7396527d8ac6f12c2583f69a7641e1dab69027ed78893275`；成都：`9fa5927fcce18cb29c619cf6419b5eca2c29a28b0b9988d26451b31e27fb8f23`。网络赛系列 SHA-256：`e0e4182fdc71c182c00db90f4d3e25ab70de7c012e64c03de9cc62d459398ebd`。原工作簿保持不变，不作为测试依赖或随站点发布。

2026-10-13 从 ICPC 官网下载并逐页查看官方附件：[成都邀请函与指南](https://icpc.pku.edu.cn/docs/2026-09/8bb3449cf16246568dbccbaa631cc242.pdf)，承办学校电子科技大学，正式赛为 2026-10-25 09:00；[武汉邀请函与指南](https://icpc.pku.edu.cn/docs/2026-09/bb7392b3bfde45dda21e1975945e63bf.pdf)，承办学校武汉大学，正式赛为 2026-11-01 09:00。均取第三页日程中的正式赛，而非前一天报到或热身赛；日程标为草案，后续以官方通知为准。

定向离线重算（需要原工作簿及可选 preview 依赖）：

```bash
python -m scripts.generate_regional_cutoffs --teams "C:/Downloads/武汉报名强度表_20261010.xlsx" --sheet "武汉报名强度表" --series static/data/series/2026-2027.json --contest-id icpc-2026-wuhan --title "2026 ICPC 亚洲区域赛（武汉）" --sort-at 2026-11-01T09:00:00+08:00 --host-school "武汉大学" --source-url https://icpc.pku.edu.cn/docs/2026-09/bb7392b3bfde45dda21e1975945e63bf.pdf --output static/data/regional-cutoffs/2026-2027.json --audit-output data-cache/regional-cutoffs-20261013/wuhan-audit.json
python -m scripts.generate_regional_cutoffs --teams "C:/Downloads/成都报名强度表_20261006.xlsx" --sheet "成都报名强度表" --series static/data/series/2026-2027.json --contest-id icpc-2026-chengdu --title "2026 ICPC 亚洲区域赛（成都）" --sort-at 2026-10-25T09:00:00+08:00 --host-school "电子科技大学" --source-url https://icpc.pku.edu.cn/docs/2026-09/8bb3449cf16246568dbccbaa631cc242.pdf --output static/data/regional-cutoffs/2026-2027.json --audit-output data-cache/regional-cutoffs-20261013/chengdu-audit.json
```

生成器只更新输出摘要中指定 ID，保留其他站；不注册完整前瞻。首次接入系列时由静态生成脚本在索引登记 `regionalCutoffsPath`，本次仅手工定向添加该索引字段，未运行联网的通用生成。可按上述命令重复生成相同摘要。

验证：23 项相关 Python 测试、88 项前端离线测试、Ruff 通过；另用既有 JS `buildPreviewCutoffs` 对本地逐队审计重新计算，两站结果一致。回归覆盖打星剔除、取整、同校第三、学校别名与队员重组、缺失值、不修改输入、与西安/长春口径一致、摘要 schema/独立加载/去重、静态打包和不生成前瞻。Chrome 1440px/390px 检查四站顺序、显示与点击无跳转，截图目视通过。

## 2026-10-13 前瞻导航与网络赛牌线

前瞻页移除比赛下拉框，顶部先展示紧凑的网络赛按钮，再展示赛站牌线表，最后展示当前比赛标题、时间和队伍明细。网络赛快照（含未声明阶段的旧快照）归入网络赛入口；`contestStage: "regional"` 归入赛站表。点击按钮或赛站行切换比赛并更新 URL；按钮支持键盘操作，当前场次高亮。没有对应场次时隐藏该分区。西安已移除 `unlisted`，和长春一起公开展示；通用隐藏能力仍保留。默认选择和历史导航沿用原规则，取代旧的“切换比赛…”占位选项。

赛站表包含赛站、比赛日期、承办学校、捧杯线、金牌线、银牌线、铜牌线。日期由 `sortAt` 转为北京时间的 `YYYY-MM-DD`；按日期升序，同日 ICPC 在 CCPC 之前，同类别以 ID 稳定排序。赛事类别优先从 ID 前缀识别，回退到标题，不使用承办学校推断。`hideContestTime: true` 的日期显示“—”并排在日期已知场次后。schema v1 新增可选非空字符串 `hostSchool`；缺省显示“—”，生成器 `--host-school` 写入去除首尾空白的校名。西安为西北工业大学，长春为东北师范大学，两站正式赛均为 2026-10-18，西安排在长春上方。仅定向修改两站元数据，不刷新队伍名单、评分或牌线。

### 比赛信息查询来源

维护比赛时间、承办学校等信息时，优先查询 [ICPC 北京总部公告](https://icpc.pku.edu.cn/tzgg/index.htm) 与 [CCPC 官网](https://ccpc.io/)，并进入该赛站的最新官方公告、邀请函或参赛指南核对。表中“比赛日期”采用正式赛日期，不将报到、开幕式或热身赛日期作为比赛日期；“承办学校”填写高校名称，不填写 ICPC / CCPC 赛事类别或主办委员会。草案时间保留草案说明；后续以最新官方通知为准。新增或修订元数据时在本文记录具体来源链接与核验日期，不凭城市名猜学校，也不因核对元数据刷新评分快照。

2026-10-13 核验来源：西安使用[官方参赛指南](https://icpc.pku.edu.cn/docs/2026-09/414cce375b4e4ce99dafececfb6ac3f5.pdf)（正式赛在西北工业大学长安校区），长春使用[盖章邀请函](https://ccpc.io/uploads/20260930/2026CCPC%E9%95%BF%E6%98%A5%E7%AB%99%E9%82%80%E8%AF%B7%E5%87%BD%E7%9B%96%E7%AB%A0%E6%B8%85%E6%99%B0%E7%89%88.pdf)的已有本地摘录（东北师范大学信息科学与技术学院承办，自由校区举行）；本次官网 PDF 工具无法重新打开长春邀请函，未声称重新下载。

### 牌线计算与验证

前端纯函数 `buildPreviewCutoffs(preview)` 从完整快照计算，与搜索、学校筛选和明细排序无关。排除打星后，按三场网络赛名次的最好、次好、第三成绩依次升序排列，缺失成绩置后。捧杯取每校最佳队伍去重后的第三所学校；金银铜分别取正式队数 N 的 `ceil(N/10)`、`ceil(N/10)+ceil(2N/10)`、`ceil(N/10)+ceil(2N/10)+ceil(3N/10)` 位置。表中显示边界队伍三场最好名次，同最好名次显示相同数值；并列不额外增加位置，数字不能区分次好成绩破同分的情况。缺失成绩的正式队伍仍计入 N，但边界无成绩或位置不存在时显示“—”。这是基于已有队员匹配结果的前瞻估计，不代表实际奖牌结果。

西安 403 支正式队伍对应捧杯/金/银/铜 `11 / 117 / 288 / 658`；长春排除 36 支打星，300 支正式队伍对应 `10 / 84 / 252 / 576`。数据来自已发布快照，不重新生成或刷新名单、评分。`previewNavigationGroups(previews, currentId)` 控制分区、排序和隐藏场次展示。Python 公开 API 不变；JSON 的可选扩展为上述 `hostSchool`。

离线回归覆盖正式名额逐档取整、同校去重、三场排序、并列、空名单、缺失成绩、输入不变、真实两站牌线和隐藏场次分区；新增北京时间跨日、同日 ICPC 优先、未知日期置后、公开西安、承办学校校验与生成器选项回归。29 项相关 Python 测试通过。浏览器检查桌面/移动端布局、日期和校名、赛站顺序、行点击、网络赛切换和 URL 历史恢复。手机端日期分为年份与月日两行，七列保持在页面宽度内。

本次 87 项前端离线测试、Ruff 通过。通过 HTTP 提供 `static/` 后，Chrome 在 1440px 与 390px 下完成浏览器回归及截图目视检查。可选浏览器测试为 `tests/test_preview_browser.mjs`：设置 `PREVIEW_BROWSER_URL` 为本地 Chrome 调试地址、`PREVIEW_SITE_URL` 为站点地址（默认 `http://127.0.0.1:8000/`），运行 `node --experimental-websocket --test tests/test_preview_browser.mjs`；Node 22+ 可省略 WebSocket 实验开关。可选 `PREVIEW_SCREENSHOT_DIR` 指定截图目录；未设置调试地址时跳过测试，不增加 npm 依赖。

## 2026-10-11 长春站名单前瞻

新增公开前瞻 `ccpc-2026-changchun`，在比赛选择器中展示并成为默认公开场次。身份来源为用户提供的 `参赛队伍-2026 CCPC国赛（长春）.xlsx` 首张表，SHA-256 为 `dff68670a695d6aa600685d9fe90266d63f4e74d45179604273816fa0268a858`。保留来源顺序，共 336 队、209 校、1007 个成员条目；海南大学“主播我第一次打ccpc能不能赏我块牌啊”在原表仅两名队员，保持原样，不补人。只提取“所属学校”“中文队名”“队员1姓名”至“队员3姓名”，使用正整数“序号”检查重复；忽略教练列，不发布原始工作簿。来源没有类型列，首次生成时全部按正式队伍处理；10 月 11 日后续按用户提供的图片修订参赛资格，见下文。身份摘录保存为 `rosters/ccpc-2026-changchun.json`。

根据用户提供的[盖章邀请函](https://ccpc.io/uploads/20260930/2026CCPC%E9%95%BF%E6%98%A5%E7%AB%99%E9%82%80%E8%AF%B7%E5%87%BD%E7%9B%96%E7%AB%A0%E6%B8%85%E6%99%B0%E7%89%88.pdf)，正式名称为“2026年中国大学生程序设计竞赛国赛（长春）”；页面按用户要求简写为“2026年CCPC国赛（长春）”，正式赛北京时间为 **2026-10-18 09:00–14:00**。已恢复时间展示，`sortAt` 为真实开赛时刻，新增可选 `endAt` 为结束时刻；前端统一按北京时间显示起止时间，同日只显示一次日期，跨日显示两端日期。邀请函第二页注明日程为草案，后续以赛事通知为准。生成器 `--end-at` 可指定结束时刻，要求晚于 `--sort-at`；前端校验日期有效性及先后关系。可选布尔字段 `hideContestTime` 和生成参数 `--hide-contest-time` 仍支持其他未确认时间的场次；省略或 false 显示时间，true 隐藏，切换场次恢复自身设置。公开 Python API 不变。

评分沿用 10 月 10 日已下载的外部快照，不声称是 10 月 11 日最新线上值：XCPC Rating `2026-09-28T19:57:35.521003+00:00`、XCPC Elo `2026-09-28T13:47:09.716Z`、CPC Finder `2026-10-10`。分别匹配 929、948、437 个成员条目；上赛季 Rating 匹配 532 人，本赛季匹配 883 人。网络赛三场分别匹配 790 / 801 / 813 个成员条目，183 队关联上赛季区域赛/总决赛。NOI/IOI 和历史榜单沿用已有缓存。区域赛标色、归一化 LSE、CPC Finder 最高分、奖牌求和及五维综合战力均沿用西安站规则。旧场次与个人 Rating 文件保持原样。

XLSX 导入兼容原西安表头与本次 CCPC 导出表头；重复表头、序号、缺失身份、成员重复和公式身份带原始行号报错。名单、当前/上赛季评分及三场网络赛排名完整离线回归，前端验证 336 队 schema、五维战力、公开索引及时间隐藏/恢复；静态生成器测试覆盖名单和前瞻一并复制。公开 Python API 不变。

```bash
python -m scripts.generate_preview_data --teams static/data/rosters/ccpc-2026-changchun.json --team-format roster --xcpcrating-data data-cache/preview-sources-20261010/xcpcrating --xcpc-elo-data data-cache/preview-sources-20261010/xcpc-elo-data.js --previous-series static/data/series/2025-2026.json --current-series static/data/series/2026-2027.json --online-series static/data/series/2026-2027.json --history-srk-root data-cache/external/xcpcrating/vendor/srk-collection/official --cpcfinder-pages data-cache/preview-sources-20261010/cpcfinder-pages --cpcfinder-snapshot-date 2026-10-10 --snapshot-date 2026-10-11 --preview-id ccpc-2026-changchun --contest-stage regional --host-school "东北师范大学" --preview-title "2026年CCPC国赛（长春）" --team-source-url ./data/rosters/ccpc-2026-changchun.json --sort-at 2026-10-18T09:00:00+08:00 --end-at 2026-10-18T14:00:00+08:00 --output static/data/previews/ccpc-2026-changchun.json
```

### 图片名单参赛资格修订

用户补充 10 张图片，覆盖图片序号 1–336。末张图明确说明：★为打星队伍，★★为女队，★★★为打星女队。仅单星与三星设为 `excluded: true`，双星女队保持正式。共匹配并更新 **36 支打星队伍、300 支正式队伍**；除下述湖南农业大学名单更正外，其他 335 队身份、评分、网络赛成绩和历史履历保持不变；全部来源快照时间不变。前端沿用已有打星规则：保留展示评分，但不参与综合战力、列内名次、校排和区域赛奖牌色档的正式队伍基数。

图片与 XLSX 的排序不同，按学校、队名和队员身份核对，不直接套用图片序号。图片单星/三星队伍序号为 4、51–53、69–71、91–93、104、106–107、116、147–148、151–152、154–159、175–177、181、185、211–212、241、284–286、289。图片 287“力拔山兮”为双星正式女队，212“贪得吴彦组”为三星打星女队。湖南农业大学按用户要求以图片为准，将 XLSX 的“喝生椰就不会拿铁咯”（李恩泽、邓从权、黄恩豪）替换为双星正式女队“零罚时”（黄瑞莎、周静、颜诗祺）。仅该队使用原有来源缓存重新匹配评分、奖牌、网络赛排名及历史记录，重建稳定队伍 ID，保留原来源顺序；不继承旧队成绩。匹配人数和总队数保持不变。

`rosters/ccpc-2026-changchun.json` 的 `excluded` 是人工核对后的资格快照；`statusSources` 保存 10 张图片文件名及 SHA-256，`note` 记录标记含义。原图起初只用于本地核对，2026-10-14 按用户要求作为正式名单加入站点，见本文“正式名单来源与姓名截断”。离线回归固定全部 36 个打星队名，校验名单与前瞻资格一致、双星女队仍正式、三星女队打星、打星无战力及网络赛列内名次。

后续生成使用上方 `--team-format roster` 命令，直接读取核对后的 `rosters/ccpc-2026-changchun.json`，同时保留修订身份和资格。导入器只读取学校、队名、1–3 名成员和布尔 `excluded`，忽略已有评分；校验非空身份、公式身份、重复成员、重复队伍和资格类型，保持来源顺序。原始 XLSX 不包含后续修订，不能直接用原 XLSX 重新覆盖发布数据。离线测试覆盖身份名单导入、资格保留、非法输入与名单全量评分/网络赛排名核对。

默认静态生成器只复制本场已提交快照，不自动刷新评分。站点索引由既有已发布系列、全部前瞻与复盘离线重投影。

本次验证：63 项相关 Python 测试、83 项前端测试、Ruff 和差异空白检查通过；复现命令输出逐字段一致，本地页面、索引、前瞻和名单 HTTP 均返回 200。浏览器控制连接失败，未完成桌面/移动端视觉验收。

## 2026-10-10 西安站名单前瞻

保留 `icpc-2026-xian` 独立前瞻，设置 `unlisted: true`；主站比赛下拉框不显示西安站，未指定场次或场次无效时仍默认选择最新公开的 CCPC 网络赛。显式 `?series=2026-2027&view=preview&previewContest=icpc-2026-xian` 可直接访问，刷新和 URL 恢复继续保留西安站。直达页的选择器显示“切换比赛…”并仅提供公开比赛。静态索引仍登记其文件供链接解析和打包，隐藏仅影响导航，并非访问控制。仅从用户提供的 `西安报名强度表_final_20261006.xlsx` 首张表提取学校、中文队名、类型、队员及用于重复检查的队伍 ID，保持来源顺序。共 403 队、227 校、1208 个成员条目，全部正式。文件 SHA-256 为 `9eb9b7c0f8e6fc5933a5b27552680b3eee74d14a1546ff6ed99b6ea784b2c8be`。忽略表内全部评分、奖牌、排名和匹配说明，不读取其他工作表，不写回 XLSX。身份摘录保存为 `static/data/rosters/icpc-2026-xian.json`，静态生成器一并复制名单和前瞻。

正式赛时间按[官方参赛指南草案](https://icpc.pku.edu.cn/docs/2026-09/414cce375b4e4ce99dafececfb6ac3f5.pdf)设为北京时间 2026-10-18 09:00。10 月 10 日重新下载公开评分：XCPC Rating 版本 `2026-09-28T19:57:35.521003+00:00`，632 页、63120 条正式榜记录；XCPC Elo 版本 `2026-09-28T13:47:09.716Z`、67513 人；CPC Finder 当日 250 页、24974 条，校验总数与唯一 studentId。缓存位于 `data-cache/preview-sources-20261010/`。前两者分别匹配 1170 / 1171 个成员条目，CPC Finder 匹配 600 人。项目上赛季评分匹配 698 人，本赛季评分匹配 1108 人，使用 9 月 23 日校正后的三场赛季数据。NOI/IOI 与上赛季历史沿用缓存。所有评分仍按原成员匹配、归一化 LSE、CPC Finder 最高分及奖牌求和规则重算。

### 网络赛排名与本场综合战力

前瞻表的 Rating 列展示顺序为 XCPC Rating、XCPC Elo、本赛季 Rating、上赛季 Rating、CPC Finder；未提供本赛季评分的旧场次保留原顺序。表头与数据单元格共用展示排序，不修改快照来源顺序、评分或综合战力。回归覆盖双赛季、单赛季和输入不变。

仅区域赛正赛前瞻中的综合战力、网络赛排名和各项 Rating（除 CPC Finder）单元格按该列全场队伍名次标注浅金、浅银、浅铜底色。基数为未筛选的正式队伍总数 N，各档名额分别为 ceil(N/10)、ceil(2N/10)、ceil(3N/10)，累计划分排名区间；西安 403 队对应 #1–41、#42–122、#123–243。按竞赛排名处理并列，同名次同色，因此边界并列可能增加实际着色队数。缺失名次和打星不标色，CPC Finder、奖牌及学校名次不标色。排序、筛选和悬浮不改变底色，网络赛列使用当前名单内的综合名次，不使用三场原始名次分别着色。这仅是前瞻档位提示，并非正式获奖结果。通过可选 `contestStage: "regional"` 显式启用标色；省略或 `"preliminary"` 不标色，三场网络赛均不标色。生成器 `--contest-stage regional` 用于区域赛，默认 preliminary；未知阶段或显式 null 拒绝。测试覆盖真实三场网络赛均无标色、西安保留标色、阶段校验、独立向上取整、各档边界、并列、缺失、打星、排除列和小规模名单。

- 一个“网络赛排名”列按 ICPC1 / ICPC2 / CCPC 展示三场排名；悬浮或聚焦显示每名成员的三场记录。
- 三场排名使用各 4ch 的固定数字槽，数字与缺失标记右对齐，斜线单独占固定居中槽；内部名次沿用独立排名槽并增加间距。副标题居中。队员明细使用相同网格，避免不同位数导致错位；渲染回归覆盖一位、四位及缺失值。排序、数据契约不变。
- 来源为项目赛季 `participations[].contestRank`，即排除打星、无提交并重建并列排名后的正式队伍名次。按规范化姓名＋学校与别名匹配；同身份多条记录逐场取最好值，重组队伍逐场取当前队员最好排名。缺失为 null，显示“—”，不填 0 或 9999。三场分别匹配 1048 / 1047 / 928 个成员条目，384 队至少有一场成绩。同校同名仍不能区分真实重名。
- 展示顺序固定；比较时把有效排名从小到大排列，缺失作为最弱值，依次比较最好、次好、第三好，全部相同则并列。支持双向排序、列内竞赛排名和随排序变化的校排；全缺失在双向排序中均置后，无列内名次。筛选不重算全局排名，打星不参与排名基数。
- 西安站综合战力只含 XCPC Rating、XCPC Elo、上赛季 Rating、本赛季 Rating、网络赛排名五维。三场排名整体作为一个维度，沿用逐维严格超过的正式队伍数、计数降序元组比较。CPC Finder 和奖牌仍展示、排序并计算内部名次，但不计战力，也不能单独触发战力名次。雷达图标签与实际五维一致。
- 旧三场赛前快照及复盘保留原维度，避免将赛后网络赛成绩回填历史前瞻。

### 数据契约、导入与验证

schema v1 新增可选 `onlineContests`（固定三场 ID 与标题），队伍及成员的 `onlineRanks`（三个正整数或 null），以及 `powerMetrics`（明确战力维度 ID）。省略配置兼容旧规则“全部 metricSources ＋ medals”；显式维度必须非空、无重复且引用已知来源。网络赛字段校验长度、正整数和队伍逐场最低排名聚合。前端 `buildPreviewPower(teams, metricIds, powerMetrics)` 新增可选第三参数，`previewPowerMetricIds(preview)` 解析默认配置；`compareOnlineRanks` 正数表示左侧更强。新增排序键 `onlineRanks`。Python core/rating 公开 API 与导出不变。

生成器新增 `--team-format xlsx`、`--online-series` 和 `--unlisted`。前瞻可选布尔字段 `unlisted` 省略时为 false，非布尔值拒绝；标记只影响页面比赛选项和默认选择，评分、排序和静态文件保持可用。回归覆盖隐藏场次不出现在选项、普通入口/无效 ID 默认公开场次、显式直达、仅隐藏场次列表以及标记类型验证。XLSX 使用可选依赖 `pip install -e ".[preview]"`，只支持本次中文身份表头；未知类型、缺失身份、重复 ID/成员和公式身份带行号报错。网络赛输入要求三场齐全且早于前瞻；新模式也拒绝不早于前瞻的外部 Rating/Elo 快照。

```bash
python -m scripts.generate_preview_data --teams "C:/Downloads/西安报名强度表_final_20261006.xlsx" --team-format xlsx --xcpcrating-data data-cache/preview-sources-20261010/xcpcrating --xcpc-elo-data data-cache/preview-sources-20261010/xcpc-elo-data.js --previous-series static/data/series/2025-2026.json --current-series static/data/series/2026-2027.json --online-series static/data/series/2026-2027.json --history-srk-root data-cache/external/xcpcrating/vendor/srk-collection/official --cpcfinder-pages data-cache/preview-sources-20261010/cpcfinder-pages --cpcfinder-snapshot-date 2026-10-10 --snapshot-date 2026-10-10 --preview-id icpc-2026-xian --contest-stage regional --host-school "西北工业大学" --preview-title "2026 ICPC 亚洲区域赛（西安）" --team-source-url ./data/rosters/icpc-2026-xian.json --sort-at 2026-10-18T09:00:00+08:00 --output static/data/previews/icpc-2026-xian.json
```

离线回归覆盖身份列白名单、错误行号、跨校同名、学校别名、重复身份最好名次、重组与缺失成绩、来源时间、整份名单与本地评分、三层排名比较、全缺失双向置后、并列与打星、CPC Finder/奖牌不影响战力、schema 及旧快照兼容。新增测试位于 `tests/test_preview_roster.py`、`tests/test_online_preview.mjs`。本地 HTTP 服务验证返回 200；本次浏览器控制连接超时，未完成视觉验收。

## 2026-09-23 CCPC 官方榜单修订（当前发布版本）

使用 [RankLand 官方榜单](https://rl.algoux.cn/collection/official?rankId=ccpc2026preliminary) 的新 SRK（文件 ID `95451702349623296`，SHA-256 `d579046c9b6bde35c9b0178fdcda574c8a2ca7f9d1a52b2110349dd2010594b1`），替换 9 月 19 日 CCPC 输入，沿用下文修订后的两场 ICPC 输入，从空状态重算三场 Rating。新旧榜单只差三支正式队伍，具体差异和复盘来源见 [赛后复盘](post-contest-review.md#2026-09-23-官方结果修订当前发布版本)。不变更算法、默认身份规范化、重复身份政策、API 或 schema。

CCPC 有效队伍从 2109 减至 2106，计分个人从 6260 减至 **6251**，其中 5724 人接续评分、527 人首次计分。本赛季累计 **8926 人**，Rating 范围仍为 1247–1991。三支移除队伍涉及九人：六人保留前两场 ICPC 历史并恢复赛前分，三人没有其他有效历史，退出本赛季榜单；不按本场移除追溯删除其他比赛记录。前两场 8399 人的所有历史逐项核验不变，未计入本场的 2675 人沿用已有分数。保留身份中共 275 人的最终分数发生变化。

更新 `static/data/series/2026-2027.json` 与 CCPC 复盘，从全部发布数据重投影索引后内容不变。三场前瞻、前两场复盘及其他系列保持原样，前瞻中的本赛季评分仍截止第二场。回归固定三场 7380 / 7464 / 6251 人次、527 名新人、8926 人总数、评分连续性，以及被移除的三名独有身份和保留历史的六人。

固定输入缓存为 `data-cache/results-20260919/` 的 ICPC 两场和 `data-cache/results-20260923/` 的 CCPC。保存文档列出的固定 URL 文件后，可离线重算：

```python
import hashlib
import json
from pathlib import Path
from core import SEASON_2026_2027, normalize_srk_contest, select_season
from rating import calculate_series_ratings, project_series_rating_data
from scripts.generate_static_data import write_json_atomic

inputs = [
    ("icpc2026preliminary-1", "results-20260919", "icpc2026",
     "8ca3ddf111c255b352021678000f4bac0040aa3e3f2cd827fd2fdc260f0dbd0b"),
    ("icpc2026preliminary-2", "results-20260919", "icpc2026",
     "a501dca75c4814277ed6a7b897db379b5ee4b3b1b560be4bc0c2cc8c84fb3fc9"),
    ("ccpc2026preliminary", "results-20260923", "ccpc2026",
     "d579046c9b6bde35c9b0178fdcda574c8a2ca7f9d1a52b2110349dd2010594b1"),
]
contests = []
for contest_id, directory, collection, sha256 in inputs:
    raw = Path(f"data-cache/{directory}/{contest_id}.srk.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError(f"{contest_id}: SHA-256 mismatch")
    contests.append(normalize_srk_contest(
        json.loads(raw), contest_uk=contest_id, series=collection,
    ))
season = select_season(tuple(contests), SEASON_2026_2027)
document = project_series_rating_data(
    calculate_series_ratings(season.contests),
    series_id="2026-2027", title="2026–2027 ICPC + CCPC",
)
write_json_atomic(Path("static/data/series/2026-2027.json"), document)
```

## 2026-09-19 CCPC 赛后 Rating（历史记录）

本赛季个人 Rating 已计入 `ccpc2026preliminary`，共三场比赛。使用复盘同一份固定 SRK（文件 ID `94747179192774656`，SHA-256 `ae8673050d54cc9a793aee461ca74c5cba11948c5a3642d393f3249818687cf2`），与下节修订后的两场 ICPC SRK 一并核验哈希，经 `normalize_srk_contest`（CCPC collection 为 `ccpc2026`）→ `select_season(SEASON_2026_2027)` → `calculate_series_ratings` → `project_series_rating_data` 从空状态离线重算，沿用默认身份规范化与重复身份取最好排名规则。

CCPC 的 2109 支有提交正式队伍对应 6260 个规范化个人身份，排除打星和无提交队伍；其中 5730 人接续既有评分、530 人首次从 1400 起算。本赛季累计 8929 人，最终 Rating 范围为 1247–1991。前两场全部 8399 人的历史逐项保持一致；未参加本场的 2669 人保持原分。

只更新 `static/data/series/2026-2027.json`，从全部已发布系列、前瞻和复盘重投影索引后内容不变。三场前瞻和复盘保持原样，CCPC 前瞻的 `currentSeason` 仍为第二场结束时的评分，不能回填本场赛后分。前瞻回归从已发布系列截取前两场历史恢复赛前分后核验，而非使用最新 `finalRating`。首次生成前瞻的命令中的 `--current-series` 需指向截至第二场的历史快照。

前端回归覆盖三场顺序、7380 / 7464 / 6260 人次、530 名新人的初始值、所有选手跨场连续性和最终评分范围。固定 SRK 缓存位于 `data-cache/results-20260919/`（ICPC 两场）与 `data-cache/review-20260919/`（CCPC）；算法、公开 API 和数据契约不变。

## 2026-09-19 官方榜单修订（CCPC 计分前）

按 [srk-collection PR #73](https://github.com/algoux/srk-collection/pull/73) 合并版本及已同步的 RankLand 数据，重新计算本赛季个人 Rating，并只刷新 CCPC 网络赛前瞻中的 `currentSeason`。不改评分算法，不把第二场赛后评分回填到两场 ICPC 赛前快照；第一场全部个人参赛历史与原发布结果逐项一致。第二场移除的队伍仍可能有有效的首场历史，不据此删除跨场身份。

固定输入均核验实际下载字节 SHA-256，解析后的 JSON 与上游提交 `ae959416ef2955159f9affd45d4ab53bf299a98e` 一致：

| 场次 | RankLand file ID | SHA-256 |
| --- | --- | --- |
| 第一场 | `94656957302009856` | `8ca3ddf111c255b352021678000f4bac0040aa3e3f2cd827fd2fdc260f0dbd0b` |
| 第二场 | `94656957834690560` | `a501dca75c4814277ed6a7b897db379b5ee4b3b1b560be4bc0c2cc8c84fb3fc9` |

下载路径为 `https://cdn.algoux.cn/rankland/file/{fileId}/icpc2026preliminary-{1或2}.srk.json`。仍通过 `normalize_srk_contest`（collection 为 `icpc2026`）→ `select_season(SEASON_2026_2027)` → `calculate_series_ratings` → `project_series_rating_data` 从空状态重算，两场分别有 7380 / 7464 个规范化选手身份；累计 **8399 人**，6445 人参加两场、1019 人第二场首次参赛、935 人仅参加第一场。最终 Rating 范围仍为 1283–1904；第二场有效提交队伍为 2521 支。

CCPC 前瞻名单仍为 2173 队、6443 个成员条目；本赛季评分仍匹配 5878 个成员条目，418 个成员分和 152 支队伍归一化 LSE 分变化。采用原 `PersonIndex` 的学校/姓名规范化和最高分消歧策略，仅更新成员与队伍 `ratings.currentSeason` 及对应来源时间/匹配计数。来源比赛时间仍为 2026-09-12 13:00；综合战力由前端从修订后评分自动重算。名单、打星状态、其他来源评分、奖牌、历史战绩和来源日期均逐项核验不变；不擅自刷新外部 XCPC Rating/XCPC Elo。

可用下文首次生成命令和保存的来源缓存重建 CCPC 前瞻：`--current-series` 使用修订后的 `static/data/series/2026-2027.json`，`--xcpc-elo-data` 使用 `data-cache/preview-sources-20260918-elo-refresh/xcpc-elo-data.js`，其余输入保持既有版本。数据快照日期仍指名单/外部源获取日期，本次修订时间由本节记录。

离线回归覆盖新的赛季人数与跨场连续性，并逐一验证 CCPC 全部成员的本赛季评分来自修订后的已发布系列、未匹配值和完整 LSE 聚合。两场 ICPC 前瞻与其他赛季/题目 Rating 文件字节未变。2026-09-19 验证通过：209 项 Python 测试、70 项前端数据测试、Ruff 和差异空白检查；1920px/390px 浏览器中第二场复盘、CCPC 前瞻和本赛季 Rating 均正常加载，无脚本异常。第二场复盘的显式移除状态和新符合度基准见 [赛后复盘](post-contest-review.md#2026-09-19-官方结果修订当前发布版本)。下文 9 月 12 日的人数为首次发布时的历史记录，以本节为当前版本。

## 2026 CCPC 网络预选赛

2026-09-18 按用户指定的 [Pintia 公开榜单](https://pintia.cn/rankings/2099750481526394880) 添加 `ccpc-2026-preliminary`，比赛时间为北京时间 2026-09-19 13:00–18:00。名单读取公开只读接口 `/api/competitions/2099750481526394880/xcpc-rankings/public`，保留返回顺序，共 2173 队、439 所学校、6443 个队员条目，其中 2169 队正式、4 队打星。不把无提交队伍过滤掉，不读取本场解题数或排名作为前瞻指标；仅代表获取时接口公开的名单，不保证覆盖未公开或后来变更的报名。

原始响应缓存在 `data-cache/pintia-investigate/rankings.json`，SHA-256 为 `e50a5d0831c41fd3d11f07b680fcf5a23041643670417f66d03a8ef2fd6ea3f1`。发布快照为 `static/data/previews/ccpc-2026-preliminary.json`，索引和默认静态生成器均纳入第三场；页面按开赛时间默认选择本场，旧场次可继续通过下拉框或 URL 访问。旧两场快照不刷新。

五项评分采用既有六维综合战力规则：XCPC Rating、XCPC Elo、上赛季和本赛季 Rating 按已匹配队员归一化 LSE 聚合，CPC Finder 取最高值，奖牌求和。XCPC Rating 使用线上 `2026-09-17T17:17:00.323004+00:00` 版本（629 页，共 62852 条正式榜记录，下载后复核元信息），XCPC Elo 使用 `2026-09-17T15:31:35.519Z` 版本（67184 人），缓存位于 `data-cache/preview-sources-20260918/`。本仓库本赛季 Rating 截至 9 月 12 日 ICPC 第二场；CPC Finder 沿用 9 月 4 日缓存。五项分别匹配 6154、6149、2626、5878、1976 个队员条目；840 队关联 2773 条上赛季区域赛/总决赛记录。NOI/IOI 沿用既有缓存与姓名匹配政策。

2026-09-18 再按用户要求仅刷新本场 XCPC Elo，当前版本为 `2026-09-18T12:04:21.949Z`（北京时间 20:04），上游仍为 67184 人，比赛范围截至 9 月 12 日 ICPC 第二场。匹配人数仍为 6149，6149 个队员 Elo、2098 支队伍聚合 Elo 变化；按既有归一化 LSE 重算，综合战力由前端随评分重算。逐项核验只有成员/队伍 `xcpcElo`、其来源时间及匹配计数字段可变，其余评分、名单、打星状态、历史战绩和两场 ICPC 快照均保留。缓存及核对摘要位于 `data-cache/preview-sources-20260918-elo-refresh/`，下载文件 SHA-256 为 `e8d64fc2f89b00930774885ce98946f848a45de7f5f6d4f113597248f1c383fb`。下方首次生成命令若要复现当前评分，应把 `--xcpc-elo-data` 改为此目录的 `xcpc-elo-data.js`。离线快照测试校验新的来源时间、6149 人覆盖和完整聚合契约。

XCPC Elo 最新数据的 history 第四项可以为 null，表示该场不计分。导入器按其 [官方前端 computeCurrentRating](https://zzzzzzyt.github.io/xcpc-elo/app.js) 从后向前取最近非空值；全部为空或无历史时使用上游 `initialRating`。这不等于为名单中未匹配到的成员补分，后者仍保持 null。

生成器新增 `--team-format pintia-public`，直接读取缓存响应；默认 `registration` 兼容原报名表。名单适配检查非空队伍列表、唯一且非空的 `teamFid`、学校/队名/成员字符串和布尔型 `excluded`，错误携带来源行号。只使用 `memberNames`，不读取教练列。Python 核心公开 API 不变。

schema v1 每队新增可选布尔值 `excluded`，省略视为正式队伍，显式 null 或非布尔值拒绝。打星队伍在任何排序下保留对应指标位置及评分、奖牌、队员和历史资料；整行淡紫色、队名加 ★、综合战力列显示“打星”。不显示综合战力名次、各项评分名次、奖牌名次或学校名次。评分与奖牌单元格始终保留和正式队伍一致的 `1.9rem` 排名槽，无排名时内容留空，主值不向右移动；缺失值也保留同样占位。历史比赛排名仍为历史事实，保留展示。渲染回归覆盖有排名、无排名的 Rating、奖牌和缺失值使用同一网格及空排名槽。

排名基数仅含非打星队伍：评分和奖牌竞赛排名先排除打星队伍；综合战力各维度统计严格超过的正式队伍数，打星队伍自身也据此计算排序元组但不给名次，且不增加正式队伍计数或挤占名次。雷达图按正式队伍数减一归一化。校排跳过打星队伍，同校由最前面的正式队伍获得校排。搜索和筛选不重算这些全局值；全部打星时各排名为空。数据不足的打星队伍沿用普通缺失值排序。

复现命令（先取得上述公开响应和来源缓存）：

```bash
python -m scripts.generate_preview_data --teams data-cache/pintia-investigate/rankings.json --team-format pintia-public --xcpcrating-data data-cache/preview-sources-20260918/xcpcrating --xcpc-elo-data data-cache/preview-sources-20260918/xcpc-elo-data.js --previous-series static/data/series/2025-2026.json --current-series static/data/series/2026-2027.json --history-srk-root data-cache/external/xcpcrating/vendor/srk-collection/official --cpcfinder-pages data-cache/cpcfinder-pages --cpcfinder-snapshot-date 2026-09-04 --snapshot-date 2026-09-18 --preview-id ccpc-2026-preliminary --preview-title "2026年CCPC网络预选赛" --team-source-url https://pintia.cn/rankings/2099750481526394880 --sort-at 2026-09-19T13:00:00+08:00 --output static/data/previews/ccpc-2026-preliminary.json
```

离线测试使用缩减的真实 Pintia 响应，覆盖零提交、打星、教练排除、非法身份、重复 ID、来源说明，以及 Elo 尾部不计分、全不计分、空历史和零分。前端校验完整 CCPC 快照、三场索引加载、评分聚合和匹配人数、来源早于比赛时间、六维战力；打星回归覆盖高于/居中/同分/缺失数据的位置、升降序、正式队伍计数与名次不变、同校打星不占校排、全打星和非法字段。静态资源版本更新为 `20260918-52`。

## 综合战力数据缺失时的展示

所有前瞻的正式队伍共用以下规则：在该场 `metricSources` 中，所有经 `previewRatingValue` 处理后的队伍评分均为空，且金、银、铜累计均为零时，`buildPreviewPower` 返回的 `rank` 为 `null`。CPC Finder 的零分沿用既有规则视为该维度缺失；其他 Rating 的零分仍是有效数据，任一有效评分或任意非零奖牌均可获得综合战力排名。NOI/IOI 成绩和历史战绩不属于综合战力维度，不能单独触发排名。

前端综合战力单元格仅显示“—”，不创建可聚焦控件、悬浮窗或雷达图。保留原始超过队伍数、排序元组、全场排序基数和其他队伍名次；这是数据可用性判定，不是把所有计数为零的队伍都隐藏。同分的有效数据队伍即便未超过任何队伍，也保留排名和雷达图。当前第一场 563 队、第二场 155 队无综合战力排名。复盘沿用自己的非零计数筛选，指标及已有统计不变。

离线回归覆盖五维与六维输入全缺失、仅 CPC Finder 零分、普通 Rating 零分、部分评分、仅奖牌、有效数据但计数全零，以及两场真实快照中无排名实体不创建雷达图或焦点控件、有排名实体保留交互。静态资源版本统一更新以刷新浏览器缓存；评分快照及 Python 公开 API 不变。

## 赛季范围与当前页面

`core.seasons.SEASON_2026_2027` 定义 `2026-2027` 系列，候选比赛来自 RankLand official collection 的 `icpc2026` 与 `ccpc2026`，沿用邀请赛排除、显式 include/exclude 覆盖和同日 CCPC 优先的排序规则。公开 API 为 `SEASON_2026_2027` 与 `load_2026_2027_season`。

当前已发布 ICPC 网络预选赛第一场、第二场及 CCPC 网络预选赛的选手 Rating，同时提供这两场及 CCPC 网络预选赛的三场赛前前瞻，并已发布这三场赛后复盘（CCPC 复盘只包含 2169 支正式队伍）。站点索引在同一条记录提供 `path`、`previewPath`、`previews` 与 `reviewPath`；本赛季尚未发布题目难度数据。复盘规则、结果关联及全指标符合度对比见 [赛后复盘](post-contest-review.md)。

2026-09-06 从 RankLand 获取 `icpc2026preliminary-1`，比赛时间为北京时间 13:00。上游共 2535 支正式队伍，排除 39 支无提交队伍后，2496 支队伍的 7380 个规范化选手身份参与计算。新赛季从空状态、初始 Rating 1400 开始，不继承上赛季评分；首次发布的最终 Rating 范围为 1334–1720。沿用学校与姓名身份规范化、成绩重建排名和重复身份取最好排名政策。

上游 SRK 文件 ID 为 `90036200580141056`，SHA-256 为 `39077e4904169b353f85c4484efa5fe9064727ba00cf6685661270d5d9bf7575`。发布文件为 `static/data/series/2026-2027.json`，默认生成器已接入 `load_2026_2027_season`；后续重新生成使用当时的实时上游数据。离线测试覆盖生成器的新赛季加载、已发布首场数据的 1400 初始值与 Rating 算术，以及索引同时包含 Rating 和前瞻入口。

2026-09-12 将第二场 `icpc2026preliminary-2` 纳入个人 Rating。使用与复盘相同的固定 SRK（文件 ID `92205039610843136`，SHA-256 `ab6a796e4ca65f1ba6dc8c9c87174a49aab7439cee6aacee17d3ce1285a9ceea`），与上述首场固定版本均核验下载哈希后，经 `normalize_srk_contest` → `select_season(SEASON_2026_2027)` → `calculate_series_ratings` → `project_series_rating_data` 离线生成。沿用默认身份规范化、重复身份取最好排名和初始 1400 规则。

第二场 2535 支有提交正式队伍对应 7505 个规范化选手身份；两场累计 8404 人，其中 6481 人参加两场，1024 人第二场首次参赛，899 人仅参加第一场。新选手从 1400 开始，复赛选手接续第一场评分，缺席者保持评分。最终 Rating 范围为 1283–1904。重新计算首场投影与原发布文件逐项一致，所有首场参赛历史均保留；两场前瞻及复盘指标仍使用赛前快照，不回填第二场赛后评分。

同时从全部已发布系列、前瞻及复盘重新投影站点索引，结果与既有索引一致。离线回归校验两场顺序、各场人数、首次参赛初始值、跨场连续性、缺席保分和最终评分范围；算法、公开 API 与数据契约不变。

## 名单来源与更新边界

第一场 2535 支队伍来自 [ICPC 报名系统队伍公示](https://uep.pintia.cn/icpc-reg/examGroups/2086678069855703040/publicTeams) 在 2026-09-04 的静态快照。只读取学校、中文队名和“队员”列，明确排除教练列。

前两场前瞻使用报名系统名单；CCPC 网络预选赛使用 Pintia 公开榜单中的队伍身份，不使用比赛过程或成绩。浏览器只读取仓库内已提交的 `static/data/previews/` 快照，不会请求报名系统，也不会随报名、审核或比赛进程自动变化。后续新增场次、替换名单或刷新某个来源，均只在用户明确指定后执行；`scripts/generate_static_data.py` 只复制已提交快照，不联网刷新它。

第二场来自 [第二场队伍公示](https://uep.pintia.cn/icpc-reg/examGroups/2086691546024431616/publicTeams) 在 2026-09-07 的快照，共 2636 支队伍、7788 名队员，沿用公示顺序并排除教练。场次 ID 为 `icpc-2026-preliminary-2`，文件为 `static/data/previews/icpc-2026-preliminary-2.json`。官方 exam group 的时间为北京时间 2026-09-12 13:00–18:00，`sortAt` 记录开赛时间。2026-09-07 按用户要求刷新第二场的 XCPC Rating 与 XCPC Elo：分别使用线上发布数据的 `2026-09-06T16:17:41.538314+00:00`（北京时间 9 月 7 日 00:17）与 `2026-09-07T04:26:01.864Z`（北京时间 12:26）版本，两者均已纳入第一场比赛。当前四项外部/上赛季评分分别匹配 7189、7155、3007、2241 人；六维综合战力随评分重新计算。上赛季最后比赛 2026-04-26、CPC Finder 2026-09-04、NOI/IOI 缓存及本赛季 Rating 保持原样；第一场前瞻保留赛前评分，不回填赛后数据。

本次 XCPC Rating 来源为 [线上数据元信息](https://hei-maom.github.io/xcpcrating/data/meta.json) 和 `data/leaderboards/official/pages/1.json` 至 `623.json`，校验正式榜总计 62261 条记录，并在下载后复核元信息未改变；仓库 `main/web/public/data` 仍是旧版，不能代替线上最新发布。XCPC Elo 来源为 [线上 data.js](https://zzzzzzyt.github.io/xcpc-elo/data.js)，当前共 66573 名选手。XCPC Rating 缓存保存在 `data-cache/preview-sources-20260907/`，最新 Elo 缓存保存在 `data-cache/preview-sources-20260907-elo-refresh/`。发布前验证仅这两个评分、来源时间与匹配计数发生变化，名单和其他维度逐项一致；离线快照测试校验更新时间、覆盖人数与完整评分聚合契约。

XCPC Elo 在 2026-09-07 再次按用户要求从 10:46 版本刷新至 12:26 版本：第二场 7175 个队员评分条目、2473 支队伍的 Elo 最高分变化，1458 支队伍的六维综合战力名次变化；匹配人数从 7197 降至 7155。新版本仍截至第一场比赛，未匹配者按既有规则保留空值。此次仅更新 `xcpcElo` 的成员/队伍评分、来源时间和匹配计数，逐项验证其余字段一致，并验证第一场快照字节未变。离线回归更新了 Elo 来源时间与覆盖人数，并通过完整前瞻 schema 和聚合校验。

2026-09-11 按用户要求仅刷新第二场 XCPC Elo，当前版本为 `2026-09-11T05:22:39.085Z`（北京时间 13:22），覆盖 66573 名上游选手，比赛范围仍截至第一场网络赛。沿用姓名、学校规范化匹配及队内最高分规则，7155 名队员匹配成功；7127 个队员评分、2458 支队伍最高分变化，前端重算后 2116 支队伍的六维综合战力名次变化。仅修改第二场的 `xcpcElo` 成员/队伍评分、来源时间和匹配计数，其余字段（含名单、其他评分、奖牌、NOI/IOI 成绩和上赛季比赛记录）逐项一致。第一场文件 SHA-256 保持 `38616a78ea1784a4e2d727a7ba5ba88fedb8e019eafeca032162369c755f9c6d`。最新 Elo 缓存及更新核对摘要保存在 `data-cache/preview-sources-20260911-elo-refresh/`，下载文件 SHA-256 为 `cbef9ca1ebf5d75537f08c29b5285e622f5c47938c774c1066a9651f75bb6534`。离线快照回归校验新来源时间、覆盖人数、完整 schema、评分聚合与六维战力；公开 API、匹配假设及未匹配值处理不变。

`scripts/generate_preview_data.py` 支持 `--preview-id`、`--preview-title`、`--team-source-url`、`--sort-at`，默认仍为第一场。第二场显式传入上述元数据和独立 `--output` 路径。`--cpcfinder-snapshot-date` 保留缓存来源日期，省略时沿用 `--snapshot-date`；名单与评分日期可以不同，均不表示实时数据。离线测试覆盖参数传递、缓存日期、教练排除、默认发布两场快照、完整快照校验及第二场 URL 选择。

第二场通过 `--current-series static/data/series/2026-2027.json` 增加 `currentSeason` 评分来源，标题为“本赛季 Rating”，位于 `previousSeason` 后、CPC Finder 前。该可选参数省略时仍生成原有四项评分。输入必须属于本赛季，且最后比赛时间严格早于前瞻开赛时间，避免将赛后结果用于赛前评分；本次来源截至 2026-09-06 13:00，匹配 6674 名队员。仍按姓名与学校匹配；第二场起队内按已匹配成员做归一化 LSE，未匹配保留空值且不计入人数，不补初始分。该来源日期记录在 `sourceSnapshots.currentSeason`；后续评分更新不会自动修改静态快照。离线测试覆盖可选参数、来源赛季与时间校验、成员匹配及聚合、六维战力排名、并列、缺失值及列顺序。

## 数据来源与聚合

2026-09-11 从第二场起启用归一化 LSE：`400 * log10(sum(10 ** (R_i / 400)) / n)`，纯 Python API 为 `rating.normalized_lse_rating`，浏览器对应 `normalizedLseRating`。仅把该来源有评分的队员计入 sum 和 n，零分有效；全员缺失保持 null，单人有分时等于该成员分，三人同分 x 时等于 x。CPC Finder 继续取 max，奖牌继续求和。成员评分、来源时间、名单、成就与历史不变；个人赛季算法和已发布个人数据不变。

前瞻 schema v1 新增可选 `ratingAggregation`，值为 `max` 或 `normalized-lse`；省略代表旧版 max，显式 null 或未知值报错。新生成前瞻默认声明 `normalized-lse`。第一场快照完全保留，复盘继续使用原聚合；第二场声明新模式并只更新队伍层四项 Rating。生成器保存完整浮点精度，前端校验容许 1e-9 绝对误差；展示固定两位小数，排序使用未舍入值，显示同分可能有不同名次。队伍分统一固定两位小数；个人明细中 XCPC Elo、上赛季和本赛季 Rating 的整数值按整数显示，XCPC Rating 与 CPC Finder 固定两位小数。回归覆盖 Python/JavaScript 固定向量、等分/单人/零分/空输入、部分与全部缺失、数值稳定性、模式校验、旧快照兼容、完整第二场聚合和 CPC Finder 不变。

第一场每名队员记录四项评分；第二场额外记录本赛季 Rating：

- [Hei-MaoM/xcpcrating](https://github.com/Hei-MaoM/xcpcrating) 的正式参赛榜 Rating；
- [Zzzzzzyt/xcpc-elo](https://github.com/Zzzzzzyt/xcpc-elo) 的选手 Elo；
- 本仓库 `2025-2026` ICPC + CCPC series 的最终 Rating；
- 第二场在上赛季 Rating 后加入本仓库 `2026-2027` series 的本赛季 Rating；
- [CPC Finder](https://cpcfinder.com/) 的选手评分。

第一场队伍表各评分仍显示已匹配队员最高值。第二场起，除 CPC Finder 继续取最高值外，XCPC Rating、XCPC Elo、上赛季及本赛季 Rating 显示已匹配成员的归一化 LSE（尺度 400），并在同一行以 `#x` 显示该值在全部报名队伍中的名次；各数据列为小号等宽数字排名保留相同的紧凑窄槽，主值右对齐，排名在窄槽内左对齐并紧随主值。同值使用竞赛排名并列，后续名次留空位，没有任何匹配时显示 `—` 且不显示名次。CPC Finder 在队伍单元格及队员悬浮明细中按原值显示：`0` 显示为 `0.00`，缺失值显示为 `—`。零分参与该列竞赛排名并显示名次，同分并列；评分排序按数值比较，缺失值始终置后且无名次。仅综合战力将零分和缺失值视为该维度同一最弱档，互不超过。回归测试覆盖 CPC Finder 整数、零分、小数的两位格式及缺失值展示、零分排名与并列、评分双向排序及缺失值置后、原值展示路径、零分与缺失值的战力计数均为 0，以及正分同时超过两者。Rating 不使用千分位，队伍分统一固定两位小数；个人明细中 XCPC Elo、上赛季和本赛季 Rating 的整数值按整数显示，XCPC Rating 与 CPC Finder 固定两位小数。XCPC Rating 使用其深牛津蓝视觉，XCPC Elo 使用其等级色与橙色定义，其中 `>=3000` 的首位数字为黑色、其余数字为红色；上赛季与本赛季 Rating 均沿用本站选手 Rating 的 Codeforces 风格等级色；CPC Finder 保持普通文本色。鼠标正常悬浮或键盘聚焦单元格会展示所有队员在该来源的值，界面不显示额外提示图标，未匹配成员仍显示 `—`。金、银、铜牌数来自 CPC Finder，按队员求和为队伍总数；奖牌表头显示“奖牌（三人总和）”，单元格仅以空白分隔三个图标及数值，排序和名次均依次比较金牌、银牌、铜牌。

综合战力按场次的 `metricSources` 加奖牌计算：第一场四项 Rating 加奖牌共五维，第二场五项 Rating 加奖牌共六维。对每支队伍、每个维度统计其严格超过的队伍数；评分缺失值作为该维度最弱值处理，两个缺失值互不超过，奖牌维度按金、银、铜字典序比较。把同一队各维度的计数从高到低排列为元组，再按元组字典序对全部队伍排序；完全相同的元组并列。有综合战力数据的队伍显示该全局名次，悬浮或聚焦时只显示按各原始维度归一化的雷达图（第一场五边形、第二场六边形），不展示内部排序元组。搜索和学校筛选不会重新计算全局战力。

## 身份匹配

匹配严格执行“先人名、后学校”：先按 `DefaultNormalizer.member` 规范化姓名查找候选，再要求 `DefaultNormalizer.school` 规范化后的学校完全相同。学校规范化会做 NFKC、繁简转换、大小写与标点清理，并默认读取项目维护的 `config/school-aliases.json` 中的更名和中英文别名；`--school-aliases` 可覆盖为其他本地文件，不依赖线上列表。维护格式、歧义处理与加载 API 见 [本地学校别名表](school-aliases.md)。不会因为某姓名在来源中只有一个候选就忽略学校；校名仍无法确认时保留为空值。

同一来源若残留多个相同规范化姓名与学校的历史身份，除 CPC Finder 外仍确定性选择评分最高的记录。CPC Finder 使用 `PersonIndex(..., sum_matches=True)`，将匹配记录的评分相加并保留两位小数，金、银、铜牌分别相加；覆盖繁简人名/校名、标点差异及学校别名表明确列出的更名、旧称和中英文别名。例如“北京师范大学-香港浸会大学联合国际学院”、带引号的无连字符写法与“北师香港浸会大学”属于同一学校。跨校同名不合并，别名表未收录的更名不猜测；同校同名仍无法区分真实重名选手。该求和政策假设 CPC Finder 每条记录是独立累计条目，输入分页不能重复收录同一条记录。队伍评分仍取合并后的队员最高值，队伍奖牌仍按队员求和。第一场 7485 名报名队员中，四项来源分别匹配 4812、5085、2959、2186 人；覆盖差异主要来自各系统收录范围和新人，不代表零分。

2026-09-08 使用既有 CPC Finder 2026-09-04 缓存修正两场快照，各有 8 个队员条目的评分或奖牌变化；姜宣丞由 996.78 修正为 1880.17，奖牌为 5 金、3 银、1 铜。核对 [学校别名表](https://github.com/JunjieCharles/xcpc-standings/blob/master/data/config/school.json) 与现有缓存一致，不刷新评分来源日期或其他评分。离线测试覆盖繁简人名与校名、输入顺序无关、跨校隔离、缺失值、零分、两位小数、跨分页更名/别名/标点合并、成员求和与队伍最高分/奖牌求和，以及两场真实快照中的姜宣丞。学校别名回归直接读取项目唯一维护的 `config/school-aliases.json`，不另存单校测试副本。

NOI 与 IOI 履历仅按原始姓名完全匹配，不要求学校一致。成员姓名下方依次使用 NOI、IOI 最佳奖牌颜色的两条线；悬浮或聚焦姓名时按年份展示履历，同年 NOI 排在 IOI 前。每条获奖记录显示为“比赛名 · 奖牌#名次 · 分数 / 总分”；NOI 名次按同届加分后总分使用竞赛排名计算，当前收录年份总分均为 705，IOI 使用该届数据记录的总分。沈吉滪另记录 IOI 2024 参赛未获奖，使用偏暖的炭灰色下划线（`#57514d`），与银牌的蓝灰色区分，履历仅显示“2024 IOI”，不显示参与、未获奖、名次、分数或分隔符。所有仅参赛的 IOI 记录沿用该展示规则；回归测试覆盖下划线颜色、文本格式和渲染行仅含比赛名称。

## 队名悬浮比赛记录

鼠标移到队名、键盘聚焦或触屏点击队伍身份时，展示上赛季区域赛与总决赛记录，格式为 `50th ICPC 成都 #1 当时队名 (2/3)`；简称无法识别时保留比赛全称。分子为当前队伍中匹配到该历史队伍的不同规范化姓名数，分母为当前名单队员数。浮窗不重复显示成员名单；比赛名、排名和历史队名使用共享网格列，排名采用等宽数字并右对齐；无匹配时显示“暂无”，旧快照未提供字段时显示“尚未收录上赛季比赛记录”。浮窗限制在视口内，长队名换行。与其他悬浮窗一致，鼠标离开触发区域立即隐藏，不延迟、不接收浮窗自身的鼠标事件；键盘聚焦时显示，失焦后隐藏。超过视口高度的记录可能被截断。

2026-09-10 从本地 `data-cache/external/xcpcrating/vendor/srk-collection/official` 缓存补入两场前瞻。范围来自已发布 `static/data/series/2025-2026.json`，排除网络预选赛，包含 13 场区域赛/总决赛，不添加邀请赛。使用已有 SRK 适配器，保留正式且有提交的队伍及重建的正式排名。按姓名和学校规范化/别名匹配，不依赖当前队名；同场不同历史队伍分行，相同历史队伍按 `contestId + teamId` 合并。ICPC 排在 CCPC 前，各类按比赛时间、排名、历史队伍 ID 排序。跨校同名不合并，同校同名仍无法区分。第一场 929 支队伍共 2932 条记录，第二场 958 支队伍共 2987 条记录；名单、评分、奖牌总数及已有来源日期不变。

schema v1 每队新增可选 `previousSeasonHistory[]`，每条含 `contestId`、完整 `contestTitle`、`startAt`、`teamId`、`teamName`、正整数 `rank`、`medal`（gold/silver/bronze/null）及正整数 `matchedMembers`。颜色依据 SRK 固定名额或比例规则：比例先以 Decimal 累加，再乘正式队伍基数取整，支持 all/submitted/scored 分母和 ceil（默认）/floor/round。submitted 根据原始 statuses 中存在非空 result 计数，scored 根据解题数大于零计数；基数在历史记录过滤无提交队伍前计算。默认同成绩同色，noTied 按成绩排序后的顺序名次切分，同成绩保留上游行序；count 与 ratio 同时存在时取各档较小端点。未配置或全零名额保持普通文本色，武汉旧缓存全零占位按已核对的 45 金、90 银、136 铜修正，已有非零配置不覆盖。不支持的过滤条件及非法奖牌配置带文件名报错。这是缓存榜单的奖牌设置，不改变 CPC Finder 队伍奖牌统计。公开 API 和 schema 不变；浏览器校验字段类型、日期、排名、匹配人数上限和重复历史队伍。

离线补充现有快照：

```bash
python -m scripts.preview_history --series static/data/series/2025-2026.json --srk-root data-cache/external/xcpcrating/vendor/srk-collection/official --preview static/data/previews/2026-2027.json --preview static/data/previews/icpc-2026-preliminary-2.json
```

重新生成前瞻时可向 `scripts/generate_preview_data.py` 传入 `--history-srk-root`，由 `scripts.preview_history.build_history_index` 与 `team_history` 从 `--previous-series` 的比赛范围投影。省略参数兼容原契约；来源必须是前一赛季，缺少任何所需榜单会报错，不发布部分结果。默认静态站生成器继续复制已提交快照，不联网更新。

离线测试覆盖 SRK 适配到前瞻历史、学校别名、跨校隔离、改队名、正式/打星及无提交过滤、正式排名、重复成员去重、多人合并、重组队伍拆分、空记录、类别/日期排序、明确奖牌名额与未知奖牌、缺失文件及前端非法字段校验。浏览器检查覆盖 1280px/390px 下鼠标悬浮、键盘聚焦、记录内容与视口边界。回归检查也覆盖无重复成员名单、共享列布局、排名右对齐、鼠标离开立即隐藏及键盘聚焦/失焦。

## 静态契约、限制与测试

前瞻选择优先级为：有效 URL `previewContest`、该赛季上次手动选择、按北京时间今天或未来最近的比赛日期。同日优先 ICPC，再 CCPC，再其他赛事，同类别按 ID 升序确定；比较日期而非开赛时刻，当日已开赛也仍可默认选择。若已无当日/未来比赛，回退到日期最近的过去比赛，沿用同日破同分规则。仅完整前瞻参与选择，牌线摘要不参与；隐藏场次仅可通过有效 URL 或既有选择恢复，未知日期（`hideContestTime: true`）仅在没有日期已知的公开场次时回退选择，空列表返回 null。`selectPreviewContest` 接收可注入的当前时间，保持输入不变。

手动点击比赛按钮或赛站行时，将 ID 保存到 `localStorage` 的 `xcpc-sight:preview-contest:{seriesId}`，按赛季隔离，重新打开无参数入口仍恢复选择。自动默认选择、URL 指定场次及复盘内部选择不覆盖持久记忆，已移除的记忆 ID 忽略；浏览器禁用存储时降级为 URL 与页面内记忆，不阻断使用。页面内切换 tab 仍保留前瞻选择，复盘不会覆盖它。离线回归覆盖北京时间跨日、当日已开赛、最近未来/全部过去、同日 ICPC 优先、确定性破同分、隐藏/未知日期、URL/记忆优先级、失效 ID、存储失败与赛季隔离；浏览器冻结日期为 2026-10-14，验证无记忆默认西安、手动选长春后无参数重新进入保持长春，以及有效 URL 恢复。

第一场的标题下方显示“比赛时间：2026年9月6日 13:00-18:00”，时间按用户指定的北京时间以静态文案呈现，不做浏览器时区转换；第二场根据 `sortAt` 按北京时间显示 2026年9月12日 13:00。

前瞻 schema v1 包含系列/场次标识、快照日期、名单来源、评分来源、匹配政策和 `teams[]`。每队含稳定 ID、来源顺序、学校、队名、成员明细、各来源的队伍聚合评分与奖牌总数。校验器检查来源 ID、队伍 ID、评分有限性、声明的队伍聚合及奖牌求和；筛选支持学校、队名和全体成员姓名；缺失评分始终排在有值队伍之后。

前两场快照分别约 2.6 MiB、2.9 MiB，一次性加载后以虚拟滚动表显示。页面不展示内部快照日期、匹配政策或静态快照说明，页面展示名单来源与各项评分数据来源；打星说明附在数据来源行，名单来源也保留于 JSON 以供追溯，并批注学校排名随当前排序方式变化，以及 NOI/IOI 成绩仅按姓名匹配、可能存在重名情况。任意列的主排序键相同时，均按学校名升序排列，再按来源顺序保持确定性。除学校、队名和成员排序外，先对未筛选的全体队伍应用当前排序，再按各校最先出现队伍的主排序键计算竞赛排名；主排序键相同的不同学校共享校排，后续名次按此前学校数跳号。同一学校有多个并列队伍时，只在其中最前面的队伍校名前显示 `#x`，其余队伍留空。搜索和学校筛选只裁剪全量排序结果，不重算校排，因此筛出的队伍若不是原结果中的校内最高队伍则不显示校排。“赛前前瞻”始终作为独立 tab 显示，即使当前系列没有其他页面；标题区保留比赛选择下拉框，当前按 ICPC 第一场、第二场、CCPC 网络预选赛排列，通过索引可选 `previews: [{id, path}]` 扩展场次，兼容现有 `previewPath`，`previewContest` URL 参数记录选择。所有前瞻列表头文字居中。各项 Rating 和奖牌名次以全部非打星队伍为基数预先计算，搜索和学校筛选不会重新排名。桌面容器宽于 `1120px` 时冻结学校、队名和成员三列，`600px` 到 `1120px` 冻结学校和队名；`600px` 以下只隐藏独立学校列，把队名作为主行、学校作为副行，校排仍以 `#x 学校` 的形式直接放在校名前，合为 `clamp(150px, 42cqw, 176px)` 的单一冻结身份列。成员列继续显示但不冻结，随 Rating 数据横向滚动；移动端身份列右侧使用阴影提示横向滚动，点击或键盘聚焦队伍身份可查看上赛季比赛记录。身份列表头显示“队伍”并继续按队名排序。表格总宽从当前可见列计算，防止浏览器重新分配列宽。成员明细与综合战力悬浮窗固定到视口并根据剩余空间显示在单元格上方或下方，避免被表格滚动容器裁切。它不是比赛结果预测，不给未匹配选手填新人先验，也不承诺外部评分体系彼此可比；综合战力仅是上述各维度相对支配计数的确定性排序。测试覆盖新赛季 collection、前瞻 schema、真实 2535 队快照、搜索、各列排序及学校名次级排序、各数据列全局名次、综合战力五维/六维元组、本赛季评分并列与缺失值、校排并列、奖牌关键字顺序、缺失值顺序、URL 状态、子路径加载与单列移动冻结布局。

金、银、铜牌在赛前前瞻、赛后复盘及成员悬浮明细中共用固定网格：每种奖牌的图标占 1em、数量占 2ch，三组依次排列。图标居中、数字右对齐并使用等宽数字，不随一位或两位数移动；当前快照的最大数量分别为 35、24、17。奖牌顺序和排序规则保持不变，浏览器回归检查两页及移动端的各组位置一致。


2026-09-11 修复历史排名漏色：第一场 882 条、第二场 901 条 medal 更新，覆盖西安、武汉和 CCPC 哈尔滨、济南、郑州、重庆。其他历史字段及顺序、名单、评分、累计奖牌与来源时间保持原样。武汉补正规则来自本地 `data-cache/external/xcpc-elo/data/srk-collection/official/icpc/icpc2025/icpc2025wuhan.srk.json`；生成器继续使用原 xcpcrating 榜单，避免另一缓存的身份差异改变关联。比例和并列处理核对 [SRK 官方实现](https://github.com/algoux/standard-ranklist-utils/blob/master/js/src/ranklist.ts)。离线测试覆盖比例累计精度、分母、取整、并列、组合规则、非法配置和武汉修正边界，并核对两场快照中 CQOI Flames 的济南 #3、郑州 #18 为金牌、武汉 #188 为铜牌。前端表头为“奖牌（三人总和）”，不足三人的实体仍仅累计实际报名成员；表头回归及静态资源版本同步更新。

2026-10-10 本次变更验证：226 项 Python 测试、81 项前端数据测试、Ruff 与差异空白检查通过。

GitHub Pages 工作流同步运行网络赛排名、布局与隐藏入口回归测试。
