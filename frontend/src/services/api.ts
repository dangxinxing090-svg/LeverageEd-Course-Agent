/**
 * API服务层
 * 
 * 核心职责：封装所有与后端API的交互逻辑
 * 包含：主题提交、推荐主题获取、跳级测试、知识点讲解等
 * 
 * 底层执行逻辑：
 * 1. 统一封装fetch请求，添加超时控制
 * 2. 统一错误处理，转换HTTP错误为业务错误
 * 3. 统一响应解析，处理JSON解析异常
 * 
 * 内存数据流转：
 * 输入: 业务参数 → 参数校验 → HTTP请求 → 后端处理
 * 输出: HTTP响应 → 响应解析 → 业务数据返回
 * 
 * 潜在风险：
 * 1. 网络超时：已添加10秒超时控制
 * 2. 后端不可用：返回标准化错误对象
 * 3. JSON解析失败：捕获异常并返回友好错误
 */

import {
  UUID,
  TopicInput,
  TopicOutput,
  RecommendedTopic,
  SkipTestInput,
  SkipTestOutput,
  SkipTestSubmitInput,
  SkipTestResult,
  ExplanationResponse,
  ApiResponse,
  TopicApiError,
  LearningHistoryItem,
  LearningPath,
  UserProgress,
  Question,
  Answer,
  ExerciseResult,
} from '../types';

// ============================================
// 配置常量
// ============================================

// API基础URL，从环境变量读取或使用默认值
const API_BASE_URL = import.meta.env.VITE_API_URL || '';

// 请求超时时间（毫秒）- LLM调用可能需要较长时间
const REQUEST_TIMEOUT = 120000;

// ============================================
// 工具函数
// ============================================

/**
 * 带超时的fetch请求
 * 
 * 底层执行逻辑：
 * 1. 创建AbortController用于取消请求
 * 2. 设置超时定时器，超时后触发abort
 * 3. 执行fetch请求
 * 4. 清理定时器，返回响应
 * 
 * 潜在风险：
 * 1. 内存泄漏：定时器未清理（已用try-finally确保）
 * 2. 竞态条件：多次请求同时触发（由调用方控制）
 * 
 * @param url 请求URL
 * @param options fetch选项
 * @returns Promise<Response>
 */
async function fetchWithTimeout(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

  // 如果外部传入了signal，当外部abort时也取消当前请求
  if (options.signal) {
    options.signal.addEventListener('abort', () => controller.abort());
  }

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    return response;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * 统一响应解析
 * 
 * 底层执行逻辑：
 * 1. 检查HTTP状态码，非2xx抛出错误
 * 2. 解析JSON响应体
 * 3. 检查业务状态码，非0抛出错误
 * 4. 返回标准化响应数据
 * 
 * 潜在风险：
 * 1. 响应体非JSON：捕获异常并抛出
 * 2. 响应体为空：返回空对象兜底
 * 
 * @param response fetch响应对象
 * @returns Promise<ApiResponse<T>>
 */
async function parseResponse<T>(response: Response): Promise<ApiResponse<T>> {
  // HTTP错误处理
  if (!response.ok) {
    throw new TopicApiError(
      `HTTP错误: ${response.status} ${response.statusText}`,
      response.status
    );
  }

  // 解析JSON
  let data: ApiResponse<T>;
  try {
    data = await response.json();
  } catch (error) {
    throw new TopicApiError('响应解析失败：无效的JSON格式', 500);
  }

  // 业务错误处理
  if (data.code !== 0) {
    throw new TopicApiError(
      data.message || '业务处理失败',
      data.code,
      data
    );
  }

  return data;
}

// ============================================
// U-001 首页主题输入组件 API
// ============================================

/**
 * 提交学习主题
 * U-001核心API调用
 * 
 * 底层执行逻辑：
 * 1. 校验输入参数（topic_text非空且长度<=500）
 * 2. 构造POST请求，Content-Type: application/json
 * 3. 发送请求到/api/v1/topics
 * 4. 解析响应，返回TopicOutput
 * 
 * 内存数据流转：
 * 输入: TopicInput → JSON序列化 → HTTP Body
 * 输出: HTTP Response → JSON解析 → TopicOutput
 * 
 * 潜在风险：
 * 1. 网络超时：fetchWithTimeout已处理
 * 2. 后端500错误：parseResponse会抛出TopicApiError
 * 3. 响应格式不符：TypeScript类型检查在编译期捕获
 * 
 * @param input 主题输入数据
 * @returns Promise<TopicOutput>
 */
export async function submitTopic(input: TopicInput): Promise<TopicOutput> {
  // 参数校验
  if (!input || !input.topic_text || input.topic_text.trim().length === 0) {
    throw new TopicApiError('参数错误：topic_text不能为空', 400);
  }
  if (input.topic_text.length > 500) {
    throw new TopicApiError('参数错误：topic_text长度不能超过500字符', 400);
  }

  const url = `${API_BASE_URL}/api/v1/topics`;

  const response = await fetchWithTimeout(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify(input),
  });

  const result = await parseResponse<TopicOutput>(response);
  return result.data;
}

