# Rating 计算规则

实现位于 `rating` 包：rating 专属模型在 `rating.models`，纯算法在 `rating.calculation`。算法依赖 `core` 的标准化竞赛与身份模型，不负责 HTTP 获取或文件输出。`rating.static_data` 位于计算之后，只把既有结果投影为静态站点 JSON 原生类型，不改变任何 rating 规则。

## 输入与身份

Rating 默认以个人为单位：没有显式 rating 实体的正式队伍展开为最多三名个人，每个人使用该队伍的比赛排名，但每个人都独立进入 expected-seed 参赛者池。身份键是“规范化学校 + 规范化姓名”；规范化包含 NFKC、繁转简、大小写折叠以及只保留 Unicode 字母和数字。别名由调用方注入，不读取机器专属文件。

来源适配器也可在 `TeamResult` 上提供显式 `CompetitorId` 和独立展示学校/名称，此时该行作为单个报名实体进入计算，不按成员展开。牛客系列采用命名空间化的 standing UID，HDU 系列采用认证榜单中的 `teamNNNN` token；显示队名和学校均不参与身份计算。

非正式队伍不参与。完全没有提交活动的队伍不参与；0 题但有失败提交的队伍仍参与。同场同一规范身份出现在多支队伍时，默认保留最好排名，使真实 RankLand 数据可计算；`RatingConfig(duplicate_competitor="error")` 可启用严格报错。单支队伍内重复成员始终报错。

## 初始状态

- 未提供历史状态时从空状态开始。
- 首次出现的选手赛前 rating 为 1400。
- 未参加某场比赛的选手 rating 保持不变。
- 计算函数不修改调用方传入的 mapping。

## 单场公式

设赛前 rating 为 `R_i`，队伍排名为 `rank_i`，rating 频次为 `count(R)`。

```text
seed_i = 1 + Σ_R count(R) / (1 + 10^((R_i - R) / 400)) - 1/2
M_i = sqrt(seed_i * rank_i)
```

通过整数二分在 `1..7999` 中寻找最大的 performance `P_i`，使按候选 performance 计算且移除该选手自身后的 seed 不小于 `M_i`。

```text
raw_delta_i = trunc_toward_zero((P_i - R_i) / 2)
```

第一次全局修正：

```text
global = -trunc_toward_zero(Σ raw_delta_i / n) - 1
```

第二次修正：按赛前 rating 降序，同分按规范身份稳定排序；令：

```text
s = min(n, 4 * floor(sqrt(n) + 0.5))
top = clamp(-trunc_toward_zero(Σ前s人(raw_delta_i + global) / s), -10, 0)
```

`top` 加到所有参赛者：

```text
new_rating_i = R_i + raw_delta_i + global + top
```

所有除法取整均为 Java/C++ 式向零截断，而不是 Python 对负数的 `//` 向下取整。

## 并列与排名

RankLand SRK 如果没有完整显式排名，则按正式队伍的 solved 降序、penalty 升序重建。solved 和 penalty 相同者并列，下一名跳号，例如 `1, 2, 2, 4`。非正式队伍不占排名位置。

## 与旧脚本的有意差异

来源脚本：`run.py` 与 `rating_utils.py`。

1. 旧脚本声称模拟 Java 除法却使用 `//`；本实现对负数也向零截断。
2. 旧脚本算出第二次 top correction，但应用语句被注释；本实现实际应用。
3. 旧脚本同场重复身份最后一行覆盖；本实现默认保留最好排名，并可启用严格拒绝模式。
4. 旧 CSV 使用上游 `Rank`；RankLand 无可靠排名时按正式 solved/penalty 重建并列排名。

## API 与测试

- `calculate_contest_ratings`
- `calculate_series_ratings`
- `project_series_rating_data`
- `project_static_data_index`
- `RatingConfig` 可显式关闭两次修正，用于分析，不改变默认规则。

JSON 字段、稳定身份 ID、稀疏参赛语义和生成流程见 [static-site-data.md](static-site-data.md)。测试覆盖空比赛、初始 1400、固定 golden vector、第二次修正、非正式/无活动过滤、重复身份、跨比赛状态传递、静态投影不变量与端到端赛季计算。
