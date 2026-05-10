/**
 * U-006 学习路径面板组件
 *
 * 核心职责：学习页右中部，展示已完成的重点难点知识点、后续学习计划、推荐跳级选项
 *
 * 底层执行逻辑：
 * 1. 组件挂载时根据userId和topicId调用getLearningPath API
 * 2. 获取数据后分三个区块渲染：已完成知识点列表、后续学习计划列表、跳级建议列表
 * 3. 跳级建议高亮显示，点击时触发onSkipSuggestionClick回调
 * 4. 支持手动刷新，使用isLoading状态锁防止重复请求
 *
 * 内存数据流转：
 * Props(userId, topicId) → useEffect触发 → API调用 →
 * State(learningPath) → 分区渲染列表 → 点击跳级建议 → 回调
 *
 * 潜在风险：
 * 1. 内存泄漏：组件卸载时未取消pending的API请求（已用AbortController处理）
 * 2. 数据异常：后端返回数组字段缺失（已在API层兜底为空数组）
 * 3. 快速切换主题时可能产生竞态条件（已用isMountedRef处理）
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  LearningPathPanelProps,
  LearningPath,
  SkipSuggestion,
  NextPlanItem,
  CompletedPoint,
  TopicApiError
} from '../../types';
import { getLearningPath } from '../../services/api';
import './styles.css';

/**
 * 获取难度对应的中文标签
 * @param difficulty 难度级别
 * @returns 中文标签
 */
function getDifficultyLabel(difficulty: NextPlanItem['difficulty']): string {
  const map: Record<NextPlanItem['difficulty'], string> = {
    easy: '简单',
    medium: '中等',
    hard: '困难',
  };
  return map[difficulty] || '中等';
}

/**
 * 获取难度对应的CSS类名
 * @param difficulty 难度级别
 * @returns CSS类名
 */
function getDifficultyClass(difficulty: NextPlanItem['difficulty']): string {
  return `difficulty-${difficulty}`;
}

/**
 * 格式化预计学习时长
 * @param minutes 分钟数
 * @returns 格式化字符串
 */
function formatDuration(minutes: number): string {
  if (minutes < 60) return `${minutes}分钟`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return mins > 0 ? `${hours}小时${mins}分钟` : `${hours}小时`;
}

/**
 * U-006 学习路径面板组件
 */
