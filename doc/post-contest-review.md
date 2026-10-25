# 赛后复盘

## 2026-10-25 成都赛后复盘

新增 `icpc2026chengdu` → `icpc-2026-chengdu`，来源为 [RankLand 成都正式榜单](https://rl.algoux.cn/ranklist/icpc2026chengdu)。文件 ID `107769046547718144`，SHA-256 `23f0b373820c561d0f219de014ed65ff0e6c6496e818d4d55f8673cb46aa6882`，已核验下载字节；上游文件发布于北京时间 2026-10-25 17:15:43。实际开赛时间采用结果中的 09:10，赛前快照保留计划时间 09:00。

328 支结果队伍中 319 支正式队伍全部有提交，全部与原前瞻自动唯一关联；9 支打星不参与 Rating 和复盘。奖牌采用本次 SRK 明确的 count `[32,64,96]`，实际金银铜为 32/64/96，累计边界 32/96/192，无边界并列扩张。页面默认选择最新的成都站，提供综合战力及其四项组成指标；上赛季 Rating 不参与成都战力和复盘。

| 指标 | 有效队伍 | Spearman ρ | 金牌命中 | 银牌命中 | 铜牌命中 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 综合战力 | 314 | 0.837135 | 24/32 | 40/63 | 53/96 |
| 网络赛排名 | 310 | 0.802967 | 23/32 | 36/62 | 55/96 |
| XCPC Rating | 314 | 0.846223 | 21/32 | 40/63 | 60/96 |
| XCPC Elo | 313 | 0.845006 | 24/32 | 40/63 | 55/96 |
| 本赛季 Rating | 310 | 0.822453 | 22/32 | 35/63 | 54/96 |

覆盖率分母为 319；奖牌预测数量按各指标有效样本计算，因此可能少于全场奖牌数。五项相关系数用 SciPy `spearmanr` 独立复核，15 项奖牌计数用预测排名区间与实际奖牌交集复核，固化于 `tests/fixtures/review/regional-metrics.json`。回归覆盖正式名单、奖牌边界、来源、四维指标排除规则及赛季成绩连续性。发布脚本离线测试验证哈希不符不写入、重复运行字节一致、保留其他复盘和前瞻；浏览器回归覆盖成都默认入口与桌面/手机五张指标卡片。

定向生成命令见[成都赛后 Rating](season-2026-2027-preview.md#2026-10-25-成都赛后-rating)。原五场复盘、全部赛前快照及其他系列保持不变。

## 2026-10-18 西安、长春与奖牌预测准确率

新增 `icpc2026xi_an` → `icpc-2026-xian`、`ccpc2026changchun` → `ccpc-2026-changchun`。来源展示 [RankLand 西安榜单](https://rl.algoux.cn/ranklist/icpc2026xi_an)和[长春榜单](https://rl.algoux.cn/ranklist/ccpc2026changchun)。当前文件 ID 为 `105318714861256704` / `105706787390464000`，核验下载字节哈希后，西安沿用原快照，长春采用 10 月 20 日官方修订版；结果中保存固定 CDN URL、file ID 与 SHA-256。复盘选择列表按北京时间日期升序，同日 ICPC 在 CCPC 前；默认选日期最近的已发布复盘，同日优先 ICPC，再以开赛时间和 ID 稳定破同分。显式 URL 和页内已选场次继续保留。

西安覆盖 403 支赛前正式队，其中 402 支有正式参赛结果，湖南科技大学 `Team366` 赛后转为打星，通过 `config/review-unofficial-results/icpc2026xi_an.json` 显式登记。长春覆盖 300 支赛前正式队，298 支有提交；深圳理工大学“SUAT曙光231”有 `I10` / `I1000` 两个同身份账号，前者无提交，通过 `config/review-overrides/ccpc2026changchun.json` 关联有成绩的 `I1000`。

复盘仅展示综合战力和实际参与其计算的指标，由 `reviewMetrics(preview)` 按 `previewPowerMetricIds(preview)` 筛选。两站各六项：综合战力、网络赛排名、XCPC Rating、XCPC Elo、上赛季 Rating、本赛季 Rating；不参与战力的 CPC Finder、奖牌不出现在区域赛复盘，也不接受为当前指标，旧 URL 回退到综合战力。综合战力沿用前瞻指定的五维原始计数与排名；网络赛排名使用三场最好名次元组比较，至少有一场记录才纳入。旧网络赛快照保留各自参与战力的六/七项指标。每张卡片增加金银铜三档的**精确命中率**及 `命中数/预测数`：

`该档准确率 = 预测为该档且实际获得同档奖牌的队数 / 预测为该档的队数`

预测银牌而实际金牌不算银牌命中。每项指标在既有的正式、实际参赛、有当前指标的有效样本中，按该样本的实际金/银/铜数量设定累计预测名次边界，再以该指标竞赛排名分档。并列同档、不拆分，边界并列会扩大预测数并压缩后续档位，CPC Finder 和奖牌零值并列也遵守此规则。零预测时为 null，显示 `— (0/0)`。这是使用已知奖牌数量的排序分档评价，不评价赛前奖牌名额估计。不同指标样本不同；搜索、学校筛选、表头升降序只改变明细，不重算指标。

纯 JS `medalPredictionAccuracy(rows)` 返回三档 `{hits, predicted, value}`；`buildReviewAnalysis.medalAccuracy` 在缺少奖牌标签的旧场次为 null。有标签的两站综合战力结果为：

| 场次 | 有效队伍 | Spearman ρ | 金牌 | 银牌 | 铜牌 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 西安 | 396 | 0.768620 | 27/41 = 65.9% | 43/82 = 52.4% | 63/122 = 51.6% |
| 长春 | 294 | 0.821510 | 20/30 = 66.7% | 36/60 = 60.0% | 41/88 = 46.6% |

schema v1 可选新增 `contest.hasMedals: true`，要求全部结果行提供 `actualMedal: "gold" | "silver" | "bronze" | null`。拒绝缺失/未知标签以及无提交、非正常结果携带奖牌。旧文件不提供标签时不展示准确率。实际奖牌用既有 `_history_medals` 解释 SRK count/ratio 和并列：西安为 41/82/124（铜牌配置 123 因并列扩张）；长春采用 2026-10-20 官方修订的固定名额 count `[30,60,90]`，累计边界为 30/90/180。

纯 API 新增可选 `result_medals`，须恰好覆盖所有正式结果 ID，值限三档或 null；新增 `unofficial_results` 映射前瞻 ID 到当前打星结果 ID，不能与其他映射重叠、重复目标或引用正式结果。对应行写入 `resultStatus: "unofficial"`，活动、名次和奖牌为 null，排除于排名、覆盖率和预测统计。默认仍拒绝自动把正式前瞻匹配到打星。通用 CLI 增加 `--medals`、`--unofficial-results`、`--source-url` 和 `--source-title`。

两站与 Rating 可通过固定输入命令离线重建，五份 SRK 的来源和哈希见[赛季发布说明](season-2026-2027-preview.md#2026-10-18-西安长春赛后-rating)。只替换两站复盘，保留三场网络赛及赛前快照。

```bash
python -m scripts.publish_october_2026_results --input-dir data-cache/results-20261018-rankland
```

测试覆盖精确分档（更高奖牌也不命中）、并列边界、零预测、缺失指标、无活动、资格变化、重复账号及标签校验。`tests/fixtures/review/regional-metrics.json` 固定两站六项指标样本、ρ 和各档计数；12 项系数经 SciPy `spearmanr`、36 项计数经独立分档交集复核。浏览器回归覆盖两站切换、同日排序与默认优先 ICPC、六张卡片及排除指标、RankLand 网页来源、网络赛指标、搜索不变、1440px/390px 与内容不越界；旧场次的滚动、雷达图和奖牌对齐继续检查。复盘取消空的全名单排名槽，并为筛选前后名次保留足够列宽，确保窄屏奖牌、网络赛值与原名次完整显示。数据来源链接同样只保留参与综合战力的指标来源。

## 2026-10-22 长春奖牌规则纠正

RankLand 在 10 月 20 日发布 file `105706787390464000`，SHA-256 `a430faa32608ae0812674333c8ff752691da3927a56a9b58b0aa0a57e6c583a2`，把旧快照按 scored 比例计算的 30/58/88 修订为固定 30/60/90。逐行核验新旧 `score`、`statuses`、正式资格、学校、姓名与成员未变，只有头像/标记等展示信息不同；不需要重算 Rating 或名次。

受影响：复盘原第 89、90 名由铜改银，第 177–180 名由无牌改铜；六项指标的奖牌命中统计随之更新，Spearman 和样本人数不变。成都前瞻“请问我们是已经教到stl了吗”的一条当前赛季历史（F28，第 180 名）补铜，不刷新其评分、名单或战力。赛前网络赛牌线不是赛后奖牌分界，不随此次修订改变。

根因是旧来源规则过期，图片又把同一份旧网站复盘当作交叉验证，未检查官方 file ID 更新。发布脚本现固定新文件 ID 和哈希；`_history_medals` 针对 `ccpc2026changchun` 的旧精确规则 `ratio {value:[.1,.2,.3], denominator:"scored"}` 使用已核验固定名额兼容，防止旧历史缓存再次写回错误。其他比赛、显式 count 和未来不同规则不覆盖。

仅重建此场复盘（其余比赛和 Rating 保持不变）：

```bash
python scripts/generate_review_data.py --preview static/data/previews/ccpc-2026-changchun.json --srk data-cache/results-20261018-rankland/ccpc2026changchun.srk.json --contest-id ccpc2026changchun --file-id 105706787390464000 --file-url https://cdn.algoux.cn/rankland/file/105706787390464000/ccpc2026changchun.srk.json --sha256 a430faa32608ae0812674333c8ff752691da3927a56a9b58b0aa0a57e6c583a2 --medals --overrides config/review-overrides/ccpc2026changchun.json
```

离线回归覆盖旧 ratio、新 count、其他比赛不受影响、显式不同名额不覆盖；发布数据回归检查 30/60/90 人数及全部边界标签。六项指标命中数由原实际排名区间和预测排名区间的独立交集复核。视频长春总结同步重绘，源规则断言为固定名额，避免仅测试硬编码边界。

## 页面与计算口径

复盘与前瞻共用 Rating 格式化：所有来源的队伍值固定两位小数，整数补零；成员明细中 XCPC Elo、上赛季和本赛季 Rating 的整数值按整数显示，XCPC Rating 与 CPC Finder 固定两位小数；缺失仍显示“—”；只改变展示，排序与聚合保留原精度，个人赛季榜与已发布数据不变。回归覆盖各来源、零分、整数、小数舍入及 Elo 特殊颜色分支。

2026-09-11 队伍聚合调整从第二场前瞻开始，第一场前瞻保持原文件，首场复盘的指标、排名和下文统计基准保持不变。后续复盘读取对应前瞻的队伍聚合值，不另行按个人分聚合；归一化 LSE 的缺失值与兼容规则见 [前瞻设计](season-2026-2027-preview.md)。

“赛前前瞻”沿用 `preview-tab` 和 `view=preview`。“赛后复盘”使用独立 `review-tab` / `view=review`，仅有已发布复盘数据的系列显示该入口；默认选择最新可复盘比赛、综合战力指标、实际排名升序。最新场次按 `startAt` 的北京时间日期比较，同日优先 ICPC，再比较开赛时间和 ID，不依赖数组顺序。首次进入且没有已有选择，或 URL 明确指定的场次无效时选最新，有效 `reviewContest` 链接保留指定场次；同一系列内切到其他 tab 再回来，以及页内切换指标、排序和筛选时均保留已选场次。前瞻与复盘独立记忆各自的选择；重新加载按 URL 恢复，不使用持久存储。离线回归覆盖乱序列表、时区偏移、同日优先 ICPC、同一时间、无效 ID、显式旧场次、单场/空列表与页签选择保留。

比赛选择框列出同时具有赛前快照和赛后结果的场次。各项指标（第一场六项、第二场七项）的 **Spearman ρ、有效队伍数和覆盖率始终同时显示**，通过同尺度的正负条形和数值直接比较；点击卡片选择下方队伍表的指标，不使用指标下拉菜单。选中卡片使用边框、底色和 `aria-pressed` 标记，可通过键盘操作。桌面六列，中等宽度三列，手机两列。符合度不是准确率，不转换成百分制，也不将不同覆盖范围的系数解释为同样本上的优劣。

表格上方以整句加粗的“前瞻排名与实际排名均仅统计已参赛且存在当前指标的队伍。”说明两列的共同统计范围；保留说明文字原有灰色，不改为黑色。

每项指标独立执行两层筛选：

1. 只保留匹配到正式结果且有提交活动的队伍；零解题但有失败提交仍然保留。
2. 普通 Rating 只排除 `null`，保留 0；奖牌以队伍 `ratings.cpcfinder !== null` 判断是否有记录，保留零分、零奖牌。综合战力使用全体赛前名单计算的各维计数（第一场五维、第二场六维），排除所有计数全部为 0 的队伍，保留原战力排序和并列，**不按剩余队伍重新计算战力**。

然后在每项指标的最终有效队伍集合中分别重编前瞻和实际名次。相同指标值或相同实际名次保留 `1, 2, 2, 4` 式竞赛排名；中间队伍被排除后压缩名次。奖牌依次按金、银、铜比较。实际原名次来自正式且有提交队伍中按解题数、罚时重建的排名。

两列排名均在主值后以括号灰色小字显示过滤前名次，例如 `#23 (#26)`，筛选后排名和括号内原排名分别占据固定宽度的槽，各自右对齐；两个表头均在主标题下加灰色小字“（过滤前）”。前瞻原名次取完整赛前名单中当前指标的既有名次（与赛前页面一致），实际原名次取发布结果中的 `actualRank`。纯分析行新增 `originalPreviewRank`、`originalActualRank` 字段；原名次只作补充，排序、符合度和涨跌仍使用筛选后名次，即使新旧名次相同也保留括号值。

表格包含学校、队伍、成员、当前指标、前瞻排名、实际排名、名次变化、上涨程度。综合战力指标列表头为“综合战力”，单元格显示原赛前全体名单中的名次；“前瞻排名”列则显示筛选后名次。名次变化为 `前瞻排名 − 实际排名`，绿色上箭头表示上涨，红色下箭头表示下降，零变化显示中性色 `—`。上涨程度为 `log10(前瞻排名 / 实际排名)`，按三位小数带符号显示，排序保留未舍入精度；极小变化可能舍入为带符号的 `0.000`。

所有表头支持双向排序，默认实际名次升序；身份和排名列首次点击升序，指标及涨跌列首次点击降序。同值以学校名升序、原名单顺序稳定排序，不拆分并列。关键词、学校多选只过滤显示，不重算排名、系数或覆盖率。空结果显示对应说明。虚拟表沿用 44px 行高及现有移动端冻结策略；宽屏铺满容器，多余宽度均分给五个数据列，保持身份列与冻结偏移一致；窄屏继续横向滚动，手机隐藏独立学校列并把学校合入队名副行。

## 符合度

首场成员评分的 max/LSE/混合聚合反事实比较见 [聚合回测](team-aggregation-first-preliminary.md)，使用同一首场快照及结果，另存实验产物。该研究不替换页面原始指标或下文复盘基准。

综合战力单元格复用赛前前瞻的 `previewPowerControl`，字体、颜色和字重一致；鼠标悬停或键盘聚焦时显示相同的雷达图（第一场五维、第二场六维）。雷达图使用完整赛前名单的原始各维超过队伍数及归一化基数，不根据复盘筛选或搜索重算。

卡片下方以“当前指标：指标名 · 符合度 系数”标明表格使用的指标。

名次变化使用固定的箭头槽和数字槽，箭头居中、数字左对齐，保证整列箭头与数字之间的分界一致，不随数字位数变化。零变化的 `—` 放在数字槽，箭头槽留空，保留辅助阅读标签。

分别将有效队伍的前瞻名次和实际名次转换为平均秩，再计算两组平均秩的 Pearson 相关系数：

`ρ = Σ((Rᵢ − R̄)(Sᵢ − S̄)) / sqrt(Σ(Rᵢ − R̄)² × Σ(Sᵢ − S̄)²)`

并列队伍取其占据位置的平均值，例如 `1, 2, 2, 4` 转为 `1, 2.5, 2.5, 4`。这个转换只用于符合度，不改变表格中的竞赛排名或涨跌计算。不能在存在并列时直接套用无并列的排名差平方简式。

取值 −1 至 1，越接近 1 表示排名越一致，0 表示没有秩相关，负值表示反向关联。少于两队或任意一边全部并列导致分母为零时显示“无法计算”及原因。采用 [Spearman 定义](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html)，不计算显著性或额外加权。浏览器纯函数 API 为 `spearmanRho(pairs)`，返回 `{value, reason}`；拒绝非有限数值对。

覆盖率分母是本场前瞻名单中实际参赛队伍数。每个比赛首次展示计算所有指标，按前瞻对象、结果对象和指标缓存；搜索、排序、重复选择卡片均复用缓存。纯计算模块位于 `static/js/review.mjs`，不引入统计库。平均秩排序为 O(n log n)，相关系数累加为 O(n)，不需要两两枚举队伍。

2026-09-08 修正前瞻中 CPC Finder 繁简身份及学校别名的累加后，复盘直接使用修正后的前瞻重新计算。首场综合战力、CPC Finder、奖牌的 Spearman ρ 分别为 0.7358560837348063、0.6425002771082232、0.6615396075355272；有效队伍数与其他评分指标不变。回归基准使用 SciPy `spearmanr` 独立复核，赛后结果快照无需修改。

## 静态契约与生成

2026-09-19 官方结果修订：赛前名单保持不变；对经旧、新榜单差异确认移除的队伍，生成器通过显式 `--removed-results` JSON 映射（前瞻队伍 ID → 旧结果队伍 ID）登记。纯 API 对应参数为 `removed_results`。映射只能引用已知前瞻、唯一且非空的旧结果 ID，不能与 overrides 重叠，也不能指向当前仍存在的结果或当前仍可按身份匹配的队伍。未显式登记的匹配失败继续报错。

schema v1 结果行新增可选 `resultStatus: "removed"`：保留旧 `resultTeamId` 供追溯，`hasActivity` 和 `actualRank` 必须为 null，表示正式结果已移除而非没有提交。正常行省略 `resultStatus`，沿用布尔活动状态。前端校验拒绝未知状态和移除状态携带名次/活动布尔值；这些记录不进入复盘样本、覆盖率分母及符合度，但仍覆盖原前瞻名单。移除不修改任何赛前评分或赛前综合战力排序。

站点 schema v2 索引新增可选 `reviewPath`，相对站点索引解析。前瞻支持可选 `previews: [{id, path}]` 多场次入口，提供列表时它是完整目录，`previewPath` 如同时存在必须等于第一项路径；仅有旧 `previewPath` 仍正常加载。索引生成器收到同系列多份不同 ID 的前瞻会输出列表及首项兼容入口，拒绝同系列重复场次 ID。复盘引用必须对应已发布前瞻。

`static/data/reviews/2026-2027.json` 为 schema v1，顶层包含 `schemaVersion`、`seriesId`、`contests[]`。每场包含：

- `id`：实际比赛 ID；`previewId`：对应赛前快照 ID，不能通过标题猜测，两者允许不同。
- `title`、`startAt`、`source`：来源标题、可打开的 RankLand `/ranklist/{contestId}` 链接；有 provenance 时还包含 `fileId`、`fileUrl`、`sha256`。
- `teams[]`：`previewTeamId`、`resultTeamId`、`hasActivity`、`actualRank`。正常行的 `hasActivity` 为布尔值，有活动时名次必须为正整数，无活动时必须为 `null`；显式 `resultStatus: "removed"` 行的活动状态和名次均为 `null`。

结果必须恰好覆盖对应快照中的每支正式队伍（排除 `excluded: true` 的打星队伍），各侧 ID 唯一；未知前瞻、重复关联、漏队、非法活动状态和名次会报出字段路径。源结果中未出现在前瞻中的队伍不加入复盘，其存在可能影响原实际名次，但筛选后名次会压缩。

纯 Python API：`core.project_review_contest(preview, contest, *, normalizer=None, overrides=None, removed_results=None, unofficial_results=None, result_medals=None)`。输入原前瞻映射和不可变 `Contest`，输出一场复盘映射，不访问网络或文件，不修改输入。先按规范化学校和队名唯一匹配，再用规范化学校及排序后的完整成员名单唯一匹配。学校、成员复用 `DefaultNormalizer`；队名仅进行 NFKC、大小写和空白归一化，保留标点，因为真实队名可能完全由标点组成。`overrides` 明确映射前瞻队伍 ID 到结果队伍 ID，并验证目标唯一且未被其他队伍使用。除显式登记的 `removed_results` 外，未匹配或歧义一律失败，不能视为无提交。

```bash
python scripts/generate_review_data.py
```

默认只下载首场指定 SRK，核验实际下载字节的 SHA-256 后生成复盘。可用 `--srk` 读取本地文件完全离线生成；`--preview`、`--contest-id`、`--file-id`、`--file-url`、`--sha256` 指定其他已授权场次。学校别名默认使用仓库 `config/school-aliases.json`，通过 `core.load_school_aliases` 加载，与前瞻共用同一份本地维护表，不下载线上列表；`--school-aliases` 可指定替代文件，兼容规范名到别名数组和旧的别名到规范名格式，详见 [学校别名设计](school-aliases.md)。`--overrides` 接受队伍 ID 的 JSON 映射。`--output` 指定复盘系列文件，同场替换、其他场保留，按比赛时间和 ID 排序后原子写入。该脚本不刷新赛前评分、不修改站点索引；新增入口需在站点发布时登记。离线生成器回归覆盖默认本地别名表的加载。

`rating.project_static_data_index` 新增 `review_publications=` 参数，与 `preview_publications=` 配合验证入口引用。`scripts/generate_static_data.py` 只复制已提交且对应本次前瞻系列的复盘快照，先发布所有内容再发布索引，不重新下载复盘结果。浏览器只访问发布 JSON，不访问上游或本地缓存。

URL 使用 `reviewContest`、`reviewMetric`、`reviewSort`、`reviewOrder`，前瞻新增 `previewContest`，并保留公共 `series/q/school`。非法场次、指标或排序回退到有效默认项。切换卡片、比赛、表头排序可前进后退，离开页面清理专属参数。已打开复盘时切换指标原地更新，不临时隐藏页面，保持窗口和表格滚动位置；新队伍集合缩短时仅将表格位置限制到新的最大可滚动高度。学校选项基于实际参赛名单，切换指标不丢弃学校筛选。加载失败显示错误面板，可重试；缺少复盘入口的系列回退到其已有页面。

## 首场数据与测试

网络赛第一场：`icpc2026preliminary-1` 对应前瞻 `icpc-2026-preliminary-1`；文件 ID `90036200580141056`，SHA-256 `39077e4904169b353f85c4484efa5fe9064727ba00cf6685661270d5d9bf7575`。2535 队全部唯一匹配，无人工覆盖；2496 队有活动。综合战力初筛 1972 队，再剔除 22 支无提交队伍后参与比较 1950 队。

| 指标 | 有效队伍 | Spearman ρ（显示精度） |
| --- | ---: | ---: |
| 综合战力 | 1950 | 0.736 |
| XCPC Rating | 1868 | 0.745 |
| XCPC Elo | 1947 | 0.731 |
| 上赛季 Rating | 1302 | 0.670 |
| CPC Finder | 980 | 0.643 |
| 奖牌 | 980 | 0.662 |

`tests/test_review_data.py` 验证匹配、歧义/漏队错误、正式资格、无提交和零题提交、确定性投影、入口引用，以及精简 SRK → Python 投影 → Node 前端排名的离线端到端链路。`tests/fixtures/review/` 保存人工缩减的七队数据，不需要网络。

`tests/test_review_frontend_data.mjs` 覆盖两层筛选、原战力保留、双侧重排及并列、CPC Finder 零值与奖牌记录、涨跌和未舍入排序、Spearman 平均秩、各种并列/完全一致/逆序/退化情况、全部指标缓存与场次隔离、URL、多场次和旧入口、请求失败重试、真实快照计数。浏览器检查桌面/手机卡片、选中状态、搜索不改变符合度、表头排序、前进后退、冻结列及滚动末行，并验证宽屏表格填满容器和错误状态。

`tests/test_review_browser.mjs` 是可选的真实 Chrome 回归，覆盖 1920px 和 390px 视口下切换指标保持窗口/表格滚动，以及从大集合末尾切换到小集合末尾。默认未设置 `REVIEW_BROWSER_URL` 时跳过。先启动本地 HTTP 服务和 Chrome 调试端口，PowerShell 示例：

```powershell
$env:REVIEW_BROWSER_URL='http://127.0.0.1:9223'
$env:REVIEW_SITE_URL='http://127.0.0.1:8001/'
node --experimental-websocket --test tests/test_review_browser.mjs
```

发布工作流运行全部四组前端数据测试；默认 Python 测试和 Node 数据测试均不访问网络。生成器测试使用精简本地 SRK，验证重复生成字节一致且错误 SHA-256 不覆盖已发布文件。

金、银、铜牌在赛前前瞻、赛后复盘及成员悬浮明细中共用固定网格：每种奖牌的图标占 1em、数量占 2ch，三组依次排列。图标居中、数字右对齐并使用等宽数字，不随一位或两位数移动；当前快照的最大数量分别为 35、24、17。奖牌顺序和排序规则保持不变，浏览器回归检查两页及移动端的各组位置一致。

赛后复盘表格额外拉开三组奖牌的间隔：银、铜图标槽增至 1.6em 并右对齐，网格间距为 .2em；数量槽仍为 2ch，保持各组对齐。赛前前瞻和成员悬浮明细保留紧凑间距。

## 第二场数据与测试

### 2026-09-19 官方结果修订（当前发布版本）

上游 [srk-collection PR #73](https://github.com/algoux/srk-collection/pull/73) 已合并为 `ae959416ef2955159f9affd45d4ab53bf299a98e`。RankLand 当前第二场文件 ID 为 `94656957834690560`，SHA-256 为 `a501dca75c4814277ed6a7b897db379b5ee4b3b1b560be4bc0c2cc8c84fb3fc9`；已核验实际下载字节哈希，并确认解析后的 JSON 与该合并版本完全一致。

第二场仍覆盖原 2636 支赛前队伍：2521 队有有效提交记录，101 队无提交，14 队标记为 `resultStatus: "removed"`。移除映射保存在 `config/review-removed-results/icpc2026preliminary-2.json`；依据官方公示与新旧榜单 ID 差异登记，不根据姓名跨场追溯删除。第一场复盘、两场 ICPC 前瞻的发布字节均不变。第二场覆盖率分母改为 2521，页面显示“官方结果已移除 14 支队伍”。

| 指标 | 有效队伍 | Spearman ρ（显示精度） |
| --- | ---: | ---: |
| 综合战力 | 2389 | 0.798 |
| XCPC Rating | 2386 | 0.820 |
| XCPC Elo | 2376 | 0.814 |
| 上赛季 Rating | 1307 | 0.666 |
| 本赛季 Rating | 2212 | 0.809 |
| CPC Finder | 991 | 0.651 |
| 奖牌 | 991 | 0.663 |

七项系数均经 SciPy `spearmanr` 独立复核。新增离线测试覆盖显式移除、未知或重复映射、与 override 冲突、当前仍存在/可匹配的结果、未登记的缺失继续报错、零题失败提交保留、CLI 确定性和哈希错误不覆盖、前端严格状态校验及移除后样本/覆盖率；完整快照回归更新了来源、14 队 ID 和七项基准。

当前版本离线复现（先保存上述固定 URL 的 SRK）：

```bash
python scripts/generate_review_data.py --preview static/data/previews/icpc-2026-preliminary-2.json --srk data-cache/results-20260919/icpc2026preliminary-2.srk.json --contest-id icpc2026preliminary-2 --file-id 94656957834690560 --file-url https://cdn.algoux.cn/rankland/file/94656957834690560/icpc2026preliminary-2.srk.json --sha256 a501dca75c4814277ed6a7b897db379b5ee4b3b1b560be4bc0c2cc8c84fb3fc9 --removed-results config/review-removed-results/icpc2026preliminary-2.json
```

### 2026-09-12 首次发布（历史记录）

2026-09-12 根据 [RankLand 第二场正式榜单](https://rl.algoux.cn/collection/official?rankId=icpc2026preliminary-2) 发布第二场复盘。比赛 ID `icpc2026preliminary-2` 对应前瞻 `icpc-2026-preliminary-2`，开赛时间为北京时间 2026-09-12 13:00。SRK 文件 ID 为 `92205039610843136`，SHA-256 为 `ab6a796e4ca65f1ba6dc8c9c87174a49aab7439cee6aacee17d3ce1285a9ceea`，下载字节与上游校验值一致。

2636 支前瞻队伍全部唯一匹配，无人工覆盖；2535 队有提交，101 队无提交并保留空名次。复盘使用已保存的赛前评分与归一化 LSE 队伍聚合值，七项指标包含本赛季 Rating；综合战力沿用赛前六维排序。第一场结果和两场前瞻保持原样；个人赛季 Rating 已另按同一结果更新至第二场，见 [赛季数据](season-2026-2027-preview.md)，不回填赛前快照。现有索引已登记复盘文件及两场前瞻，无需新增入口；默认打开最新的第二场，也可选择第一场。

| 指标 | 有效队伍 | Spearman ρ（显示精度） |
| --- | ---: | ---: |
| 综合战力 | 2403 | 0.798 |
| XCPC Rating | 2400 | 0.821 |
| XCPC Elo | 2390 | 0.814 |
| 上赛季 Rating | 1312 | 0.667 |
| 本赛季 Rating | 2224 | 0.810 |
| CPC Finder | 996 | 0.651 |
| 奖牌 | 996 | 0.662 |

覆盖率分母为 2535；各指标样本不同，不能将系数差直接解释为同样本预测能力差异。全部系数经 SciPy `spearmanr` 独立复核。`tests/test_review_frontend_data.mjs` 校验两场共同加载、第二场来源与时间、全部队伍关联、无活动空名次、七项指标样本数、覆盖率与完整精度系数，并继续验证第一场基准。

离线复现（先保存并核验上述 SRK 文件）：

```bash
python scripts/generate_review_data.py --preview static/data/previews/icpc-2026-preliminary-2.json --srk data-cache/review-20260912/icpc2026preliminary-2.srk.json --contest-id icpc2026preliminary-2 --file-id 92205039610843136 --file-url https://cdn.algoux.cn/rankland/file/92205039610843136/icpc2026preliminary-2.srk.json --sha256 ab6a796e4ca65f1ba6dc8c9c87174a49aab7439cee6aacee17d3ce1285a9ceea
```

## CCPC 网络预选赛（2026-09-19）

### 2026-09-23 官方结果修订（当前发布版本）

核对用户指定的 [RankLand 官方榜单](https://rl.algoux.cn/collection/official?rankId=ccpc2026preliminary)，当前文件 ID 为 `95451702349623296`，上游文件更新时间为北京时间 2026-09-21 17:30:59，SHA-256 为 `d579046c9b6bde35c9b0178fdcda574c8a2ca7f9d1a52b2110349dd2010594b1`，已核验下载字节。与首次发布的 SRK 比较，移除结果 ID `6`、`687`、`769`，无新增队伍，其余 2170 行记录完全一致。

移除映射保存在 `config/review-removed-results/ccpc2026preliminary.json`。复盘仍覆盖原前瞻的 2169 支正式队伍：2106 队有提交、60 队无提交、3 队标记 `resultStatus: "removed"`，页面沿用“官方结果已移除 3 支队伍”提示。被移除记录保留旧结果 ID，活动状态及名次为空，不进入指标样本和覆盖率分母；4 支打星队伍仍不进入复盘。三场前瞻评分与前两场复盘不变。

| 指标 | 有效队伍 | Spearman ρ（显示精度） |
| --- | ---: | ---: |
| 综合战力 | 2044 | 0.825 |
| XCPC Rating | 2043 | 0.872 |
| XCPC Elo | 2040 | 0.890 |
| 上赛季 Rating | 1127 | 0.706 |
| 本赛季 Rating | 1964 | 0.869 |
| CPC Finder | 871 | 0.641 |
| 奖牌 | 871 | 0.657 |

覆盖率分母更新为 2106。七项系数由 SciPy `spearmanr` 独立复核。完整快照回归固定新来源、三个移除 ID、无提交与移除的区别、七项样本/覆盖率/完整精度系数，并核验移除映射与发布数据一致。算法、API 和 schema 无变化，默认测试仍离线；榜单仅证明本场结果移除，不据此删除其他场次的历史。

离线复现（先下载并保存固定 SRK，生成器核验哈希）：

```bash
python scripts/generate_review_data.py --preview static/data/previews/ccpc-2026-preliminary.json --srk data-cache/results-20260923/ccpc2026preliminary.srk.json --contest-id ccpc2026preliminary --file-id 95451702349623296 --file-url https://cdn.algoux.cn/rankland/file/95451702349623296/ccpc2026preliminary.srk.json --sha256 d579046c9b6bde35c9b0178fdcda574c8a2ca7f9d1a52b2110349dd2010594b1 --removed-results config/review-removed-results/ccpc2026preliminary.json
```

本赛季个人 Rating 同步使用该 SRK 重算，见 [赛季数据](season-2026-2027-preview.md)。

### 2026-09-19 首次发布（历史记录）

根据 [RankLand 榜单](https://rl.algoux.cn/ranklist/ccpc2026preliminary) 新增第三场复盘。比赛 ID `ccpc2026preliminary` 对应前瞻 `ccpc-2026-preliminary`，开赛时间为北京时间 2026-09-19 13:00。文件 ID `94747179192774656`，SHA-256 为 `ae8673050d54cc9a793aee461ca74c5cba11948c5a3642d393f3249818687cf2`，已核验实际下载字节。

按用户要求，复盘不包含 4 支打星队伍。投影在匹配前排除前瞻中 `excluded: true` 的队伍，不要求其结果存在；前端完整性校验只接受正式名单，所有指标的样本和覆盖率分母均排除打星队伍。无需新增结果字段或更改公开 API。原前瞻保留 2173 队及全部评分，复盘覆盖其中 2169 支正式队伍，全部自动唯一匹配，无人工覆盖；2109 队有提交，60 队无提交。正式队伍匹配失败仍报错，不当作缺席。两场 ICPC 复盘内容保持不变。

| 指标 | 有效队伍 | Spearman ρ（显示精度） |
| --- | ---: | ---: |
| 综合战力 | 2046 | 0.825 |
| XCPC Rating | 2045 | 0.872 |
| XCPC Elo | 2042 | 0.890 |
| 上赛季 Rating | 1128 | 0.706 |
| 本赛季 Rating | 1966 | 0.869 |
| CPC Finder | 871 | 0.641 |
| 奖牌 | 871 | 0.657 |

覆盖率分母为 2109，七项系数已用 SciPy `spearmanr` 独立复核；不同指标覆盖范围不同。既有索引已包含 CCPC 前瞻和复盘路径，页面默认选择最新的 CCPC 场次。此次不更新个人赛季 Rating。静态资源版本为 `20260919-54`。

离线回归覆盖打星队伍不要求结果存在、输入不变、前端拒绝打星结果行、所有指标排除打星队伍，以及完整 CCPC 快照来源、名单、活动计数和七项统计基准；继续核验前两场复盘。17 项 Python 复盘测试、72 项前端数据测试及 Ruff 检查通过。

离线复现（先保存并核验上述固定 SRK）：

```bash
python scripts/generate_review_data.py --preview static/data/previews/ccpc-2026-preliminary.json --srk data-cache/review-20260919/ccpc2026preliminary.srk.json --contest-id ccpc2026preliminary --file-id 94747179192774656 --file-url https://cdn.algoux.cn/rankland/file/94747179192774656/ccpc2026preliminary.srk.json --sha256 ae8673050d54cc9a793aee461ca74c5cba11948c5a3642d393f3249818687cf2
```