// ============================================
// U-002 推荐主题列表组件 API
// ============================================

/**
 * 获取推荐主题列表
 * U-002核心API调用
 * 
 * 底层执行逻辑：
 * 1. 校验count参数（1-10，默认3）
 * 2. 构造GET请求，count作为查询参数
 * 3. 发送请求到/api/v1/topics/recommend
 * 4. 解析响应，返回RecommendedTopic数组
 * 
 * 内存数据流转：
 * 输入: count参数 → URL查询参数
 * 输出: HTTP Response → JSON解析 → RecommendedTopic[]
 * 
 * 潜在风险：
 * 1. count参数越界：已在函数内修正
 * 2. 返回空数组：业务层需处理空状态
 * 3. 网络抖动：fetchWithTimeout超时控制
 * 
 * @param count 推荐数量（1-10，默认3）
 * @returns Promise<RecommendedTopic[]>
 */
export async function getRecommendedTopics(count: number = 3): Promise<RecommendedTopic[]> {
  // 参数校验与修正
  const validCount = Math.max(1, Math.min(10, count));

  const url = `${API_BASE_URL}/api/v1/topics/recommend?count=${validCount}`;

  const response = await fetchWithTimeout(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
    },
  });

  const result = await parseResponse<RecommendedTopic[]>(response);
  return result.data || [];
}

/**
 * 获取默认推荐主题列表（兜底数据）
 * U-002兜底数据
 * 
 * 底层执行逻辑：
 * 1. 返回预定义的默认推荐主题列表
 * 2. 用于API请求失败时的降级展示
 * 
 * @returns RecommendedTopic[] 默认推荐主题数组
 */
export function getDefaultRecommendedTopics(): RecommendedTopic[] {
  return [
    {
      topic_id: 'default-001',
      topic_name: 'Python编程入门',
      description: '从零开始学习Python编程，掌握编程基础',
      category: '编程开发',
      difficulty: 'beginner',
      estimated_hours: 20,
    },
    {
      topic_id: 'default-002',
      topic_name: '数据分析基础',
      description: '学习数据分析的核心概念和常用工具',
      category: '数据科学',
      difficulty: 'beginner',
      estimated_hours: 15,
    },
    {
      topic_id: 'default-003',
      topic_name: '产品经理实战',
      description: '掌握产品设计和项目管理的核心技能',
      category: '产品管理',
      difficulty: 'intermediate',
      estimated_hours: 25,
    },
    {
      topic_id: 'default-004',
      topic_name: '机器学习入门',
      description: '了解机器学习的基本原理和常见算法',
      category: '人工智能',
      difficulty: 'intermediate',
      estimated_hours: 30,
    },
    {
      topic_id: 'default-005',
      topic_name: '前端开发基础',
      description: '学习HTML、CSS和JavaScript基础知识',
      category: '编程开发',
      difficulty: 'beginner',
      estimated_hours: 25,
    },
    {
      topic_id: 'default-006',
      topic_name: '项目管理精要',
      description: '掌握敏捷开发和项目管理方法论',
      category: '管理技能',
      difficulty: 'intermediate',
      estimated_hours: 12,
    },
  ];
}

// ============================================
// U-007 跳级测试组件 API
// ============================================

/**
 * 发起跳级测试
 * U-007核心API调用
 * 
 * 底层执行逻辑：
 * 1. 校验topic_id和user_id参数
 * 2. 构造POST请求
 * 3. 发送请求到/api/v1/skip/test
 * 4. 解析响应，返回跳级测试数据
 * 
 * 内存数据流转：
 * 输入: SkipTestInput → JSON序列化 → HTTP Body
 * 输出: HTTP Response → JSON解析 → SkipTestOutput
 * 
 * 潜在风险：
 * 1. 用户未登录：后端返回401，需跳转登录页
 * 2. 主题不存在：后端返回404
 * 3. 测试进行中：后端返回409，需等待或取消
 * 
 * @param input 跳级测试输入
 * @returns Promise<SkipTestOutput>
 */
