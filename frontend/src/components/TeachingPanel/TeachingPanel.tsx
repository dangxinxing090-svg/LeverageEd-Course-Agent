import React, { useState, useEffect, useCallback, useRef } from 'react';
import { getExplanationStream, askQuestionStream } from '../../services/api';
import './styles.css';

interface TeachingMessage {
  id: string;
  type: 'ai' | 'user';
  content: string;
  timestamp: number;
}

interface TeachingPanelProps {
  componentId?: string;
  onNext?: () => void;
  onExercise?: () => void;
  onPanorama?: () => void;
  onError?: (error: Error) => void;
  className?: string;
}

function generateId(): string {
  return `tmsg-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
}

export const TeachingPanel: React.FC<TeachingPanelProps> = ({
  componentId = 'default-component',
  onNext,
  onExercise,
  onPanorama,
  onError,
  className = '',
}) => {
  const [messages, setMessages] = useState<TeachingMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => { isMountedRef.current = false; };
  }, []);

  // 加载知识点讲解
  useEffect(() => {
    let isMounted = true;
    const loadContent = async () => {
      setIsLoading(true);
      const abortController = new AbortController();
      try {
        let currentContent = '';
        await getExplanationStream(
          componentId,
          'BEGINNER',
          (chunk) => {
            currentContent += chunk;
            if (isMounted) {
              setMessages([{
                id: generateId(),
                type: 'ai',
                content: currentContent,
                timestamp: Date.now(),
              }]);
            }
          },
          abortController.signal
        );
      } catch (error) {
        if (isMounted) {
          setMessages([{
            id: generateId(),
            type: 'ai',
            content: '加载讲解内容失败，请稍后重试。',
            timestamp: Date.now(),
          }]);
          onError?.(error as Error);
        }
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };
    loadContent();
    return () => { isMounted = false; };
  }, [componentId, onError]);

  // 自动滚动
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // 发送消息
  const handleSend = useCallback(async () => {
    const text = inputValue.trim();
    if (!text || isLoading) return;

    const userMsg: TeachingMessage = {
      id: generateId(),
      type: 'user',
      content: text,
      timestamp: Date.now(),
    };
    setMessages(prev => [...prev, userMsg]);
    setInputValue('');

    // 调用流式问答API获取真实回复
    const aiReply: TeachingMessage = {
      id: generateId(),
      type: 'ai',
      content: '',
      timestamp: Date.now(),
    };
    setMessages(prev => [...prev, aiReply]);

    try {
      let fullAnswer = '';
      await askQuestionStream(
        text,
        componentId || 'general',
        'anonymous',
        (chunk) => {
          fullAnswer += chunk;
          setMessages(prev =>
            prev.map(msg =>
              msg.id === aiReply.id ? { ...msg, content: fullAnswer } : msg
            )
          );
        }
      );
    } catch (error) {
      setMessages(prev =>
        prev.map(msg =>
          msg.id === aiReply.id
            ? { ...msg, content: '抱歉，获取回复失败，请稍后重试。' }
            : msg
        )
      );
    }
  }, [inputValue, isLoading]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend]);

  return (
    <div className={`teaching-panel ${className}`}>
      <div className="teaching-panel-header">
        <h3 className="teaching-panel-title">知识讲解</h3>
        {isLoading && <span className="teaching-panel-status">加载中...</span>}
      </div>

      <div className="teaching-panel-messages">
        {messages.length === 0 && !isLoading && (
          <div className="teaching-panel-empty">
            <p>正在准备讲解内容...</p>
          </div>
        )}
        {messages.map(msg => (
          <div key={msg.id} className={`teaching-message teaching-message--${msg.type}`}>
            <div className="teaching-message-avatar">
              {msg.type === 'ai' ? 'AI' : '你'}
            </div>
            <div
              className="teaching-message-content"
              dangerouslySetInnerHTML={{ __html: msg.content }}
            />
          </div>
        ))}
        {isLoading && messages.length === 0 && (
          <div className="teaching-message teaching-message--ai">
            <div className="teaching-message-avatar">AI</div>
            <div className="teaching-message-content">
              <div className="teaching-typing">
                <span /><span /><span />
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="teaching-panel-actions">
        <button className="teaching-action-btn teaching-action-next" onClick={onNext} disabled={isLoading}>
          <svg viewBox="0 0 24 24" fill="none" width="16" height="16"><path d="M9 5l7 7-7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
          <span>下一个知识组件</span>
        </button>
        <button className="teaching-action-btn teaching-action-exercise" onClick={onExercise} disabled={isLoading}>
          <svg viewBox="0 0 24 24" fill="none" width="16" height="16"><path d="M9 11l3 3L22 4M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
          <span>练习题</span>
        </button>
      </div>

      <div className="teaching-panel-input-area">
        <input
          type="text"
          className="teaching-panel-input"
          value={inputValue}
          onChange={e => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入问题或回答..."
          disabled={isLoading}
        />
        <button
          className="teaching-panel-send-btn"
          onClick={handleSend}
          disabled={isLoading || !inputValue.trim()}
        >
          <svg viewBox="0 0 24 24" fill="none" width="18" height="18"><path d="M22 2L11 13M22 2L15 22L11 13M22 2L2 9L11 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
        </button>
      </div>
    </div>
  );
};

export default TeachingPanel;
