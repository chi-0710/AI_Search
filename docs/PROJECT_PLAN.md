# AI 技术调研 Agent｜项目总规划与实施清单

> 文档定位：项目主规划、功能清单、阶段验收标准和持续更新看板。  
> 当前版本：V1.1
> 当前阶段：迭代 1——数据获取与工作流骨架（最小研究闭环尚未完成）
> 状态基线日期：2026-08-01
> 适用范围：第一版最小闭环至数据库、RAG、Reviewer、每日简报产品化。

---

## 0. 使用说明

### 0.1 状态标记规则

- `[x]`：功能已经实现，并且现有证据足以确认达到本任务当前阶段的验收标准。
- `[ ]`：功能尚未实现，或只完成了一部分，尚未满足完整验收标准。
- 部分完成的父任务保持 `[ ]`，其下已经完成的子项单独标记为 `[x]`。
- “文件已经创建”不等于“功能已经完成”；必须同时检查调用关系、自动测试和验收结果。
- 后续增强项不影响当前阶段完成时，会单独放在“后续增强”中，不与当前任务验收混淆。

### 0.2 规划依据

本规划综合以下内容整理：

- 《AI 技术调研 Agent_第一版方案与详细开发流程》
- 《AI 技术调研 Agent_项目结构与调用关系说明》
- 当前仓库中的代码、测试、配置和 `docs/PROJECT_PROGRESS.md`
- 2026-07-28 对当前项目进行的代码、依赖、测试与质量门禁检查

### 0.3 当前完成度摘要

| 评估范围 | 当前判断 |
|---|---|
| 第一轮 T01–T12 | 约完成 50%（3 项完成，7 项部分完成，2 项未开始） |
| 迭代 1 最小研究闭环 | 已打通 `normalize → plan → search`，尚缺 `process → write → Markdown` |
| 完整第一版产品 | 约完成 15%–20% |
| 当前主要成果 | 数据契约、配置、请求规范化基础、Planner、统一工具接口、Tavily 搜索、基础 URL/正文去重、三节点 LangGraph、CLI 骨架 |
| 当前主要缺口 | 可复现依赖环境、搜索工具 Mock 测试、独立 Services、Writer、Markdown 渲染、完整主图、端到端测试 |

### 0.4 当前任务状态

- [ ] T01：初始化项目和质量工具（部分完成）
- [x] T02：定义配置和环境变量
- [x] T03：定义第一阶段数据模型和 ResearchState
- [ ] T04：实现完整请求规范化（部分完成）
- [ ] T05：实现 Planner Agent（主体已完成，验收未闭环）
- [x] T06：定义 ToolResult 和工具基础接口
- [ ] T07：实现 WebSearchTool（Tavily 主体已完成，测试与验收未闭环）
- [ ] T08：实现来源标准化和去重（基础逻辑已完成，分层与完整测试未闭环）
- [ ] T09：实现 Writer Agent 和 Markdown 渲染
- [ ] T10：组装最小 LangGraph（三节点骨架已完成，尚不能输出报告）
- [ ] T11：提供 CLI 或同步调试 API（CLI 骨架已完成，尚不能输出 Markdown）
- [ ] T12：建立端到端验收测试

### 0.5 2026-08-01 仓库核验结果

| 核验项 | 结果 | 判断 |
|---|---|---|
| 本地健康检查 | `python -m app.main health` 通过 | 配置加载和规则 Planner 可用 |
| Python 版本 | base 为 3.12.7，`ai-search` Conda 环境为 3.12.13 | 版本满足 3.11+，但项目环境未安装声明依赖 |
| 测试清单 | 检出 37 个测试函数，其中 7 个位于当前未跟踪的搜索节点测试文件 | 测试数量已增长，但不能视为已通过 |
| pytest | base 环境因缺少 LangGraph 与 pytest-asyncio，在收集阶段失败 | T01/T05/T07/T10 不能完成验收 |
| Ruff | base 与 `ai-search` 环境均未安装 Ruff | 不能确认 lint/format 通过 |
| mypy | 7 个错误：6 个缺失依赖导入，1 个 `SourceDocument.url` 类型错误 | 质量门禁未通过 |
| 工作区 | `search_sources.py` 已修改，`test_search_sources_node.py` 未跟踪 | 视为正在开发的 T08/T10 工作，不覆盖或回退 |

---

## 1. 项目目标

### 1.1 一句话定义

AI 技术调研 Agent 是一个面向人工智能、大模型、Agent 和软件开发主题，能够自动理解任务、制定调研计划、检索可信资料、筛选重点信息，并生成带引用技术简报或深度报告的研究系统。

### 1.2 目标研究闭环

```text
用户输入
  → 请求规范化
  → 研究规划
  → 多来源检索
  → 内容抓取与处理
  → 去重与来源排序
  → 实时资料 + 历史知识库检索
  → 结构化报告生成
  → 引用与事实审核
  → 定向修改
  → 保存、评估和输出
```

### 1.3 核心设计原则

- [x] 使用结构化 Pydantic 数据模型定义核心输入与输出。
- [x] Planner 与图节点之间通过 Protocol 和 Runtime Context 解耦。
- [x] Planner 输出失败时具有有限重试和规则计划降级。
- [ ] LLM 只负责规划、判断、总结和写作；确定性处理全部下沉到普通 Python 模块。
- [ ] 所有外部来源真实、可追溯，模型不能自行编造 URL。
- [ ] 关键事实、数字、日期和版本号必须关联来源。
- [ ] 关键工作流状态可以持久化、恢复和重试。
- [ ] Reviewer 循环最多修订 2 次，禁止无限循环。
- [ ] 每份报告都有引用覆盖率、来源权威度、时间准确率等质量指标。
- [ ] 单任务具有来源数量、并发、Token、费用和总耗时预算。

### 1.4 第一版成功标准

- [ ] 输入任意合法主题后，系统可通过 LangGraph 完成完整研究链路。
- [ ] 自动生成 3–5 个相互补充的研究问题。
- [ ] 至少接入一个通用搜索工具、一个 GitHub 工具和一个论文工具。
- [ ] 重要事实可以追溯到工具实际返回的来源。
- [ ] 来源可以抓取、清洗、标准化、去重、评分和排序。
- [ ] 支持实时资料与历史知识库的混合检索。
- [ ] 输出结构化 JSON 和稳定 Markdown。
- [ ] 不合格报告可以被识别并定向修改，最多修改 2 次。
- [ ] 任务、来源、报告、评估和 Checkpoint 可以持久化。
- [ ] FastAPI 可以创建任务、查询状态、获取报告并通过 SSE 查看进度。
- [ ] 至少 5 个固定验收案例通过。

---

## 2. 产品场景与输出

### 2.1 每日 AI 技术简报

#### 功能目标

- [ ] 支持配置用户关注主题。
- [ ] 检索最近 24 小时的官方发布、GitHub 更新、论文和开发者动态。
- [ ] 将相对时间转换为明确的绝对时间边界。
- [ ] 对同一事件的不同报道进行聚类和去重。
- [ ] 按权威性、新颖度、技术影响和相关性评分。
- [ ] 只保留 5 条真正值得关注的信息。
- [ ] 每条简报包含标题、核心说明、标签、发布日期和原始链接。
- [ ] 支持定时运行、历史查询和失败重试。

#### 输出验收

- [ ] 每日稳定输出 5 条重点。
- [ ] 不重复报道同一事件。
- [ ] 每条信息都有日期和至少一个原始来源。
- [ ] 优先引用官方发布、原始论文或原仓库。

### 2.2 专题深度调研

#### 功能目标

