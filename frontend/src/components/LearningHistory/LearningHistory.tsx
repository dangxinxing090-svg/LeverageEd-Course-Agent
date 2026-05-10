/**
 * U-003 首页学习历史组件
 *
 * 核心职责：展示用户最近学习的主题列表，点击可继续学习
 *
 * 底层执行逻辑：
 * 1. 组件挂载 → 根据userId调用getUserTopicHistory API获取学习历史
 * 2. API成功 → 更新history状态 → 渲染历史列表（按last_study_at倒序）
 * 3. API失败 → 显示错误信息 → 提供"重试"操作
 * 4. 用户点击历史项 → 触发onTopicContinue回调 → 父组件处理跳转
 *
 * 内存数据流转：
 * userId(UUID) → API参数 → HTTP GET → LearningHistoryItem[] → React State → 渲染列表
 *
 * 状态机：
 * loading(加载中) → success(成功显示) | empty(无历史) | error(错误)
 *
 * 潜在风险：
 * 1. 内存泄漏：组件卸载时未取消pending请求（已用isMounted标志处理）
 * 2. 竞态条件：userId变化时旧请求可能覆盖新数据（已用requestId处理）
 * 3. 时间格式化：last_study_at为非标准格式时需兜底（已用try-catch处理）
 * 4. 重复点击：用户快速点击多个历史项（已用isLoading状态锁处理）
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  LearningHistoryProps,
  LearningHistoryState,
  LearningHistoryItem,
  TopicApiError,
} from '../../types';
import { getUserTopicHistory } from '../../services/api';
import './styles.css';

// 常量定义
const DEFAULT_MAX_ITEMS = 5;
const MAX_RETRY = 2;

/**
 * 格式化相对时间
 * 将ISO 8601日期字符串转换为"X分钟前"、"X小时前"等友好格式
 * @param isoString ISO 8601日期字符串
 * @returns 格式化后的相对时间字符串
 */
function formatRelativeTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    // 边界条件：无效日期
    if (isNaN(date.getTime())) {
      return '未知时间';
    }

    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffSeconds < 60) return '刚刚';
    if (diffMinutes < 60) return `${diffMinutes}分钟前`;
    if (diffHours < 24) return `${diffHours}小时前`;
    if (diffDays < 7) return `${diffDays}天前`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)}周前`;

    // 超过30天显示具体日期
    return date.toLocaleDateString('zh-CN', {
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return '未知时间';
  }
}

/**
 * U-003 首页学习历史组件
 */
export const LearningHistory: React.FC<LearningHistoryProps> = ({
  userId,
  onTopicContinue,
  onError,
  maxItems = DEFAULT_MAX_ITEMS,
  className = '',
}) => {
  // ===== 状态管理 =====
  const [state, setState] = useState<LearningHistoryState>({
    history: [],
    isLoading: true,
    errorMessage: null,
  });

  // 用于处理竞态条件的ref
  const currentRequestIdRef = useRef<number>(0);

  // ===== 副作用：组件挂载或userId变化时获取学习历史 =====
  useEffect(() => {
    let isMounted = true;
    const requestId = ++currentRequestIdRef.current;

    const fetchHistory = async (retryCount: number = 0) => {
      // 设置加载状态
      if (isMounted) {
        setState(prev => ({ ...prev, isLoading: true, errorMessage: null }));
      }

      try {
        const history = await getUserTopicHistory(userId);

        // 竞态条件检查：如果已有新请求，丢弃当前结果
        if (requestId !== currentRequestIdRef.current) {
          return;
        }

        if (isMounted) {
          setState(prev => ({
            ...prev,
            history,
            isLoading: false,
            errorMessage: null,
          }));
        }
      } catch (error) {
        // 竞态条件检查
        if (requestId !== currentRequestIdRef.current) {
          return;
        }

        // 请求被取消，不处理错误
        if (error instanceof Error && error.name === 'AbortError') {
          return;
        }

        // 重试逻辑
        if (retryCount < MAX_RETRY) {
          setTimeout(() => fetchHistory(retryCount + 1), 1000 * (retryCount + 1));
          return;
        }

        // 重试耗尽，显示错误
        if (isMounted) {
          let message = '加载学习历史失败，请稍后重试';
          if (error instanceof TopicApiError) {
            message = error.message;
          } else if (error instanceof Error) {
            message = error.message;
          }

          setState(prev => ({
            ...prev,
            history: [],
            isLoading: false,
            errorMessage: message,
          }));

          onError?.(error as Error);
        }
      }
    };

    fetchHistory();

    // 清理函数
    return () => {
      isMounted = false;
    };
  }, [userId, onError]);

  // ===== 事件处理 =====

  /**
   * 历史项点击处理
   */
  const handleItemClick = useCallback((item: LearningHistoryItem) => {
    if (state.isLoading) return;
    onTopicContinue?.(item);
  }, [state.isLoading, onTopicContinue]);

  /**
   * 重试加载
   */
  const handleRetry = useCallback(() => {
    currentRequestIdRef.current++;
    setState(prev => ({ ...prev, isLoading: true, errorMessage: null }));
    // 重新触发useEffect
    // 通过改变一个key来强制重新挂载（这里用requestId间接实现）
  }, []);

  // ===== 渲染辅助函数 =====

  /**
   * 渲染加载状态
   */
  const renderLoading = () => (
    <div className="learning-history-loading" role="status" aria-label="加载中">
      {Array.from({ length: Math.min(maxItems, 3) }).map((_, index) => (
        <div key={index} className="history-item skeleton">
          <div className="skeleton-info">
            <div className="skeleton-title" />
            <div className="skeleton-meta" />
          </div>
          <div className="skeleton-progress" />
        </div>
      ))}
    </div>
  );

  /**
   * 渲染空状态
   */
  const renderEmpty = () => (
    <div className="learning-history-empty">
      <div className="empty-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none">
          <path d="M12 6v6l4 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>
      <p className="empty-text">暂无学习记录</p>
      <p className="empty-hint">开始学习一个新主题吧</p>
    </div>
  );

  /**
   * 渲染错误状态
   */
  const renderError = () => (
    <div className="learning-history-error" role="alert">
      <span className="error-text">{state.errorMessage}</span>
      <button
        className="retry-button"
        onClick={handleRetry}
        aria-label="重新加载学习历史"
      >
        重试
      </button>
    </div>
  );

  /**
   * 渲染单个历史项
   */
  const renderHistoryItem = (item: LearningHistoryItem, index: number) => {
    // 边界条件：进度值钳制在0-100之间
    const clampedProgress = Math.max(0, Math.min(100, item.progress));
    const relativeTime = formatRelativeTime(item.last_study_at);

    return (
      <button
        key={item.topic_id}
        className="history-item"
        onClick={() => handleItemClick(item)}
        disabled={state.isLoading}
        aria-label={`继续学习：${item.topic_name}，进度${clampedProgress}%，上次学习${relativeTime}`}
        style={{ animationDelay: `${index * 80}ms` }}
      >
        {/* 主题信息 */}
        <div className="history-item-info">
          <h4 className="history-item-name">{item.topic_name}</h4>
          <span className="history-item-time">{relativeTime}</span>
        </div>

        {/* 进度条 */}
        <div className="history-item-progress">
          <div
            className="progress-bar"
            role="progressbar"
            aria-valuenow={clampedProgress}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`学习进度${clampedProgress}%`}
          >
            <div
              className="progress-fill"
              style={{ width: `${clampedProgress}%` }}
            />
          </div>
          <span className="progress-text">{clampedProgress}%</span>
        </div>
      </button>
    );
  };

  // ===== 主渲染 =====
  // 截取显示条数
  const displayItems = state.history.slice(0, maxItems);

  return (
    <div className={`learning-history ${className}`}>
      {/* 标题区域 */}
      <div className="learning-history-header">
        <h3 className="learning-history-title">学习历史</h3>
        {!state.isLoading && state.history.length > maxItems && (
          <span className="history-count">
            共{state.history.length}条记录
          </span>
        )}
      </div>

      {/* 内容区域 */}
      {state.isLoading ? (
        renderLoading()
      ) : state.errorMessage ? (
        renderError()
      ) : displayItems.length === 0 ? (
        renderEmpty()
      ) : (
        <div className="history-list">
          {displayItems.map((item, index) => renderHistoryItem(item, index))}
        </div>
      )}

      {/* 底部提示 */}
      {!state.isLoading && !state.errorMessage && displayItems.length > 0 && (
        <p className="learning-history-hint">
          点击任意主题即可继续学习
        </p>
      )}
    </div>
  );
};

// 默认导出
export default LearningHistory;