export async function initiateSkipTest(input: SkipTestInput): Promise<SkipTestOutput> {
  // 参数校验
  if (!input || !input.topic_id) {
    throw new TopicApiError('参数错误：topic_id不能为空', 400);
  }
  if (!input.user_id) {
    throw new TopicApiError('参数错误：user_id不能为空', 400);
  }

  const url = `${API_BASE_URL}/api/v1/skip/test`;

  const response = await fetchWithTimeout(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify(input),
  });

  const result = await parseResponse<SkipTestOutput>(response);
  return result.data;
}

/**
 * 创建跳级测试（兼容旧组件接口）
 * @deprecated 请使用 initiateSkipTest
 */
export async function createSkipTest(input: { user_id: string; target_point_id: string }): Promise<SkipTestOutput> {
  // 适配旧接口：target_point_id 映射为 topic_id
  return initiateSkipTest({
    user_id: input.user_id as UUID,
    topic_id: input.target_point_id as UUID,
  });
}

/**
 * 提交跳级测试答案
 * U-007核心API调用
 * 
 * 底层执行逻辑：
 * 1. 校验test_id、user_id和answers数组
 * 2. 构造POST请求
 * 3. 发送请求到/api/v1/skip/test/submit
 * 4. 解析响应，返回跳级测试结果
 * 
 * 内存数据流转：
 * 输入: SkipTestSubmitInput → JSON序列化 → HTTP Body
 * 输出: HTTP Response → JSON解析 → SkipTestResult
 * 
 * 潜在风险：
 * 1. answers数组长度需与题目数一致
 * 2. 网络中断可能导致答案丢失
 * 
 * @param input 测试提交数据
 * @returns Promise<SkipTestResult>
 */
export async function submitSkipTest(input: SkipTestSubmitInput): Promise<SkipTestResult> {
  // 参数校验
  if (!input || !input.test_id || typeof input.test_id !== 'string') {
    throw new TopicApiError('参数错误：test_id必须为有效UUID', 400);
  }
  if (!input.user_id || typeof input.user_id !== 'string') {
    throw new TopicApiError('参数错误：user_id必须为有效UUID', 400);
  }
  if (!Array.isArray(input.answers) || input.answers.length === 0) {
    throw new TopicApiError('参数错误：answers必须为非空数组', 400);
  }

  const url = `${API_BASE_URL}/api/v1/skip/test/submit`;

  const response = await fetchWithTimeout(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify(input),
  });

  const result = await parseResponse<SkipTestResult>(response);
  return result.data;
}

// ============================================
// U-004 教学面板组件 API
// ============================================

/**
 * 获取知识点讲解内容（结构化JSON格式，8维度卡片展示）
 * U-004核心API调用
 *
 * @param componentId 知识组件ID
 * @param userLevel 用户水平（可选）
 * @returns Promise<ExplanationResponse>
 */
export async function getExplanation(
  componentId: string,
  userLevel?: string
): Promise<ExplanationResponse> {
  // 参数校验
  if (!componentId || typeof componentId !== 'string') {
    throw new TopicApiError('参数错误：componentId必须为有效UUID', 400);
  }

  let url = `${API_BASE_URL}/api/v1/knowledge/components/${encodeURIComponent(componentId)}/explanation`;

  // 添加user_level查询参数
  if (userLevel) {
    url += `?user_level=${encodeURIComponent(userLevel)}`;
  }

  const response = await fetchWithTimeout(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
    },
  });

  const result = await parseResponse<ExplanationResponse>(response);

  // 边界条件：后端返回的data为null时兜底为默认值
  if (!result.data) {
    return {
      component_id: componentId,
      sections: [],
      teaching_method: '',
    };
  }

  return result.data;
}

/**
 * 流式获取知识点讲解 (SSE)
 */
export async function getExplanationStream(
  componentId: string,
  userLevel: string = 'BEGINNER',
  onChunk: (text: string) => void,
  signal?: AbortSignal
): Promise<string> {
  const url = `${API_BASE_URL}/api/v1/learning/knowledge/components/${encodeURIComponent(componentId)}/explanation/stream?user_level=${encodeURIComponent(userLevel)}`;

  const response = await fetch(url, {
    method: 'GET',
    headers: { 'Accept': 'text/event-stream' },
    signal,
  });

  if (!response.ok) {
    throw new TopicApiError(`HTTP ${response.status}`, response.status);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new TopicApiError('无法读取响应流', 0);

  const decoder = new TextDecoder();
  let fullText = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value, { stream: true });
    // Parse SSE data lines
    const lines = chunk.split('\n');
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        if (data === '[DONE]') continue;
        if (data.startsWith('[ERROR]')) {
          throw new TopicApiError(data.slice(7), 500);
        }
        fullText += data;
        onChunk(data);
      }
    }
  }

  return fullText;
}

