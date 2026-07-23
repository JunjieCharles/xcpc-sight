# 输出结果

本目录用于保存人工或后续代码生成的 rating 结果、竞赛分析报告、图片和可复现快照。

- 普通生成物默认被 Git 忽略，避免将大量临时结果误提交。
- 经审阅、确需纳入仓库的结果可使用 `git add -f results/<file>` 显式添加。
- 可丢弃的 RankLand/牛客下载缓存应放在 `data-cache/`，不要与面向用户的输出结果混放。
- 当前 Python 库只返回数据模型，不会自动写入本目录；调用方应显式选择输出路径。
- `scripts/fetch_nowcoder_leaderboards.py` 会显式生成 `nowcoder-<contest-id>-leaderboard.csv`；这些文件仍按普通生成物处理。
