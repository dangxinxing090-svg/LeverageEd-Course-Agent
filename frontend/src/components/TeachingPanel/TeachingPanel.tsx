import React, { useState, useEffect, useCallback, useRef } from 'react';
import { 
  getOrCreateSession, 
  getSessionMessages, 
  sendChatMessage, 
  explainComponent,
  generateExercise,
  submitExerciseAnswer,
  Session,
  ChatMessage
} from '../../services/api';
import type { ExplanationSection } from '../../types';
import './styles.css';

// 消息类型定义
interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  messageType: 'chat' | 'explanation' | 'exercise_question' | 'exercise_answer' | 'exercise_grading';
  content: string;
  structuredContent?: ExplanationSection[];
  componentId?: string;
  componentName?: string;
  metadata?: any;
  timestamp: number;
  isStreaming?: boolean;
}

interface TeachingPanelProps {
  topicId: string;
  topicName: string;
  userId?: string;
  currentComponentId?: string;
  currentComponentName?: string;
  onComponentChange?: (componentId: string, componentName: string) => void;
  onError?: (error: Error) => void;
  className?: string;
}

function generateId(): string {
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
}

export const TeachingPanel: React.FC<TeachingPanelProps> = ({
  topicId,
  topicName,
  userId = 'default_user',
  currentComponentId,
  currentComponentName,
  onComponentChange,
  onError,
  className = '',
}) => {
  // Session状态
  const [session, setSession] = useState<Session | null>(null);
  const [sessionLoading, setSessionLoading] = useState(true);
  
  // 消息状态
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  
  // 当前练习题状态
  const [currentQuestion, setCurrentQuestion] = useState<any>(null);
  const [waitingForAnswer, setWaitingForAnswer] = useState(false);
  
  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // ==================== Session初始化 ====================
  
  useEffect(() => {
    const initSession = async () => {
      try {
        setSessionLoading(true);
        const newSession = await getOrCreateSession(userId, topicId, topicName);
        setSession(newSession);
        
        // 加载历史消息
        if (newSession.id) {
          const historyMessages = await getSessionMessages(newSession.id, 50);
          const formattedMessages: Message[] = historyMessages.map((msg: ChatMessage) => ({
            id: msg.id,
            role: msg.role as 'user' | 'assistant' | 'system',
            messageType: msg.message_type as any,
            content: msg.content,
            structuredContent: msg.structured_content,
            componentId: msg.component_id,
            componentName: msg.component_name,
            metadata: msg.metadata,
            timestamp: new Date(msg.created_at).getTime(),
          }));
          setMessages(formattedMessages);
        }
      } catch (error) {
        console.error('初始化Session失败:', error);
        onError?.(error as Error);
      } finally {
        setSessionLoading(false);
      }
    };
    
    if (topicId) {
      initSession();
    }
    
    return () => {
      abortControllerRef.current?.abort();
    };
  }, [topicId, topicName, userId, onError]);

  // ==================== 知识组件切换 ====================
  
  useEffect(() => {
    const handleComponentChange = async () => {
      if (!session?.id || !currentComponentId || !currentComponentName) return;
      
      // 检查是否已经有该组件的讲解消息
      const hasExplanation = messages.some(
        m => m.componentId === currentComponentId && m.messageType === 'explanation'
      );
      
      if (hasExplanation) {
        // 已有讲解，不重复获取
        return;
      }
      
      // 获取知识讲解
      try {
        setIsStreaming(true);
        abortControllerRef.current = new AbortController();
        
        // 添加系统消息表示正在加载
        const loadingMsg: Message = {
          id: generateId(),
          role: 'assistant',
          messageType: 'explanation',
          content: `正在准备【${currentComponentName}】的讲解...`,
          componentId: currentComponentId,
          componentName: currentComponentName,
          timestamp: Date.now(),
          isStreaming: true,
        };
        setMessages(prev => [...prev, loadingMsg]);
        
        await explainComponent(
          session.id,
          currentComponentId,
          currentComponentName,
          (data) => {
            // 流式更新
            if (data.sections) {
              setMessages(prev => {
                const lastMsg = prev[prev.length - 1];
                if (lastMsg?.isStreaming) {
                  return [
                    ...prev.slice(0, -1),
                    {
                      ...lastMsg,
                      content: `## ${currentComponentName}\n\n` + data.sections.map((s: any) => 
                        `${s.icon} **${s.title}**\n${s.content}`
                      ).join('\n\n'),
                      structuredContent: data.sections,
                    }
                  ];
                }
                return prev;
              });
            }
          },
          abortControllerRef.current.signal
        );
        
        // 标记加载完成
        setMessages(prev => {
          const lastMsg = prev[prev.length - 1];
          if (lastMsg?.isStreaming) {
            return [...prev.slice(0, -1), { ...lastMsg, isStreaming: false }];
          }
          return prev;
        });
        
      } catch (error) {
        console.error('获取讲解失败:', error);
        // 移除加载消息，添加错误消息
        setMessages(prev => {
          const filtered = prev.filter(m => !m.isStreaming);
          return [...filtered, {
            id: generateId(),
            role: 'assistant',
            messageType: 'chat',
            content: '抱歉，获取讲解内容失败，请稍后重试。',
            timestamp: Date.now(),
          }];
        });
      } finally {
        setIsStreaming(false);
      }
    };
    
    handleComponentChange();
  }, [session?.id, currentComponentId, currentComponentName]);

  // ==================== 自动滚动 ====================
  
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ==================== 发送消息 ====================
  
  const handleSendMessage = useCallback(async () => {
    if (!inputValue.trim() || !session?.id || isStreaming) return;
    
    const content = inputValue.trim();
    setInputValue('');
    
    // 添加用户消息
    const userMsg: Message = {
      id: generateId(),
      role: 'user',
      messageType: waitingForAnswer ? 'exercise_answer' : 'chat',
      content,
      componentId: currentComponentId,
      componentName: currentComponentName,
      timestamp: Date.now(),
    };
    setMessages(prev => [...prev, userMsg]);
    
    // 如果是等待练习题答案
    if (waitingForAnswer && currentQuestion) {
      setWaitingForAnswer(false);
      setIsStreaming(true);
      
      try {
        // 提交答案并获取批改结果
        const result = await submitExerciseAnswer(
          session.id,
          currentQuestion.content,
          content,
          currentComponentId
        );
        
        // 添加批改结果消息
        const gradingMsg: Message = {
          id: generateId(),
          role: 'assistant',
          messageType: 'exercise_grading',
          content: result.is_correct 
            ? `✅ **回答正确！**\n\n${result.feedback}`
            : `❌ **回答有误**\n\n${result.feedback}\n\n**错误分析：**\n${result.error_analysis}\n\n**参考答案：**\n${result.correct_answer}`,
          componentId: currentComponentId,
          componentName: currentComponentName,
          metadata: { exerciseResult: result },
          timestamp: Date.now(),
        };
        setMessages(prev => [...prev, gradingMsg]);
        setCurrentQuestion(null);
        
      } catch (error) {
        console.error('批改失败:', error);
        const errorMsg: Message = {
          id: generateId(),
          role: 'assistant',
          messageType: 'chat',
          content: '批改失败，请稍后重试。',
          timestamp: Date.now(),
        };
        setMessages(prev => [...prev, errorMsg]);
      } finally {
        setIsStreaming(false);
      }
      
      return;
    }
    
    // 普通对话
    setIsStreaming(true);
    abortControllerRef.current = new AbortController();
    
    // 添加AI加载消息
    const loadingMsg: Message = {
      id: generateId(),
      role: 'assistant',
      messageType: 'chat',
      content: '',
      timestamp: Date.now(),
      isStreaming: true,
    };
    setMessages(prev => [...prev, loadingMsg]);
    
    try {
      let fullContent = '';
      
      await sendChatMessage(
        session.id,
        content,
        (chunk) => {
          fullContent += chunk;
          setMessages(prev => {
            const lastMsg = prev[prev.length - 1];
            if (lastMsg?.isStreaming) {
              return [...prev.slice(0, -1), { ...lastMsg, content: fullContent }];
            }
            return prev;
          });
        },
        'chat',
        currentComponentId,
        currentComponentName,
        abortControllerRef.current.signal
      );
      
      // 标记完成
      setMessages(prev => {
        const lastMsg = prev[prev.length - 1];
        if (lastMsg?.isStreaming) {
          return [...prev.slice(0, -1), { ...lastMsg, isStreaming: false }];
        }
        return prev;
      });
      
    } catch (error) {
      console.error('发送消息失败:', error);
      setMessages(prev => {
        const filtered = prev.filter(m => !m.isStreaming);
        return [...filtered, {
          id: generateId(),
          role: 'assistant',
          messageType: 'chat',
          content: '抱歉，回复生成失败，请稍后重试。',
          timestamp: Date.now(),
        }];
      });
    } finally {
      setIsStreaming(false);
    }
  }, [inputValue, session?.id, isStreaming, waitingForAnswer, currentQuestion, currentComponentId, currentComponentName]);

  // ==================== 生成练习题 ====================
  
  const handleGenerateExercise = useCallback(async () => {
    if (!session?.id || !currentComponentId || isStreaming) return;
    
    setIsStreaming(true);
    abortControllerRef.current = new AbortController();
    
    try {
      const result = await generateExercise(
        session.id,
        currentComponentId,
        (data) => {
          if (data.question) {
            setCurrentQuestion(data.question);
          }
        },
        abortControllerRef.current.signal
      );
      
      if (result.question) {
        setCurrentQuestion(result.question);
        setWaitingForAnswer(true);
        
        // 添加题目消息
        const questionMsg: Message = {
          id: generateId(),
          role: 'assistant',
          messageType: 'exercise_question',
          content: `📚 **练习题**\n\n${result.question.content}\n\n💡 请在下方输入你的答案...`,
          componentId: currentComponentId,
          componentName: currentComponentName,
          metadata: { question: result.question },
          timestamp: Date.now(),
        };
        setMessages(prev => [...prev, questionMsg]);
      }
      
    } catch (error) {
      console.error('生成练习题失败:', error);
      const errorMsg: Message = {
        id: generateId(),
        role: 'assistant',
        messageType: 'chat',
        content: '生成练习题失败，请稍后重试。',
        timestamp: Date.now(),
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsStreaming(false);
    }
  }, [session?.id, currentComponentId, isStreaming]);

  // ==================== 键盘事件 ====================
  
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  }, [handleSendMessage]);

  // ==================== 渲染消息内容 ====================
  
  const renderMessageContent = (msg: Message) => {
    // 知识讲解 - 8维度卡片
    if (msg.messageType === 'explanation' && msg.structuredContent) {
      return (
        <div className="teaching-sections">
          <h4 className="explanation-title">📚 {msg.componentName}</h4>
          {msg.structuredContent.map((section, index) => (
            <div key={index} className="teaching-section-card">
              <div className="teaching-section-header">
                <span className="teaching-section-icon">{section.icon}</span>
                <span className="teaching-section-title">{section.title}</span>
              </div>
              <div className="teaching-section-content">
                {section.content.split('\n').map((line, lineIndex) => (
                  <p key={lineIndex}>{line}</p>
                ))}
              </div>
            </div>
          ))}
        </div>
      );
    }
    
    // 练习题
    if (msg.messageType === 'exercise_question') {
      return (
        <div className="exercise-question-message">
          <div className="exercise-badge">📚 练习题</div>
          <div className="exercise-content">{msg.content}</div>
        </div>
      );
    }
    
    // 批改结果
    if (msg.messageType === 'exercise_grading') {
      return (
        <div className="exercise-grading-message">
          <div className="grading-content" dangerouslySetInnerHTML={{ 
            __html: msg.content.replace(/\n/g, '<br/>') 
          }} />
        </div>
      );
    }
    
    // 普通消息
    return (
      <div className="chat-content" style={{ whiteSpace: 'pre-wrap' }}>
        {msg.content}
      </div>
    );
  };

  // ==================== 渲染 ====================
  
  if (sessionLoading) {
    return (
      <div className={`teaching-panel ${className}`}>
        <div className="teaching-panel-loading">
          <div className="loading-spinner"></div>
          <p>正在初始化教学会话...</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`teaching-panel ${className}`}>
      {/* 头部 */}
      <div className="teaching-panel-header">
        <div className="header-info">
          <h3 className="teaching-panel-title">💬 学习对话</h3>
          {currentComponentName && (
            <span className="current-component">📖 {currentComponentName}</span>
          )}
        </div>
        <div className="header-actions">
          <button 
            className="action-btn exercise-btn"
            onClick={handleGenerateExercise}
            disabled={isStreaming || !currentComponentId}
            title="生成练习题"
          >
            📝 练习题
          </button>
        </div>
      </div>

      {/* 消息列表 */}
      <div className="teaching-panel-messages">
        {messages.length === 0 && (
          <div className="welcome-message">
            <div className="welcome-icon">👋</div>
            <h4>欢迎使用对话式学习！</h4>
            <p>点击左侧知识图谱中的组件开始学习，或在这里直接提问。</p>
            {waitingForAnswer && (
              <p className="hint">💡 检测到正在等待练习题答案，请在下方输入你的答案。</p>
            )}
          </div>
        )}
        
        {messages.map((msg) => (
          <div 
            key={msg.id} 
            className={`message message--${msg.role} message--${msg.messageType}`}
          >
            <div className="message-avatar">
              {msg.role === 'user' ? '👤' : '🤖'}
            </div>
            <div className="message-content">
              {renderMessageContent(msg)}
              {msg.isStreaming && (
                <span className="typing-indicator">
                  <span></span><span></span><span></span>
                </span>
              )}
            </div>
          </div>
        ))}
        
        <div ref={messagesEndRef} />
      </div>

      {/* 输入区域 */}
      <div className="teaching-panel-input-area">
        {waitingForAnswer && (
          <div className="input-hint">
            💡 请回答上方的练习题
          </div>
        )}
        <div className="input-container">
          <textarea
            ref={inputRef}
            className="message-input"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={waitingForAnswer ? "请输入你的答案..." : "输入问题或回复..."}
            disabled={isStreaming}
            rows={1}
          />
          <button
            className="send-btn"
            onClick={handleSendMessage}
            disabled={!inputValue.trim() || isStreaming}
          >
            {isStreaming ? '⏳' : '➤'}
          </button>
        </div>
        <div className="input-tips">
          <span>按 Enter 发送，Shift+Enter 换行</span>
          <span className="session-info">
            Session: {session?.id?.slice(0, 8)}... | 主题: {topicName}
          </span>
        </div>
      </div>
    </div>
  );
};

export default TeachingPanel;