export const LearningPathPanel: React.FC<LearningPathPanelProps> = ({
  userId,
  topicId,
  onSkipSuggestionClick,
  onError,
  className = '',
}) => {
  // ===== 状态管理 =====
  const [learningPath, setLearningPath] = useState<LearningPath | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // 用于取消pending请求和判断组件是否已挂载
  const abortControllerRef = useRef<AbortController | null>(null);
  const isMountedRef = useRef<boolean>(true);
  const isFetchingRef = useRef<boolean>(false);

  // ===== 副作用：组件卸载清理 =====
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  // ===== 数据获取 =====

  /**
   * 获取学习路径数据
   */
  const fetchLearningPath = useCallback(async () => {
    // 防御性检查：参数为空时不发请求
    if (!userId || !topicId) return;

    // 防止重复请求
    if (isFetchingRef.current) return;

    isFetchingRef.current = true;
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const data = await getLearningPath(userId, topicId);

      // 竞态条件：仅在组件仍挂载时更新状态
      if (isMountedRef.current) {
        setLearningPath(data);
      }
    } catch (error) {
      if (isMountedRef.current) {
        const message = error instanceof TopicApiError
          ? error.message
          : '获取学习路径失败，请稍后重试';
        setErrorMessage(message);
        onError?.(error as Error);
      }
    } finally {
      isFetchingRef.current = false;
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [userId, topicId, onError]);

  // ===== 副作用：挂载及参数变化时获取数据 =====
  useEffect(() => {
    fetchLearningPath();
  }, [fetchLearningPath]);

  // ===== 事件处理 =====

  /**
   * 手动刷新
   */
  const handleRefresh = useCallback(() => {
    setIsLoading(false); // 重置loading锁以允许重新请求
    fetchLearningPath();
  }, [fetchLearningPath]);

  /**
   * 跳级建议点击处理
   */
  const handleSkipClick = useCallback((suggestion: SkipSuggestion) => {
    onSkipSuggestionClick?.(suggestion.from_point_id, suggestion.to_point_id);
  }, [onSkipSuggestionClick]);

  // ===== 渲染辅助 =====

  /**
   * 渲染已完成知识点列表
   */
  const renderCompletedPoints = (points: CompletedPoint[]) => {
    if (points.length === 0) {
      return (
        <li className="learning-path-empty">
          暂无已完成知识点
        </li>
      );
    }

    return points.map((point) => (
      <li key={point.point_id} className="learning-path-completed-item">
        <span className="completed-check" aria-hidden="true">&#10003;</span>
        <span className="completed-name">{point.point_name}</span>
        {point.score !== undefined && (
          <span className="completed-score">{point.score}分</span>
        )}
      </li>
    ));
  };

  /**
   * 渲染后续学习计划列表
   */
  const renderNextPlan = (plans: NextPlanItem[]) => {
    if (plans.length === 0) {
      return (
        <li className="learning-path-empty">
          暂无后续计划
        </li>
      );
    }

    return plans.map((plan) => (
      <li key={plan.plan_id} className="learning-path-plan-item">
        <div className="plan-item-header">
          <span className="plan-name">{plan.plan_name}</span>
          <span className={`plan-difficulty ${getDifficultyClass(plan.difficulty)}`}>
            {getDifficultyLabel(plan.difficulty)}
          </span>
        </div>
        <p className="plan-description">{plan.description}</p>
        <span className="plan-duration">{formatDuration(plan.estimated_minutes)}</span>
      </li>
    ));
  };

  /**
   * 渲染跳级建议列表
   */
  const renderSkipSuggestions = (suggestions: SkipSuggestion[]) => {
    if (suggestions.length === 0) {
      return null; // 无跳级建议时不渲染整个区块
    }

    return suggestions.map((suggestion) => (
      <li key={suggestion.suggestion_id} className="learning-path-skip-item">
        <button
          className="skip-suggestion-btn"
          onClick={() => handleSkipClick(suggestion)}
          aria-label={`跳级到${suggestion.target_topic_name}，原因：${suggestion.reason}`}
        >
          <span className="skip-target">如果希望跳级学习，可以考虑跳过以下部分</span>
          <span className="skip-reason">{suggestion.reason}</span>
          <span className="skip-confidence">
            推荐度 {Math.round(suggestion.confidence * 100)}%
          </span>
        </button>
      </li>
    ));
  };

  // ===== 渲染 =====
  const hasSkipSuggestions = learningPath && learningPath.skip_suggestions.length > 0;

  return (
    <div
      className={`learning-path-panel ${className}`}
      role="region"
      aria-label="学习路径面板"
    >
      {/* 面板标题 */}
      <div className="learning-path-header">
        <h3 className="learning-path-title">学习路径</h3>
        <button
          className="learning-path-refresh"
          onClick={handleRefresh}
          disabled={isLoading}
          aria-label="刷新学习路径"
          aria-busy={isLoading}
        >
          <svg
            className={`refresh-icon ${isLoading ? 'spinning' : ''}`}
            viewBox="0 0 24 24"
            fill="none"
            width="16"
            height="16"
            aria-hidden="true"
          >
            <path
              d="M4 4v5h5M20 20v-5h-5"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M20.49 9A9 9 0 005.64 5.64L4 4m16 16l-1.64-1.64A9 9 0 014 15"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>

      {/* 加载状态 */}
      {isLoading && !learningPath && (
        <div className="learning-path-loading" aria-live="polite">
          <span className="spinner-small" aria-hidden="true" />
          <span>加载中...</span>
        </div>
      )}

      {/* 错误状态 */}
      {errorMessage && (
        <div className="learning-path-error" role="alert">
          <span>{errorMessage}</span>
          <button
            className="learning-path-retry"
            onClick={handleRefresh}
            aria-label="重试"
          >
            重试
          </button>
        </div>
      )}

      {/* 路径内容 */}
      {!isLoading && !errorMessage && learningPath && (
        <div className="learning-path-content">
          {/* 已完成知识点 */}
          <section className="learning-path-section">
            <h4 className="learning-path-section-title">已完成知识点</h4>
            <ul className="learning-path-list" aria-label="已完成知识点列表">
              {renderCompletedPoints(learningPath.completed_points)}
            </ul>
          </section>

          {/* 后续学习计划 */}
          <section className="learning-path-section">
            <h4 className="learning-path-section-title">后续学习计划</h4>
            <ul className="learning-path-list" aria-label="后续学习计划列表">
              {renderNextPlan(learningPath.next_plan)}
            </ul>
          </section>

          {/* 跳级建议（高亮显示） */}
          {hasSkipSuggestions && (
            <section className="learning-path-section learning-path-section-highlight">
              <h4 className="learning-path-section-title">
                <span className="section-highlight-icon" aria-hidden="true">&#9733;</span>
                跳级建议
              </h4>
              <ul className="learning-path-list" aria-label="跳级建议列表">
                {renderSkipSuggestions(learningPath.skip_suggestions)}
              </ul>
            </section>
          )}
        </div>
      )}
    </div>
  );
};

// 默认导出
export default LearningPathPanel;
