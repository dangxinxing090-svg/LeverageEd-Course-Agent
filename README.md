# AI 智能教育课程平台

基于多 Agent 协同架构的智能教育课程平台，支持知识体系自动拆解、个性化学习路径规划、AI 讲解与练习生成、学习行为分析等功能。后端 Agent 引擎支持 OpenAI、智谱 GLM、Kimi、通义千问、豆包等多种大模型，可灵活切换。

## 功能概览

| 模块 | 功能 | 说明 |
|------|------|------|
| 知识处理 | 知识拆分 / 难度标注 | 由 UnifiedTeachingAgent 统一负责，将学习主题自动拆解为三层体系 |
| 学习支持 | 讲解 / 练习 / 批改 | UnifiedTeachingAgent 生成7维度结构化讲解、实操性问答题，自动批改 |
| 综合练习 | 定制定制练习 / 批改 | CustomExerciseAgent 根据多知识点生成综合问答题并批改 |
| 路径规划 | 学习路径 / 跳级建议 | 在 API endpoint 层直接调用 LLM 实现 |
| 行为分析 | 学习画像 / 记忆压缩 | BehaviorAnalysisAgent 基于 BKT 模型分析，MemoryCompressionAgent 归档压缩 |
| 全景视图 | 知识图谱 / 架构图 | 分层架构图风格展示三层知识体系，支持交互式浏览 |

## 环境要求

| 依赖 | 最低版本 | 说明 |
|------|---------|------|
| Python | 3.10+ | 后端运行时 |
| Node.js | 18+ | 前端构建（React + TypeScript + Vite） |
| PostgreSQL | 14+ | 数据库（可选，当前使用内存存储） |
| Redis | 6+ | 缓存和限流（可选） |

## 快速开始

### 1. 克隆项目

```bash
git clone <repo-url>
cd ai-education-platform
```

### 2. 后端启动

```bash
# 进入后端目录
cd backend

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate   # Linux / macOS
# venv\Scripts\activate    # Windows

# 安装依赖
pip install -r requirements.txt --break-system-packages

# 启动服务（默认 0.0.0.0:8000）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

启动成功后可访问：
- API 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

### 3. 前端启动

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器（Vite）
npm start
```

前端默认运行在 `http://localhost:5173/`，API 请求会通过 Vite 代理到后端 `http://localhost:8000`。

### 4. 配置 LLM 模型（可选）

平台默认使用模拟模式运行，无需 API Key 即可测试全部 Agent 功能。如需接入真实大模型，选择以下任一方式配置：

**方式一：环境变量**

```bash
# 智谱 GLM（推荐国产首选）
export ZHIPU_API_KEY="your-zhipu-api-key"

# Kimi（Moonshot）
export KIMI_API_KEY="your-kimi-api-key"

# 通义千问
export QWEN_API_KEY="your-qwen-api-key"

# 豆包（字节跳动）
export DOUBAO_API_KEY="your-doubao-api-key"

# OpenAI
export OPENAI_API_KEY="your-openai-api-key"
```

**方式二：配置文件**

复制 `backend/app/agents/llm_providers/config.example.json` 为 `llm_config.json`，填入各模型的 API Key。

**方式三：安装对应 SDK**

```bash
pip install openai zhipuai dashscope --break-system-packages
```

### 5. 运行测试

```bash
cd backend

# 运行全部 Agent 测试（模拟模式，无需 API Key）
python tests/test_agents.py
```

## 项目结构

