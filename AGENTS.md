# Agent 开发指南

## 文档职责

- README.md 是面向用户的入口，介绍项目功能、安装、浏览、数据生成命令和公开 Python API 的用法。
- AGENTS.md 面向开发代理，规定架构约束、修改流程、验证方法和文档维护要求。
- `doc/` 记录详细的功能行为、算法、数据契约、假设、限制和测试覆盖。通过 `doc/README.md` 查找相关设计文档；在 README.md 中引用这些文档，避免重复堆放实现细节或更新历史。

## 修改流程

- 修改已有功能前，先阅读相关设计文档，并检查现有实现和测试。
- 将修改范围限定在用户请求内。数据生成必须显式执行，不要因无关的代码或文档修改而重新生成已发布数据。
- 每项功能都应归属于 `doc/` 下的一份设计文档；功能范围变化时，在 `doc/README.md` 中新增或更新对应条目。
- 完成工作前，回到相关设计文档，同步功能行为、公开 API、数据假设、已知限制和测试覆盖。
- 如果实现与文档不一致，应在同一次修改中更新两者，或明确记录设计决策。不要明知不一致却保留原状。
- 公开 API 变化时，还需更新 README.md，以及 `src/core/__init__.py`、`src/rating/__init__.py` 或 `src/problem_rating/__init__.py` 中相应的包导出。

## 架构与项目方向

- 保持项目灵活、轻量、可扩展。不要为假想需求引入框架或抽象层。
- 优先使用明确的数据模型和小型、可组合的函数，避免全局状态。
- 领域计算应独立于 HTTP、文件、展示和报表生成。库 API 不得隐式写文件；由脚本负责显式输出。
- `src/core/` 负责上游数据适配、标准化、领域模型和赛季选择。`src/rating/` 负责选手与报名实体 Rating，以及纯 JSON 投影。`src/problem_rating/` 负责独立的题目难度模型；两个 Rating 包之间不共享模型或状态。
- 发行名称为 `xcpc-sight`，导入包名为 `core`、`rating` 和 `problem_rating`，不提供 `xcpc_sight` 统一入口。
- `static/` 保持为使用浏览器原生 ES modules、无需构建的前端，不引入 npm 依赖或 `package.json`。

## 数据处理

- 将上游比赛数据视为不可信输入，校验失败时提供有用的上下文。对于真实上游数据中已知的歧义，采用有文档说明的确定性策略，并在可行时提供严格校验。
- 保持输出可复现：相同输入必须生成确定的静态 JSON，并遵守各功能的数据结构和投影规则。
- `static/data/` 存放已发布数据。`data-cache/` 存放被 Git 忽略的上游缓存、训练输入和本地输出；不要假定全新检出的仓库中存在这些文件，也不要将其作为测试样例直接提交。
- 题目 Rating 的缓存和本地输出统一放在 `data-cache/problem-rating/` 下。仅发布文档规定的题目级聚合数据，不发布账号标识、队伍 token 或逐人提交记录。
- 前瞻名单和评分是外部数据快照。仅刷新用户明确指定的比赛或名单；通用静态数据生成器只复制已提交的前瞻快照，不刷新快照内容。
- 在 `config/school-aliases.json` 中维护学校别名，并按 `doc/school-aliases.md` 处理歧义。

## 测试与验证

- 新功能和缺陷修复必须配有针对性的单元测试。
- 纯 Rating 计算和筛选规则必须有确定性的回归测试。
- 默认测试不得依赖网络访问。使用注入的 HTTP 传输层，以及已提交的精简测试样例。
- 保留一个覆盖数据适配、赛季排序和 Rating 计算的小型端到端测试。
- 访问实时 RankLand、牛客和 HDU 的数据生成命令不属于离线测试，不要将其用作常规验证。
- 仅修改文档时，检查命令准确性、本地链接和差异；行为未变时无需新增单元测试。

在项目虚拟环境中安装开发依赖：

```bash
python -m pip install -e ".[dev]"
```

运行与本次修改相关的检查。标准代码检查、Python 覆盖率测试和前端回归命令如下：

```bash
ruff check .
pytest --cov=core --cov=rating --cov=problem_rating
node --test tests/test_frontend_data.mjs tests/test_problem_rating_frontend_data.mjs tests/test_preview_frontend_data.mjs tests/test_online_preview.mjs tests/test_review_frontend_data.mjs
```

前端测试使用 Node 内置测试运行器。修改布局或交互时，还应通过 HTTP 提供 `static/`，检查受影响的桌面端和移动端页面；仅靠数据测试无法验证渲染效果。