// ============================================
// U-008 学习历史组件 API
// ============================================

/**
 * 获取用户学习历史
 * U-008核心API调用
 *
 * 底层执行逻辑：
 * 1. 校验userId参数
 * 2. 构造GET请求
 * 3. 发送请求到/api/v1/users/{userId}/history
 * 4. 解析响应，返回学习历史记录数组
 *
 * 内存数据流转：
 * 输入: userId → URL路径参数
 * 输出: HTTP Response → JSON解析 → LearningHistoryItem[]
 *
 * 潜在风险：
 * 1. userId不存在：后端返回404
 * 2. 无历史记录：返回空数组
 * 3. 数据量大：需分页处理（当前版本未实现）
 *
 * @param userId 用户ID
 * @returns Promise<LearningHistoryItem[]>
 */
/**
 * 获取用户学习历史（别名，兼容旧组件）
 * @deprecated 请使用 getLearningHistory
 */
export async function getUserTopicHistory(userId: string): Promise<LearningHistoryItem[]> {
  return getLearningHistory(userId);
}

// ============================================
// U-004 全景进度组件 API
// ============================================

import { KnowledgeBlock } from '../types';

/**
 * 获取主题知识结构
 * U-004核心API调用
 *
 * 底层执行逻辑：
 * 1. 校验topicId和userId参数
 * 2. 构造GET请求
 * 3. 发送请求到/api/v1/topics/{topicId}/structure
 * 4. 解析响应，返回知识板块数组
 *
 * 内存数据流转：
 * 输入: topicId, userId → URL路径参数
 * 输出: HTTP Response → JSON解析 → KnowledgeBlock[]
 *
 * 潜在风险：
 * 1. topicId不存在：后端返回404
 * 2. userId无权限：后端返回403
 * 3. 数据结构不符：TypeScript类型检查
 *
 * @param topicId 主题ID
 * @param userId 用户ID
 * @returns Promise<KnowledgeBlock[]>
 */
export async function getTopicStructure(topicId: string, userId: string): Promise<KnowledgeBlock[]> {
  // 参数校验
  if (!topicId || typeof topicId !== 'string') {
    throw new TopicApiError('参数错误：topicId必须为有效UUID', 400);
  }
  if (!userId || typeof userId !== 'string') {
    throw new TopicApiError('参数错误：userId必须为有效UUID', 400);
  }

  const url = `${API_BASE_URL}/api/v1/topics/${encodeURIComponent(topicId)}/structure?user_id=${encodeURIComponent(userId)}`;

  const response = await fetchWithTimeout(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
    },
  });

  const result = await parseResponse<KnowledgeBlock[]>(response);
  return result.data || [];
}

/**
 * 获取主题全景介绍
 */
export async function getTopicOverview(topicId: string): Promise<{ topic_id: string; topic_name: string; overview: string }> {
  if (!topicId || typeof topicId !== 'string') {
    throw new TopicApiError('参数错误：topicId不能为空', 400);
  }

  const url = `${API_BASE_URL}/api/v1/topics/${encodeURIComponent(topicId)}/overview`;

  const response = await fetchWithTimeout(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
    },
  });

  const result = await parseResponse<{ topic_id: string; topic_name: string; overview: string }>(response);
  return result.data || { topic_id: topicId, topic_name: '', overview: '' };
}

/**
 * 查询主题处理状态
 * 用于轮询后台LLM处理进度（overview和structure是否已生成）
 *
 * @param topicId 主题ID
 * @returns Promise<{ topic_id: string; structure_ready: boolean; overview_ready: boolean; status: string }>
 */
export async function getTopicStatus(topicId: string): Promise<{ topic_id: string; structure_ready: boolean; overview_ready: boolean; status: string }> {
  const url = `${API_BASE_URL}/api/v1/topics/${encodeURIComponent(topicId)}/status`;
  const response = await fetchWithTimeout(url, { method: 'GET', headers: { 'Accept': 'application/json' } });
  const result = await parseResponse<{ topic_id: string; structure_ready: boolean; overview_ready: boolean; status: string }>(response);
  return result.data || { topic_id: topicId, structure_ready: false, overview_ready: false, status: 'processing' };
}

// ============================================
// U-003 问答面板组件 API
// ============================================

