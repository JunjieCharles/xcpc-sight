# 静态站点数据

第一版仅发布 `2025-2026` ICPC + CCPC 综合 rating 系列。生成器不包含前端、后端或数据库，也不生成统计数据、分块、独立单场文件以及独立 ICPC/CCPC 系列。

## 文件与生成

```bash
python scripts/generate_static_data.py
```

默认按 RankLand → 赛季选择 → rating 计算流程写入：

- `static/data/index.json`
- `static/data/series/2025-2026.json`

`--output-dir` 可覆盖根目录。生成器先原子发布系列文件，最后发布入口索引。JSON 是紧凑 UTF-8（无 BOM），禁止 NaN，保留一个末尾换行，不包含生成时间；固定输入产生固定字节。生成命令访问实时 RankLand，默认离线测试不会执行它。

## 索引契约

```json
{"schemaVersion":1,"defaultSeriesId":"2025-2026","series":[{"id":"2025-2026","title":"2025–2026 ICPC + CCPC","path":"series/2025-2026.json"}]}
```

字段含义：

- `schemaVersion`：当前为 `1`；
- `defaultSeriesId`：静态站点默认打开的系列；
- `series[]`：可用系列的 `id`、显示 `title` 和相对索引文件的 `path`。

## 系列契约

顶层字段：

- `schemaVersion`、`id`、`title`；
- `initialRating`：当前系列默认 `1400`；
- `contests[]`：rating 计算顺序中的比赛；
- `competitors[]`：最终 rating 排序后的选手。

`contests[]` 每项包含：

- `id`、`title`；
- `collection`：例如 `icpc2025` 或 `ccpc2025`；
- `startAt`：转换到 `Asia/Shanghai` 后的带偏移 ISO 8601 时间。无时区的上游时间按上海时间解释。

`competitors[]` 每项包含：

- `id`：`c_` 加 SHA-256(`normalized_school + "\0" + normalized_member`) 的完整小写十六进制值；
- `rank`：按最终 rating 的 competition ranking，同分同名次且后续名次跳号；
- `school`、`member`：最后一次实际参赛记录中的上游显示值；
- `finalRating`、`contestsParticipated`；
- `participations[]`：严格按 `contestIndex` 递增的实际参赛记录。

每条 participation 包含：

```json
{"contestIndex":0,"contestRank":1,"before":1400,"delta":25,"after":1425}
```

选手按 `finalRating` 降序，再按稳定 `id` 升序排列。投影会验证稳定 ID 唯一、比赛引用范围、同场身份唯一、`before + delta == after`、跨参赛场次 rating 连续、最终 rating 和参赛次数一致。

## 从稀疏记录派生页面数据

`participations` 只记录实际计入 rating 的场次：

- 某场没有记录表示未参加；
- 有记录且 `delta == 0` 表示参加但 rating 未变化。

因此可以派生：

1. **系列宽表**：按比赛顺序扫描；首次参赛前留空，参赛时使用 `after`，缺席时延续最近 rating。
2. **单场参赛者表**：筛选 `contestIndex`，直接读取 `contestRank`、`before`、`delta`、`after`。
3. **选手完整曲线**：按所有比赛顺序扫描，参赛点更新为 `after`，缺席点延续；首次参赛前不构造 rating。

系列文件不输出 seed、performance、修正项等计算诊断，不生成缺席记录、稠密 rating 数组或重复的单场 JSON。
