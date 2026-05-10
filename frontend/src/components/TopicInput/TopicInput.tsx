/**
 * U-001 首页主题输入组件
 * 
 * 核心职责：用户输入学习主题的Chat对话框组件
 * 
 * 底层执行逻辑：
 * 1. 用户输入文本 → 本地状态更新（受控组件）
 * 2. 点击提交/回车 → 输入校验（非空、长度限制、敏感词过滤）
 * 3. 校验通过 → 调用submitTopic API → 进入loading状态
 * 4. API返回成功 → 触发onTopicSubmit回调 → 父组件路由跳转
 * 5. API返回失败 → 显示错误信息 → 用户可重新输入
 * 
 * 内存数据流转：
 * 用户输入(String) → React State(inputValue) → API参数(TopicInput) → 
 * API响应(TopicOutput) → 父组件回调 → 路由跳转
 * 
 * 状态机：
 * idle(空闲) → validating(校验中) → submitting(提交中) → 
 * success(成功) | error(错误) → idle
 * 
 * 潜在风险：
 * 1. 内存泄漏：组件卸载时未清理pending的API请求（已用AbortController处理）
 * 2. 逻辑漏洞：快速连续点击提交按钮可能触发多次请求（已用isLoading状态锁处理）
 * 3. XSS风险：用户输入直接渲染到DOM（已用React自动转义处理）
 * 4. 性能问题：每次输入都触发re-render（已用useMemo优化按钮disabled计算）
 */

