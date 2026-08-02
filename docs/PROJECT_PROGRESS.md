# AI 技术调研 Agent｜项目进度与功能路线图

> 文件用途：记录当前已经完成的功能、尚未实现的功能、推荐开发顺序和每个阶段的验收标准。  
> 建议位置：`docs/PROJECT_PROGRESS.md`  
> 当前阶段：**迭代 1——数据获取与工作流骨架（最小研究闭环尚未完成）**
> 更新日期：2026-08-01

---

## 0. 2026-08-01 现状核验

- [x] T02 配置和环境变量。
- [x] T03 第一阶段数据模型与 ResearchState。
- [x] T06 ToolResult 与 ToolProtocol。
- [ ] T01 工程质量基线：Python 版本满足要求，但项目环境未安装完整依赖，pytest/Ruff/mypy 未全绿。
- [ ] T04 请求规范化：ISO 日期和默认值已完成，相对时间和自然语言参数解析未完成。
- [ ] T05 Planner：主体、降级和测试已编写，但 warning 断言与完整质量门禁未关闭。
- [ ] T07 Web 搜索：Tavily 主体已实现，缺 Mock/External 验收测试和重试次数记录。
- [ ] T08 来源处理：URL/哈希基础去重和问题关联已实现，尚未下沉到 Services，完整测试未通过。
- [ ] T09 Writer 与 Markdown：未实现。
- [ ] T10 LangGraph：已有 normalize/plan/search 三节点固定图，process/write 和工作流验收未实现。
- [ ] T11 CLI：已有 health/plan/search/research 骨架，尚不能输出 Markdown 报告。
- [ ] T12 端到端验收：未实现。

详细勾选、核验命令与下一步代码见 `docs/PROJECT_PLAN.md` 和 `docs/NEXT_STEP_IMPLEMENTATION.md`。

---

## 1. 项目目标

AI 技术调研 Agent 面向人工智能、大模型、Agent 和软件开发主题，最终完成以下研究闭环：

```text
理解任务
  → 规范化请求
  → 制定研究计划
  → 检索外部来源
  → 来源处理与去重
  → 来源排序与知识检索
  → 生成带引用报告
  → 审核与定向修改
  → 保存和输出结果
```

第一版优先保证：

- 研究流程可以完整运行；
- 来源真实且可以追溯；
- 工作流状态清晰、可测试；
- 外部服务失败时能够降级；
- 后续可以平滑加入数据库、RAG、Reviewer 和每日简报。

---

## 2. 当前已经完成的功能

以下内容根据当前项目开发进度记录为已完成。

### 2.1 研究请求模型

**主要文件：**

```text
app/models/research.py
```

**已经实现：**

- [x] `ResearchRequest`
- [x] 研究主题 `topic` 的长度校验
- [x] `research_type` 类型限制
- [x] 开始日期和结束日期字段
- [x] 非法时间范围校验
- [x] 来源偏好 `source_preferences`
- [x] 最大来源数量 `max_sources`
- [x] 默认输出语言 `zh-CN`
- [x] 使用 `default_factory` 避免可变默认值问题

支持的研究类型：

```text
daily_brief
深度报告：deep_report
学习指南：learning_guide
GitHub 分析：github_analysis
```

---

### 2.2 研究子问题模型

**主要文件：**

```text
app/models/research.py
```

**已经实现：**

- [x] `ResearchQuestion`
- [x] 子问题内容 `question`
- [x] 研究目标 `goal`
- [x] 推荐来源类型 `preferred_sources`

该模型将作为 Planner Agent 的结构化输出格式。

---

### 2.3 来源数据模型

**主要文件：**

```text
app/models/source.py
```

**已经实现：**

- [x] `SourceDocument`
- [x] 来源唯一标识 `source_id`
- [x] 标题和 URL
- [x] 来源类型
- [x] 发布时间
- [x] 搜索摘要
- [x] 清洗后的正文
- [x] 内容哈希
- [x] 扩展元数据 `metadata`

当前阶段先使用内存对象保存来源。数据库接入后，将进一步补充 `canonical_url`、抓取时间、分块信息和来源评分。

---

### 2.4 报告与引用模型

**主要文件：**

```text
app/models/report.py
```

**已经实现：**

- [x] `Citation`
- [x] `ReportSection`
- [x] `ReportSchema`
- [x] 引用与 `source_id` 的关联
- [x] 报告标题和摘要
- [x] 结构化章节
- [x] 关键发现
- [x] 引用列表
- [x] 置信度范围校验

报告设计采用以下流程：

```text
Writer 生成 ReportSchema
  → Pydantic 校验
  → ReportRenderer 渲染
  → Markdown 输出
```

