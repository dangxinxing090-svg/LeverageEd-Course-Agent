AI智能教育课程平台

项目架构设计文档

  -------------------------------- ------------------------------------------------------------------ ----------------------------------------------------------------
  **项目**                         **内容**                                                           
  文档名称                         AI智能教育课程平台 - 项目架构设计文档                              
  文档版本                         V1.4                                                               
  编制日期                         2026年5月23日                                                      
  编制人                           架构师                                                             
  密级                             内部使用                                                           
  全景知识图谱视图简化（V1.3）     移除架构视图，只保留列表视图；保留KnowledgeGraphArch文件但不引用   简化用户界面，减少视图切换的复杂度，聚焦列表视图的知识体系展示
  知识讲解结构化JSON输出（V1.3）   LLM输出8维度结构化JSON，前端按独立卡片渲染；改为非流式一次性返回   解决流式渲染闪烁问题，8维度清晰分离提升可读性和结构化展示
  知识结构加载优化（V1.4）         将轮询机制改为SSE推送，每2秒轮询改为服务器主动推送完成通知 减      少前端HTTP请求频率，降低服务器负载，提升实时性和用户体验
  -------------------------------- ------------------------------------------------------------------ ----------------------------------------------------------------

一、项目核心目标与边界范围

1.1 核心目标

  -------------- -------------------------------------------------------------------------------
  **目标层级**   **具体目标**
  核心目标       构建基于多Agent协作的AI智能教育课程平台，实现「从森林到树木」的个性化学习体验
  技术目标       9个Agent协同工作，支持三层知识体系、动态学习路径规划、实时行为分析
  业务目标       支持跳级学习、实时答疑、鼓励奖励、用户行为驱动的个性化推荐
  -------------- -------------------------------------------------------------------------------

1.2 范围边界

1.2.1 包含范围

\- 9个核心Agent的设计与实现

\- 三层知识体系（知识板块-知识点-知识组件）的存储与管理

\- 用户行为记录与分析系统

\- 基于BKT/DKT的学习曲线建模

\- 三页交互界面（首页/学习页/全景进度页）

\- 鼓励奖励系统（积分、勋章）

\- 免费版与专业版功能区分

1.2.2 不包含范围

\- 多语言国际化支持（首期仅中文）

\- 移动端原生App（首期仅Web）

\- 第三方内容接入（首期仅平台自生成内容）

\- 社交功能（社区、讨论区）

\- 直播/视频讲解（首期仅文字讲解）

二、整体顶层架构图（文字版）

┌─────────────────────────────────────────────────────────────────────────────┐

│ 用户交互层 (Presentation Layer) │

├─────────────────────────────────────────────────────────────────────────────┤

│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │

│ │ 首页模块 │ │ 学习页模块 │ │ 全景进度页 │ │

│ │ HomePage │ │ LearningPage │ │ ProgressPage │ │

│ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ │

└─────────┼────────────────┼────────────────┼──────────────────────────────────┘

│ │ │

└────────────────┴────────────────┘

│

▼

┌─────────────────────────────────────────────────────────────────────────────┐

│ API网关层 (API Gateway) │

│ 统一入口、认证鉴权、请求路由、限流熔断 │

└─────────────────────────────────────────────────────────────────────────────┘

│

▼

┌─────────────────────────────────────────────────────────────────────────────┐

│ 核心业务层 (Core Business Layer) │

├─────────────────────────────────────────────────────────────────────────────┤

│ │

│
┌─────────────────────────────────────────────────────────────────────┐
│

│ │ Agent调度中心 (Agent Orchestrator) │ │

│ │ 负责Agent注册、任务分发、结果聚合、异常处理 │ │

│
└─────────────────────────────────────────────────────────────────────┘
│

│ │ │

│ ┌────────────┬───────────────┼───────────────┬────────────┐ │

│ ▼ ▼ ▼ ▼ ▼ │

│ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ │

│ │知识处理 │ │学习支持 │ │路径规划 │ │激励系统 │ │数据基础 │ │

│ │ Agent群 │ │ Agent群 │ │ Agent群 │ │ Agent群 │ │ Agent群 │ │

│ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ │

│ │ │ │ │ │ │

│ ┌───┴───┐ ┌───┴───┐ ┌───┴───┐ ┌───┴───┐ ┌───┴───┐ │

│ │Agent1 │ │Agent3 │ │Agent5 │ │Agent7 │ │Agent8 │ │

│ │知识拆分│ │统一教学│ │路径规划│ │鼓励奖励│ │行为记录│ │

│ ├───────┤ └───────┘ ├───────┤ └───────┘ ├───────┤ │

│ │Agent2 │ │Agent6 │ │Agent9 │ │

│ │重点标注│ │跳级建议│ │行为分析│ │

│ └───────┘ └───────┘ └───────┘ └───────┘ │

│ │

└──────────────────────────────────────────────────────────────────────────┘

│

▼

┌─────────────────────────────────────────────────────────────────────────────┐

│ 数据存储层 (Data Layer) │

├─────────────────────────────────────────────────────────────────────────────┤

│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │

│ │ 关系型数据库 │ │ 缓存服务 │ │ 消息队列 │ │ 对象存储 │ │

│ │ PostgreSQL │ │ Redis │ │ Kafka │ │ MinIO │ │

│ │ 业务数据存储 │ │ 热点数据缓存 │ │ 异步消息处理 │ │ 文件资源存储 │ │

│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │

└─────────────────────────────────────────────────────────────────────────────┘

三、一级核心模块职责定义

3.1 模块总览

  -------------- ----------------- -------------------------------
  **模块编号**   **模块名称**      **核心职责**
  M01            用户交互层        负责三页界面的渲染与交互处理
  M02            API网关层         统一入口、认证鉴权、路由转发
  M03            Agent调度中心     Agent注册、任务分发、结果聚合
  M04            知识处理Agent群   知识体系构建与标注
  M05            学习支持Agent群   讲解、练习、答疑
  M06            路径规划Agent群   学习路径动态规划与跳级建议
  M07            激励系统Agent群   鼓励奖励发放
  M08            数据基础Agent群   行为记录与分析
  M09            数据存储层        数据持久化与缓存
  -------------- ----------------- -------------------------------

3.2 各模块详细职责

3.2.1 M01 用户交互层

  ---------------- --------------------------------------------------------
  **子模块**       **职责描述**
  首页模块         学习主题输入、推荐主题展示、学习历史展示
  学习页模块       教学面板渲染、提示面板更新、学习路径面板、问答面板交互
  全景进度页模块   三层知识体系可视化、状态标识、跳级操作界面
  ---------------- --------------------------------------------------------

3.2.2 M02 API网关层

  ------------ -----------------------------
  **职责项**   **说明**
  统一入口     所有前端请求统一入口
  认证鉴权     JWT Token验证、用户身份识别
  请求路由     按路径路由到对应服务
  限流熔断     防止系统过载、服务降级
  日志记录     请求响应日志
  ------------ -----------------------------

3.2.3 M03 Agent调度中心

  ------------ -----------------------------
  **职责项**   **说明**
  Agent注册    管理所有Agent的注册与发现
  任务分发     根据任务类型分发到对应Agent
  结果聚合     收集多Agent结果并整合
  异常处理     Agent失败时的重试与降级
  依赖管理     处理Agent间的依赖执行顺序
  ------------ -----------------------------