- [x] 已定义 `deep_report` 研究类型。
- [x] Planner 已提供深度报告的规则降级问题模板。
- [ ] 自动形成执行摘要、技术背景、主要进展、开发影响、风险限制和应用建议。
- [ ] 按用户指定时间范围过滤资料。
- [ ] 重要结论关联 citation/source_id。
- [ ] 明确区分事实、来源观点和模型推断。
- [ ] 对来源冲突进行并列说明。

#### 输出验收

- [ ] 报告覆盖 Planner 的全部研究问题。
- [ ] 关键事实引用覆盖率不低于 90%。
- [ ] 官方资料、原论文、原仓库占引用来源的比例不低于 60%。
- [ ] 输出同时提供结构化 JSON 和 Markdown。

### 2.3 GitHub 项目分析

#### 功能目标

- [x] 已定义 `github_analysis` 研究类型。
- [x] Planner 已提供 GitHub 分析的规则降级问题模板。
- [ ] 读取仓库元数据和 README。
- [ ] 读取目录树并识别核心代码。
- [ ] 读取 Release、近期 Commit、Issue 和 Pull Request。
- [ ] 分析项目定位、架构、维护状态、优缺点和学习价值。
- [ ] 输出建议阅读顺序和核心文件清单。
- [ ] 使用结构化 GitHub API，而不是只抓取网页。

#### 输出验收

- [ ] README 描述可以通过目录和核心代码进行验证。
- [ ] 维护状态结论有 Commit、Release 或 Issue 证据。
- [ ] 工具保持只读，不执行仓库写操作。

### 2.4 技术学习指南

#### 功能目标

- [x] 已定义 `learning_guide` 研究类型。
- [x] Planner 已提供学习指南的规则降级问题模板。
- [ ] 输出前置知识、知识地图和推荐学习顺序。
- [ ] 整理官方资料、优秀开源项目和高质量教程。
- [ ] 设计实战任务和验收方式。
- [ ] 总结常见误区、适用边界和进一步学习方向。

#### 输出验收

- [ ] 学习路线具有明确先后顺序。
- [ ] 每个阶段至少提供一个官方来源和一个实践任务。
- [ ] 推荐资料链接均来自工具实际返回结果。

---

## 3. 第一版范围边界

### 3.1 第一版必须完成

- [ ] 任务规范化：主题、类型、绝对时间范围、语言、来源偏好和来源数量。
- [ ] 研究规划：自动拆分 3–5 个结构化子问题。
- [ ] 通用网络搜索：关键词、时间、域名和最大结果数。
- [ ] GitHub 调研：README、目录、Release、Commit 和核心文件。
- [ ] 论文检索：标题、摘要、作者、日期、论文标识和链接。
- [ ] 内容处理：抓取、清洗、日期解析、分块、哈希和去重。
- [ ] 来源评分：权威度、相关性、新鲜度、原创性和完整度。
- [ ] RAG：向量检索与关键词检索合并、去重和重排。
- [ ] 报告生成：简报、深度报告、学习指南和 GitHub 分析。
- [ ] 报告审核：引用、时间、重复、计划覆盖和事实支持。
- [ ] 持久化：任务、来源、报告、评估和 Checkpoint。
- [ ] API 与进度：FastAPI、任务状态和 SSE。
- [ ] 自动评估：质量分数和问题清单。

### 3.2 第一版暂不实现

- [x] 暂不开发复杂 React/Next.js 前端。
- [x] 暂不接入大量搜索 Provider。
- [x] 暂不实现无限递归 Deep Research。
- [x] 暂不实现自动图片生成。
- [x] 暂不实现 PDF 和 Word 多格式导出。
- [x] 暂不实现复杂多租户权限系统。
- [x] 暂不让 Agent 自动执行 GitHub 或外部系统写操作。
- [x] 暂不建设复杂分布式任务调度平台。

---

## 4. 目标系统架构

### 4.1 分层架构

| 层级 | 目标模块 | 主要职责 | 当前状态 |
|---|---|---|---|
| 入口层 | FastAPI / CLI | 接收请求、创建任务、查询状态和报告 | CLI 已有 health/plan/search/research 骨架；FastAPI 未实现 |
| 编排层 | LangGraph | State、Node、Edge、路由、重试和 Checkpoint | 已有 normalize/plan/search 三节点固定图；报告链路、路由和 Checkpoint 未实现 |
| 智能层 | Planner / Writer / Reviewer | 规划、写作、审核 | 仅 Planner 主体已实现 |
| 工具层 | Web / GitHub / Paper | 外部系统只读访问，统一返回 ToolResult | ToolResult/Protocol 与 Tavily Web 搜索主体已实现 |
| 处理层 | Services / RAG / Evaluation | 抓取、清洗、去重、评分、检索和评估 | URL/哈希基础处理暂内嵌在 Tool/Node；独立 Services、RAG、Evaluation 未实现 |
| 持久化层 | PostgreSQL / pgvector / Redis | 永久数据、向量、Checkpoint、缓存和任务锁 | 未实现 |

### 4.2 目标工作流

```text
START
  ↓
normalize_request
  ↓
create_research_plan
  ↓
search_sources
  ↓
process_sources
  ↓
rank_sources
  ↓
retrieve_knowledge
  ↓
write_report
  ↓
review_report
  ├─ 通过 → save_report → END
  └─ 不通过且修订次数 < 2
       ↓
     revise_report
       ↓
     review_report
```

### 4.3 当前已经形成的调用关系

```text
ResearchRequest
  ├─→ normalize_request
  └─→ PlannerAgent → create_plan 节点

TavilySearchTool → ToolResult[SourceDocument]
  └─→ search_sources → 基础 URL/正文去重 → processed_sources

app.main research
  └─→ normalize_request → create_plan → search_sources → END
```

### 4.4 依赖方向约束

- [x] `models` 保持纯数据契约，不依赖业务层。
- [x] Planner 依赖 Models 和 Config，不反向依赖 API。
- [x] create_plan 节点通过 Runtime Context 获取 Planner。
- [x] search_sources 节点通过 Runtime Context 获取搜索工具。
- [x] `graph/nodes → agents/tools` 的当前调用方向成立。
- [x] 禁止 `tools → graph`。
- [x] 禁止 `agents → api`。
- [ ] `api → graph`：API 只启动工作流，不手工串联业务函数。
- [ ] `graph/nodes → services/rag/repositories`。
- [ ] `repositories → infrastructure/database`。
- [ ] 禁止 `services → api`。
- [ ] 禁止在节点中直接堆叠 Prompt、SQL、网页解析和评分算法（当前去重与基础排序仍内嵌在搜索节点）。

---

## 5. 核心数据契约

### 5.1 ResearchRequest

- [x] `topic`
- [x] `research_type`
- [x] `time_start`
- [x] `time_end`
- [x] `source_preferences`
- [x] `max_sources`
- [x] `language`
- [x] 主题长度校验
- [x] 研究类型限制
- [x] 非法时间范围校验
- [x] 可变默认值使用 `default_factory`

### 5.2 ResearchQuestion 与 ResearchPlan

- [x] ResearchQuestion 包含 `question`。
- [x] ResearchQuestion 包含 `goal`。
- [x] ResearchQuestion 包含 `preferred_sources`。
- [x] ResearchPlan 限制为 3–5 个问题。
- [x] Planner 会清理和去重来源类型。
- [x] Planner 会过滤近似重复问题。

### 5.3 SourceDocument

- [x] `source_id`
- [x] `title`
- [x] `url`
- [x] `source_type`
- [x] `published_at`
- [x] `summary`
- [x] `clean_content`
- [x] `content_hash`
- [x] `metadata`
- [ ] `canonical_url`
- [ ] `publisher`
- [ ] `retrieved_at`
- [ ] `chunks`
- [ ] 来源质量评分字段
- [ ] 来源关联的研究问题 ID