```
ai-education-platform/
├── backend/                          # 后端（Python / FastAPI）
│   ├── app/
│   │   ├── main.py                   # FastAPI 应用入口
│   │   ├── core/
│   │   │   ├── config.py             # 全局配置（端口、数据库、JWT 等）
│   │   │   └── exceptions.py         # 自定义异常
│   │   ├── agents/                   # Agent 引擎（核心）
│   │   │   ├── base.py               # Agent 基类、TaskRequest / TaskResult
│   │   │   ├── registry.py           # Agent 注册表
│   │   │   ├── dispatcher.py         # Agent 调度器
│   │   │   ├── dependency.py         # Agent 依赖管理
│   │   │   ├── aggregator.py         # 多 Agent 结果聚合
│   │   │   ├── error_handler.py      # Agent 错误处理
│   │   │   ├── knowledge/            # 知识处理模块（功能已合并至 UnifiedTeachingAgent）
│   │   │   ├── learning/             # 学习支持 Agent
│   │   │   │   ├── unified_teaching_agent.py  # 统一教学Agent（讲解/出题/批改）
│   │   │   │   └── custom_exercise.py        # 定制综合练习Agent
│   │   │   ├── path_planning/        # 路径规划模块（功能在 API endpoint 层实现）
│   │   │   ├── incentive/            # 激励系统模块（待开发）
│   │   │   ├── behavior/             # 行为分析 Agent
│   │   │   │   ├── behavior_analysis.py  # 行为分析（BKT 模型）
│   │   │   │   └── memory_compression.py # 记忆压缩
│   │   │   └── llm_providers/        # 多模型 Provider 层
│   │   │       ├── base.py               # Provider 抽象接口
│   │   │       ├── config.py             # 配置管理
│   │   │       ├── factory.py            # Provider 工厂
│   │   │       ├── agent_adapter.py      # Agent 适配器
│   │   │       ├── mock_client.py        # 模拟客户端（测试用）
│   │   │       ├── openai_provider.py    # OpenAI 适配器
│   │   │       ├── zhipu_provider.py     # 智谱 GLM 适配器
│   │   │       ├── kimi_provider.py      # Kimi 适配器
│   │   │       ├── qwen_provider.py      # 通义千问适配器
│   │   │       ├── doubao_provider.py    # 豆包适配器
│   │   │       └── config.example.json   # 配置示例
│   │   ├── api/                      # API 路由层
│   │   │   └── v1/
│   │   │       ├── endpoints/        # 接口端点
│   │   │       │   ├── topics.py     # 主题相关 API
│   │   │       │   ├── learning.py   # 学习相关 API
│   │   │       │   └── users.py      # 用户相关 API
│   │   │       └── middleware/       # 中间件
│   │   │           ├── auth.py       # JWT 认证
│   │   │           ├── rate_limiter.py # 限流
│   │   │           ├── logging.py    # 请求日志
│   │   │           ├── response.py   # 统一响应格式
│   │   │           └── router.py     # 路由注册
│   │   └── repositories/            # 数据访问层
│   │       ├── user_repo.py         # 用户数据仓库
│   │       ├── knowledge_repo.py    # 知识数据仓库
│   │       ├── progress_repo.py     # 学习进度仓库
│   │       └── exercise_repo.py     # 练习记录仓库（用户答题历史）
│   ├── tests/
│   │   └── test_agents.py           # Agent 系统测试脚本
│   └── requirements.txt             # Python 依赖
│
├── frontend/                         # 前端（React + TypeScript + Vite）
│   ├── src/
│   │   ├── components/               # UI 组件
│   │   │   ├── TopicInput/           # 主题输入
│   │   │   ├── TopicRecommendations/ # 推荐主题
│   │   │   ├── TeachingPanel/        # 教学面板
│   │   │   ├── ExercisePanel/        # 练习面板（含历史记录）
│   │   │   ├── ProgressPanel/        # 进度面板
│   │   │   ├── PanoramaProgress/     # 全景进度（含分层架构图）
│   │   │   │   ├── KnowledgeGraphArch.tsx     # 分层架构图组件
│   │   │   │   ├── KnowledgeGraphArch.css     # 架构图样式
│   │   │   │   ├── KnowledgeGraphV2.tsx       # 树形图谱组件
│   │   │   │   └── KnowledgeGraphV2.css       # 树形图谱样式
│   │   │   ├── LearningPathPanel/    # 学习路径
│   │   │   ├── LearningHistory/      # 学习历史
│   │   │   └── SkipTest/             # 跳级测试
│   │   ├── services/
│   │   │   └── api.ts                # API 调用封装
│   │   └── types/
│   │       └── index.ts              # TypeScript 类型定义
│   ├── index.html                    # Vite 入口 HTML
│   ├── vite.config.mjs               # Vite 配置
│   └── package.json                  # 前端依赖
│
├── prompts/                          # Prompt 设计文档
│   └── question_agent_prompt.md      # 出题 Agent Prompt 设计
│
└── docs/                             # 项目文档
    ├── AI智能教育课程平台_项目立项书.docx
    ├── AI智能教育课程平台_项目架构设计文档.docx
    ├── AI智能教育课程平台_任务拆解清单.docx
    └── AI智能教育课程平台_专家评审意见.docx
```

## 核心架构

### Agent 架构（精简后）

当前项目仅保留 4 个实际运行的 Agent，其余废弃 Agent 已删除：

| Agent | 文件 | 职责 | 是否需要 LLM |
|-------|------|------|:---:|
| **UnifiedTeachingAgent** | `learning/unified_teaching_agent.py` | 知识讲解（7维度）、练习题生成、答案批改、知识拆分 | ✅ |
| **CustomExerciseAgent** | `learning/custom_exercise.py` | 多知识点综合问答题生成与批改 | ✅ |
| **BehaviorAnalysisAgent** | `behavior/behavior_analysis.py` | 用户行为四维度分析、BKT 知识追踪、学习画像生成 | ❌ 纯代码 |
| **MemoryCompressionAgent** | `behavior/memory_compression.py` | 行为日志冷热分类、日/周聚合压缩 | ❌ 纯代码 |

### 已删除的废弃 Agent（10 个）