3.2.4 M04-M08 Agent群职责

  -------------- ----------------- --------------------------------------------------------------
  **Agent群**    **Agent**         **职责**
  M04 知识处理   Agent1 知识拆分   将学习主题拆分为三层知识体系
  M04 知识处理   Agent2 重点标注   标注知识点的概念难度、学习难度、重要性
  M05 学习支持   Agent3 统一教学   统一负责全景介绍生成、知识点讲解、练习题生成与批改、实时答疑
  M06 路径规划   Agent5 路径规划   基于用户行为记录动态规划学习路径
  M06 路径规划   Agent6 跳级建议   推荐可跳级知识点，生成跳级测试
  M07 激励系统   Agent7 鼓励奖励   生成鼓励内容、发放积分勋章
  M08 数据基础   Agent8 行为记录   详细记录所有用户学习行为
  M08 数据基础   Agent9 行为分析   分析用户行为、生成画像、输出建议
  -------------- ----------------- --------------------------------------------------------------

3.2.5 M09 数据存储层

  ------------ --------------------------------------------
  **组件**     **职责**
  PostgreSQL   存储用户数据、知识体系、学习记录、配置数据
  Redis        缓存热点数据、会话状态、临时计算结果
  Kafka        异步处理行为日志、Agent间消息通信
  MinIO        存储用户上传文件、生成资源文件
  ------------ --------------------------------------------

四、模块间数据流转关系

4.1 核心业务流程数据流

4.1.1 用户首次学习流程

用户交互层 → 输入学习主题 → API网关 → 后端API层

↓

后端立即返回topic\_id（asyncio.create\_task后台处理）→ 用户交互层

↓

1秒内跳转到学习页（/learn?topicId=xxx&topicName=xxx）

↓

后台并行调用两个LLM请求（asyncio.gather）：

├─ 统一教学Agent → 使用「知识向导」Prompt → 输出: 主题全景介绍文本

└─ 知识拆分Agent → 使用「知识拆分」Prompt → 输出: 三层知识体系JSON

↓

前端每2秒轮询 GET /topics/{topic\_id}/status 检查处理状态

↓

全景介绍就绪 → 教学面板流式展示「主题全景介绍」（SSE）

↓

知识拆分就绪 → 学习路径面板显示学习路径 + 全景知识页可展示知识图谱

↓

用户点击「开始学习第一个知识组件」→ 教学面板调用流式讲解接口（SSE）→
逐字展示讲解内容

4.1.2 用户学习知识点流程

用户交互层 → 请求讲解 → 后端流式讲解接口（SSE）→ Agent3统一教学 →
使用「知识讲解」Prompt → 逐字返回讲解内容 → 用户交互层实时渲染

↓

Agent8 行为记录 (学习时长、滚动、暂停)

讲解完成后 → 显示\"下一个知识点\"和\"练习题\"按钮

↓

如果当前知识点为重点难点（difficulty=hard）且用户未做练习题直接点击\"下一个知识点\"→
弹出对话框提示建议做练习题

↓

用户选择练习题 →
在教学面板对话框内直接展示练习题（内嵌模式，非独立面板）→
用户在输入框输入答案并提交

↓

Agent8 行为记录 (答题行为)

用户提交答案 → Agent3统一教学 → 使用「批改」Prompt → 返回批改结果和讲解
→ 在教学面板对话框内展示批改结果

↓

Agent8 行为记录 (答案、正确性、错误类型)

↓

Agent9 行为分析 (更新掌握度、识别难点)

↓

后端标记知识点完成状态（knowledge\_cache.mark\_point\_completed）→
同步更新知识结构缓存中该知识点的status为completed

↓

前端TeachingPanel通过onExerciseCompleted回调通知App →
App刷新knowledgeBlocks状态和sessionStorage →
LearningPathPanel通过refreshKey重新获取学习路径数据

↓

Agent5 路径规划 (调整后续路径)

4.1.3 全景知识图谱交互流程

用户从学习页导航到全景进度页 → 从sessionStorage读取topicId →
加载三层知识体系

↓

全景页展示完整知识图谱（L1板块 → L2知识点 → L3组件）

↓

用户点击某个知识点或知识组件 →
携带componentId跳转到学习页（/learn?topicId=xxx&componentId=yyy）

↓

学习页自动定位到该组件 → 教学面板流式讲解该知识点

用户从全景页点击导航栏「学习」→ 无URL参数 →
自动从sessionStorage恢复topicId → 保持之前的学习状态

4.2 模块调用顺序

  ------------------ ---------------------------------------------------------------------------------------------------------------------
  **场景**           **调用顺序**
  用户输入学习主题   M01 → M02 → M03 → M04(Agent1→Agent2) + M05(Agent3全景介绍) → M01(SSE接收完成通知) → M08(Agent8) → M06(Agent5) → M01
  用户学习知识点     M01 → M02 → M03 → M05(Agent3讲解) → M08(Agent8) → M01
  用户做练习题       M01 → M02 → M03 → M05(Agent3出题) → M08(Agent8) → M01 → M05(Agent3批改) → M08(Agent8→Agent9) → M06(Agent5) → M01
  用户提问           M01 → M02 → 后端流式问答接口(SSE) → Agent3(答疑) → M01
  完成知识点         M08(Agent8) → M09(Agent9) → M07(Agent7) → M06(Agent5) → M01
  ------------------ ---------------------------------------------------------------------------------------------------------------------

4.3 流式输出（SSE）机制

平台采用 Server-Sent
Events（SSE）实现LLM内容的流式输出，大幅改善用户体感速度。

4.3.1 技术实现

后端：FastAPI StreamingResponse + AgentLLMClient.generate\_stream() +
DoubaoProvider.generate\_stream()

前端：fetch ReadableStream 解析SSE数据流，通过onChunk回调实时更新UI

4.3.2 流式接口

  ---------- --------------------------------------------------- ---------------------
  **接口**   **路径**                                            **说明**
  流式讲解   GET /knowledge/components/{id}/explanation/stream   SSE逐字返回讲解内容
  流式问答   POST /learning/qa/ask/stream                        SSE逐字返回回答内容
  ---------- --------------------------------------------------- ---------------------

4.3.3 数据格式

SSE事件格式：data: {文本片段}\\n\\n

结束标记：data: \[DONE\]\\n\\n

错误标记：data: \[ERROR\] {错误信息}\\n\\n

4.3.4 后台任务与轮询机制

平台采用「立即返回+后台处理+轮询」模式，解决LLM调用耗时长的问题：

后端：create\_topic接口通过asyncio.create\_task启动后台任务，立即返回topic\_id

后台任务：使用asyncio.gather并行调用全景介绍和知识拆分两个LLM请求

轮询接口：GET
/topics/{topic\_id}/status，返回structure\_ready和overview\_ready状态

前端：每2秒轮询一次，检测到数据就绪后触发相应的UI更新

4.4 Prompt策略

平台采用六套精心设计的Prompt模板，统一由统一教学Agent管理：

4.4.1 主题全景介绍Prompt（知识向导）

定位：为学习者点亮第一盏灯，建立对领域的整体认知

核心原则：先见森林再看树木、先通脉络再填血肉、先建直觉再立逻辑

价值序列：可理解性 \> 完整性 \> 实用性 \> 系统性 \> 激发兴趣 \> 灌输知识

4.4.2 主题知识拆分Prompt

定位：搭建标准三层知识体系全景版图（L1知识板块 → L2知识点 → L3知识组件）

输出要求：全景知识版图总览、完整三层结构化列表、知识点前置依赖关系、最优线性学习路径、配套评估体系

输出格式：严格JSON格式，便于程序解析

4.4.3 知识点讲解Prompt

定位：以专业知识向导身份精讲单个知识点