### 5.4 ReportSchema

- [x] Citation 模型。
- [x] ReportSection 模型。
- [x] ReportSchema 模型。
- [x] 标题和摘要字段。
- [x] 结构化章节。
- [x] 关键发现。
- [x] 引用列表。
- [x] 置信度范围校验。
- [ ] 校验 `ReportSection.citation_ids` 必须存在于报告引用列表。
- [ ] 校验 Citation 的 `source_id` 必须来自检索上下文。
- [ ] 增加报告限制、警告、成本和质量分字段。
- [ ] 增加 ReviewResult 和 ReviewIssue 模型。

### 5.5 ResearchState

- [x] `thread_id`
- [x] `task_id`
- [x] 主题、类型、语言和时间范围。
- [x] 来源偏好和最大来源数量。
- [x] 研究问题列表。
- [x] 原始来源和处理后来源。
- [x] 草稿报告和最终报告。
- [x] 修订次数、状态和错误列表。
- [x] Token 用量和估算成本。
- [ ] 将大型正文改为数据库 ID 引用。
- [ ] 增加 `ranked_source_ids`。
- [ ] 增加 `retrieved_context`。
- [ ] 增加 `review_result`。
- [ ] 增加 `quality_score` 和未解决警告。
- [ ] 增加 `state_schema_version`。
- [ ] 验证 State 可以被 Checkpointer 完整序列化。

---

## 6. 迭代 0：项目环境与质量基线

### 6.1 T01：初始化项目和质量工具

- [ ] **父任务完成**

#### 已完成

- [x] 初始化 Git 仓库。
- [x] 创建 Python 包目录。
- [x] 创建 `pyproject.toml`。
- [x] 配置项目基础依赖。
- [x] 配置 pytest 测试目录和 marker。
- [x] 配置 Ruff 规则。
- [x] 配置 mypy 和 Pydantic 插件。
- [x] 配置 `.gitignore` 忽略 `.env`、缓存和构建产物。
- [x] 创建 `.env.example`。

#### 待完成

- [ ] 安装与 `pyproject.toml` 一致的项目依赖和开发依赖。
- [x] 已确认 `ai-search` Conda 环境使用 Python 3.12.13（依赖尚未安装）。
- [ ] 创建 `.pre-commit-config.yaml`。
- [ ] 补充 README：定位、安装、配置、运行和测试方式。
- [ ] 编写可用 Dockerfile。
- [ ] 创建 `docker-compose.yml`。
- [ ] 配置 PostgreSQL、Redis 和 pgvector 服务。
- [ ] 增加 FastAPI 健康检查。
- [ ] 增加 CI，运行 pytest、Ruff 和 mypy。
- [ ] 清理全部代码格式和未使用导入问题。

#### 当前质量问题

- [ ] 全量 pytest 可以在真实依赖环境中完成收集。
- [ ] 全量 pytest 通过。
- [ ] `ruff check app tests` 通过。
- [ ] `ruff format --check app tests` 通过。
- [ ] `mypy app` 在不忽略外部导入的情况下通过。
- [ ] 工作区无非预期未提交修改。

#### 验收标准

- [ ] 新环境执行一次安装命令后可以运行全部测试。
- [ ] FastAPI 健康检查可启动。
- [ ] PostgreSQL 和 Redis 可通过 Docker Compose 连接。
- [ ] pytest、Ruff、mypy 和 pre-commit 全部通过。

### 6.2 T02：配置和环境变量

- [x] **父任务完成**

#### 已完成

- [x] 使用 Pydantic Settings 管理配置。
- [x] 支持 `.env` 和系统环境变量。
- [x] 应用名、环境、调试、日志和默认语言配置。
- [x] Planner 问题数量限制。
- [x] 来源数量、并发和任务超时配置。
- [x] Reviewer 最大修订次数配置。
- [x] DeepSeek Provider、模型、温度、超时和重试配置。
- [x] Web Search Provider 的预留配置。
- [x] GitHub、论文、LangSmith、PostgreSQL 和 Redis 示例配置。
- [x] API Key 使用 `SecretStr`。
- [x] 最小问题数不能大于最大问题数。
- [x] 配置单元测试通过。

#### 后续增强

- [ ] 将默认研究类型约束为 `ResearchType`，而不是普通字符串。
- [ ] 将 normalize_request 的默认值统一改为从 Settings 读取。
- [ ] 为数据库、Redis、GitHub 和论文工具补充正式 Settings 字段。
- [ ] 增加启动时配置完整性检查。
- [ ] 避免日志输出密钥、Token 和敏感正文。

---

## 7. 迭代 1：最小研究闭环

### 7.1 T03：第一阶段数据模型与 ResearchState

- [x] **父任务完成**

#### 已完成

- [x] ResearchRequest。
- [x] ResearchQuestion。
- [x] ResearchPlan。
- [x] SourceDocument 第一阶段模型。
- [x] Citation。
- [x] ReportSection。
- [x] ReportSchema。
- [x] ResearchState 第一阶段结构。
- [x] 研究请求和研究问题基础测试。

#### 后续增强

- [ ] 增加 SourceDocument 独立模型测试。
- [ ] 增加 Citation、ReportSection、ReportSchema 独立测试。
- [ ] 增加模型序列化、反序列化和 JSON Schema 测试。
- [ ] 增加引用 ID 与来源 ID 的交叉校验。

### 7.2 T04：请求规范化

- [ ] **父任务完成**

#### 已完成

- [x] 去除主题首尾空格。
- [x] 使用 ResearchRequest 校验。
- [x] 支持 ISO 日期字符串转 `date`。
- [x] 检查开始日期不能晚于结束日期。
- [x] 设置默认研究类型。
- [x] 设置默认语言。
- [x] 设置默认最大来源数量。
- [x] 只返回本节点负责更新的字段。
- [x] 更新状态为 `request_normalized`。
- [x] 正常、默认值、非法范围和非法格式测试通过。

#### 待完成

- [ ] 将“最近三个月”转换为绝对开始和结束日期。
- [ ] 将“过去 24 小时”转换为明确时间边界。
- [ ] 从自然语言中识别研究类型。
- [ ] 从自然语言中识别来源偏好。
- [ ] 从自然语言中识别报告长度和最大来源数。
- [ ] 复杂输入可选使用 LLM 解析，并有确定性降级。
- [ ] 将默认值改为从统一 Settings 读取。
- [ ] 明确无时区日期和带时区时间的处理规则。

#### 验收标准

- [ ] 自然语言请求可稳定转换为 ResearchRequest。
- [ ] 所有相对时间在节点完成后均为绝对时间。
- [ ] 空主题、非法研究类型和非法时间范围给出清晰错误。
- [ ] 节点不直接修改原 State。

### 7.3 T05：Planner Agent

- [ ] **父任务完成**

#### 已完成

- [x] 定义 PlannerProtocol。
- [x] 定义 StructuredPlannerModel Protocol。
- [x] 定义 PlannerExecution。
- [x] 定义 PlannerOutputError。
- [x] 使用 ChatPromptTemplate 构造 Planner Prompt。
- [x] 限定 Planner 只规划，不搜索、不回答、不写报告。
- [x] 使用 ResearchPlan 结构化输出。
- [x] 限制问题数量为 3–5。
- [x] 每个问题包含 question、goal、preferred_sources。
- [x] 清理来源类型的空格和大小写。
- [x] 对来源类型保持顺序去重。
- [x] 使用确定性字符串相似度过滤近似重复问题。
- [x] 对模型输出进行有限重试。
- [x] 连续失败后使用规则计划降级。
- [x] 为四种研究类型提供规则计划。
- [x] 用户来源偏好会合并到规则计划。
- [x] 提供 DeepSeek Planner 构建函数。
- [x] 缺少 DeepSeek API Key 时给出明确错误。
- [x] 实现 create_plan LangGraph 节点。
- [x] 使用 Runtime Context 注入 Planner。
- [x] 节点返回增量更新，不直接修改原 State。
- [x] Planner 单元测试和节点测试文件已创建。

