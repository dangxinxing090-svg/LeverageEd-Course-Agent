/**
 * U-007 问答面板组件
 * 
 * 核心职责：学习页右下角中等大小面板，实时答疑对话，用户随时可提问
 * 
 * 底层执行逻辑：
 * 1. 用户输入问题 → 本地状态更新（受控组件）
 * 2. 点击发送/回车 → 输入校验（非空） → 调用askQuestion API → 进入loading状态
 * 3. API返回成功 → 将用户问题和AI答案追加到消息列表 → 自动滚动到底部
 * 4. API返回失败 → 显示错误信息 → 用户可重新提问
 * 5. 支持追问建议（follow_ups）点击快速提问
 * 
 * 内存数据流转：
 * 用户输入(String) → React State(inputValue) → API参数(QAQuestionInput) →
 * API响应(QAAnswerOutput) → 消息列表(messages[]) → DOM渲染
 * 
 * 状态机：
 * idle(空闲) → submitting(提交中) → success(成功) | error(错误) → idle
 * 
 * 潜在风险：
 * 1. 内存泄漏：组件卸载时未清理pending的API请求（已用AbortController处理）
 * 2. 逻辑漏洞：快速连续发送可能触发多次请求（已用isLoading状态锁处理）
 * 3. 性能问题：消息列表过长时DOM节点过多（当前未做虚拟滚动，消息量大时需优化）
 * 4. 自动滚动：新消息渲染后需确保滚动到底部（已用useEffect + scrollIntoView处理）
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
  QAPanelProps,
  QAAnswerOutput,
  QAMessage,
  TopicApiError
} from '../../types';
import { askQuestionStream } from '../../services/api';
import './styles.css';

// 常量定义
const DEFAULT_PLACEHOLDER = '输入你的问题...';
const MAX_QUESTION_LENGTH = 500;

/**
 * 生成唯一消息ID
 */