export async function getLearningHistory(userId: string): Promise<LearningHistoryItem[]> {
  // 参数校验
  if (!userId || typeof userId !== 'string') {
    throw new TopicApiError('参数错误：userId必须为有效UUID', 400);
  }

  const url = `${API_BASE_URL}/api/v1/users/${encodeURIComponent(userId)}/history`;

  const response = await fetchWithTimeout(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
    },
  });

  const result = await parseResponse<LearningHistoryItem[]>(response);
  return result.data || [];
}

// ============================================
// U-006 学习路径面板组件 API
// ============================================

/**
 * 获取用户学习路径
 * U-006核心API调用
 *
 * 底层执行逻辑：
 * 1. 校验userId和topicId参数
 * 2. 构造GET请求，topic_id作为查询参数
 * 3. 发送请求到/api/v1/users/{userId}/learning-path
 * 4. 解析响应，返回学习路径数据
 *
 * 内存数据流转：
 * 输入: userId, topicId → URL路径和查询参数
 * 输出: HTTP Response → JSON解析 → LearningPath
 *
 * 潜在风险：
 * 1. 用户未学习该主题：返回空路径
 * 2. topicId无效：后端返回404
 * 3. 权限不足：后端返回403
 *
 * @param userId 用户ID
 * @param topicId 主题ID
 * @returns Promise<LearningPath>
 */
export async function getLearningPath(userId: string, topicId: string): Promise<LearningPath> {
  // 参数校验
  if (!userId || typeof userId !== 'string') {
    throw new TopicApiError('参数错误：userId必须为有效UUID', 400);
  }
  if (!topicId || typeof topicId !== 'string') {
    throw new TopicApiError('参数错误：topicId必须为有效UUID', 400);
  }

  const url = `${API_BASE_URL}/api/v1/users/${encodeURIComponent(userId)}/learning-path?topic_id=${encodeURIComponent(topicId)}`;

  const response = await fetchWithTimeout(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
    },
  });

  const result = await parseResponse<LearningPath>(response);

  // 边界条件：后端返回的data为null时兜底为默认值
  if (!result.data) {
    return {
      completed_points: [],
      next_plan: [],
      skip_suggestions: [],
    };
  }

  return result.data;
}

// ============================================
// U-005 学习进度面板组件 API
// ============================================

/**
 * 获取用户学习进度
 * U-005核心API调用
 *
 * 底层执行逻辑：
 * 1. 校验userId参数
 * 2. 构造GET请求
 * 3. 发送请求到/api/v1/users/{userId}/progress
 * 4. 解析响应，返回学习进度数据
 *
 * 内存数据流转：
 * 输入: userId → URL路径参数
 * 输出: HTTP Response → JSON解析 → UserProgress
 *
 * 潜在风险：
 * 1. userId不存在：后端返回404
 * 2. 无学习记录：返回全0进度
 * 3. 数据精度：百分比使用整数存储
 *
 * @param userId 用户ID
 * @returns Promise<UserProgress>
 */
export async function getUserProgress(userId: string): Promise<UserProgress> {
  // 参数校验
  if (!userId || typeof userId !== 'string') {
    throw new TopicApiError('参数错误：userId必须为有效UUID', 400);
  }

  const url = `${API_BASE_URL}/api/v1/users/${encodeURIComponent(userId)}/progress`;

  const response = await fetchWithTimeout(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
    },
  });

  const result = await parseResponse<UserProgress>(response);

  // 边界条件：后端返回的data为null时兜底为默认值
  if (!result.data) {
    return {
      total_progress: 0,
      key_point_progress: 0,
      difficulty_progress: 0,
    };
  }

  return result.data;
}

// ============================================
// U-024 练习题面板组件 API
// ============================================

/**
 * 生成练习题
 * U-024核心API调用
 *
 * 底层执行逻辑：
 * 1. 校验pointId和totalQuestions参数
 * 2. 构造GET请求，total_questions作为查询参数
 * 3. 发送请求到/api/v1/exercises/generate
 * 4. 解析响应，返回题目数组
 *
 * 内存数据流转：
 * 输入: componentId, totalQuestions → URL查询参数
 * 输出: HTTP Response → JSON解析 → Question[]
 *
 * 潜在风险：
 * 1. componentId不存在：后端返回404
 * 2. 题目数量不足：返回实际可生成的题目数
 * 3. 网络超时：fetchWithTimeout已处理
 *
 * @param componentId 知识组件ID
 * @param totalQuestions 题目数量
 * @param signal AbortController信号，用于取消请求
 * @returns Promise<{ questions: Question[] }>
 */