#### 待完成

- [ ] 修复 Planner fallback 警告文本的中英文逗号断言差异。
- [ ] 在安装真实 LangChain/LangGraph 依赖的环境中运行测试。
- [ ] 确认异步测试插件版本符合 `pyproject.toml`。
- [ ] Ruff 和 mypy 完整通过。
- [ ] 使用真实 DeepSeek API 完成一次受控冒烟测试。
- [ ] 将 Planner 与编译后的最小主图连接。
- [ ] 记录模型 Token、耗时和估算成本。
- [ ] 区分“模型输出非法”和“网络/鉴权失败”的告警类型。

#### 验收标准

- [ ] 合法请求稳定获得 3–5 个结构化问题。
- [ ] 不生成同义或近似重复问题。
- [ ] Planner 不直接回答研究主题。
- [ ] 非法输出可以重试并降级。
- [ ] 节点只更新 research_questions、status 和必要 warnings/errors。
- [ ] Planner 相关 pytest、Ruff 和 mypy 全部通过。

### 7.4 T06：统一工具接口

- [x] **父任务完成**

#### 已完成

- [x] 定义泛型 ToolResult。
- [x] 包含 tool_name。
- [x] 包含 query。
- [x] 包含 success。
- [x] 包含 items。
- [x] 包含 error。
- [x] 包含 duration_ms。
- [x] 包含 cached。
- [x] 成功结果不能携带 error。
- [x] 失败结果必须携带 error。
- [x] 耗时不能为负数。
- [x] 定义 ToolProtocol。
- [x] Tool 层不依赖 LangGraph。
- [x] 5 个 ToolResult 单元测试通过。

#### 后续增强

- [ ] 增加统一错误 code 和是否可重试字段。
- [ ] 统一整数毫秒或浮点毫秒的规范。
- [ ] 评估 ToolProtocol 是否需要统一 options/context 参数。
- [ ] 为工具结果增加 Provider、重试次数和原始响应追踪字段。

### 7.5 T07：WebSearchTool

- [ ] **父任务完成**

#### 开发清单

- [x] 选择 Tavily 作为第一阶段搜索 Provider。
- [x] 创建等价实现 `app/tools/search.py`。
- [x] 定义 `TavilySearchParams`，并将条目统一转换为 `SourceDocument`。
- [x] 支持关键词查询。
- [x] 支持开始日期和结束日期。
- [x] 支持域名白名单和黑名单。
- [x] 支持最大结果数量。
- [x] 返回标题、URL、摘要和可能的发布时间。
- [x] 使用统一 ToolResult。
- [x] 配置请求超时。
- [x] 配置有限重试和指数退避。
- [x] 处理空结果。
- [x] 处理鉴权失败、限流、超时和 Provider 异常。
- [ ] 记录 duration_ms、cached 和重试次数。
- [x] 搜索阶段不主动请求完整正文。
- [ ] 使用 Mock 编写稳定单元测试。
- [ ] 增加可选的真实 Provider 集成测试，并标记为 external。

#### 验收标准

- [x] 代码支持按关键词、日期、域名和数量进行搜索。
- [x] 正常结果转换为统一模型。
- [x] 空结果返回 success=True 和空 items。
- [x] 超时或 Provider 失败返回稳定错误文本。
- [x] 错误结果不包含 API Key 或原始敏感响应。

### 7.6 T08：来源标准化与去重

- [ ] **父任务完成**

#### 开发清单

- [ ] 创建 `app/services/source_normalizer.py`。
- [ ] 创建 `app/services/source_deduplicator.py`。
- [x] 统一 URL scheme、host、path、默认端口和尾部斜杠。
- [x] 移除 `utm_*` 等常见跟踪参数。
- [x] 在 metadata 中生成 canonical_url（模型正式字段尚未增加）。
- [x] 将搜索结果转换为 SourceDocument。
- [x] 为缺失标题生成安全回退值。
- [x] 正确处理缺失或不确定发布日期。
- [x] 计算搜索内容 content_hash（完整正文抓取尚未实现）。
- [x] 按 canonical_url 去重。
- [x] 按 content_hash 去重。
- [ ] 按标题相似度辅助去重。
- [x] 保留来源与研究问题之间的关系。
- [x] 去重过程按 Provider 分数确定性排序，同分保持输入顺序。
- [ ] 记录输入数量、去重数量和保留数量。
- [ ] 增加 URL、哈希、缺失字段和稳定顺序测试。

#### 验收标准

- [x] 代码可将相同 URL 的不同跟踪参数版本规范为同一来源。
- [x] 代码可将相同 content_hash 的不同 URL 识别为重复来源。
- [x] Web 来源根据 canonical_url 生成稳定 source_id。
- [x] 去重合并研究问题和研究目标关联信息。

### 7.7 T09：Writer Agent 与 Markdown 渲染

- [ ] **父任务完成**

#### 开发清单

- [ ] 创建 `app/agents/writer.py`。
- [ ] 创建 `app/graph/nodes/write_report.py`。
- [ ] 创建 `app/services/report_renderer.py`。
- [ ] 为四种 research_type 定义报告模板。
- [ ] Writer 只使用传入的来源和上下文。
- [ ] Writer 输出严格符合 ReportSchema。
- [ ] 每个关键结论关联 citation_id。
- [ ] Citation 的 source_id 必须来自实际来源。
- [ ] 禁止 Writer 自行编造 URL。
- [ ] 明确区分事实、来源观点和模型推断。
- [ ] 来源冲突时并列说明。
- [ ] 对非法结构输出进行一次定向修复或重试。
- [ ] 将 ReportSchema 稳定渲染为 Markdown。
- [ ] Markdown 章节顺序不依赖模型自由发挥。
- [ ] 对特殊字符、长链接、空章节和无来源情况进行测试。
- [ ] 增加 Writer Mock 测试和 Renderer 确定性测试。

#### 验收标准

- [ ] 相同 ReportSchema 多次渲染得到相同 Markdown。
- [ ] 报告中的 URL 全部来自实际 SourceDocument。
- [ ] 无来源支持的关键结论不会被静默输出为事实。
- [ ] 报告结构符合对应研究类型模板。

### 7.8 T10：最小 LangGraph

- [ ] **父任务完成**

#### 第一阶段主图

```text
START
  → normalize_request
  → create_plan
  → search_sources
  → process_sources
  → write_report
  → END
```

#### 开发清单

- [x] 创建等价工作流构建模块 `app/graph/workflow.py`。
- [x] 定义 StateGraph。
- [x] 注册 normalize_request。
- [x] 注册 create_plan。
- [x] 注册 search_sources。
- [ ] 注册 process_sources。
- [ ] 注册 write_report。
- [ ] 注册固定边。
- [x] 编译当前三节点工作流。
- [ ] 创建统一初始 State 工厂。
- [x] 通过 Context 注入 Planner 和 Tool。
- [x] 当前三个节点只返回自己负责的增量字段。
- [x] 单个问题搜索失败时保留其他结果并返回警告；全部失败时返回失败状态。
- [ ] 测试节点执行顺序。
- [ ] 测试 State 增量更新。
- [ ] 测试连续多次运行无状态污染。
- [ ] 测试搜索超时和空结果（测试已编写但尚未在完整依赖环境通过）。
- [ ] 测试 Planner fallback 后仍能继续执行。

