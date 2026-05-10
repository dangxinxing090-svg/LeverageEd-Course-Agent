# AI 智能教育课程平台

基于多 Agent 协同架构的智能教育课程平台，支持知识体系自动拆解、个性化学习路径规划、AI 讲解与练习生成、学习行为分析等功能。后端 Agent 引擎支持 OpenAI、智谱 GLM、Kimi、通义千问、豆包等多种大模型，可灵活切换。

## 功能概览

| 模块 | 功能 | 说明 |
|------|------|------|
| 知识处理 | 知识拆分 / 难度标注 | 将学习主题自动拆解为「板块 → 知识点 → 知识组件」三层体系 |
| 学习支持 | 讲解 / 练习 / 批改 / 问答 | AI 生成通俗易懂的讲解内容、高难度实操性练习题，自动批改并答疑 |
| 路径规划 | 学习路径 / 跳级建议 | 根据用户画像生成个性化学习路径，支持跳级测试 |
| 激励系统 | 鼓励奖励 | 在关键学习节点生成个性化鼓励文案和积分奖励 |
| 行为分析 | 行为记录 / 学习画像 | 基于 BKT 模型追踪学习行为，输出活跃度与掌握度分析 |
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
│   │   │   ├── knowledge/            # 知识处理 Agent
│   │   │   │   ├── knowledge_split.py    # 知识拆分
│   │   │   │   └── difficulty_tag.py     # 难度标注
│   │   │   ├── learning/             # 学习支持 Agent（已合并为 UnifiedTeachingAgent）
│   │   │   │   ├── unified_teaching_agent.py  # 统一教学Agent（讲解/出题/批改/问答）
│   │   │   │   ├── exercise_generate.py       # 练习题生成（独立版本）
│   │   │   │   └── answer_grade.py            # 题目批改
│   │   │   ├── path_planning/        # 路径规划 Agent
│   │   │   │   ├── path_planning.py      # 学习路径规划
│   │   │   │   └── skip_suggest.py       # 跳级建议
│   │   │   ├── incentive/            # 激励系统 Agent
│   │   │   │   └── reward_generate.py    # 鼓励奖励生成
│   │   │   ├── behavior/             # 行为分析 Agent
│   │   │   │   ├── behavior_record.py    # 行为记录
│   │   │   │   └── behavior_analysis.py  # 行为分析（BKT 模型）
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
│   │       └── progress_repo.py     # 学习进度仓库
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
│   │   │   ├── ExercisePanel/        # 练习面板
│   │   │   ├── QAPanel/              # 问答面板
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

## 核心架构更新

### Agent 合并优化
- 将原有的 11 个独立 Agent 合并为 9 个，减少调度开销
- **UnifiedTeachingAgent** 统一负责：知识讲解、练习题生成、答案批改、实时问答
- 采用异步任务模式 + 轮询机制，提升响应速度

### 练习题升级
- 从简单选择题升级为**高难度实操性问答题**
- 支持 5 种题型：故障排查、方案设计、代码优化、安全攻防、工程实践
- 每次只出一道题，确保质量

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
| POST | `/api/v1/exercises/submit` | 提交练习答案 |
| POST | `/api/v1/qa/ask` | 提交问答（流式） |
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