这可以避免 Writer 随意改变最终报告格式。

---

### 2.5 LangGraph 共享状态

**主要文件：**

```text
app/graph/state.py
```

**已经实现：**

- [x] `ResearchState`
- [x] 任务标识 `task_id`
- [x] 工作流标识 `thread_id`
- [x] 研究主题和研究类型
- [x] 语言和时间范围
- [x] 研究子问题列表
- [x] 原始来源
- [x] 处理后来源
- [x] 草稿报告和最终报告
- [x] 修订次数
- [x] 任务状态
- [x] 错误列表
- [x] Token 用量和估算成本字段

当前 State 中不保存数据库连接、模型客户端、搜索客户端或其他不可序列化对象。

---

### 2.6 请求规范化节点

**主要文件：**

```text
app/graph/nodes/normalize_request.py
```

**已经实现：**

- [x] 去除研究主题首尾空格
- [x] 使用 `ResearchRequest` 校验输入
- [x] 校验研究类型
- [x] ISO 日期字符串转换
- [x] 校验开始日期和结束日期
- [x] 设置默认语言
- [x] 返回当前节点负责更新的 State 字段
- [x] 更新任务状态为 `request_normalized`

后续仍可增强：

- [ ] 将“最近三个月”“过去 24 小时”等相对时间转换为绝对日期
- [ ] 识别自然语言中的来源偏好
- [ ] 识别报告长度和最大来源数量
- [ ] 对复杂输入启用可选 LLM 解析

---

### 2.7 基础单元测试

**主要目录：**

```text
tests/unit/
```

**已经覆盖或应已覆盖：**

- [x] 正常创建研究请求
- [x] 拒绝过短主题
- [x] 拒绝非法研究类型
- [x] 拒绝开始日期晚于结束日期
- [x] 创建结构化研究子问题
- [x] 模型默认值检查
- [x] 基础序列化和校验

建议持续执行：

```bash
pytest -v
ruff check app tests
mypy app
```

---

## 3. 当前里程碑判断

当前已经基本完成：

```text
T03：定义 Pydantic 模型和 ResearchState
T04：实现 normalize_request
```

当前项目还没有形成完整研究闭环，因为 Planner、搜索工具、来源去重、Writer 和 LangGraph 主图尚未连接完成。

下一项推荐任务：

```text
T05：实现 Planner Agent
```

---

## 4. 下一阶段需要实现的功能

## 4.1 T05：Planner Agent

**主要文件：**

```text
app/agents/planner.py
app/graph/nodes/create_plan.py
tests/unit/test_planner.py
tests/graph/test_create_plan_node.py
```

**目标：**

把规范化后的研究主题拆分成 3～5 个相互补充的研究问题。

**需要实现：**

- [ ] 定义 Planner 接口
- [ ] 编写 Planner Prompt
- [ ] 使用结构化输出返回 `ResearchQuestion`
- [ ] 限制问题数量为 3～5 个
- [ ] 避免生成同义重复问题
- [ ] 每个问题包含 `question`、`goal`、`preferred_sources`
- [ ] Planner 只负责规划，不直接回答问题
- [ ] 处理模型返回非法 JSON
- [ ] 处理空问题列表
- [ ] 添加重试或规则降级方案
- [ ] 实现 `create_plan` LangGraph 节点
- [ ] 添加单元测试和节点测试

**验收标准：**

输入一个合法研究主题后，可以稳定获得 3～5 个结构化研究问题。

---

## 4.2 T06：统一工具接口

**主要文件：**

```text
app/tools/base.py
tests/unit/test_tool_base.py
```

**需要实现：**

- [ ] 定义 `ToolResult`
- [ ] 统一成功和失败返回格式
- [ ] 包含工具名称、查询内容、结果列表、错误信息和耗时
- [ ] 预留缓存命中字段
- [ ] 定义工具抽象接口或 Protocol
- [ ] 保证 Tool 不依赖 LangGraph

建议结构：

```text
tool_name
query
success
items
error
duration_ms
cached
```

---

## 4.3 T07：WebSearchTool

**主要文件：**

```text
app/tools/web_search.py
tests/unit/test_web_search.py
tests/integration/test_web_search_integration.py
```

**需要实现：**

- [ ] 接入一个网页搜索服务
- [ ] 支持关键词查询
- [ ] 支持开始和结束日期
- [ ] 支持域名限制
- [ ] 支持最大结果数量
- [ ] 返回标题、URL、摘要和可能的发布时间
- [ ] 设置超时
- [ ] 设置有限重试
- [ ] 处理空结果
- [ ] 使用统一 `ToolResult`
- [ ] 使用 Mock 完成稳定测试