#### 验收标准

- [ ] 完整链路由 LangGraph 执行。
- [ ] 输入主题可生成包含真实来源的 Markdown。
- [ ] 连续运行至少两次不存在跨任务状态污染。
- [x] 搜索节点代码可对单问题失败降级，并对全部失败给出明确状态。

### 7.9 T11：CLI 或同步调试 API

- [ ] **父任务完成**

#### 推荐先实现 CLI

- [x] 创建等价命令入口 `python -m app.main`。
- [x] 输入研究主题。
- [x] 选择研究类型。
- [ ] 可选指定开始和结束时间。
- [ ] 可选指定来源偏好和最大来源数。
- [x] 构造初始 State。
- [x] `research` 子命令调用编译后的 LangGraph。
- [x] health/plan/search/research 输出结构化 JSON。
- [ ] 输出 Markdown 文件或标准输出。
- [ ] 显示清晰失败信息。
- [x] 当前日志和 ToolResult 不显示 API Key。

#### 同步调试 API

- [ ] 创建 FastAPI 应用。
- [ ] 增加健康检查。
- [ ] 增加开发环境同步研究接口。
- [ ] 返回统一错误结构。
- [ ] 在正式异步任务接口完成后保留或移除调试接口。

#### 验收标准

- [ ] 用户无需直接调用 Python 函数即可运行最小研究任务。
- [ ] 输入一个主题后能获得 Markdown 报告。
- [ ] 失败时退出码或 HTTP 状态明确。

### 7.10 T12：端到端验收测试

- [ ] **父任务完成**

#### 开发清单

- [ ] 创建 `tests/integration/`。
- [ ] 固定测试主题。
- [ ] Mock Planner 模型。
- [ ] Mock Web Search Provider。
- [ ] 验证生成 3–5 个问题。
- [ ] 验证至少得到 5 个来源。
- [ ] 验证重复 URL 被删除。
- [ ] 验证相同正文被删除。
- [ ] 验证报告包含真实引用。
- [ ] 验证 Markdown 结构稳定。
- [ ] 验证整个流程由 LangGraph 执行。
- [ ] 验证连续运行无状态污染。
- [ ] 验证搜索超时可降级。
- [ ] 验证 Planner 非法输出可降级。
- [ ] 验证无来源时给出明确限制说明。

#### 迭代 1 最终验收

- [ ] 输入任意 AI 技术主题后，自动生成 3 个结构化问题。
- [ ] 通过一个 WebSearchTool 找到至少 5 个来源。
- [ ] 可以识别相同 URL 或相同正文的重复来源。
- [ ] Writer 只能引用工具实际返回的 source_id 和 URL。
- [ ] 输出结构稳定的 Markdown 报告。
- [ ] 整个链路通过 LangGraph 执行。
- [ ] 至少一个失败场景可以正确降级。
- [ ] pytest、Ruff 和 mypy 全部通过。

---

## 8. 迭代 2：数据库、Checkpoint 与 API 工程化

### 8.1 数据库与迁移

- [ ] 添加 SQLAlchemy 和 PostgreSQL 驱动。
- [ ] 配置 Alembic。
- [ ] 创建数据库连接和 Session 管理。
- [ ] 建立 `research_tasks` 表。
- [ ] 建立 `research_plans` 表。
- [ ] 建立 `sources` 表。
- [ ] 建立 `source_chunks` 表。
- [ ] 建立 `reports` 表。
- [ ] 建立 `report_citations` 表。
- [ ] 建立 `evaluation_results` 表。
- [ ] 为 canonical_url 建立唯一索引。
- [ ] 为 task_id + revision 建立唯一约束。
- [ ] 迁移可在空库执行。
- [ ] 迁移可在已有库升级和回滚。

### 8.2 Repository 层

- [ ] 创建 TaskRepository。
- [ ] 创建 PlanRepository。
- [ ] 创建 SourceRepository。
- [ ] 创建 ReportRepository。
- [ ] 创建 EvaluationRepository。
- [ ] Repository 隔离 SQLAlchemy 细节。
- [ ] 写入操作使用事务。
- [ ] 重试不重复创建相同报告版本。
- [ ] 节点保存数据成功后再推进 State。
- [ ] 使用测试数据库覆盖唯一约束和事务回滚。

### 8.3 LangGraph Checkpoint

- [ ] 接入 PostgreSQL Checkpointer。
- [ ] 创建任务时生成 thread_id。
- [ ] graph 调用通过 configurable.thread_id 关联状态。
- [ ] 服务重启后可查询保存状态。
- [ ] 支持从允许的节点恢复或重试。
- [ ] 限制 Checkpoint 大小。
- [ ] 大型正文只保存数据库 ID，不直接放入 State。
- [ ] 测试中断恢复和幂等。

### 8.4 FastAPI 异步任务接口

- [ ] `POST /api/research/tasks`
- [ ] `GET /api/research/tasks/{task_id}`
- [ ] `POST /api/research/tasks/{task_id}/retry`
- [ ] `GET /api/reports/{report_id}`
- [ ] `GET /api/reports/{report_id}.md`
- [ ] `GET /api/sources/{source_id}`
- [ ] 统一请求校验和错误码。
- [ ] API 不同步阻塞等待完整研究任务。
- [ ] 明确任务状态机。
- [ ] 增加 OpenAPI 示例。

### 8.5 SSE 事件

- [ ] `GET /api/research/tasks/{task_id}/events`
- [ ] 定义 progress 事件。
- [ ] 定义 source 事件。
- [ ] 定义 warning 事件。
- [ ] 定义 completed 事件。
- [ ] 每个事件包含 task_id、timestamp 和 code。
- [ ] 事件 ID 单调递增。
- [ ] 支持断线重连和 Last-Event-ID。
- [ ] 显示文本与内部 code 分离。
- [ ] 测试事件顺序和重连。

### 8.6 Redis

- [ ] 搜索结果缓存。
- [ ] 抓取结果短期缓存。
- [ ] URL 去重集合。
- [ ] 任务锁。
- [ ] API 限流。
- [ ] 短期进度事件。
- [ ] 缓存键包含 query、时间范围、域名和结果数量。
- [ ] 缓存具有合理 TTL。
- [ ] 任务完成或失败后释放锁。
- [ ] 测试缓存命中和锁超时。

### 8.7 日志、Trace 与成本

- [ ] 结构化日志包含 task_id 和 thread_id。
- [ ] 记录节点开始、结束和耗时。
- [ ] 记录工具查询、结果数、缓存、失败和重试。
- [ ] 记录模型 Provider、模型、Token、耗时和估算成本。
- [ ] 记录来源抓取成功率和去重数量。
- [ ] 记录 Reviewer 问题、修订次数和未解决警告。
- [ ] 接入 LangSmith 或等价 Trace。
- [ ] 日志不输出 API Key、Token 和敏感正文。

### 8.8 迭代 2 验收

- [ ] 可以创建异步研究任务。
- [ ] 可以实时查看节点进度。
- [ ] 可以查询任务、来源和报告。
- [ ] 服务重启后可以查询或恢复状态。
- [ ] 相同搜索请求再次执行可命中缓存。
- [ ] 重复请求不会重复创建相同数据。

---

## 9. 迭代 3：多来源、抓取与 RAG

### 9.1 GitHubResearchTool

- [ ] 仓库 URL 与 owner/repo 解析。
- [ ] 仓库元数据读取。
- [ ] README 读取。
- [ ] 目录树读取。
- [ ] Release 读取。
- [ ] 近期 Commit 读取。
- [ ] Issue 搜索。
- [ ] Pull Request 搜索。
- [ ] 指定核心文件读取。
- [ ] 速率限制和鉴权处理。
- [ ] 大文件截断和二进制文件拒绝。
- [ ] 统一 ToolResult。
- [ ] Mock 和集成测试。