讲解结构（8个维度）：通俗定义 → 底层原理 → 入门示例 → 核心拆解 →
易混对比 → 常见错误 → 适用场景 → 核心口诀

讲解风格：由浅入深、先直觉再原理、再落地实操

4.4.4 练习题生成Prompt

定位：基于知识点和用户掌握情况，生成个性化练习题

核心原则：难度适配、现实对应性、循序渐进

4.4.5 答案批改Prompt

定位：批改用户答案，分析错误原因，提供针对性补充学习建议

核心原则：鼓励为主、精准定位错误、提供改进方向

4.4.6 实时答疑Prompt

定位：以苏格拉底式引导回答用户在学习过程中的提问

核心原则：不直接给答案、引导思考、结合当前学习上下文

4.5 前端状态管理

4.5.1 跨页面状态共享

使用sessionStorage存储学习状态，实现页面间无缝切换：

  ------------------ ------------------ ----------------------
  **存储Key**        **说明**           **用途**
  currentTopicId     当前学习主题ID     学习页与全景页共享
  currentTopicName   当前学习主题名称   导航栏和页面标题显示
  ------------------ ------------------ ----------------------

4.5.2 学习页双模式

全景介绍模式（overviewMode=true）：展示主题全景介绍，点击后进入组件讲解模式

组件讲解模式（overviewMode=false）：展示具体知识组件的详细讲解

4.5.3 URL参数设计

+-------------+--------------------+---------------------------------+
| **参数**    | **说明**           | **示例**                        |
+-------------+--------------------+---------------------------------+
| topicId     | 学习主题ID         | topic-abc123                    |
+-------------+--------------------+---------------------------------+
| topicName   | 学习主题名称       | Python编程                      |
+-------------+--------------------+---------------------------------+
| componentId | 知识组件ID（可选） | comp-x                          |
|             |                    | yz789（从全景页点击进入时携带） |
|             |                    |                                 |
|             |                    | 4.5.4 难度提示对话框            |
|             |                    |                                 |
|             |                    | 当用户学习完重                  |
|             |                    | 点难点知识（difficulty=hard）后 |
|             |                    | ，若未做练习题直接点击\"下一个  |
|             |                    | 知识点\"，系统弹出提示对话框：  |
|             |                    |                                 |
|             |                    | 对话框内容：\"该知识点难        |
|             |                    | 度较高，建议做练习题加深理解\"  |
|             |                    |                                 |
|             |                    | 选项一：\"继续                  |
|             |                    | 下一个知识点\"（尊重用户选择）  |
|             |                    |                                 |
|             |                    | 选项二：\"去                    |
|             |                    | 做练习题\"（跳转到练习题界面）  |
|             |                    |                                 |
|             |                    | 实现方式：window.confirm(       |
|             |                    | )弹窗，根据用户选择执行不同逻辑 |
+-------------+--------------------+---------------------------------+

**4.5.5 知识点完成状态同步机制（V1.2新增）**

当用户在教学面板内完成练习题并提交答案后，系统通过以下机制同步知识点完成状态：

后端：submit\_exercises接口在LLM批改成功后，调用knowledge\_cache.mark\_point\_completed()将知识点及其所属组件的status标记为completed，同时记录分数和完成时间到\_completed\_points内存字典。

前端：TeachingPanel通过onExerciseCompleted(pointId,
score)回调通知App组件。App组件收到回调后：(1) 重新调用getTopicStructure
API获取最新知识结构并更新knowledgeBlocks状态和sessionStorage；(2)
递增learningPathRefreshKey触发LearningPathPanel重新获取学习路径数据。

影响范围：全景知识图谱页面（从sessionStorage读取最新知识结构，已完成知识点显示为completed状态）、学习路径面板（从API获取最新completed\_points和next\_plan）。

**4.5.6 LLM生成数据持久化缓存（V1.2新增）**

为避免重复调用LLM，系统对全景介绍和知识图谱数据实施文件级持久化缓存：

缓存Key：以用户输入的topic\_text（主题文本）的MD5哈希作为文件名，存储在backend/data/topics/目录下，每个主题一个JSON文件，包含topic\_text、topic\_id、overview（全景介绍）、structure（知识结构）、saved\_at（保存时间）。

读取策略：用户提交主题时，create\_topic接口先调用load\_topic\_from\_file(topic\_text)检查本地文件。命中缓存则直接将数据加载到内存缓存（\_topic\_cache和\_topic\_overview），跳过LLM调用，立即标记为completed状态；未命中则启动后台LLM任务，生成完成后同时写入内存缓存和本地文件（save\_topic\_to\_file）。

涉及文件：knowledge\_cache.py（新增save\_topic\_to\_file、load\_topic\_from\_file、\_topic\_text\_to\_key、\_get\_topic\_file\_path函数）、topics.py（create\_topic中增加缓存检查分支，\_process\_topic\_background中增加文件保存调用）。

**4.5.7 知识点讲解持久化缓存（V1.2新增）**

与主题数据缓存策略一致，知识点讲解也实施文件级持久化：

缓存Key：以component\_id的MD5哈希作为文件名，存储在backend/data/topics/explanations/目录下。每个组件一个JSON文件，包含component\_id、knowledge\_name、content（讲解全文）、saved\_at。

流式接口处理：缓存命中时，将已保存的完整文本按20字符分段模拟SSE流式输出（cached\_event\_generator），前端无需任何改动，用户体验与LLM实时生成一致。缓存未命中时调用LLM流式生成，生成完成后将完整文本保存到文件。

涉及文件：knowledge\_cache.py（新增save\_explanation\_to\_file、load\_explanation\_from\_file、\_get\_explanation\_file\_path函数）、learning.py（get\_explanation和get\_explanation\_stream中增加缓存检查和保存逻辑）。

**4.5.8 学习路径面板展示简化（V1.2新增）**

学习路径面板（LearningPathPanel）简化为两个展示区块：已完成知识点列表和跳级建议。移除后续学习计划区块（后端API仍返回next\_plan字段，前端不再渲染）。

已完成知识点展示逻辑：后端get\_learning\_path
API新增total\_points字段返回知识点总数。前端根据completed\_points.length与total\_points比较判断：已完成数量等于总数时显示绿色\"全部完成\"提示；否则逐条列出已完成知识点名称和分数；无已完成知识点时显示\"暂无已完成知识点\"。

涉及文件：LearningPathPanel.tsx（移除后续学习计划渲染区块，renderCompletedPoints增加totalPoints参数和全部完成判断逻辑，新增learning-path-all-completed
CSS样式）、users.py（get\_learning\_path返回值新增total\_points字段）、types/index.ts（LearningPath接口新增total\_points可选字段）。

**4.5.9 学习页状态持久化（V1.2新增）**

解决从全景知识页返回学习页时教学面板状态丢失的问题。当用户从全景页点击\"返回学习\"按钮时，应恢复之前的学习状态（正在学习的知识组件或全景介绍），而非重新加载全景介绍。

状态保存：LearnPage组件通过useEffect监听overviewMode、currentComponentIndex和overview变化，实时保存到sessionStorage（键名：learnPage\_overviewMode\_{topicId}、learnPage\_componentIndex\_{topicId}、learnPage\_overview\_{topicId}）。knowledgeBlocks在获取和刷新时通过已有的sessionStorage同步机制保存（knowledgeBlocks\_{topicId}）。

