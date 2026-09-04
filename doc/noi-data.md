# NOI 获奖名单数据

`data-cache/noi/` 保存从 CCF NOI 官方获奖名单页面提取的原始二维表格缓存。缓存是本地上游输入，不进入 Git，也不由浏览器直接访问。

## 标准化

在已缓存原始页面后，运行：

```bash
python scripts/normalize_noi_awards.py
```

默认从 `data-cache/noi/sources.json` 读取年份、原始缓存文件和官方来源 URL，并发布到 `data-cache/noi/normalized/`。该命令不访问网络。`index.json` 使用 schema v1，并按年份升序列出各年份文件与来源 URL；每个 `<year>.json` 为：

```json
{"schemaVersion":1,"year":2025,"awards":[{"year":2025,"name":"刘恒熙","province":"浙江","school":"宁波市镇海中学","grade":"高二","score":650,"medal":"gold"}]}
```

`awards[]` 保留且只保留：

- `year`：NOI 年份；
- `name`：选手姓名；
- `province`：省份；
- `school`：官方名单中的学校全称；
- `grade`：官方名单中的年级；
- `score`：加分后的“总分”，为非负整数；
- `medal`：`gold`、`silver` 或 `bronze`。

解析器根据名单中的“金牌/银牌/铜牌…名”分段确定奖牌，并根据列头定位字段，以兼容 2020 年的“学校”“年级”列和后续年份带说明后缀的列头。它不输出证书编号、性别、原始得分、加分、集训队或指导教师。缺失必需列、记录不在奖牌分段内、缺失值或非整数总分会导致命令失败。

## 测试

```bash
python -m pytest tests/test_noi.py
```

测试覆盖奖牌分段、带后缀的学校/年级列头、所需字段投影及非法总分拒绝。实际年份数据生成后还应解析所有发布文件并检查记录数量。