### 9.2 PaperSearchTool

- [ ] 选择 arXiv、OpenAlex 或 Semantic Scholar。
- [ ] 关键词搜索。
- [ ] 时间范围过滤。
- [ ] 返回标题、作者、摘要、日期、论文标识和原始链接。
- [ ] 区分预印本、正式发表和二手解读。
- [ ] 处理重复版本和论文标识。
- [ ] 统一 ToolResult。
- [ ] Mock 和集成测试。

### 9.3 ContentFetcher

- [ ] HTTP 下载和重定向。
- [ ] 请求超时和有限重试。
- [ ] User-Agent 和基础请求头。
- [ ] 最大响应体限制。
- [ ] Content-Type 检查。
- [ ] 拒绝明显二进制和异常文件。
- [ ] 编码识别。
- [ ] HTML 正文抽取。
- [ ] 标题、作者和发布时间提取。
- [ ] robots、登录墙和抓取失败原因记录。
- [ ] Prompt Injection 初步模式标记。
- [ ] 单元和故障注入测试。

### 9.4 内容清洗与分块

- [ ] 删除脚本、导航、广告和无关页脚。
- [ ] 统一空白、换行和特殊字符。
- [ ] 保留标题层级和章节路径。
- [ ] 官方文档按标题切分。
- [ ] README 按 Markdown 标题切分。
- [ ] Release/Commit 按单条事件切分。
- [ ] 论文按摘要、方法、实验和结论切分。
- [ ] 新闻和博客按自然段与小标题切分。
- [ ] 每个 chunk 携带 source_id、标题、URL、日期和章节。
- [ ] 计算 token_count。
- [ ] 批量处理并避免超大内存占用。

### 9.5 Embedding 与 pgvector

- [ ] 选择 Embedding Provider 和向量维度。
- [ ] 批量生成向量。
- [ ] 失败批次可重试。
- [ ] source_chunks.embedding 使用 pgvector。
- [ ] 建立向量索引。
- [ ] 模型或维度变化具有迁移策略。
- [ ] 避免重复生成相同 content_hash 的向量。

### 9.6 混合检索

- [ ] PostgreSQL 全文检索。
- [ ] pgvector 向量检索。
- [ ] 为每个研究问题分别检索。
- [ ] 使用 Reciprocal Rank Fusion 合并排名。
- [ ] 合并后按 source_id/chunk 去重。
- [ ] 结合来源分数、相关性和时间进行重排。
- [ ] 输出 Top K 上下文。
- [ ] 设置输入 Token 预算。
- [ ] Writer 不能引用未进入上下文的来源。
- [ ] 测试关键词命中、语义命中、去重和裁剪。

### 9.7 来源评分

```text
source_score =
    0.30 × authority
  + 0.25 × relevance
  + 0.20 × freshness
  + 0.15 × originality
  + 0.10 × completeness
```

- [ ] authority：域名、官方组织、论文数据库和仓库所有者。
- [ ] relevance：关键词、向量相似度和问题覆盖。
- [ ] freshness：用户时间范围和时间衰减。
- [ ] originality：原始发布、原论文和原仓库优先。
- [ ] completeness：正文、日期、作者和上下文完整度。
- [ ] 超出时间范围的来源降权或过滤。
- [ ] 无正文、重复转载和低可信来源降权。
- [ ] 来源评分过程可解释和可测试。

### 9.8 迭代 3 验收

- [ ] 可分析 GitHub 仓库。
- [ ] 可检索论文元数据。
- [ ] 可抓取和清洗网页正文。
- [ ] 可保存来源分块和向量。
- [ ] 可执行关键词 + 向量混合检索。
- [ ] 报告优先引用官方或原始来源。
- [ ] 重复运行不重复保存相同来源。

---

## 10. 迭代 4：Reviewer、引用验证与自动评估

### 10.1 规则引用检查

- [ ] 关键事实必须包含 citation_id。
- [ ] citation_id 必须存在于报告引用列表。
- [ ] source_id 必须存在于已检索来源。
- [ ] URL 必须来自 SourceDocument。
- [ ] 日期、数字和版本号优先检查引用。
- [ ] 统计引用覆盖率。
- [ ] 无引用结论生成结构化 issue。

### 10.2 时间与计划覆盖检查

- [ ] 来源发布时间是否在用户范围内。
- [ ] 区分发布时间和事件发生时间。
- [ ] 过期来源生成 outdated_source issue。
- [ ] 每个研究问题是否被报告回答。
- [ ] 计算计划完成率。
- [ ] 所有资料不足时明确说明限制。

### 10.3 Reviewer Agent

- [ ] 创建 `app/agents/reviewer.py`。
- [ ] 创建 ReviewIssue。
- [ ] 创建 ReviewResult。
- [ ] 规则检查先于 LLM Reviewer。
- [ ] 检查引用是否真正支持结论。
- [ ] 检查是否遗漏关键背景。
- [ ] 检查事实与推测是否混淆。
- [ ] 检查章节重复。
- [ ] 每个 issue 包含 type、location、message、severity 和修复建议。
- [ ] Reviewer 只审核，不重写完整报告。

### 10.4 revise_report 与条件路由

- [ ] 创建 revise_report 节点。
- [ ] 只修改 Reviewer 指出的具体问题。
- [ ] 创建 `route_after_review`。
- [ ] 审核通过时进入 save_report。
- [ ] 审核不通过且次数不足时进入 revise_report。
- [ ] 最大修订次数为 2。
- [ ] 达到上限后保存当前最佳版本并记录警告。
- [ ] 测试通过、失败、达到上限和 Reviewer 异常。

### 10.5 自动评估

```text
quality_score =
    0.25 × citation_coverage
  + 0.20 × source_authority
  + 0.15 × freshness_accuracy
  + 0.15 × plan_completion
  + 0.15 × citation_consistency
  + 0.10 × non_duplication
```

- [ ] 引用覆盖率目标 ≥ 90%。
- [ ] 来源权威度目标 ≥ 60%。
- [ ] 时间准确率目标 ≥ 95%。
- [ ] 计划完成率目标 = 100%。
- [ ] 引用一致性目标 ≥ 85%。
- [ ] 非重复度目标 ≥ 90%。
- [ ] 保存每项指标、综合分和详情。
- [ ] 建立固定离线评估数据集。

### 10.6 迭代 4 验收

- [ ] 无引用结论可以被识别。
- [ ] 过期来源可以被标记。
- [ ] 不支持结论的引用可以被识别。
- [ ] 不合格报告可以定向修改。
- [ ] 最多修改 2 次后结束。
- [ ] 每份报告都有质量分和问题清单。

---

## 11. 迭代 5：每日简报产品化

### 11.1 用户配置

- [ ] 用户关注主题。
- [ ] 来源偏好。
- [ ] 输出语言。
- [ ] 每日条数，第一版固定或默认 5。
- [ ] 定时执行时间。
- [ ] 时区。
- [ ] 邮件或页面展示偏好。

### 11.2 定时运行

- [ ] 建立每日任务入口。
- [ ] 生成明确的最近 24 小时时间范围。
- [ ] 防止同一日期重复运行。
- [ ] 支持手动补跑。
- [ ] 任务失败可重试。
- [ ] 记录每次运行状态和报告 ID。

### 11.3 事件聚类与重要性评分