export async function generateExercises(
  componentId: string,
  totalQuestions: number,
  signal?: AbortSignal
): Promise<{ questions: Question[] }> {
  // 参数校验
  if (!componentId || typeof componentId !== 'string') {
    throw new TopicApiError('参数错误：componentId必须为有效字符串', 400);
  }
  if (!totalQuestions || totalQuestions < 1) {
    throw new TopicApiError('参数错误：totalQuestions必须大于0', 400);
  }

  const url = `${API_BASE_URL}/api/v1/exercises/generate?component_id=${encodeURIComponent(componentId)}&total_questions=${totalQuestions}`;

  const response = await fetchWithTimeout(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
    },
    signal,
  });

  const result = await parseResponse<{ questions: Question[] }>(response);
  return result.data || { questions: [] };
}

/**
 * 提交答案
 * U-024核心API调用
 *
 * 底层执行逻辑：
 * 1. 校验pointId和answers数组
 * 2. 构造POST请求
 * 3. 发送请求到/api/v1/exercises/submit
 * 4. 解析响应，返回答题结果
 *
 * 内存数据流转：
 * 输入: pointId, answers → JSON序列化 → HTTP Body
 * 输出: HTTP Response → JSON解析 → ExerciseResult
 *
 * 潜在风险：
 * 1. answers数组为空：前端校验拦截
 * 2. 答案格式错误：后端返回400
 * 3. 重复提交：后端幂等处理
 *
 * @param componentId 知识组件ID
 * @param answers 答案数组
 * @returns Promise<ExerciseResult>
 */
export async function submitAnswers(
  componentId: string,
  answers: Answer[],
  questionContent: string = ""
): Promise<ExerciseResult> {
  // 参数校验
  if (!componentId || typeof componentId !== 'string') {
    throw new TopicApiError('参数错误：componentId必须为有效字符串', 400);
  }
  if (!Array.isArray(answers) || answers.length === 0) {
    throw new TopicApiError('参数错误：answers必须为非空数组', 400);
  }

  const url = `${API_BASE_URL}/api/v1/exercises/submit`;

  const response = await fetchWithTimeout(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify({ component_id: componentId, answers, question_content: questionContent, user_id: 'default_user' }),
  });

  const result = await parseResponse<ExerciseResult>(response);
  return result.data;
}

// ============================================
// 练习历史记录 API
// ============================================

/**
 * 获取用户练习历史记录
 */
export async function getExerciseHistory(
  userId: string = 'default_user',
  limit: number = 50
): Promise<import('../types').ExerciseHistoryResponse> {
  const url = `${API_BASE_URL}/api/v1/exercises/history?user_id=${encodeURIComponent(userId)}&limit=${limit}`;

  const response = await fetchWithTimeout(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
    },
  });

  const result = await parseResponse<import('../types').ExerciseHistoryResponse>(response);
  return result.data;
}

/**
 * 获取单条练习记录详情
 */
export async function getExerciseDetail(
  recordId: string,
  userId: string = 'default_user'
): Promise<import('../types').ExerciseRecord> {
  const url = `${API_BASE_URL}/api/v1/exercises/history/${recordId}?user_id=${encodeURIComponent(userId)}`;

  const response = await fetchWithTimeout(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
    },
  });

  const result = await parseResponse<import('../types').ExerciseRecord>(response);
  return result.data;
}

// ============================================
// 定制综合练习 API
// ============================================

/**
 * 生成综合练习题
 * @param pointNames 知识点名称列表
 * @param totalQuestions 题目总数
 * @returns Promise<CustomExerciseSet>
 */
export async function generateCustomExercise(
  topicName: string,
  pointNames: string[]
): Promise<import('../types').CustomExerciseSet> {
  if (!Array.isArray(pointNames) || pointNames.length === 0) {
    throw new TopicApiError('参数错误：pointNames必须为非空数组', 400);
  }

  const url = `${API_BASE_URL}/api/v1/custom-exercise/generate`;

  const response = await fetchWithTimeout(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify({ topic_name: topicName, point_names: pointNames }),
  });

  const result = await parseResponse<import('../types').CustomExerciseSet>(response);
  return result.data;
}

/**
 * 批改综合练习题
 * @param exerciseId 练习ID
 * @param questions 题目列表
 * @param answers 用户答案
 * @returns Promise<CustomGradeReport>
 */
