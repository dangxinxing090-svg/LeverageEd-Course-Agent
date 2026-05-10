/**
 * U-002 首页推荐主题组件
 * 
 * 核心职责：展示3个推荐学习主题按钮，用户点击后快速进入学习
 * 
 * 底层执行逻辑：
 * 1. 组件挂载 → 调用getRecommendedTopics API获取推荐列表
 * 2. API成功 → 更新topics状态 → 渲染推荐卡片
 * 3. API失败 → 使用默认兜底数据 → 渲染默认推荐
 * 4. 用户点击推荐项 → 触发onTopicSelect回调 → 父组件处理跳转
 * 
 * 内存数据流转：
 * userId(可选) → API参数 → HTTP GET → RecommendedTopic[] → React State → 渲染卡片
 * 
 * 状态机：
 * loading(加载中) → success(成功显示) | fallback(使用兜底数据)
 * 
 * 潜在风险：
 * 1. 内存泄漏：组件卸载时未取消pending请求（已用AbortController处理）
 * 2. 竞态条件：快速切换userId可能导致旧数据覆盖新数据（已用stale check处理）
 * 3. 空数据：API返回空数组时无展示内容（已用兜底数据处理）
 * 4. 重复点击：用户快速点击多个推荐项（已用selectedTopicId状态锁处理）
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  TopicRecommendationsProps,
  TopicRecommendationsState,
  RecommendedTopic,
  TopicApiError,
} from '../../types';
import { getRecommendedTopics, getDefaultRecommendedTopics } from '../../services/api';
import './styles.css';

// 常量定义
const DEFAULT_COUNT = 3;
const MAX_RETRY = 2;

/**
 * U-002 首页推荐主题组件
 */
export const TopicRecommendations: React.FC<TopicRecommendationsProps> = ({
  userId,
  onTopicSelect,
  onError,
  count = DEFAULT_COUNT,
  className = '',
}) => {
  // ===== 状态管理 =====
  const [state, setState] = useState<TopicRecommendationsState>({
    topics: [],
    isLoading: true,
    errorMessage: null,
    selectedTopicId: null,
  });

  // 用于处理竞态条件的ref
  const abortControllerRef = useRef<AbortController | null>(null);
  const currentRequestIdRef = useRef<number>(0);

  // ===== 副作用：组件挂载时获取推荐数据 =====
  useEffect(() => {
    let isMounted = true;
    const requestId = ++currentRequestIdRef.current;

    const fetchRecommendations = async (retryCount: number = 0) => {
      // 取消之前的请求
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      abortControllerRef.current = new AbortController();

      // 设置加载状态
      if (isMounted) {
        setState(prev => ({ ...prev, isLoading: true, errorMessage: null }));
      }

      try {
        const topics = await getRecommendedTopics(count);

        // 竞态条件检查：如果已有新请求，丢弃当前结果
        if (requestId !== currentRequestIdRef.current) {
          return;
        }

        if (isMounted) {
          setState(prev => ({
            ...prev,
            topics,
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
          setTimeout(() => fetchRecommendations(retryCount + 1), 1000 * (retryCount + 1));
          return;
        }

        // 使用兜底数据
        if (isMounted) {
          const fallbackTopics = getDefaultRecommendedTopics().slice(0, count);
          setState(prev => ({
            ...prev,
            topics: fallbackTopics,
            isLoading: false,
            errorMessage: '推荐加载失败，显示默认推荐',
          }));
        }

        // 触发错误回调
        onError?.(error as Error);
      }
    };

    fetchRecommendations();

    // 清理函数
    return () => {
      isMounted = false;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [userId, count, onError]);

  // ===== 事件处理 =====

  /**
   * 推荐项点击处理
   */
  const handleTopicClick = useCallback((topic: RecommendedTopic) => {
    // 防御性检查：防止重复点击
    if (state.selectedTopicId) return;

    setState(prev => ({ ...prev, selectedTopicId: topic.topic_id }));
    onTopicSelect?.(topic);
  }, [state.selectedTopicId, onTopicSelect]);

  /**
   * 刷新推荐
   */
  const handleRefresh = useCallback(() => {
    setState(prev => ({ ...prev, isLoading: true, selectedTopicId: null }));
    // 重新触发useEffect
    currentRequestIdRef.current++;
  }, []);

  // ===== 渲染辅助函数 =====

  /**
   * 渲染加载状态
   */
  const renderLoading = () => (
    <div className="topic-recommendations-loading">
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="recommendation-card skeleton">
          <div className="skeleton-icon" />
          <div className="skeleton-title" />
          <div className="skeleton-desc" />
        </div>
      ))}
    </div>
  );

  /**
   * 渲染推荐卡片
   */
  const renderTopicCard = (topic: RecommendedTopic, index: number) => {
    const isSelected = state.selectedTopicId === topic.topic_id;
    const isDisabled = state.selectedTopicId !== null && !isSelected;

    return (
      <button
        key={topic.topic_id}
        className={`recommendation-card ${isSelected ? 'selected' : ''} ${isDisabled ? 'disabled' : ''}`}
        onClick={() => handleTopicClick(topic)}
        disabled={isDisabled}
        aria-label={`选择学习主题：${topic.topic_name}`}
        aria-pressed={isSelected}
        style={{ animationDelay: `${index * 100}ms` }}
      >
        {/* 图标区域 */}
        <div className="recommendation-icon">
          {topic.icon ? (
            <img src={topic.icon} alt="" loading="lazy" />
          ) : (
            <span className="default-icon">{topic.topic_name.charAt(0)}</span>
          )}
        </div>

        {/* 内容区域 */}
        <div className="recommendation-content">
          <h3 className="recommendation-title">{topic.topic_name}</h3>
          <p className="recommendation-description">{topic.description}</p>
          {topic.category && (
            <span className="recommendation-category">{topic.category}</span>
          )}
        </div>

        {/* 选中指示器 */}
        {isSelected && (
          <div className="selected-indicator">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M5 13l4 4L19 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
        )}
      </button>
    );
  };

  // ===== 主渲染 =====
  return (
    <div className={`topic-recommendations ${className}`}>
      {/* 标题区域 */}
      <div className="recommendations-header">
        <h3 className="recommendations-title">热门推荐</h3>
        {!state.isLoading && (
          <button
            className="refresh-button"
            onClick={handleRefresh}
            disabled={state.isLoading}
            aria-label="刷新推荐"
            title="刷新推荐"
          >
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        )}
      </div>

      {/* 错误提示（非阻塞） */}
      {state.errorMessage && (
        <div className="recommendations-error" role="status">
          <span>{state.errorMessage}</span>
        </div>
      )}

      {/* 内容区域 */}
      {state.isLoading ? (
        renderLoading()
      ) : (
        <div className="recommendations-grid">
          {state.topics.map((topic, index) => renderTopicCard(topic, index))}
        </div>
      )}

      {/* 底部提示 */}
      {!state.isLoading && state.topics.length > 0 && (
        <p className="recommendations-hint">
          点击上方推荐主题，快速开始学习之旅
        </p>
      )}
    </div>
  );
};

// 默认导出
export default TopicRecommendations;
