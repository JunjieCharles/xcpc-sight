# 2026–2027 赛季与前瞻

## 赛季范围与当前页面

`core.seasons.SEASON_2026_2027` 定义 `2026-2027` 系列，候选比赛来自 RankLand official collection 的 `icpc2026` 与 `ccpc2026`，沿用邀请赛排除、显式 include/exclude 覆盖和同日 CCPC 优先的排序规则。公开 API 为 `SEASON_2026_2027` 与 `load_2026_2027_season`。

当前赛季尚未产生用于本站计算的正式比赛结果，因此不发布选手 Rating 和题目难度页，也不发布空 series 文件。本次只发布“2026 ICPC Asia EC网络预选赛 - 第一场”前瞻。站点索引通过 `previewPath` 表示只有前瞻的系列；产生正式数据后可在同一条索引记录同时提供 `path` 与 `previewPath`。

## 名单来源与更新边界

本次 2535 支队伍来自 [ICPC 报名系统队伍公示](https://uep.pintia.cn/icpc-reg/examGroups/2086678069855703040/publicTeams) 在 2026-09-04 的静态快照。只读取学校、中文队名和“队员”列，明确排除教练列。

前瞻名单不是 Pintia 比赛榜单，不包含比赛过程或成绩。浏览器只读取仓库内已提交的 `static/data/previews/2026-2027.json`，不会请求报名系统，也不会随报名、审核或比赛进程自动变化。后续新增场次、替换名单或刷新某个来源，均只在用户明确指定后执行；`scripts/generate_static_data.py` 只复制已提交快照，不联网刷新它。

## 数据来源与聚合

每名队员记录四项评分：

- [Hei-MaoM/xcpcrating](https://github.com/Hei-MaoM/xcpcrating) 的正式参赛榜 Rating；
- [Zzzzzzyt/xcpc-elo](https://github.com/Zzzzzzyt/xcpc-elo) 的选手 Elo；
- 本仓库 `2025-2026` ICPC + CCPC series 的最终 Rating；
- [CPC Finder](https://cpcfinder.com/) 的选手评分。

队伍表每个评分单元格显示该项已匹配队员中的最高值；没有任何匹配时显示 `—`。鼠标悬浮或键盘聚焦单元格会展示所有队员在该来源的值，未匹配成员仍显示 `—`。金、银、铜牌数来自 CPC Finder，按队员求和为队伍总数；奖牌只有一个捆绑列，排序依次比较金牌、银牌、铜牌。

## 身份匹配

匹配严格执行“先人名、后学校”：先按 `DefaultNormalizer.member` 规范化姓名查找候选，再要求 `DefaultNormalizer.school` 规范化后的学校完全相同。学校规范化会做 NFKC、繁简转换、大小写与标点清理，并使用 `xcpc-standings/data/config/school.json` 的中英文别名。不会因为某姓名在来源中只有一个候选就忽略学校；校名仍无法确认时保留为空值。

同一来源若残留多个相同规范化姓名与学校的历史身份，确定性选择评分最高的记录。该策略服务于本页面“队内最高分”口径，并避免重复累计 CPC Finder 奖牌。当前 7485 名报名队员中，四项来源分别匹配 4812、5085、2959、2186 人；覆盖差异主要来自各系统收录范围和新人，不代表零分。

## 静态契约、限制与测试

前瞻 schema v1 包含系列/场次标识、快照日期、名单来源、评分来源、匹配政策和 `teams[]`。每队含稳定 ID、来源顺序、学校、队名、成员明细、四项队内最大评分与奖牌总数。校验器检查来源 ID、队伍 ID、评分有限性、队内最大值及奖牌求和；筛选支持学校、队名和全体成员姓名；缺失评分始终排在有值队伍之后。

当前快照约 1.7 MB，一次性加载后以虚拟滚动表显示。它不是排名预测，不给未匹配选手填新人先验，也不承诺外部评分体系彼此可比。测试覆盖新赛季 collection、前瞻 schema、真实 2535 队快照、搜索、各列排序、奖牌关键字顺序、缺失值顺序、URL 状态与子路径加载。