export async function gradeCustomExercise(
  exerciseId: string,
  questions: import('../types').CustomQuestion[],
  answers: Record<string, string>
): Promise<import('../types').CustomGradeReport> {
  if (!exerciseId) {
    throw new TopicApiError('参数错误：exerciseId必须为有效字符串', 400);
  }

  const url = `${API_BASE_URL}/api/v1/custom-exercise/grade`;

  const response = await fetchWithTimeout(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify({ exercise_id: exerciseId, questions, answers }),
  });

  const result = await parseResponse<import('../types').CustomGradeReport>(response);
  return result.data;
}

// ============================================
// 教学Session API (对话式教学)
// ============================================

export interface Session {
  id: string;
  user_id: string;
  topic_id: string;
  topic_name: string;
  status: string;
  current_component_id?: string;
  current_component_name?: string;
  learned_components: string[];
  created_at: string;
  last_message_at: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  message_type: string;
  content: string;
  structured_content?: any[];
  component_id?: string;
  component_name?: string;
  metadata?: any;
  created_at: string;
}

/**
 * 获取或创建Session
 * 每个主题对应一个Session
 */
export async function getOrCreateSession(
  userId: string,
  topicId: string,
  topicName: string,
  maxRetries: number = 2
): Promise<Session> {
  const url = `${API_BASE_URL}/api/v1/sessions`;
  const requestBody = JSON.stringify({ user_id: userId, topic_id: topicId, topic_name: topicName });

  let lastError: Error | null = null;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      if (attempt > 0) {
        // 重试前等待，递增延迟
        await new Promise(resolve => setTimeout(resolve, 1000 * attempt));
      }
      const response = await fetchWithTimeout(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: requestBody,
      });

      const result = await parseResponse<any>(response);
      // 后端返回 session_id，前端接口期望 id，做字段映射
      const data = result.data;
      if (data.session_id && !data.id) {
        data.id = data.session_id;
      }
      return data as Session;
    } catch (error) {
      lastError = error as Error;
      // 只对服务端错误重试（500/502/503/504），客户端错误不重试
      if (error instanceof TopicApiError && error.status >= 400 && error.status < 500) {
        break;
      }
    }
  }
  throw lastError;
}

/**
 * 获取Session详情
 */
export async function getSession(sessionId: string, includeMessages: boolean = true): Promise<Session & { messages?: ChatMessage[] }> {
  const url = `${API_BASE_URL}/api/v1/sessions/${sessionId}?include_messages=${includeMessages}`;

  const response = await fetchWithTimeout(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
    },
  });

  const result = await parseResponse<Session & { messages?: ChatMessage[] }>(response);
  return result.data;
}

/**
 * 获取Session消息列表
 */
export async function getSessionMessages(sessionId: string, limit: number = 50): Promise<ChatMessage[]> {
  const url = `${API_BASE_URL}/api/v1/sessions/${sessionId}/messages?limit=${limit}`;

  const response = await fetchWithTimeout(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
    },
  });

  const result = await parseResponse<{ messages: ChatMessage[] }>(response);
  return result.data?.messages || [];
}

/**
 * 切换当前知识组件
 */
export async function switchComponent(
  sessionId: string,
  componentId: string,
  componentName: string
): Promise<Session> {
  const url = `${API_BASE_URL}/api/v1/sessions/${sessionId}/component`;

  const response = await fetchWithTimeout(url, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify({ component_id: componentId, component_name: componentName }),
  });

  const result = await parseResponse<Session>(response);
  return result.data;
}

/**
 * 发送聊天消息 (SSE流式响应)
 */
export async function sendChatMessage(
  sessionId: string,
  content: string,
  onChunk: (chunk: string) => void,
  messageType: string = 'chat',
  componentId?: string,
  componentName?: string,
  signal?: AbortSignal
): Promise<string> {
  const url = `${API_BASE_URL}/api/v1/sessions/${sessionId}/chat`;

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
    },
    body: JSON.stringify({
      content,
      message_type: messageType,
      component_id: componentId,
      component_name: componentName,
    }),
    signal,
  });

  if (!response.ok) {
    throw new TopicApiError(`HTTP ${response.status}`, response.status);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new TopicApiError('无法读取响应流', 0);

  const decoder = new TextDecoder();
  let fullContent = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value, { stream: true });
    const lines = chunk.split('\n');
    
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        try {
          const parsed = JSON.parse(data);
          if (parsed.chunk) {
            fullContent += parsed.chunk;
            onChunk(parsed.chunk);
          } else if (parsed.done) {
            return fullContent;
          } else if (parsed.error) {
            throw new TopicApiError(parsed.error, 500);
          }
        } catch (e) {
          // 忽略解析错误，继续处理
        }
      }
    }
  }

  return fullContent;
}