- [ ] canonical_url 去重。
- [ ] content_hash 去重。
- [ ] 标题相似度聚类。
- [ ] 语义相似度聚类。
- [ ] 同一事件优先引用原始来源。
- [ ] 评分考虑权威性、新颖度、技术影响和用户相关性。
- [ ] 选择 Top 5。
- [ ] 避免五条信息来自同一子主题。

### 11.4 展示与发送

- [ ] 稳定 Markdown 简报模板。
- [ ] 简单 HTML 页面。
- [ ] 邮件渲染。
- [ ] 邮件发送。
- [ ] 发送失败重试。
- [ ] 历史简报查询。
- [ ] 重复发送保护。

### 11.5 迭代 5 验收

- [ ] 每天可生成 5 条重点 AI 技术简报。
- [ ] 每条包含日期和原始链接。
- [ ] 不重复报道同一事件。
- [ ] 发送失败可以重试且不会重复发送成功邮件。
- [ ] 可以查询历史简报。

---

## 12. 安全性、稳定性与预算

### 12.1 密钥与配置安全

- [x] `.env` 已被 `.gitignore` 忽略。
- [x] DeepSeek API Key 使用 SecretStr。
- [ ] CI 检查密钥误提交。
- [ ] 日志脱敏。
- [ ] API 响应不返回内部密钥或堆栈。

### 12.2 外部内容与 Prompt Injection

- [ ] 所有网页、Issue、论文和 README 均视为不可信输入。
- [ ] 系统提示词明确外部资料不能成为 Agent 指令。
- [ ] 外部资料使用清晰分隔符包裹。
- [ ] 典型 Prompt Injection 片段被标记或降权。
- [ ] 外部内容不能触发写操作。
- [ ] 来源 URL 必须来自工具实际返回。
- [ ] 增加 Prompt Injection 故障注入测试。

### 12.3 超时、重试和降级

- [x] Planner 具有有限输出重试。
- [x] Planner 具有规则计划降级。
- [x] 当前唯一 Web 外部工具 Tavily 具有超时。
- [x] 当前唯一 Web 外部工具 Tavily 具有有限重试和指数退避。
- [ ] 一个工具失败不阻断其他工具。
- [ ] 抓取失败可保留搜索摘要并降低完整度。
- [ ] Writer 输出非法时定向重试一次。
- [ ] Reviewer 失败时使用规则评估并带警告完成。
- [ ] 数据库失败时回滚并不推进节点。
- [ ] 任务超预算时使用已有资料生成受限报告。

### 12.4 资源预算

- [x] 已配置 Planner 最小和最大问题数。
- [x] 已配置最大来源数量。
- [x] 已配置最大并发数。
- [x] 已配置任务超时。
- [x] 已配置最大修订次数。
- [x] 已通过 `WEB_SEARCH_MAX_RESULTS` 配置每个问题最大搜索结果数。
- [ ] 最大抓取页面数。
- [ ] 最大响应体。
- [ ] 最大网页正文长度。
- [ ] 单任务 Token 预算。
- [ ] 单任务费用预算。
- [ ] 上下文 Token 裁剪。
- [ ] 大文件分块或拒绝。

---

## 13. 测试计划

### 13.1 单元测试

- [x] Settings 默认值和问题数量范围。
- [x] ResearchRequest 正常创建。
- [x] 过短主题拒绝。
- [x] 非法时间范围拒绝。
- [x] ResearchQuestion 创建。
- [x] normalize_request 正常处理。
- [x] normalize_request 默认值。
- [x] normalize_request 非法日期。
- [x] ToolResult 成功和失败状态。
- [x] ToolResult 错误一致性。
- [x] ToolResult 负耗时拒绝。
- [x] Planner 正常输出、重试、去重和 fallback 测试已编写。
- [x] create_plan 节点测试已编写。
- [ ] 修复 Planner warning 文本断言。
- [ ] SourceDocument 测试。
- [ ] ReportSchema 测试。
- [ ] URL 标准化测试。
- [ ] 内容哈希和去重测试（测试已编写但尚未在完整依赖环境通过）。
- [ ] 来源评分测试。
- [ ] Markdown Renderer 测试。
- [ ] Reviewer 路由测试。
- [ ] 引用覆盖率测试。

### 13.2 工具集成测试

- [ ] Web Search Provider。
- [ ] GitHub API。
- [ ] Paper API。
- [ ] ContentFetcher。
- [ ] Redis 缓存。
- [ ] 外部测试使用 marker 与普通单元测试隔离。

### 13.3 数据库测试

- [ ] Alembic 迁移。
- [ ] Repository CRUD。
- [ ] 唯一约束。
- [ ] 事务回滚。
- [ ] Checkpointer。
- [ ] 服务重启恢复。

### 13.4 图工作流测试

- [ ] 节点顺序。
- [ ] State 增量更新。
- [ ] 条件路由。
- [ ] 失败降级。
- [ ] 最大修订次数。
- [ ] Checkpoint 恢复。
- [ ] 连续多次运行无状态污染。

### 13.5 端到端测试

- [ ] CLI/API 输入到最终报告。
- [ ] 真实引用。
- [ ] Markdown 输出。
- [ ] 任务状态和 SSE。
- [ ] 持久化与历史查询。
- [ ] 固定验收数据集。

### 13.6 故障注入测试

- [ ] 搜索服务超时。
- [ ] 一个搜索工具失败。
- [ ] Planner 返回非法 JSON。
- [ ] Writer 返回非法结构。
- [ ] 数据库连接中断。
- [ ] Reviewer 连续不通过。
- [ ] 所有来源超出时间范围。
- [ ] 网页包含 Prompt Injection。
- [ ] 任务超出 Token 或费用预算。

---

## 14. 五个固定验收案例

### 案例 A：GPT Researcher 项目分析

- [ ] 读取 README 和目录树。
- [ ] 识别核心文件和主要架构。
- [ ] 分析维护状态和学习价值。
- [ ] 结论有 GitHub 来源。

### 案例 B：LangGraph 最近一个月更新

- [ ] 正确计算最近一个月的绝对时间范围。
- [ ] 优先引用官方 Release 和官方文档。
- [ ] 日期判断准确。
- [ ] 输出带引用深度报告。

### 案例 C：MCP 对 Agent 开发的作用

- [ ] 覆盖官方规范、架构、应用场景和限制。
- [ ] 区分官方定义和社区观点。
- [ ] 重要结论有来源支持。

### 案例 D：最近 24 小时 AI 技术简报

- [ ] 绝对时间边界正确。
- [ ] 只输出 5 条。
- [ ] 同一事件完成聚类。
- [ ] 每条有日期和原始链接。

### 案例 E：LangGraph 初学者学习路径

- [ ] 输出前置知识和学习顺序。
- [ ] 提供官方资料。
- [ ] 提供实战任务和验收方法。
- [ ] 总结常见误区。

---

## 15. 推荐项目目录与当前差异

```text
AI_Search/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   ├── research.py
│   │   ├── reports.py
│   │   └── events.py
│   ├── graph/
│   │   ├── builder.py
│   │   ├── state.py
│   │   ├── context.py
│   │   ├── routes.py
│   │   └── nodes/
│   │       ├── normalize_request.py
│   │       ├── create_plan.py
│   │       ├── search_sources.py
│   │       ├── process_sources.py
│   │       ├── rank_sources.py
│   │       ├── retrieve_knowledge.py
│   │       ├── write_report.py
│   │       ├── review_report.py
│   │       ├── revise_report.py
│   │       └── save_report.py
│   ├── agents/
│   │   ├── planner.py
│   │   ├── writer.py
│   │   └── reviewer.py
│   ├── tools/
│   │   ├── base.py
│   │   ├── web_search.py
│   │   ├── github_research.py
│   │   └── paper_search.py
│   ├── services/
│   │   ├── content_fetcher.py
│   │   ├── source_normalizer.py
│   │   ├── source_deduplicator.py
│   │   ├── source_ranker.py
│   │   ├── citation_service.py
│   │   └── report_renderer.py
│   ├── rag/
│   │   ├── chunker.py
│   │   ├── embeddings.py
│   │   ├── retriever.py
│   │   └── reranker.py
│   ├── models/
│   ├── repositories/
│   ├── evaluation/
│   └── infrastructure/
├── tests/
│   ├── unit/
│   ├── graph/
│   ├── integration/
│   └── evaluation/
├── docs/
├── migrations/
├── scripts/
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── .env.example
└── README.md
```