第一阶段暂时不在搜索工具中抓取完整网页正文。

---

## 4.4 T08：来源标准化与去重

**主要文件：**

```text
app/services/source_normalizer.py
app/services/source_deduplicator.py
tests/unit/test_source_normalizer.py
tests/unit/test_source_deduplicator.py
```

**需要实现：**

- [ ] URL 标准化
- [ ] 移除常见跟踪参数
- [ ] 生成 `canonical_url`
- [ ] 搜索结果转换为 `SourceDocument`
- [ ] 根据 URL 去重
- [ ] 根据正文哈希去重
- [ ] 处理缺失标题或缺失日期
- [ ] 保留来源与研究问题之间的关系

**验收标准：**

相同 URL、不同跟踪参数的 URL，以及相同正文内容可以被识别为重复来源。

---

## 4.5 T09：Writer Agent 与 Markdown 渲染

**主要文件：**

```text
app/agents/writer.py
app/graph/nodes/write_report.py
app/services/report_renderer.py
tests/unit/test_writer.py
tests/unit/test_report_renderer.py
```

**需要实现：**

- [ ] Writer 只使用传入的来源内容
- [ ] 输出严格符合 `ReportSchema`
- [ ] 每个关键结论关联引用
- [ ] 引用的 `source_id` 必须来自工具实际结果
- [ ] 禁止模型自行编造 URL
- [ ] 区分事实、来源观点和模型推断
- [ ] 将结构化 JSON 稳定渲染为 Markdown
- [ ] 处理 Writer 非法结构输出

**验收标准：**

报告结构稳定，且关键结论能够追溯到真实来源。

---

## 4.6 T10：组装最小 LangGraph

**主要文件：**

```text
app/graph/builder.py
app/graph/nodes/search_sources.py
app/graph/nodes/process_sources.py
app/graph/nodes/write_report.py
tests/graph/test_minimal_graph.py
```

第一阶段主流程：

```text
START
  → normalize_request
  → create_plan
  → search_sources
  → process_sources
  → write_report
  → END
```

**需要实现：**

- [ ] 创建 `StateGraph`
- [ ] 注册所有节点
- [ ] 注册固定边
- [ ] 编译工作流
- [ ] 构造初始 State
- [ ] 确保每个节点只更新自己负责的字段
- [ ] 测试节点顺序
- [ ] 测试多次运行不存在状态污染
- [ ] 测试搜索失败时的降级行为

---

## 4.7 T11：CLI 或同步调试 API

**推荐第一步先实现 CLI，随后再实现 FastAPI 调试接口。**

**可能文件：**

```text
app/main.py
app/api/research.py
scripts/run_research.py
```

**需要实现：**

- [ ] 输入研究主题
- [ ] 选择研究类型
- [ ] 调用编译后的 LangGraph
- [ ] 输出结构化报告
- [ ] 输出 Markdown 文件
- [ ] 显示明确的失败信息

---

## 4.8 T12：端到端验收测试

**主要目录：**

```text
tests/integration/
```

**需要实现：**

- [ ] 固定输入主题
- [ ] Mock LLM 和搜索服务
- [ ] 验证生成 3～5 个研究问题
- [ ] 验证至少得到 5 个来源
- [ ] 验证重复来源被删除
- [ ] 验证报告包含真实引用
- [ ] 验证整个流程由 LangGraph 执行
- [ ] 验证连续运行没有状态污染
- [ ] 验证搜索超时可以降级

---

## 5. 后续迭代路线

## 5.1 迭代 2：数据库、Checkpoint 与 API 工程化

在最小闭环稳定后实现：

- [ ] SQLAlchemy 数据模型
- [ ] Alembic 数据库迁移
- [ ] Task Repository
- [ ] Source Repository
- [ ] Report Repository
- [ ] PostgreSQL 持久化
- [ ] LangGraph Postgres Checkpointer
- [ ] FastAPI 异步任务接口
- [ ] 任务状态查询接口
- [ ] 报告查询接口
- [ ] SSE 进度事件
- [ ] Redis 搜索缓存
- [ ] Redis 任务锁
- [ ] 结构化日志和 Trace

**完成标志：**

任务可以持久化，服务重启后可以查询或恢复状态。

---

## 5.2 迭代 3：多来源、抓取与 RAG

- [ ] `GitHubResearchTool`
- [ ] 仓库元数据读取
- [ ] README、目录树和 Release 读取
- [ ] Commit、Issue 和 PR 检索
- [ ] `PaperSearchTool`
- [ ] arXiv 或 OpenAlex 接入
- [ ] `ContentFetcher`
- [ ] 网页正文抽取和清洗
- [ ] 文档分块
- [ ] Embedding 批量生成
- [ ] pgvector 索引
- [ ] PostgreSQL 全文检索
- [ ] 关键词与向量混合检索
- [ ] 候选结果去重和重排
- [ ] 来源权威度评分
- [ ] 相关性、新鲜度、原创性和完整度评分