/**
 * 生成全景介绍 (SSE流式响应)
 * 模拟用户发送"请介绍{主题}的全景知识"消息
 */
export async function generateOverview(
  sessionId: string,
  onChunk?: (data: any) => void,
  signal?: AbortSignal
): Promise<{ content: string }> {
  const url = `${API_BASE_URL}/api/v1/sessions/${sessionId}/overview`;

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
    },
    signal,
  });

  if (!response.ok) {
    throw new TopicApiError(`HTTP ${response.status}`, response.status);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new TopicApiError('无法读取响应流', 0);

  const decoder = new TextDecoder();
  let fullContent = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value, { stream: true });
    const lines = chunk.split('\n');
    
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        try {
          const parsed = JSON.parse(data);
          if (parsed.content) {
            fullContent = parsed.content;
            onChunk?.(parsed);
          } else if (parsed.done) {
            return { content: fullContent };
          } else if (parsed.error) {
            throw new TopicApiError(parsed.error, 500);
          }
        } catch (e) {
          // 忽略解析错误
        }
      }
    }
  }

  return { content: fullContent };
}

/**
 * 获取知识组件讲解 (SSE流式响应)
 * 每次都调用LLM生成，不依赖缓存
 */
export async function explainComponent(
  sessionId: string,
  componentId: string,
  componentName: string,
  onChunk: (data: any) => void,
  signal?: AbortSignal
): Promise<{ sections: any[]; is_cached: boolean }> {
  const url = `${API_BASE_URL}/api/v1/sessions/${sessionId}/explain`;

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
    },
    body: JSON.stringify({ component_id: componentId, component_name: componentName }),
    signal,
  });

  if (!response.ok) {
    throw new TopicApiError(`HTTP ${response.status}`, response.status);
  }

  // SSE流式响应（后端总是返回SSE，不再检查缓存）
  const reader = response.body?.getReader();
  if (!reader) throw new TopicApiError('无法读取响应流', 0);

  const decoder = new TextDecoder();
  let fullData: any = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value, { stream: true });
    const lines = chunk.split('\n');
    
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        try {
          const parsed = JSON.parse(data);
          if (parsed.sections) {
            fullData = parsed;
            onChunk(parsed);
          } else if (parsed.done && fullData) {
            return { sections: fullData.sections || [], is_cached: false };
          } else if (parsed.error) {
            throw new TopicApiError(parsed.error, 500);
          }
        } catch (e) {
          // 忽略解析错误
        }
      }
    }
  }

  return fullData || { sections: [], is_cached: false };
}

/**
 * 生成练习题 (SSE流式响应)
 */
export async function generateExercise(
  sessionId: string,
  componentId?: string,
  onChunk?: (data: any) => void,
  signal?: AbortSignal
): Promise<{ question: any }> {
  const url = `${API_BASE_URL}/api/v1/sessions/${sessionId}/exercise`;

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
    },
    body: JSON.stringify({ component_id: componentId }),
    signal,
  });

  if (!response.ok) {
    throw new TopicApiError(`HTTP ${response.status}`, response.status);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new TopicApiError('无法读取响应流', 0);

  const decoder = new TextDecoder();
  let fullData: any = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value, { stream: true });
    const lines = chunk.split('\n');
    
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        try {
          const parsed = JSON.parse(data);
          if (parsed.question) {
            fullData = parsed;
            onChunk?.(parsed);
          } else if (parsed.done && fullData) {
            return { question: fullData.question };
          } else if (parsed.error) {
            throw new TopicApiError(parsed.error, 500);
          }
        } catch (e) {
          // 忽略解析错误
        }
      }
    }
  }

  return fullData || { question: null };
}

/**
 * 提交练习题答案
 */
export async function submitExerciseAnswer(
  sessionId: string,
  questionContent: string,
  userAnswer: string,
  componentId?: string
): Promise<{
  is_correct: boolean;
  score: number;
  feedback: string;
  error_analysis: string;
  correct_answer: string;
}> {
  const url = `${API_BASE_URL}/api/v1/sessions/${sessionId}/exercise/submit`;

  const response = await fetchWithTimeout(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify({
      question_content: questionContent,
      user_answer: userAnswer,
      component_id: componentId,
    }),
  });

  const result = await parseResponse<{
    is_correct: boolean;
    score: number;
    feedback: string;
    error_analysis: string;
    correct_answer: string;
  }>(response);
  
  return result.data;
}