状态恢复：knowledgeBlocks和overview在useState初始化时直接从sessionStorage恢复（使用topicId或sessionTopicId作为key）；loading初始值根据是否有缓存数据决定（有缓存则为false，避免显示加载中）。轮询useEffect在检测到已有缓存数据时直接跳过，不重新请求API。overviewMode和currentComponentIndex的恢复逻辑由独立的useEffect处理（在knowledgeBlocks加载完成后执行，使用knowledgeBlocks.length而非allComponents.length作为条件，确保恢复逻辑在数据恢复后立即执行）。为防止保存useEffect在恢复useEffect之前执行导致默认值覆盖正确值，新增isRestoredRef标记，只有恢复逻辑完成后才允许保存状态到sessionStorage。

涉及文件：App.tsx（LearnPage组件：knowledgeBlocks、overview、loading的useState初始化时从sessionStorage恢复；轮询useEffect增加缓存检查跳过逻辑；状态保存useEffect增加overview持久化）。

**4.5.10 教学面板按钮可用性修复（V1.2新增）**

修复教学面板在加载知识点讲解时，\"下一个知识组件\"和\"练习题\"按钮被禁用的问题。用户应能在加载过程中自由点击切换到下一个知识组件或进入练习题模式。

**4.5.10a 教学面板componentId有效性检查（V1.2修复）**

修复教学面板在componentId为空或无效时调用API导致错误的问题。在TeachingPanel组件的加载知识点讲解useEffect中，添加对componentId的有效性检查（检查是否为空字符串、\'default-component\'或undefined），如果无效则显示提示信息\"请选择有效的知识组件开始学习\"，跳过API调用避免错误。

涉及文件：frontend/src/components/TeachingPanel/TeachingPanel.tsx（在加载知识点讲解useEffect开头添加componentId有效性检查）。

修改内容：\"下一个知识组件\"按钮移除disabled属性中的isLoading条件，始终可点击；\"练习题\"按钮的disabled条件从isLoading
\|\| exerciseLoading \|\| exerciseMode改为exerciseLoading \|\|
exerciseMode，仅在练习题加载中或答题中禁用。输入框和发送按钮保持isLoading禁用不变。

涉及文件：TeachingPanel.tsx（第312行移除disabled={isLoading}；第316行disabled条件移除isLoading）。

**4.5.11 学习进度同步机制（V1.2新增）**

用户完成知识点学习后，学习进度需要同步更新到全景知识页的知识图谱和学习页的学习路径面板。

学习路径面板：已有refreshKey机制，handleExerciseCompleted中调用setLearningPathRefreshKey触发重新获取学习路径数据。

