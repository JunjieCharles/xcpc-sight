# IOI 成绩数据

`data-cache/ioi/` 保存用户明确提供的 IOI 中国选手成绩快照。它是本地上游输入，不进入 Git，不由浏览器直接访问，也不声称是每届 IOI 的完整获奖名单。

## 数据契约

`index.json` 使用 schema v1，按年份升序列出年度文件；顶层 `source` 为 `user-provided`。每个 `<year>.json` 的顶层字段为 `schemaVersion`、`year`、`max_score` 和 `results`：

```json
{"schemaVersion":1,"year":2025,"max_score":600,"results":[{"rank":1,"name":"刘恒熙","grade":"高二","score":591.23,"medal":"gold","school":"宁波市镇海中学"}]}
```

每条 `results[]` 保留：

- `rank`：IOI 公开排名，正整数；并列选手保留相同排名；
- `name`、`grade`、`school`：用户提供的原始展示文本；
- `score`：实际得分，可为整数或小数；
- `medal`：`gold`、`silver` 或 `bronze`。

数据中没有省份信息，不能从学校推断或补造。`parse_ioi_results(year, max_score, records)` 是 `core` 导出的纯校验 API：它拒绝缺失或额外字段、空文本、非正排名、非法奖牌，以及不在 $[0, max\_score]$ 内的非有限得分。

## 测试

```bash
python -m pytest tests/test_ioi.py
```

测试覆盖并列排名、小数得分和字段值域校验。每次更新快照后，应使用该 API 重新验证所有年度文件。