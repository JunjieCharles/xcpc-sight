# 本地学校别名表

## 数据与维护

项目以 `config/school-aliases.json` 为学校别名的本地维护源，纳入 Git，生成时不下载、不检查线上版本。初始完整导入 2026-09-08 核对的 [xcpc-standings 学校配置](https://github.com/JunjieCharles/xcpc-standings/blob/master/data/config/school.json)，共 658 个学校条目、730 个别名；该链接仅作来源记录，后续修改直接在本项目完成。

格式为“规范校名 → 别名字符串数组”，规范校名无需再加入自己的数组。学校更名时可将新名称加入现有学校的数组，保持原规范身份稳定；如确需修改规范校名，应将旧名保留为别名，并考虑重新生成数据带来的身份变化。校区或名称相似不代表同校，仅在确认同一学校后归并。繁简体、大小写、全半角、连字符和引号由 `DefaultNormalizer` 处理，无需逐一枚举。

```json
{
  "北京师范大学香港浸会大学联合国际学院": [
    "Beijing Normal-Hong Kong Baptist University",
    "北师香港浸会大学"
  ]
}
```

## 加载 API 与歧义

`core.load_school_aliases(path)` 只读取指定本地 UTF-8 JSON，返回规范化后的 `dict[str, str]`，交给 `DefaultNormalizer(school_aliases=...)` 使用。为兼容原复盘命令，也接受旧格式“别名 → 规范校名”。文件不存在、JSON 无效、字段类型或空身份非法时抛出包含文件路径和相关学校的 `DataValidationError`，不静默回退或联网下载。空对象可显式禁用别名。

同一规范化别名若指向多个不同学校，确定性地排除该别名，不按文件顺序选学校；规范校名始终保留自己的身份，不被其他条目的别名覆盖。原表中的 `Taizhou University` 同时指向台州学院与泰州学院，`Wuyi University` 同时指向五邑大学与武夷学院，均保留原始记录但不映射到其中任一学校。需使用无歧义的校名匹配；本表不能消除同校同名选手的歧义。

## 接入边界

前瞻与复盘生成器的 `--school-aliases` 默认指向仓库 `config/school-aliases.json`，默认路径以脚本所在目录确定，不依赖工作目录。显式参数仍可指定另一份本地文件，完整替代默认表。

纯 `DefaultNormalizer()` 不读文件；其他领域计算 API 继续通过显式传入 normalizer 使用别名，避免隐式改变已发布 Rating 身份。修改表不会自动刷新静态快照，需重新执行相应生成流程。本次迁移不更新评分来源或已发布数据。

## 测试

`tests/test_school_aliases.py` 离线校验完整本地表加载、更名与中英文匹配、歧义隔离和输入顺序无关、规范名保护、旧格式兼容、空覆盖以及文件和字段错误上下文。前瞻测试直接复用正式本地列表，校验默认本地路径及 CPC Finder 合并，不维护另一份同名测试 JSON；复盘生成器离线端到端测试使用默认本地表。维护后运行这些测试，不要求网络或 `data-cache/` 文件。