全景知识页：新增跨页面同步机制。handleExerciseCompleted在更新knowledgeBlocks后，设置sessionStorage标记knowledgeBlocks\_refresh\_timestamp。PanoramaPageWrapper增加refreshKey
state，并通过两种方式监听更新：（1）window.addEventListener(\'storage\')监听跨标签页事件；（2）setInterval轮询检查标记（解决同一标签页内storage事件不触发的问题）。当检测到标记变化时，触发refreshKey更新，重新从sessionStorage加载知识结构。

涉及文件：App.tsx（handleExerciseCompleted中设置knowledgeBlocks\_refresh\_timestamp标记；PanoramaPageWrapper增加refreshKey
state、storage事件监听、轮询检查逻辑）。

**4.5.12 记忆系统数据库层（P0阶段）**

P0阶段完成记忆系统的数据库层基础建设，实现从内存存储到持久化存储的迁移。

数据库连接：新增app/db/database.py，使用SQLAlchemy+PostgreSQL，支持连接池、健康检查。环境变量DATABASE\_URL配置，默认postgresql://postgres:postgres\@localhost:5432/ai\_education。

数据模型：新增app/models/目录，定义4个核心表：（1）user\_profiles-用户画像（学习能力、风格标签、BKT参数）；（2）behavior\_logs-行为日志（学习/提问/练习/跳级/交互行为）；（3）learning\_progress-学习进度（组件掌握度、BKT概率）；（4）exercise\_history-练习历史（答题记录、错误类型）。

行为记录API：新增app/api/v1/endpoints/behavior.py，提供POST
/behavior/record记录行为、GET /behavior/logs/{user\_id}查询日志、GET
/behavior/stats/{user\_id}行为统计。自动创建用户画像（不存在时）。

前端集成：新增frontend/src/api/behavior.ts行为记录API封装，提供recordBehavior、recordLearnStart、recordLearnEnd、recordPracticeComplete等便捷函数。新增vite-env.d.ts解决import.meta.env类型定义。

涉及文件：backend/app/db/database.py、backend/app/models/\*.py、backend/app/api/v1/endpoints/behavior.py、backend/app/api/v1/\_\_init\_\_.py、backend/requirements.txt、frontend/src/api/behavior.ts、frontend/src/vite-env.d.ts。

**4.5.13 记忆系统前端集成（P1阶段）**

P1阶段完成前端行为记录集成，在关键用户行为点发送行为数据到后端。

学习行为记录（App.tsx）：LearnPage组件新增learnStartTimeRef和lastComponentIdRef追踪学习状态。useEffect监听overviewMode和currentComponent变化，自动调用recordLearnStart/recordLearnEnd。组件卸载时记录学习结束。

练习行为记录（App.tsx）：handleExerciseCompleted中调用recordPracticeComplete，记录is\_correct（60分以上为正确）和score。

提问行为记录（TeachingPanel.tsx）：handleSend中调用recordBehavior，记录behavior\_type为question，details包含question内容。

涉及文件：frontend/src/App.tsx（导入行为记录API、新增学习行为追踪useEffect、handleExerciseCompleted增加练习记录）、frontend/src/components/TeachingPanel/TeachingPanel.tsx（handleSend增加提问记录）。

**4.5.14 BKT算法与掌握度计算（P2阶段）**

P2阶段实现BKT（Bayesian Knowledge
Tracing）贝叶斯知识追踪算法，自动计算和更新知识组件掌握度。

BKT算法核心（app/core/bkt.py）：BKTModel类实现贝叶斯知识追踪，使用4个参数-p\_init（初始掌握概率，默认0.3）、p\_transit（学习概率，默认0.1）、p\_slip（失误概率，默认0.1）、p\_guess（猜测概率，默认0.2）。update方法根据答题结果更新掌握度，使用贝叶斯公式P(L\_n\|obs)
= P(obs\|L\_n) \* P(L\_n) / P(obs)，然后应用学习转移P(L\_{n+1}) =
P(L\_n\|obs) +
(1-P(L\_n\|obs))\*P(T)。掌握阈值MASTERY\_THRESHOLD=0.95，掌握等级1-5级（初学/了解/熟悉/掌握/精通）。

BKT服务层（app/services/bkt\_service.py）：BKTService封装BKT与数据库交互。get\_or\_create\_progress获取或创建学习进度记录；update\_progress\_after\_attempt答题后更新掌握度，自动保存ExerciseHistory练习历史，更新learning\_progress表的bkt\_p\_known、status、attempt\_count、correct\_count等字段；get\_component\_mastery查询组件掌握度；get\_user\_mastery\_summary获取用户掌握度汇总统计。

API集成（app/api/v1/endpoints/behavior.py）：record\_behavior接口在接收到practice行为时，自动调用BKTService更新掌握度，返回bkt\_update字段包含更新后的掌握度信息。新增GET
/behavior/mastery/{user\_id}/{component\_id}查询组件掌握度接口、GET
/behavior/mastery/summary/{user\_id}查询用户掌握度汇总接口。

涉及文件：backend/app/core/bkt.py、backend/app/services/bkt\_service.py、backend/app/services/\_\_init\_\_.py、backend/app/api/v1/endpoints/behavior.py。

**4.5.15 用户行为分析与画像生成（P3阶段）**

P3阶段实现用户行为分析与画像生成的持久化，将已有BehaviorAnalysisAgent的分析结果写入数据库。

用户画像服务层（app/services/user\_profile\_service.py）：UserProfileService封装画像持久化逻辑。analyze\_and\_update\_profile方法从behavior\_logs读取原始行为数据，转换为Agent事件格式，调用BehaviorAnalysisAgent.execute()进行四维度分析（时间/内容/练习/路径），将分析结果写入user\_profiles表。画像字段包括：learning\_ability\_level（基于活跃度映射1-5级）、learning\_style\_tags（基于专注度/一致性/准确率/学习路径生成标签列表）、preference\_settings（高峰时段、日均学习时长等）、统计信息（总学习时长、已完成组件数、练习统计）。

新增API接口：GET /behavior/profile/{user\_id}查询用户画像；POST
/behavior/profile/{user\_id}/analyze触发画像分析并更新。

涉及文件：backend/app/services/user\_profile\_service.py、backend/app/services/\_\_init\_\_.py、backend/app/api/v1/endpoints/behavior.py。

**4.5.16 DKT知识状态转移预测（P4阶段）**

P4阶段实现DKT（Deep Knowledge
Tracing）知识状态转移预测，基于知识组件依赖图和答题序列预测掌握度。采用简化版实现（无PyTorch依赖），预留深度学习模型接口。

DKT模型核心（app/core/dkt.py）：DKTModel类实现知识状态转移预测。核心参数-learning\_rate=0.15（答对提升）、forgetting\_rate=0.05（答错下降）、transfer\_rate=0.1（知识迁移）、decay\_rate=0.02（时间衰减）。update方法根据答题结果更新掌握度，并应用知识迁移（前置组件巩固、后续组件影响）。predict方法综合当前掌握度和前置掌握度预测正确概率（权重0.7:0.3）。get\_weak\_components识别薄弱组件，get\_learning\_path\_recommendation推荐学习路径（优先掌握度低且前置满足的组件）。

DKT服务层（app/services/dkt\_service.py）：DKTService封装DKT与数据库交互。build\_dkt\_model从behavior\_logs读取答题历史，注册知识组件依赖关系，回放序列重建隐状态。get\_dkt\_predictions获取全组件预测，get\_weak\_components识别薄弱组件，get\_learning\_path\_recommendation推荐学习路径，get\_bkt\_dkt\_comparison提供BKT与DKT对比分析。

新增API接口：GET /behavior/dkt/{user\_id}获取DKT预测、GET
/behavior/dkt/{user\_id}/weak获取薄弱组件、GET
/behavior/dkt/{user\_id}/recommend获取学习路径推荐、GET
/behavior/dkt/{user\_id}/compare获取BKT/DKT对比。

涉及文件：backend/app/core/dkt.py、backend/app/services/dkt\_service.py、backend/app/services/\_\_init\_\_.py、backend/app/api/v1/endpoints/behavior.py。

**4.5.17 记忆压缩与数据归档（P5阶段）**

P5阶段实现记忆压缩Agent，定期归档旧行为数据，生成学习摘要，释放存储空间。

数据温度分类：热数据（7天内）保留原始日志支持实时分析；温数据（7-30天）聚合为每日统计；冷数据（30天以上）聚合为每周统计仅保留摘要。

记忆压缩Agent（app/agents/behavior/memory\_compression.py）：MemoryCompressionAgent实现行为日志的温度分类（classify\_temperature）、每日聚合（aggregate\_daily按user\_id+date+topic\_id分组统计各行为类型数量、练习正确率、学习时长、涉及组件）、每周聚合（generate\_weekly\_summary从每日摘要生成周维度统计）。CompressionConfig支持hot\_days/warm\_days/batch\_size/dry\_run配置。CompressionResult返回扫描/保留/压缩/归档数量和压缩率。

压缩服务层（app/services/compression\_service.py）：CompressionService封装压缩与数据库交互。execute\_compression扫描可压缩日志、调用Agent聚合摘要、将压缩历史记录到user\_profiles的preference\_settings、删除已归档原始日志。get\_compression\_stats返回各温度数据量统计。get\_user\_daily\_summaries查询指定天数的每日学习摘要。

新增API接口：GET /behavior/compression/stats获取压缩统计、POST
/behavior/compression/execute执行压缩（默认dry\_run=true试运行）、GET
/behavior/compression/summaries/{user\_id}获取用户每日摘要。

涉及文件：backend/app/agents/behavior/memory\_compression.py、backend/app/agents/behavior/\_\_init\_\_.py、backend/app/services/compression\_service.py、backend/app/services/\_\_init\_\_.py、backend/app/api/v1/endpoints/behavior.py。

五、全局通用数据结构

5.1 核心实体定义

5.1.1 用户 User

\- user\_id: UUID (PK)

\- username: String

\- email: String

\- password\_hash: String

\- created\_at: Timestamp

\- updated\_at: Timestamp

\- subscription\_type: Enum \[FREE, PRO\]

\- subscription\_expire\_at: Timestamp (nullable)

5.1.2 学习主题 LearningTopic

\- topic\_id: UUID (PK)

\- topic\_name: String

\- description: Text

\- created\_by: UUID (FK -\> User)

\- created\_at: Timestamp

\- status: Enum \[DRAFT, ACTIVE, ARCHIVED\]

5.1.3 知识板块 KnowledgeBlock

\- block\_id: UUID (PK)

\- topic\_id: UUID (FK -\> LearningTopic)

\- block\_name: String

\- block\_order: Integer

\- description: Text

5.1.4 知识点 KnowledgePoint

\- point\_id: UUID (PK)

\- block\_id: UUID (FK -\> KnowledgeBlock)

\- point\_name: String

\- point\_order: Integer

\- concept\_difficulty: Enum \[LOW, MEDIUM, HIGH\]

\- learning\_difficulty: Enum \[EASY, MEDIUM, HARD\]

\- importance: Enum \[CORE, IMPORTANT, AUXILIARY\]

\- description: Text

5.1.5 知识组件 KnowledgeComponent

\- component\_id: UUID (PK)

\- point\_id: UUID (FK -\> KnowledgePoint)

\- component\_name: String

\- component\_order: Integer

\- learning\_objective: Text

\- bkt\_params: JSON {p\_l0, p\_t, p\_g, p\_s}

5.1.6 用户行为日志 UserBehaviorLog

\- log\_id: UUID (PK)

\- user\_id: UUID (FK -\> User)

\- session\_id: String

\- event\_type: Enum \[LEARN\_START, LEARN\_END, QUESTION\_ASK,
QUESTION\_ANSWER, EXERCISE\_START, EXERCISE\_SUBMIT, SKIP\_SUGGEST,
SKIP\_TEST, CLICK, SCROLL, PAUSE\]

\- knowledge\_point\_id: UUID (nullable)

\- component\_id: UUID (nullable)

\- event\_data: JSON

\- timestamp: Timestamp

\- metadata: JSON {device, os, browser}

5.1.7 用户掌握状态 UserMasteryState

\- state\_id: UUID (PK)

\- user\_id: UUID (FK -\> User)

\- component\_id: UUID (FK -\> KnowledgeComponent)

\- mastery\_probability: Float \[0,1\]

\- attempt\_count: Integer

\- correct\_count: Integer

\- last\_attempt\_at: Timestamp

\- updated\_at: Timestamp

5.1.8 学习路径 LearningPath

\- path\_id: UUID (PK)

\- user\_id: UUID (FK -\> User)

\- topic\_id: UUID (FK -\> LearningTopic)

\- path\_sequence: JSON \[ordered list of point\_ids\]

\- current\_position: Integer

\- status: Enum \[ACTIVE, COMPLETED, ABANDONED\]

\- created\_at: Timestamp

\- updated\_at: Timestamp

5.2 公共接口定义

5.2.1 Agent调度接口 AgentOrchestrator

TaskResult submitTask(TaskRequest request)

List\<TaskResult\> submitTasks(List\<TaskRequest\> requests)

TaskStatus queryTaskStatus(String taskId)

void registerAgent(AgentRegistration registration)

5.2.2 任务请求 TaskRequest

\- task\_id: UUID

\- task\_type: Enum \[KNOWLEDGE\_SPLIT, DIFFICULTY\_TAG,
CONTENT\_GENERATE, EXERCISE\_GENERATE, ANSWER\_GRADE, PATH\_PLAN,
SKIP\_SUGGEST, QA\_ANSWER, REWARD\_GENERATE, BEHAVIOR\_RECORD,
BEHAVIOR\_ANALYZE\]

\- input\_data: JSON

\- priority: Integer \[1-10\]

\- dependencies: List\<UUID\>

\- timeout\_ms: Integer

5.2.3 任务结果 TaskResult

\- task\_id: UUID

\- status: Enum \[PENDING, RUNNING, SUCCESS, FAILED, TIMEOUT\]

\- output\_data: JSON

\- error\_message: String (nullable)

\- execution\_time\_ms: Integer

\- completed\_at: Timestamp

5.2.4 行为记录接口 BehaviorRecorder

void recordEvent(BehaviorEvent event)

void recordEvents(List\<BehaviorEvent\> events)

List\<BehaviorEvent\> queryUserHistory(UUID userId, TimeRange range)

5.2.5 行为分析接口 BehaviorAnalyzer

UserLearningProfile analyzeLearningState(UUID userId)

Map\<UUID, Float\> getMasteryProbabilities(UUID userId, List\<UUID\>
componentIds)

List\<UUID\> identifyDifficultPoints(UUID userId)

LearningSuggestion generateSuggestion(UUID userId)

5.2.6 学习路径接口 LearningPathPlanner

LearningPath generateInitialPath(UUID userId, UUID topicId)

LearningPath updatePathBasedOnBehavior(UUID userId, BehaviorEvent
latestEvent)

List\<SkipSuggestion\> suggestSkipPoints(UUID userId)

SkipTest generateSkipTest(UUID userId, UUID targetPointId)

5.2.7 知识服务接口 KnowledgeService

KnowledgeStructure getKnowledgeStructure(UUID topicId)

KnowledgePoint getKnowledgePoint(UUID pointId)

KnowledgeComponent getKnowledgeComponent(UUID componentId)

LearningContent getExplanation(UUID componentId, UUID userId)

Exercise generateExercise(UUID componentId, DifficultyLevel difficulty)

GradingResult gradeAnswer(UUID exerciseId, String userAnswer, UUID
userId)

Answer answerQuestion(String question, UUID currentPointId, UUID userId)

5.2.8 激励服务接口 IncentiveService

Reward grantReward(UUID userId, RewardTrigger trigger)

UserPoints getUserPoints(UUID userId)

List\<Badge\> getUserBadges(UUID userId)

List\<Achievement\> checkAchievements(UUID userId)

六、技术栈选型

  ----------- ------------------------------------------------------ ---------------- ------------------------------------------------------
  **层级**    **技术选型**                                           **版本**         **选型理由**
  前端        React + TypeScript                                     18.x             组件化、类型安全、生态丰富
  后端        Python + FastAPI                                       3.11+ / 0.100+   异步支持、高性能、AI生态友好
  Agent引擎   多LLM Provider适配（豆包/OpenAI/智谱/Kimi/通义千问）   最新稳定版       多Provider灵活切换、doubao-seed-2.0-lite（当前使用）
  数据库      PostgreSQL                                             15.x             关系型数据、JSON支持、稳定
  缓存        Redis                                                  7.x              高性能缓存、Pub/Sub支持
  消息队列    Kafka                                                  3.x              高吞吐、持久化、流处理
  对象存储    MinIO                                                  最新稳定版       S3兼容、私有化部署
  容器化      Docker + Docker Compose                                最新稳定版       环境一致性、易于部署
  ----------- ------------------------------------------------------ ---------------- ------------------------------------------------------

七、目录结构规范

ai-education-platform/

├── docs/ \# 文档

│ ├── architecture/ \# 架构文档

│ ├── api/ \# API文档

│ └── requirements/ \# 需求文档

├── frontend/ \# 前端项目

│ ├── src/

│ │ ├── components/ \# 通用组件

│ │ ├── pages/ \# 页面组件

│ │ │ ├── Home/

│ │ │ ├── Learning/

│ │ │ └── Progress/

│ │ ├── services/ \# API服务

│ │ ├── stores/ \# 状态管理

│ │ └── utils/ \# 工具函数

│ ├── public/

│ └── package.json

├── backend/ \# 后端项目

│ ├── app/

│ │ ├── api/ \# API路由

│ │ │ └── v1/

│ │ ├── core/ \# 核心配置

│ │ ├── models/ \# 数据模型

│ │ ├── services/ \# 业务服务

│ │ ├── agents/ \# Agent实现

│ │ ├── repositories/ \# 数据访问

│ │ └── utils/ \# 工具函数

│ ├── alembic/ \# 数据库迁移

│ ├── tests/ \# 测试

│ ├── Dockerfile

│ └── requirements.txt

├── infrastructure/ \# 基础设施

│ └── docker/

├── scripts/ \# 脚本

├── .env.example

├── .gitignore

└── README.md

八、关键设计决策

  -------------------------------- -------------------------------------------------------------------------------------- -----------------------------------------------------------------------------------------
  **决策项**                       **决策内容**                                                                           **理由**
  Agent通信方式                    通过调度中心间接通信                                                                   解耦Agent、便于监控和重试
  行为记录策略                     实时记录 + 批量写入                                                                    保证实时性同时减少DB压力
  学习路径更新                     事件驱动实时更新                                                                       及时响应用户行为变化
  BKT/DKT选择                      BKT实时更新 + DKT离线训练                                                              BKT可解释性强，DKT精度高
  免费版策略                       核心功能全开放                                                                         让用户自然体验价值
  专业版增值                       挑战关卡 + 完整奖励 + 报告                                                             提供额外价值而非限制基础功能
  Prompt策略                       使用自定义Prompt直接调用LLM                                                            比Agent内置Prompt更精准可控
  流式输出                         SSE逐字渲染                                                                            大幅改善用户体感速度
  状态管理                         sessionStorage跨页面共享                                                               实现学习页与全景页无缝切换
  知识缓存                         内存字典缓存知识结构                                                                   避免重复调用LLM，支持组件名查找
  后台任务模式                     asyncio.create\_task立即返回+后台处理                                                  避免用户等待LLM响应，1秒内跳转学习页
  轮询机制                         前端2秒间隔轮询任务状态                                                                实时感知后台处理进度，及时更新UI
  Agent合并                        教学相关Agent合并为统一教学Agent                                                       减少通信开销，统一Prompt管理
  练习题内嵌模式（V1.2）           练习题在教学面板对话框内直接展示和作答，不弹出独立面板                                 减少页面切换，保持学习上下文连续性，提升用户体验
  完成状态实时同步（V1.2）         后端内存缓存记录完成状态 + 前端回调刷新机制                                            练习题完成后全景图谱和学习路径面板实时更新，无需手动刷新
  LLM数据文件持久化（V1.2）        以topic\_text的MD5为key，将全景介绍和知识结构保存为本地JSON文件                        相同主题不再重复调用LLM，大幅降低API成本和响应时间
  知识点讲解缓存（V1.2）           以component\_id的MD5为key，缓存LLM讲解全文；流式接口命中时模拟SSE分段输出              重复点击同一知识点不再调用LLM，响应从秒级降至毫秒级
  学习路径面板简化（V1.2）         只展示已完成知识点（第二层）和跳级建议，移除后续学习计划；全部完成时显示完成提示       减少信息噪音，聚焦学习进度；用户一目了然掌握完成情况
  学习页状态持久化（V1.2）         使用sessionStorage保存和恢复学习页状态（overviewMode、currentComponentIndex）          从全景页返回学习页时保持学习上下文，避免重新加载全景介绍
  按钮加载中可用（V1.2）           移除\"下一个知识组件\"和\"练习题\"按钮的isLoading禁用条件                              用户无需等待加载完成即可切换知识点或进入练习题，提升操作流畅度
  学习进度跨页面同步（V1.2）       使用sessionStorage标记+storage事件+轮询实现学习页与全景页进度同步                      学习完成后全景知识图谱和学习路径面板实时显示最新进度
  练习题空值安全修复（V1.2）       generate\_exercises端点中comp\_info为None时安全回退，避免NoneType调用.get()报500错误   修复用户直接点击练习题时因组件信息缓存未命中导致的500 Internal Server Error
  组件信息持久化查找增强（V1.2）   find\_component\_info增加子目录跳过、持久化查找日志记录，提升缓存未命中时的排查能力    服务重启或内存缓存失效后，能更可靠地从持久化文件恢复组件信息，减少练习题/讲解等功能异常
  -------------------------------- -------------------------------------------------------------------------------------- -----------------------------------------------------------------------------------------

**4.5.18 练习题500错误修复与持久化查找增强（V1.2修复）**

修复教学面板点击练习题时出现的500 Internal Server
Error错误。根因：generate\_exercises端点中，当find\_component\_info返回None时，代码直接对None调用.get(\"point\_name\",
\"\")导致AttributeError。方案1修复（learning.py第229行）：将comp\_info.get(\"point\_name\",
\"\")改为comp\_info.get(\"point\_name\", \"\") if comp\_info else
\"\"，与同函数中component\_name和block\_name的回退逻辑保持一致。方案2增强（knowledge\_cache.py的find\_component\_info函数）：在持久化文件查找逻辑中增加子目录跳过判断（排除explanations/目录），并添加debug/info级别日志记录，便于排查组件信息缓存命中情况。涉及文件：backend/app/api/v1/endpoints/learning.py（第229行空值安全修复）、backend/app/api/v1/endpoints/knowledge\_cache.py（find\_component\_info函数增加子目录跳过和日志记录）。

**4.5.19 全景知识图谱视图简化（V1.3）**

简化全景知识图谱页面，移除架构视图，只保留列表视图。修改内容：移除视图切换按钮及相关状态（viewMode），移除KnowledgeGraphArch组件的引用和CSS导入，主内容区直接渲染列表视图。保留KnowledgeGraphArch.tsx和KnowledgeGraphArch.css文件但不引用，便于将来可能恢复。涉及文件：frontend/src/components/PanoramaProgress/PanoramaProgress.tsx（移除import语句、viewMode状态、视图切换按钮、架构视图条件渲染）。

**4.5.20 知识讲解结构化JSON输出（V1.3）**

将知识讲解从流式纯文本输出改为结构化JSON输出，前端按8维度独立卡片渲染。后端新增EXPLAIN\_JSON\_PROMPT模板和explain\_knowledge\_json()方法，要求LLM按8个维度（定义、原理、示例、拆解、对比、错误、场景、口诀）输出JSON格式的sections数组。修改get\_explanation端点使用JSON讲解方法，返回结构化sections数据。前端TeachingPanel改为调用非流式getExplanation接口，按section渲染独立卡片（带图标、标题、内容）。新增ExplanationSection类型定义。缓存机制兼容新旧格式。保留原有流式方法（explain\_knowledge\_stream、get\_explanation\_stream端点、getExplanationStream前端方法）不删除。涉及文件：backend/app/agents/learning/unified\_teaching\_agent.py（新增EXPLAIN\_JSON\_PROMPT和explain\_knowledge\_json方法）、backend/app/api/v1/endpoints/learning.py（修改get\_explanation端点）、backend/app/api/v1/endpoints/knowledge\_cache.py（save\_explanation\_to\_file新增sections参数）、frontend/src/types/index.ts（新增ExplanationSection接口，ExplanationResponse增加sections字段）、frontend/src/services/api.ts（getExplanation适配结构化返回）、frontend/src/components/TeachingPanel/TeachingPanel.tsx（改为非流式调用+卡片渲染）、frontend/src/components/TeachingPanel/styles.css（新增8维度卡片样式）。

**4.5.21 知识讲解Prompt增加知识体系上下文（V1.3）**

在EXPLAIN\_JSON\_PROMPT中增加目标知识信息，从全景知识图谱中确认知识点（point\_name）和所属板块（block\_name）的名称，放入知识讲解prompt，使LLM能基于更完整的上下文生成更精准的讲解内容。修改explain\_knowledge\_json()方法新增point\_name和block\_name可选参数（默认空字符串，保持向后兼容）。修改get\_explanation端点通过find\_component\_info获取完整上下文并传入。同时修复缓存命中时result\_data类型不一致导致的AttributeError（list
object has no attribute
get）。涉及文件：backend/app/agents/learning/unified\_teaching\_agent.py（EXPLAIN\_JSON\_PROMPT增加block\_name/point\_name占位符，explain\_knowledge\_json增加参数）、backend/app/api/v1/endpoints/learning.py（get\_explanation传入point\_name/block\_name，修复缓存类型Bug）。

**4.5.22 练习题Prompt简化（V1.3）**

简化EXERCISE\_PROMPT，移除详细的题目类型分类（故障排查类、方案设计类、代码优化类、安全攻防类、工程实践类）和出题原则中的部分条目（场景新鲜、答案开放、紧跟趋势），简化实操性要求（移除工具/技术明确），简化当前学习内容信息的描述（知识组件改为知识，所属板块改为所属知识板块）。移除JSON输出中的category字段。使Prompt更加简洁聚焦。涉及文件：backend/app/agents/learning/unified\_teaching\_agent.py（EXERCISE\_PROMPT简化）。

**4.5.23 知识讲解Prompt简化（V1.3）**

简化EXPLAIN\_JSON\_PROMPT，将\"精讲单个知识组件\"改为\"精讲单个知识\"，简化目标知识信息描述（所属板块改为所属知识板块，当前知识组件改为当前知识），移除第8维度\"summary
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------

核心口诀\"及其JSON输出结构，使讲解维度从8个减为7个。涉及文件：backend/app/agents/learning/unified\_teaching\_agent.py（EXPLAIN\_JSON\_PROMPT简化）。

**4.5.24 一键启动脚本（V1.3）**

新增一键安装和启动脚本，方便用户快速部署和运行项目。创建install.sh/install.bat安装脚本（检测Python/Node环境、创建虚拟环境、安装依赖、创建.env文件）；创建start.sh/start.bat启动脚本（并行启动后端和前端、自动等待服务就绪、统一日志输出）；创建stop.sh/stop.bat停止脚本（优雅停止所有服务、清理残留进程）；创建.env.example环境变量模板。脚本支持Mac/Linux/Windows三平台，不影响原有代码和架构，纯新增文件。涉及文件：install.sh、install.bat、start.sh、start.bat、stop.sh、stop.bat、.env.example。

**4.5.25 练习题面板UI优化（V1.3）**

优化练习题面板的展示效果和交互体验。修改ExercisePanel.tsx：移除hints（提示信息）的显示逻辑，简化题目展示；添加questions-scroll-container容器包裹题目列表，将题目区域和提交按钮区域分离；将提交按钮移入submit-button-container容器，确保始终可见。修改styles.css：为exercise-panel添加flex布局和max-height限制；新增questions-scroll-container样式，添加overflow-y:
auto实现滚动，自定义滚动条样式（webkit-scrollbar）；新增submit-button-container样式，添加上边框和flex-shrink:
0确保按钮固定在底部。使题目过多时可滚动查看，提交按钮始终可见，界面更简洁。涉及文件：frontend/src/components/ExercisePanel/ExercisePanel.tsx、frontend/src/components/ExercisePanel/styles.css。

**4.5.26 教学面板按钮文字简化（V1.3）**

简化教学面板中\"下一个知识组件\"按钮的文字显示，改为\"下一个\"，使界面更简洁。修改TeachingPanel.tsx第230行，将按钮内的span文字从\"下一个知识\"改为\"下一个\"。涉及文件：frontend/src/components/TeachingPanel/TeachingPanel.tsx。

**4.5.27 开始学习按钮文字简化（V1.3）**

简化学习页全景概况中\"开始学习第一个知识组件\"按钮的文字显示，改为\"开始学习第一个知识\"，使界面更简洁。修改App.tsx第486行，将按钮内的span文字从\"开始学习第一个知识组件\"改为\"开始学习第一个知识\"。涉及文件：frontend/src/App.tsx。

**4.5.28 教学面板增加知识组件名称标题（V1.3）**

在教学面板顶部增加当前知识组件名称标题，知识讲解和练习题时均可看到。采用方案B：由父组件传入componentName。修改types/index.ts中TeachingPanelProps接口新增componentName可选属性。修改TeachingPanel.tsx：组件函数接收componentName参数，在teaching-panel-header区域渲染知识组件名称标签（紫色背景标签样式）。修改styles.css：新增teaching-panel-component-name样式（紫色文字、浅紫背景、圆角标签）。修改App.tsx：调用TeachingPanel时传入currentComponent.componentName。涉及文件：frontend/src/types/index.ts、frontend/src/components/TeachingPanel/TeachingPanel.tsx、frontend/src/components/TeachingPanel/styles.css、frontend/src/App.tsx。

**4.5.29 学习进度记忆系统（V1.3）**

新增基于localStorage的学习进度记忆系统，在全景知识页标记每个知识组件的学习状态和练习状态。新建frontend/src/utils/progressStorage.ts工具模块，提供getComponentProgress、markLearning、markLearnCompleted、markPracticing、markExercisePassed等函数，使用learn\_progress\_前缀存储在localStorage中。修改App.tsx：进入新知识组件时调用markLearning记录学习中状态。修改TeachingPanel.tsx：监听讲解内容区域滚动事件（onScroll），当滚到底部时调用markLearnCompleted记录完成学习。修改ExercisePanel.tsx：提交答案后根据correctCount与totalCount比较，全对调用markExercisePassed，不全对调用markPracticing。修改PanoramaProgress.tsx：每个知识组件按钮读取getComponentProgress，在按钮内渲染component-progress-tags区域，根据状态显示学习中（橙色）、完成（绿色）、做题中（橙色）、练习通过（绿色）四个文字标签。修改PanoramaProgress/styles.css：新增component-progress-tags容器样式和progress-tag标签样式（橙色/绿色两套配色）。涉及文件：frontend/src/utils/progressStorage.ts（新建）、frontend/src/App.tsx、frontend/src/components/TeachingPanel/TeachingPanel.tsx、frontend/src/components/ExercisePanel/ExercisePanel.tsx、frontend/src/components/PanoramaProgress/PanoramaProgress.tsx、frontend/src/components/PanoramaProgress/styles.css。

**4.5.30 修复 behavior API 地址（V1.3）**

修复 behavior.ts 中 API 请求地址缺少 /api/v1 前缀的问题。原代码中
recordBehavior 函数请求 /behavior/record，getBehaviorStats 函数请求
/behavior/stats/\${userId}，均缺少 /api/v1
前缀导致请求被发送到前端开发服务器而非后端 API
服务器。修改第40行和第108行，在路径前添加 /api/v1
前缀，使请求正确指向后端 http://localhost:8000/api/v1/behavior/record 和
http://localhost:8000/api/v1/behavior/stats/\${userId}。涉及文件：frontend/src/api/behavior.ts。

**4.5.31 删除知识点框右上角标记（V1.3）**

删除全景知识页中知识点框（黄色背景大框）右上角的\"重点\"和状态标记（\"未开始\"/\"学习中\"/\"已完成\"）。原设计中知识点框右上角显示\"重点\"徽章和状态文字，与知识组件的标记重复且界面拥挤。修改PanoramaProgress.tsx第187-196行，删除panorama-point-badge（\"重点\"标记）和panorama-point-status（状态文字）的渲染逻辑，只保留知识点编号和名称。重点/难点标记和学习进度标记统一在知识组件（小按钮）上显示。涉及文件：frontend/src/components/PanoramaProgress/PanoramaProgress.tsx。

**4.5.32 定制综合练习功能（V1.3）**

将学习路径面板改造为定制综合练习面板，支持用户选择多个知识点生成综合练习题。后端新建CustomExerciseAgent（backend/app/agents/learning/custom\_exercise.py），包含async
generate\_exercise方法（根据知识点列表生成综合练习题）和async
grade\_answers方法（批改用户答案），使用AgentLLMClient调用LLM。新增两个API端点：POST
/api/v1/custom-exercise/generate（生成练习题）和POST
/api/v1/custom-exercise/grade（批改答案）。在JWT认证中间件白名单中添加/api/v1/custom-exercise路径（backend/app/api/v1/middleware/auth.py）。修复unified\_teaching\_agent.py中explain\_knowledge\_json方法的Prompt参数名不匹配问题（knowledge改为component\_name）。前端新增类型定义：CustomQuestion、CustomExerciseSet、CustomGradeResult、CustomGradeReport。前端新增API调用函数：generateCustomExercise、gradeCustomExercise。重写LearningPathPanel.tsx：初始状态显示\"开始综合练习\"按钮，点击弹出知识点选择对话框（展示三层知识结构），用户选择知识点后生成练习题，展示题目并支持答题和提交，显示批改结果。更新styles.css：新增对话框样式、题目样式、批改结果样式。修改App.tsx：LearningPathPanel传入blocks参数。涉及文件：backend/app/agents/learning/custom\_exercise.py（新建）、backend/app/api/v1/endpoints/learning.py、backend/app/api/v1/middleware/auth.py、backend/app/agents/learning/unified\_teaching\_agent.py、frontend/src/types/index.ts、frontend/src/services/api.ts、frontend/src/components/LearningPathPanel/LearningPathPanel.tsx、frontend/src/components/LearningPathPanel/styles.css、frontend/src/App.tsx。