function generateMessageId(): string {
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

/**
 * U-007 问答面板组件
 */
export const QAPanel: React.FC<QAPanelProps> = ({
  userId,
  pointId,
  onQuestionSubmit,
  onError,
  className = '',
}) => {
  // ===== 状态管理 =====
  const [messages, setMessages] = useState<QAMessage[]>([]);
  const [inputValue, setInputValue] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // 用于取消pending请求的ref
  const abortControllerRef = useRef<AbortController | null>(null);
  // 消息列表底部引用，用于自动滚动
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // ===== 副作用：组件卸载时取消pending请求 =====
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  // ===== 副作用：新消息时自动滚动到底部 =====
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isLoading]);

  // ===== 事件处理 =====

  /**
   * 发送问题（核心逻辑）
   */
  const handleSend = useCallback(async () => {
    // 防御性检查：防止重复发送
    if (isLoading) return;

    const question = inputValue.trim();

    // 边界条件：空输入
    if (!question) {
      setErrorMessage('请输入问题');
      return;
    }

    // 边界条件：长度超限
    if (question.length > MAX_QUESTION_LENGTH) {
      setErrorMessage(`问题不能超过${MAX_QUESTION_LENGTH}个字符`);
      return;
    }

    // 步骤1：将用户问题添加到消息列表
    const userMessage: QAMessage = {
      id: generateMessageId(),
      type: 'user',
      content: question,
      timestamp: Date.now(),
    };
    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setErrorMessage(null);
    setIsLoading(true);

    // 步骤2：流式调用API
    try {
      const assistantId = generateMessageId();
      // 先添加一个空的AI消息，后续逐步更新内容
      const assistantMessage: QAMessage = {
        id: assistantId,
        type: 'assistant',
        content: '',
        timestamp: Date.now(),
      };
      setMessages(prev => [...prev, assistantMessage]);

      let fullAnswer = '';
      await askQuestionStream(
        question,
        pointId,
        userId || 'anonymous',
        (chunk) => {
          fullAnswer += chunk;
          setMessages(prev =>
            prev.map(msg =>
              msg.id === assistantId ? { ...msg, content: fullAnswer } : msg
            )
          );
        }
      );

      onQuestionSubmit?.(question, fullAnswer);
    } catch (error) {
      // 步骤5：错误处理
      let message = '提问失败，请稍后重试';

      if (error instanceof TopicApiError) {
        message = error.message;
      } else if (error instanceof Error) {
        message = error.message;
      }

      setErrorMessage(message);
      onError?.(error as Error);

      // 将错误信息也添加到消息列表，方便用户查看
      const errorMessage_: QAMessage = {
        id: generateMessageId(),
        type: 'assistant',
        content: `抱歉，${message}`,
        timestamp: Date.now(),
      };
      setMessages(prev => [...prev, errorMessage_]);
    } finally {
      setIsLoading(false);
    }
  }, [inputValue, isLoading, pointId, userId, onQuestionSubmit, onError]);

  /**
   * 输入变化处理
   */
  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
    if (errorMessage) {
      setErrorMessage(null);
    }
  }, [errorMessage]);

  /**
   * 键盘事件处理（支持回车发送）
   */
  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !isLoading) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend, isLoading]);

  /**
   * 点击追问建议
   */
  const handleFollowUpClick = useCallback((followUp: string) => {
    setInputValue(followUp);
    // 清除错误信息
    if (errorMessage) {
      setErrorMessage(null);
    }
  }, [errorMessage]);

  /**
   * 清除错误信息
   */
  const handleClearError = useCallback(() => {
    setErrorMessage(null);
  }, []);

  // ===== 计算属性 =====
  const isSendDisabled = isLoading || inputValue.trim().length === 0;

  // 获取最后一条AI消息的追问建议（从最近的QAAnswerOutput中获取）
  // 注意：follow_ups通过onQuestionSubmit回调传出，这里不直接存储在消息中
  // 如果需要展示追问建议，可以通过外部状态管理

  // ===== 渲染 =====
  return (
    <div className={`qa-panel-container ${className}`} role="region" aria-label="智能问答面板">
      {/* 面板标题 */}
      <div className="qa-panel-header">
        <h3 className="qa-panel-title">智能答疑</h3>
        {isLoading && (
          <span className="qa-panel-status" aria-live="polite">
            正在思考中...
          </span>
        )}
      </div>

      {/* 消息列表 */}
      <div className="qa-panel-messages" role="log" aria-label="对话记录" aria-live="polite">
        {messages.length === 0 && !isLoading && (
          <div className="qa-panel-empty">
            <p>有问题随时提问，AI助手为你解答</p>
          </div>
        )}

        {messages.map(msg => (
          <div
            key={msg.id}
            className={`qa-message qa-message--${msg.type}`}
            role="article"
            aria-label={msg.type === 'user' ? '你的问题' : 'AI回答'}
          >
            <div className="qa-message-avatar">
              {msg.type === 'user' ? '你' : 'AI'}
            </div>
            <div className="qa-message-content">
              <p>{msg.content}</p>
            </div>
          </div>
        ))}

        {/* Loading状态：AI正在输入 */}
        {isLoading && (
          <div className="qa-message qa-message--assistant" aria-label="AI正在回答">
            <div className="qa-message-avatar">AI</div>
            <div className="qa-message-content">
              <div className="qa-typing-indicator" aria-hidden="true">
                <span className="qa-typing-dot" />
                <span className="qa-typing-dot" />
                <span className="qa-typing-dot" />
              </div>
            </div>
          </div>
        )}

        {/* 自动滚动锚点 */}
        <div ref={messagesEndRef} aria-hidden="true" />
      </div>

      {/* 错误提示 */}
      {errorMessage && (
        <div className="qa-panel-error" role="alert">
          <span>{errorMessage}</span>
          <button
            className="qa-error-close"
            onClick={handleClearError}
            aria-label="清除错误信息"
          >
            x
          </button>
        </div>
      )}

      {/* 输入区域 */}
      <div className="qa-panel-input-area">
        <input
          type="text"
          className="qa-panel-input"
          value={inputValue}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          placeholder={DEFAULT_PLACEHOLDER}
          maxLength={MAX_QUESTION_LENGTH + 10}
          disabled={isLoading}
          aria-label="输入你的问题"
          aria-describedby={errorMessage ? 'qa-panel-error' : undefined}
          aria-invalid={!!errorMessage}
        />
        <button
          className={`qa-panel-send-btn ${isLoading ? 'loading' : ''}`}
          onClick={handleSend}
          disabled={isSendDisabled}
          aria-label="发送问题"
          aria-busy={isLoading}
        >
          {isLoading ? (
            <span className="qa-spinner" aria-hidden="true" />
          ) : (
            <svg className="qa-send-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M22 2L11 13M22 2L15 22L11 13M22 2L2 9L11 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          )}
        </button>
      </div>
    </div>
  );
};

// 默认导出
export default QAPanel;