以下 Agent 已从代码库中移除，其功能已被其他实现替代：

| 废弃 Agent | 替代方案 |
|------------|----------|
| ContentExplainAgent | UnifiedTeachingAgent 内置讲解 |
| ExerciseGenerateAgent | UnifiedTeachingAgent 内置出题 |
| AnswerGradeAgent | UnifiedTeachingAgent 内置批改 |

| KnowledgeSplitAgent | UnifiedTeachingAgent.split_knowledge() |
| DifficultyTagAgent | UnifiedTeachingAgent 内联处理 |
| PathPlanningAgent | users.py endpoint 直接调用 LLM |
| SkipSuggestAgent | users.py / learning.py endpoint 直接调用 LLM |
| RewardGenerateAgent | 功能未实现，已删除 |
| BehaviorRecordAgent | behavior.py endpoint 直接操作数据库 |

### 练习题升级
- 从简单选择题升级为**高难度实操性问答题**
- 支持 5 种题型：故障排查、方案设计、代码优化、安全攻防、工程实践
- 每次只出一道题，确保质量
- **ExercisePanel 增强**：
  - 新增大文本域支持详细答题
  - 题目提示（Hints）展示功能
  - 知识点关联展示
  - 前后端类型兼容性优化
- **智能批改升级**（2025-05-18）：
  - LLM 批改传入完整上下文（知识主题 + 知识点 + 题目内容）
  - 批改结果包含：正确/错误判断、错误分析（指出哪里出错）、改进建议
  - 错题提供"查看正确答案"按钮，展开显示原题 + 正确答案
- **练习历史记录**（2025-05-18）：
  - 后端 `ExerciseRepository` 保存用户每次练习记录
  - 前端"做过的练习题"按钮查看历史列表
  - 点击列表项展开详情：原题 + 用户答案 + 正确答案 + 错误分析
- **学习页布局改造**（2025-05-19）：
  - 左侧新增"教学"和"综合练习"两个 Tab 按钮
  - 点击 Tab 切换显示对应面板，面板铺满学习页
  - 教学面板移除问答输入功能（智能答疑功能已删除）
- **删除智能答疑功能**（2025-05-19）：
  - 移除 QAPanel 组件及相关代码
  - 后端移除 `/qa/ask` 和 `/qa/ask/stream` 接口
  - UnifiedTeachingAgent 移除 `answer_question` 方法

### 全景知识图谱
- 新增**分层架构图**视图（蓝色系技术架构风格）
- 三层结构：L1 知识块（深蓝）→ L2 知识点（中蓝）→ L3 知识元（浅蓝）
- 支持展开/折叠、进度统计、重点标记

### 前端构建工具迁移
- 从 Create React App 迁移到 **Vite**
- 启动速度更快，热更新更及时
- 开发服务器默认端口：5173

## 支持的 LLM 模型

| 模型 | 厂商 | 默认模型 | SDK |
|------|------|---------|-----|
| OpenAI | 国际 | gpt-3.5-turbo | `openai` |
| 智谱 GLM | 国产 | glm-4 | `zhipuai` |
| Kimi | 国产 | moonshot-v1-8k | `openai`（兼容） |
| 通义千问 | 国产 | qwen-turbo | `dashscope` |
| 豆包 | 国产 | doubao-pro-4k | `openai`（兼容） |

## API 接口

后端启动后访问 `http://localhost:8000/docs` 查看完整 Swagger 文档，主要接口：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/topics` | 提交学习主题 |
| GET | `/api/v1/topics/recommend` | 获取推荐主题 |
| GET | `/api/v1/topics/{id}/structure` | 获取知识体系 |
| GET | `/api/v1/topics/{id}/overview` | 获取主题全景介绍 |
| GET | `/api/v1/knowledge/components/{id}/explanation` | 获取知识点讲解（流式） |
| GET | `/api/v1/exercises/generate` | 生成练习题 |
| POST | `/api/v1/exercises/submit` | 提交练习答案（单题批改，保存记录，返回 isCorrect/errorAnalysis/correctAnswer） |
| GET | `/api/v1/exercises/history` | 获取用户练习历史列表 |
| GET | `/api/v1/exercises/history/{record_id}` | 获取单条练习记录详情 |

| POST | `/api/v1/skip/test` | 发起跳级测试 |
| POST | `/api/v1/skip/test/submit` | 提交跳级测试 |
| GET | `/api/v1/users/{id}/history` | 获取学习历史 |
| GET | `/api/v1/learning-path` | 获取学习路径 |

## 技术栈

**后端**: Python 3.10 / FastAPI / Pydantic / SQLAlchemy / Redis

**前端**: React 18 / TypeScript / Vite / CSS Modules

**AI**: 多 Agent 协同架构 / BKT 知识追踪模型 / 多 LLM Provider 适配

## License

MIT
