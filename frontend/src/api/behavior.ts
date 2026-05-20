/**
 * 行为记录API
 * 用于发送用户学习行为到后端
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || "";

/**
 * 行为类型
 */
export type BehaviorType =
  | "learn"      // 学习行为
  | "question"   // 提问行为
  | "practice"   // 练习行为
  | "skip"       // 跳级行为
  | "interact";  // 交互行为

/**
 * 组件状态类型
 */
export type ComponentStatusType = 'in_progress' | 'learn_completed' | 'practicing' | 'exercise_passed';

/**
 * 行为记录请求参数
 */
export interface BehaviorRecordRequest {
  user_id: string;
  session_id?: string;
  behavior_type: BehaviorType;
  topic_id?: string;
  point_id?: string;
  component_id?: string;
  details?: Record<string, any>;
}

/**
 * 记录用户行为
 * @param data 行为数据
 * @returns 记录结果
 */
export async function recordBehavior(data: BehaviorRecordRequest): Promise<{
  code: number;
  data: { log_id: string; message: string };
}> {
  const response = await fetch(`${API_BASE_URL}/api/v1/behavior/record`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    throw new Error(`记录行为失败: ${response.status}`);
  }

  return response.json();
}

/**
 * 获取用户行为日志
 * @param userId 用户ID
 * @param behaviorType 行为类型（可选）
 * @param limit 返回条数限制
 * @returns 行为日志列表
 */
export async function getBehaviorLogs(
  userId: string,
  behaviorType?: BehaviorType,
  limit: number = 100
): Promise<{
  code: number;
  data: {
    logs: Array<{
      log_id: string;
      behavior_type: string;
      topic_id: string;
      point_id: string;
      component_id: string;
      details: Record<string, any>;
      timestamp: string;
    }>;
    total: number;
  };
}> {
  const params = new URLSearchParams();
  if (behaviorType) params.append("behavior_type", behaviorType);
  params.append("limit", limit.toString());

  const response = await fetch(
    `${API_BASE_URL}/behavior/logs/${userId}?${params.toString()}`
  );

  if (!response.ok) {
    throw new Error(`获取行为日志失败: ${response.status}`);
  }

  return response.json();
}

/**
 * 获取用户行为统计
 * @param userId 用户ID
 * @returns 行为统计数据
 */
export async function getBehaviorStats(userId: string): Promise<{
  code: number;
  data: {
    user_id: string;
    stats: Record<string, number>;
  };
}> {
  const response = await fetch(`${API_BASE_URL}/api/v1/behavior/stats/${userId}`);

  if (!response.ok) {
    throw new Error(`获取行为统计失败: ${response.status}`);
  }

  return response.json();
}

/**
 * 更新知识组件的学习状态到后端（写入数据库）
 * @param componentId 组件ID
 * @param status 状态值
 * @param topicId 主题ID（可选）
 * @param pointId 知识点ID（可选）
 */
export async function updateComponentStatus(
  componentId: string,
  status: ComponentStatusType,
  topicId?: string,
  pointId?: string
): Promise<void> {
  try {
    await fetch(`${API_BASE_URL}/api/v1/behavior/component/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        component_id: componentId,
        status,
        topic_id: topicId,
        point_id: pointId,
        user_id: 'anonymous',
      }),
    });
  } catch {
    // 后端同步失败不影响前端体验
  }
}

/**
 * 便捷函数：记录学习开始
 */
export function recordLearnStart(
  userId: string,
  topicId: string,
  pointId: string,
  componentId: string
) {
  return recordBehavior({
    user_id: userId,
    behavior_type: "learn",
    topic_id: topicId,
    point_id: pointId,
    component_id: componentId,
    details: { action: "start", timestamp: Date.now() },
  });
}

/**
 * 便捷函数：记录学习结束
 */
export function recordLearnEnd(
  userId: string,
  topicId: string,
  pointId: string,
  componentId: string,
  duration: number
) {
  return recordBehavior({
    user_id: userId,
    behavior_type: "learn",
    topic_id: topicId,
    point_id: pointId,
    component_id: componentId,
    details: { action: "end", duration, timestamp: Date.now() },
  });
}

/**
 * 便捷函数：记录练习题完成
 */
export function recordPracticeComplete(
  userId: string,
  topicId: string,
  pointId: string,
  componentId: string,
  isCorrect: boolean,
  score: number
) {
  return recordBehavior({
    user_id: userId,
    behavior_type: "practice",
    topic_id: topicId,
    point_id: pointId,
    component_id: componentId,
    details: {
      is_correct: isCorrect,
      score,
      timestamp: Date.now(),
    },
  });
}