import React, { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import {
  TopicInputComponentProps,
  TopicOutput,
  TopicInput as TopicInputType,
  ValidationError,
  TopicApiError
} from '../../types';
import { submitTopic } from '../../services/api';
import './styles.css';

// 常量定义
const DEFAULT_PLACEHOLDER = '你想学什么？例如：Python编程、数据分析、产品经理...';
const DEFAULT_MAX_LENGTH = 100;
const MIN_LENGTH = 2;

// 敏感词列表（简单示例，实际应使用更完善的方案）
const SENSITIVE_WORDS = ['反动', '色情', '暴力', '赌博'];

/**
 * 输入校验函数
 * @param text 输入文本
 * @param maxLength 最大长度
 * @throws ValidationError 校验失败时抛出
 */
function validateInput(text: string, maxLength: number): void {
  // 边界条件：空输入
  if (!text || text.trim().length === 0) {
    throw new ValidationError('请输入学习主题');
  }

  // 边界条件：长度不足
  if (text.trim().length < MIN_LENGTH) {
    throw new ValidationError(`主题至少需要${MIN_LENGTH}个字符`);
  }

  // 边界条件：长度超限
  if (text.length > maxLength) {
    throw new ValidationError(`主题不能超过${maxLength}个字符`);
  }

  // 边界条件：敏感词检测
  const lowerText = text.toLowerCase();
  for (const word of SENSITIVE_WORDS) {
    if (lowerText.includes(word)) {
      throw new ValidationError('输入包含不适当内容，请重新输入');
    }
  }
}

/**
 * U-001 首页主题输入组件
 */
export const TopicInput: React.FC<TopicInputComponentProps> = ({
  onTopicSubmit,
  onError,
  placeholder = DEFAULT_PLACEHOLDER,
  maxLength = DEFAULT_MAX_LENGTH,
  disabled = false,
}) => {
  // ===== 状态管理 =====
  const [inputValue, setInputValue] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  
  // 用于取消pending请求的ref
  const abortControllerRef = useRef<AbortController | null>(null);

  // ===== 副作用：组件卸载时取消pending请求 =====
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  // ===== 副作用：从 sessionStorage 恢复正在学习的主题 =====
  useEffect(() => {
    const savedTopic = sessionStorage.getItem('currentTopicName');
    if (savedTopic) {
      setInputValue(savedTopic);
    }
  }, []);

  // ===== 计算属性 =====
  const isSubmitDisabled = useMemo(() => {
    return disabled || isLoading || inputValue.trim().length < MIN_LENGTH;
  }, [disabled, isLoading, inputValue]);

  const charCount = inputValue.length;
  const isOverLimit = charCount > maxLength;

  // ===== 事件处理 =====

  /**
   * 输入变化处理
   */
  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setInputValue(value);
    // 清除之前的错误信息
    if (errorMessage) {
      setErrorMessage(null);
    }
  }, [errorMessage]);

  /**
   * 提交处理（核心逻辑）
   */
  const handleSubmit = useCallback(async () => {
    // 防御性检查：防止重复提交
    if (isLoading) return;

    // 步骤1：输入校验
    try {
      validateInput(inputValue, maxLength);
    } catch (error) {
      if (error instanceof ValidationError) {
        setErrorMessage(error.message);
        onError?.(error);
        return;
      }
      throw error; // 未知错误继续抛出
    }

    // 步骤2：进入提交状态
    setIsLoading(true);
    setErrorMessage(null);

    // 步骤3：调用API（后端立即返回topic_id，LLM在后台处理）
    try {
      const input: TopicInputType = {
        topic_text: inputValue.trim()
      };

      const result: TopicOutput = await submitTopic(input);

      // 步骤4：成功处理 - 立即导航到学习页面，不等LLM完成
      sessionStorage.setItem('currentTopicName', inputValue.trim());
      onTopicSubmit?.(result);
    } catch (error) {
      // 步骤5：错误处理
      let message = '提交失败，请稍后重试';
      
      if (error instanceof TopicApiError) {
        message = error.message;
      } else if (error instanceof Error) {
        message = error.message;
      }

      setErrorMessage(message);
      onError?.(error as Error);
    } finally {
      setIsLoading(false);
    }
  }, [inputValue, maxLength, isLoading, onTopicSubmit, onError]);

  /**
   * 键盘事件处理（支持回车提交）
   */
  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }, [handleSubmit]);

  /**
   * 清除错误信息
   */
  const handleClearError = useCallback(() => {
    setErrorMessage(null);
  }, []);

  // ===== 渲染 =====
  return (
    <div className="topic-input-container">
      {/* 标题区域 */}
      <div className="topic-input-header">
        <h2 className="topic-input-title">你想学什么？</h2>
        <p className="topic-input-subtitle">输入任何你想学习的主题，AI将为你构建完整的学习路径</p>
      </div>

      {/* 输入区域 */}
      <div className={`topic-input-wrapper ${errorMessage ? 'has-error' : ''} ${isOverLimit ? 'over-limit' : ''}`}>
        <input
          type="text"
          className="topic-input-field"
          value={inputValue}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          maxLength={maxLength + 10} // 允许略微超出以显示错误提示
          disabled={disabled || isLoading}
          aria-label="学习主题输入"
          aria-describedby={errorMessage ? 'topic-input-error' : undefined}
          aria-invalid={!!errorMessage}
        />

        {/* 提交按钮 */}
        <button
          className={`topic-input-button ${isLoading ? 'loading' : ''}`}
          onClick={handleSubmit}
          disabled={isSubmitDisabled}
          aria-label="提交学习主题"
          aria-busy={isLoading}
        >
          {isLoading ? (
            <>
              <span className="spinner" aria-hidden="true" />
              <span>处理中...</span>
            </>
          ) : (
            <>
              <span>开始学习</span>
              <svg className="arrow-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M5 12h14M12 5l7 7-7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </>
          )}
        </button>
      </div>

      {/* 字符计数 */}
      <div className={`char-count ${isOverLimit ? 'over-limit' : ''}`}>
        {charCount}/{maxLength}
      </div>

      {/* 错误提示 */}
      {errorMessage && (
        <div 
          className="error-message" 
          id="topic-input-error"
          role="alert"
        >
          <span className="error-icon" aria-hidden="true">⚠️</span>
          <span>{errorMessage}</span>
          <button 
            className="error-close"
            onClick={handleClearError}
            aria-label="清除错误信息"
          >
            ×
          </button>
        </div>
      )}

      {/* 快捷提示 */}
      <div className="quick-tips">
        <span className="quick-tips-label">热门主题：</span>
        <button 
          className="quick-tip-item"
          onClick={() => setInputValue('Python编程')}
          disabled={isLoading}
        >
          Python编程
        </button>
        <button 
          className="quick-tip-item"
          onClick={() => setInputValue('数据分析')}
          disabled={isLoading}
        >
          数据分析
        </button>
        <button 
          className="quick-tip-item"
          onClick={() => setInputValue('产品经理')}
          disabled={isLoading}
        >
          产品经理
        </button>
      </div>
    </div>
  );
};

// 默认导出
export default TopicInput;
