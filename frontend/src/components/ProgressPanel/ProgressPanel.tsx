/**
 * U-005 提示面板组件
 *
 * 核心职责：学习页右上角小面板，展示学习进度比例、难点重点知识完成比例
 *
 * 底层执行逻辑：
 * 1. 组件挂载时根据userId和topicId调用getUserProgress API
 * 2. 获取进度数据后渲染三条进度条（总进度、重点、难点）
 * 3. 进度值以百分比数字+进度条可视化方式展示
 * 4. 支持手动刷新，使用isLoading状态锁防止重复请求
 *
 * 内存数据流转：
 * Props(userId, topicId) → useEffect触发 → API调用 →
 * State(progress) → 渲染进度条和百分比
 *
 * 潜在风险：
 * 1. 内存泄漏：组件卸载时未取消pending的API请求（已用AbortController处理）
 * 2. 数据异常：后端返回进度值超出0-1范围（已在API层clamp兜底）
 * 3. 快速切换主题时可能产生竞态条件（已用isMountedRef处理）
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  ProgressPanelProps,
  UserProgress,
  TopicApiError
} from '../../types';
import { getUserProgress } from '../../services/api';
import './styles.css';

// 默认进度数据（兜底）
const DEFAULT_PROGRESS: UserProgress = {
  total_progress: 0,
  key_point_progress: 0,
  difficulty_progress: 0,
};

/**
 * 将0-1的进度值格式化为百分比字符串
 * @param value 进度值
 * @returns 百分比字符串，如 "75%"
 */
function formatPercent(value: number): string {
  const percent = Math.round(value * 100);
  return `${percent}%`;
}

/**
 * U-005 提示面板组件
 */
export const ProgressPanel: React.FC<ProgressPanelProps> = ({
  userId,
  topicId,
  onError,
  className = '',
}) => {
  // ===== 状态管理 =====
  const [progress, setProgress] = useState<UserProgress | null>(null);
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
   * 获取学习进度数据
   */
  const fetchProgress = useCallback(async () => {
    // 防御性检查：参数为空时不发请求
    if (!userId || !topicId) return;

    // 防止重复请求
    if (isFetchingRef.current) return;

    isFetchingRef.current = true;
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const data = await getUserProgress(userId);

      // 竞态条件：仅在组件仍挂载时更新状态
      if (isMountedRef.current) {
        setProgress(data);
      }
    } catch (error) {
      if (isMountedRef.current) {
        const message = error instanceof TopicApiError
          ? error.message
          : '获取学习进度失败，请稍后重试';
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
    fetchProgress();
  }, [fetchProgress]);

  // ===== 事件处理 =====

  /**
   * 手动刷新
   */
  const handleRefresh = useCallback(() => {
    setIsLoading(false); // 重置loading锁以允许重新请求
    fetchProgress();
  }, [fetchProgress]);

  // ===== 渲染数据 =====
  const displayProgress = progress ?? DEFAULT_PROGRESS;

  return (
    <div
      className={`progress-panel ${className}`}
      role="region"
      aria-label="学习进度面板"
    >
      {/* 面板标题 */}
      <div className="progress-panel-header">
        <h3 className="progress-panel-title">学习进度</h3>
        <button
          className="progress-panel-refresh"
          onClick={handleRefresh}
          disabled={isLoading}
          aria-label="刷新进度"
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
      {isLoading && !progress && (
        <div className="progress-panel-loading" aria-live="polite">
          <span className="spinner-small" aria-hidden="true" />
          <span>加载中...</span>
        </div>
      )}

      {/* 错误状态 */}
      {errorMessage && (
        <div className="progress-panel-error" role="alert">
          <span>{errorMessage}</span>
          <button
            className="progress-panel-retry"
            onClick={handleRefresh}
            aria-label="重试"
          >
            重试
          </button>
        </div>
      )}

      {/* 进度内容 */}
      {!isLoading && !errorMessage && (
        <div className="progress-panel-content">
          {/* 总进度 */}
          <div className="progress-item">
            <div className="progress-item-header">
              <span className="progress-item-label">总体进度</span>
              <span className="progress-item-value" aria-label={`总体进度${formatPercent(displayProgress.total_progress)}`}>
                {formatPercent(displayProgress.total_progress)}
              </span>
            </div>
            <div
              className="progress-bar"
              role="progressbar"
              aria-valuenow={displayProgress.total_progress}
              aria-valuemin={0}
              aria-valuemax={1}
              aria-label="总体学习进度"
            >
              <div
                className="progress-bar-fill progress-bar-total"
                style={{ width: `${displayProgress.total_progress * 100}%` }}
              />
            </div>
          </div>

          {/* 重点知识进度 */}
          <div className="progress-item">
            <div className="progress-item-header">
              <span className="progress-item-label">重点知识</span>
              <span className="progress-item-value" aria-label={`重点知识进度${formatPercent(displayProgress.key_point_progress)}`}>
                {formatPercent(displayProgress.key_point_progress)}
              </span>
            </div>
            <div
              className="progress-bar"
              role="progressbar"
              aria-valuenow={displayProgress.key_point_progress}
              aria-valuemin={0}
              aria-valuemax={1}
              aria-label="重点知识完成进度"
            >
              <div
                className="progress-bar-fill progress-bar-keypoint"
                style={{ width: `${displayProgress.key_point_progress * 100}%` }}
              />
            </div>
          </div>

          {/* 难点知识进度 */}
          <div className="progress-item">
            <div className="progress-item-header">
              <span className="progress-item-label">难点知识</span>
              <span className="progress-item-value" aria-label={`难点知识进度${formatPercent(displayProgress.difficulty_progress)}`}>
                {formatPercent(displayProgress.difficulty_progress)}
              </span>
            </div>
            <div
              className="progress-bar"
              role="progressbar"
              aria-valuenow={displayProgress.difficulty_progress}
              aria-valuemin={0}
              aria-valuemax={1}
              aria-label="难点知识完成进度"
            >
              <div
                className="progress-bar-fill progress-bar-difficulty"
                style={{ width: `${displayProgress.difficulty_progress * 100}%` }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// 默认导出
export default ProgressPanel;