### 15.1 已存在并有实际实现

- [x] `app/config.py`
- [x] `app/models/research.py`
- [x] `app/models/source.py`
- [x] `app/models/report.py`
- [x] `app/graph/state.py`
- [x] `app/graph/context.py`
- [x] `app/graph/nodes/normalize_request.py`
- [x] `app/graph/nodes/create_plan.py`
- [x] `app/agents/planner.py`
- [x] `app/tools/base.py`
- [x] `app/tools/search.py`
- [x] `app/graph/nodes/search_sources.py`
- [x] `app/graph/workflow.py`
- [x] `app/main.py`（CLI 与本地健康检查骨架）
- [x] 当前相关单元测试和 create_plan 节点测试

### 15.2 已存在但为空或未形成能力

- [ ] `README.md`：文件为空。
- [ ] `Dockerfile`：文件为空。
- [ ] `migrations/`：目录未形成迁移能力。
- [ ] `scripts/`：目录未形成运行入口。

### 15.3 尚未创建

- [ ] `app/api/`
- [ ] `app/graph/builder.py`（已有等价的 `workflow.py`，后续决定是否改名）
- [ ] `app/graph/routes.py`
- [ ] process/rank/retrieve/write/review/revise/save 节点
- [ ] Writer 和 Reviewer
- [ ] GitHub、Paper 工具（Web 工具主体已实现）
- [ ] Services
- [ ] RAG
- [ ] Repositories
- [ ] Evaluation
- [ ] Infrastructure
- [ ] `tests/integration/`
- [ ] `tests/evaluation/`
- [ ] `docker-compose.yml`

---

## 16. 里程碑与 Definition of Done

### M0：工程基线可复现

- [ ] 依赖可一次安装。
- [ ] README 可指导新开发者启动项目。
- [ ] pytest、Ruff、mypy、pre-commit 全部通过。
- [ ] Docker Compose 可启动 PostgreSQL 和 Redis。

### M1：最小研究闭环

- [ ] plan → search → process → write 通过 LangGraph 运行。
- [ ] 至少 5 个来源。
- [ ] URL 和正文去重。
- [ ] 输出带真实引用 Markdown。
- [ ] 至少一个失败场景正确降级。
- [ ] 连续运行无状态污染。

### M2：任务可持久化

- [ ] FastAPI 异步任务。
- [ ] PostgreSQL、Checkpoint、Redis。
- [ ] SSE 进度。
- [ ] 服务重启后可查询或恢复。

### M3：多来源与 RAG

- [ ] Web、GitHub、Paper 三类来源。
- [ ] 抓取、清洗、分块、Embedding。
- [ ] 关键词 + 向量混合检索。
- [ ] 来源评分和官方来源优先。

### M4：质量闭环

- [ ] Reviewer。
- [ ] 定向修改。
- [ ] 最大 2 次修订。
- [ ] 引用验证。
- [ ] 自动质量分。
- [ ] 固定离线评估集。

### M5：每日简报产品化

- [ ] 用户关注主题。
- [ ] 定时运行。
- [ ] 最近 24 小时过滤。
- [ ] 事件聚类。
- [ ] Top 5。
- [ ] 页面或邮件展示。

---

## 17. 当前建议执行顺序

### P0：先关闭现有基础问题

- [ ] 安装项目声明的真实依赖和开发依赖。
- [ ] 修复 Planner fallback warning 的逗号断言。
- [ ] 运行当前检出的 37 个测试函数（含 7 个未跟踪的搜索节点测试）。
- [ ] 清理 Ruff/格式问题和未使用导入。
- [ ] 让 pytest、Ruff、mypy 全绿。
- [x] 更新 `docs/PROJECT_PROGRESS.md`，反映 T05–T11 的实际代码进度。
- [ ] 补充 README 的最小安装和测试说明。

### P1：实现最小数据获取与输出

- [ ] T07 WebSearchTool：补齐 Mock 单元测试、外部 marker 测试与重试次数追踪。
- [ ] T08 来源标准化和去重：将 Tool/Node 中的逻辑下沉到 Services，并补齐 URL/哈希/顺序测试。
- [ ] T09 Writer 和 Markdown Renderer。

### P2：完成端到端链路

- [ ] T10 最小 LangGraph：补 process/write 节点和工作流测试。
- [ ] T11 CLI：补日期/来源参数、Markdown 输出和统一异常处理。
- [ ] T12 端到端测试。

### P3：进入工程化阶段

- [ ] PostgreSQL、Repository 和 Checkpoint。
- [ ] FastAPI 异步任务和 SSE。
- [ ] Redis 缓存和任务锁。

### 当前最近里程碑

> 输入主题 → 生成 3 个问题 → 获得至少 5 个来源 → 去重 → 生成带真实引用的 Markdown → 通过 LangGraph 连续运行两次且无状态污染。

在该里程碑完成前，不优先开发数据库、复杂 RAG、Reviewer、每日邮件和前端。

---

## 18. Git 与 AI 协作规范

- [ ] 每个分支只处理一个明确任务。
- [ ] 分支名使用 `feature/*`、`fix/*` 或 `test/*`。
- [ ] 每个任务明确允许修改和禁止修改的文件。
- [ ] 每个功能同步添加或更新测试。
- [ ] 修改 State、Prompt、数据模型或公共接口时同步更新 docs。
- [ ] 提交信息说明修改原因和影响。
- [ ] PR 列出变更范围、测试结果、数据结构变化和风险。
- [ ] 合并前运行 pytest、Ruff 和 mypy。
- [ ] 禁止在未授权情况下重构无关模块。
- [ ] 禁止将“文件存在”直接标记为“功能完成”。

### 18.1 单任务模板

```text
任务：

目标：

依据：

允许修改：

禁止修改：

输入与输出：

验收标准：

测试要求：

回滚方式：
```

---

## 19. 进度更新规则

每完成一个任务：

1. 将满足全部验收条件的父任务从 `[ ]` 更新为 `[x]`。
2. 勾选实际完成的子任务。
3. 记录新增或修改的文件。
4. 记录 pytest、Ruff、mypy 和集成测试结果。
5. 记录仍未解决的风险。
6. 更新“当前完成度摘要”和“当前任务状态”。
7. 如果 State、Prompt、数据模型或 API 发生变化，同步更新架构说明。
8. 如果新增外部依赖，同步更新 `pyproject.toml`、`.env.example` 和 README。

### 19.1 更新记录

| 日期 | 版本 | 内容 |
|---|---|---|
| 2026-08-01 | V1.1 | 依据当前工作区重新核验：记录 Tavily 搜索、基础去重、三节点 LangGraph 和 CLI 骨架；逐项勾选 T07/T08/T10/T11 已实现子项；保留所有未满足测试与端到端验收的父任务为未完成。 |
| 2026-07-28 | V1.0 | 根据两份项目设计文件和当前仓库代码，建立完整项目规划与 Todo 清单；标记 T02、T03、T06 完成，T01、T04、T05 部分完成，其余待开发。 |