**完成标志：**

系统能够分析 GitHub 项目、检索论文，并优先使用官方或原始资料。

---

## 5.3 迭代 4：Reviewer、引用验证与自动评估

- [ ] 引用存在性检查
- [ ] 引用覆盖率计算
- [ ] 引用与结论一致性检查
- [ ] 时间范围检查
- [ ] 计划完成率检查
- [ ] 重复内容检查
- [ ] `Reviewer Agent`
- [ ] 结构化 `ReviewResult`
- [ ] `revise_report` 定向修订
- [ ] 审核条件路由
- [ ] 最大修订次数限制为 2 次
- [ ] 保存质量分和问题列表
- [ ] 建立固定离线评估数据集

**完成标志：**

不合格报告能够被识别并定向修改，每份报告都有质量分和问题清单。

---

## 5.4 迭代 5：每日 AI 技术简报产品化

- [ ] 用户关注主题配置
- [ ] 来源偏好配置
- [ ] 每日定时任务
- [ ] 最近 24 小时绝对时间过滤
- [ ] 多来源事件聚类
- [ ] 跨来源去重
- [ ] 事件重要性评分
- [ ] Top 5 重点选择
- [ ] 简报模板
- [ ] Markdown 邮件渲染
- [ ] 邮件发送
- [ ] 发送失败重试
- [ ] 历史简报查询

**完成标志：**

系统每天能够生成 5 条不重复、带日期和原始链接的 AI 技术简报。

---

## 6. 当前不应优先实现的内容

在最小闭环完成前，暂时不要优先开发：

```text
复杂前端
多租户权限系统
大量搜索 Provider
无限递归 Deep Research
自动图片生成
PDF 和 Word 多格式导出
自动执行 GitHub 写操作
复杂任务调度平台
```

这些功能会增加工程复杂度，但不能替代核心研究闭环。

---

## 7. 下一项开发任务建议

### 任务名称

```text
P0 + T07/T08 收口：恢复质量门禁，补搜索测试，拆分来源处理服务
```

### 允许修改

```text
pyproject.toml
tests/unit/test_planner.py
tests/unit/test_search_tool.py
app/tools/base.py
app/tools/search.py
app/services/source_normalizer.py
app/services/source_deduplicator.py
app/graph/nodes/search_sources.py
对应文档
```

### 暂时禁止修改

```text
ResearchState 字段名称
ReportSchema
数据库相关文件
FastAPI 正式任务接口
Reviewer / RAG / 前端
```

### 验收要求

1. 项目依赖可以在 `ai-search` 环境一次安装；
2. 当前全部测试完成收集并通过；
3. Tavily 正常、空结果、超时、限流和非法响应均有 Mock 测试；
4. URL 与 content_hash 去重不丢失研究问题关联；
5. Tool 只处理 Provider I/O，确定性处理下沉到 Services；
6. 搜索节点只负责并发调度和 State 增量更新；
7. `pytest`、`ruff check`、`ruff format --check`、`mypy` 全部通过。

---

## 8. 进度更新规则

每完成一个功能，应同步更新本文件：

1. 将对应任务由 `[ ]` 改为 `[x]`；
2. 补充实际创建或修改的文件；
3. 写明已经通过的测试；
4. 记录尚未处理的风险；
5. 修改 State、Prompt 或公共接口时，同步更新项目设计文档；
6. 不要把“代码已经创建”直接视为“功能已经完成”，必须通过验收测试。

---

## 9. 变更记录

| 日期 | 版本 | 变更内容 |
|---|---|---|
| 2026-08-01 | V0.2 | 重新核验当前仓库；补记 Planner、Tavily 搜索、基础去重、三节点 LangGraph 和 CLI 骨架进度；将下一任务调整为 P0 与 T07/T08 收口。 |
| 2026-07-26 | V0.1 | 创建项目进度文件；记录 Models、ResearchState、normalize_request 和基础测试完成情况；整理后续 T05～T12 与迭代 2～5 路线。 |

---

## 10. 当前状态摘要

```text
已完成：配置、数据契约、ResearchState、Planner 主体、ToolResult/Protocol
部分完成：请求规范化、Tavily 搜索、基础去重、三节点 LangGraph、CLI 骨架
当前任务：恢复质量门禁并收口 T07/T08
下一里程碑：plan → search → process → write 最小闭环可运行
最终目标：可检索、可引用、可审核、可恢复、可评估的 AI 技术调研 Agent
```
