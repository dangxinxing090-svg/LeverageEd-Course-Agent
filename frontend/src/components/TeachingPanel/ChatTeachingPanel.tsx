import React, { useState, useEffect, useCallback, useRef } from 'react';
import { 
  getOrCreateSession, 
  getSessionMessages, 
  sendChatMessage, 
  generateOverview,
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

// 组件信息接口
interface ComponentInfo {
  componentId: string;
  componentName: string;
  pointId: string;
  pointName: string;
  blockName: string;
}

interface ChatTeachingPanelProps {
  topicId: string;
  topicName: string;
  userId?: string;
  components?: ComponentInfo[];
  currentComponentIndex?: number;
  onComponentChange?: (index: number) => void;
  onError?: (error: Error) => void;
  className?: string;
  initialComponentId?: string;  // 新增：来自全景页的组件ID
}

function generateId(): string {
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
}

export const ChatTeachingPanel: React.FC<ChatTeachingPanelProps> = ({
  topicId,
  topicName,
  userId = 'default_user',
  components = [],
  currentComponentIndex = 0,
  onComponentChange,
  onError,
  className = '',
  initialComponentId,
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
  
  // 当前组件状态
  const [currentIndex, setCurrentIndex] = useState(currentComponentIndex);
  
  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  
  // 追踪已加载的内容，避免重复加载
  const loadedOverviewRef = useRef(false);
  const loadedComponentsRef = useRef<Set<string>>(new Set());
  const processedInitialComponentRef = useRef<string>('');
  
  // 初始化状态机：用 useState 替代 useRef，防止 React StrictMode 并发问题
  const [initStatus, setInitStatus] = useState<'idle' | 'loading' | 'completed' | 'error'>('idle');
  
  // 使用ref标记是否正在初始化，防止useEffect依赖变化导致的无限循环
  const isInitializingRef = useRef(false);
  
  // 使用ref记录上次加载的组件，防止重复加载
  const lastLoadedComponentRef = useRef<string>('');

  // 标记是否应该自动加载讲解（区分初始化恢复 vs 用户主动切换）
  const shouldAutoLoadRef = useRef(false);

  // 获取当前组件
  const currentComponent = components[currentIndex];
  const hasNextComponent = currentIndex < components.length - 1;

  // ==================== 加载全景介绍 ====================
  
  const loadOverview = useCallback(async (sessionId: string, tName: string) => {
    if (!sessionId) return;
    
    try {
      setIsStreaming(true);
      abortControllerRef.current = new AbortController();
      
      // 添加用户消息
      const userMsg: Message = {
        id: generateId(),
        role: 'user',
        messageType: 'chat',
        content: `请介绍 ${tName} 的全景知识`,
        timestamp: Date.now(),
      };
      setMessages(prev => [...prev, userMsg]);
      
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
      
      await generateOverview(
        sessionId,
        (data) => {
          if (data.content) {
            setMessages(prev => {
              const lastMsg = prev[prev.length - 1];
              if (lastMsg?.isStreaming) {
                return [...prev.slice(0, -1), { 
                  ...lastMsg, 
                  content: `## 📚 ${tName} - 全景介绍\n\n${data.content}` 
                }];
              }
              return prev;
            });
          }
        },
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
      console.error('加载全景介绍失败:', error);
      setMessages(prev => {
        const filtered = prev.filter(m => !m.isStreaming);
        return [...filtered, {
          id: generateId(),
          role: 'assistant',
          messageType: 'chat',
          content: '抱歉，加载全景介绍失败，请稍后重试。',
          timestamp: Date.now(),
        }];
      });
    } finally {
      setIsStreaming(false);
    }
  }, []);

  // ==================== 加载知识讲解 ====================
  
  const loadExplanation = useCallback(async (component: ComponentInfo, sId: string) => {
    if (!sId || !component) return;
    
    // 移除重复检查：每次点击都重新生成
    // 之前的检查代码已删除
    
    try {
      setIsStreaming(true);
      abortControllerRef.current = new AbortController();
      
      // 添加用户消息
      const userMsg: Message = {
        id: generateId(),
        role: 'user',
        messageType: 'chat',
        content: `请讲解 ${component.componentName}`,
        componentId: component.componentId,
        componentName: component.componentName,
        timestamp: Date.now(),
      };
      setMessages(prev => [...prev, userMsg]);
      
      // 添加AI加载消息
      const loadingMsg: Message = {
        id: generateId(),
        role: 'assistant',
        messageType: 'explanation',
        content: '',
        componentId: component.componentId,
        componentName: component.componentName,
        timestamp: Date.now(),
        isStreaming: true,
      };
      setMessages(prev => [...prev, loadingMsg]);
      
      await explainComponent(
        sId,
        component.componentId,
        component.componentName,
        (data) => {
          if (data.sections) {
            // 移除重复检查标记：每次点击都重新生成
            
            setMessages(prev => {
              const lastMsg = prev[prev.length - 1];
              if (lastMsg?.isStreaming) {
                const content = `## ${component.componentName}\n\n` + data.sections.map((s: any) => 
                  `${s.icon} **${s.title}**\n${s.content}`
                ).join('\n\n');
                
                return [...prev.slice(0, -1), {
                  ...lastMsg,
                  content,
                  structuredContent: data.sections,
                }];
              }
              return prev;
            });
          }
        },
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
      console.error('加载知识讲解失败:', error);
      setMessages(prev => {
        const filtered = prev.filter(m => !m.isStreaming);
        return [...filtered, {
          id: generateId(),
          role: 'assistant',
          messageType: 'chat',
          content: '抱歉，加载知识讲解失败，请稍后重试。',
          timestamp: Date.now(),
        }];
      });
    } finally {
      setIsStreaming(false);
    }
  }, []);

  // ==================== Session初始化 ====================
  
  // 根据 initStatus 同步 sessionLoading
  useEffect(() => {
    setSessionLoading(initStatus === 'loading' || initStatus === 'idle');
  }, [initStatus]);
  
  // 当 topicId 或 initialComponentId 变化时，重置状态并执行初始化（合并为一个useEffect，避免StrictMode竞态）
  useEffect(() => {
    console.log('[ChatTeachingPanel] topicId or initialComponentId changed, resetting states and initializing');
    
    // 1. 先重置所有状态
    setSession(null);
    setMessages([]);
    setInitStatus('idle');
    isInitializingRef.current = false;
    loadedOverviewRef.current = false;
    loadedComponentsRef.current.clear();
    processedInitialComponentRef.current = '';
    lastLoadedComponentRef.current = '';
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    
    // 2. 立即开始初始化（同步执行，无竞态窗口）
    let isMounted = true;
    
    const initSession = async () => {
      console.log('[ChatTeachingPanel] initSession called, topicId:', topicId);
      if (!topicId) {
        console.log('[ChatTeachingPanel] No topicId, returning');
        return;
      }
      if (isInitializingRef.current) {
        console.log('[ChatTeachingPanel] Skipping init - already initializing');
        return;
      }
      
      // 立即标记为正在初始化
      console.log('[ChatTeachingPanel] Starting initialization...');
      isInitializingRef.current = true;
      setInitStatus('loading');
      
      try {
        console.log('[ChatTeachingPanel] Calling getOrCreateSession...');
        const newSession = await getOrCreateSession(userId, topicId, topicName);
        console.log('[ChatTeachingPanel] getOrCreateSession success:', newSession);
        
        if (!isMounted) {
          console.log('[ChatTeachingPanel] Component unmounted, returning');
          return;
        }
        setSession(newSession);
        
        // 加载历史消息
        if (newSession.id) {
          console.log('[ChatTeachingPanel] Loading history messages...');
          const historyMessages = await getSessionMessages(newSession.id, 50);
          console.log('[ChatTeachingPanel] History messages loaded:', historyMessages.length);
          
          if (!isMounted) return;
          
          // 恢复历史消息
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
          
          // ========== 先显示历史消息 ==========
          setMessages(formattedMessages);
          console.log('[ChatTeachingPanel] History messages displayed:', formattedMessages.length);
          
          // 标记已加载的内容
          formattedMessages.forEach(msg => {
            if (msg.messageType === 'chat' && msg.content.includes('全景知识')) {
              loadedOverviewRef.current = true;
            }
            if (msg.componentId) {
              loadedComponentsRef.current.add(msg.componentId);
            }
          });
          
          // ========== 根据场景处理自动发送内容 ==========
          console.log('[ChatTeachingPanel] Checking scene - initialComponentId:', initialComponentId, 'historyMessages.length:', historyMessages.length);
          
          if (historyMessages.length === 0 && !initialComponentId) {
            // ========== 场景A：从首页进入，全新session，发送全景介绍 ==========
            console.log('[ChatTeachingPanel] Scene A: New session from home, loading overview...');
            loadedOverviewRef.current = true;
            await loadOverview(newSession.id, topicName);
            console.log('[ChatTeachingPanel] Overview loaded');
          } else if (historyMessages.length > 0 && !initialComponentId) {
            // ========== 场景B：从导航点击学习进入，已有历史会话，只显示历史 ==========
            console.log('[ChatTeachingPanel] Scene B: Existing session from nav, showing history only');
            shouldAutoLoadRef.current = false;  // 不自动加载当前组件讲解
          } else {
            // ========== 场景C：从全景页点击知识点跳转，initialComponentId 有值 ==========
            console.log('[ChatTeachingPanel] Scene C: From panorama with componentId, will auto-load');
            shouldAutoLoadRef.current = true;  // 允许自动加载指定组件讲解
          }
        }
        
        if (isMounted) {
          console.log('[ChatTeachingPanel] Setting initStatus to completed');
          setInitStatus('completed');
        }
      } catch (error) {
        console.error('[ChatTeachingPanel] 初始化Session失败:', error);
        if (isMounted) {
          setInitStatus('error');
          onError?.(error as Error);
        }
      } finally {
        console.log('[ChatTeachingPanel] Resetting isInitializingRef');
        isInitializingRef.current = false;
      }
    };
    
    initSession();
    
    return () => {
      isMounted = false;
      abortControllerRef.current?.abort();
    };
  }, [topicId, initialComponentId]);

  // ==================== 同步外部组件索引 ====================
  
  useEffect(() => {
    setCurrentIndex(currentComponentIndex);
  }, [currentComponentIndex]);

  // ==================== 组件切换时自动加载讲解 ====================
  
  useEffect(() => {
    if (currentComponent && session?.id && !sessionLoading) {
      // 检查是否已经加载过该组件，防止重复加载
      if (currentComponent.componentId !== lastLoadedComponentRef.current) {
        lastLoadedComponentRef.current = currentComponent.componentId;
        // 只有标记为需要自动加载时才调用（区分初始化恢复 vs 用户主动切换）
        if (shouldAutoLoadRef.current) {
          loadExplanation(currentComponent, session.id);
        }
      }
    }
  }, [currentComponent?.componentId, session?.id, sessionLoading]);

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
      componentId: currentComponent?.componentId,
      componentName: currentComponent?.componentName,
      timestamp: Date.now(),
    };
    setMessages(prev => [...prev, userMsg]);
    
    // 如果是等待练习题答案
    if (waitingForAnswer && currentQuestion) {
      setWaitingForAnswer(false);
      setIsStreaming(true);
      
      try {
        const result = await submitExerciseAnswer(
          session.id,
          currentQuestion.content,
          content,
          currentComponent?.componentId
        );
        
        const gradingMsg: Message = {
          id: generateId(),
          role: 'assistant',
          messageType: 'exercise_grading',
          content: result.is_correct 
            ? `✅ **回答正确！**\n\n${result.feedback}`
            : `❌ **回答有误**\n\n${result.feedback}\n\n**错误分析：**\n${result.error_analysis}\n\n**参考答案：**\n${result.correct_answer}`,
          componentId: currentComponent?.componentId,
          componentName: currentComponent?.componentName,
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
        currentComponent?.componentId,
        currentComponent?.componentName,
        abortControllerRef.current.signal
      );
      
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
  }, [inputValue, session?.id, isStreaming, waitingForAnswer, currentQuestion, currentComponent]);

  // ==================== 下一个按钮 ====================
  
  const handleNext = useCallback(() => {
    if (!hasNextComponent || isStreaming) return;
    
    shouldAutoLoadRef.current = true;  // 标记需要自动加载下一个组件讲解
    const nextIndex = currentIndex + 1;
    setCurrentIndex(nextIndex);
    onComponentChange?.(nextIndex);
  }, [hasNextComponent, isStreaming, currentIndex, onComponentChange]);

  // ==================== 练习题按钮 ====================
  
  const handleExercise = useCallback(async () => {
    if (!session?.id || !currentComponent || isStreaming) return;
    
    setIsStreaming(true);
    abortControllerRef.current = new AbortController();
    
    try {
      // 添加用户消息
      const userMsg: Message = {
        id: generateId(),
        role: 'user',
        messageType: 'chat',
        content: `请出一道关于 ${currentComponent.componentName} 的练习题`,
        componentId: currentComponent.componentId,
        componentName: currentComponent.componentName,
        timestamp: Date.now(),
      };
      setMessages(prev => [...prev, userMsg]);
      
      const result = await generateExercise(
        session.id,
        currentComponent.componentId,
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
        
        const questionMsg: Message = {
          id: generateId(),
          role: 'assistant',
          messageType: 'exercise_question',
          content: `📚 **练习题**\n\n${result.question.content}\n\n💡 请在下方输入你的答案...`,
          componentId: currentComponent.componentId,
          componentName: currentComponent.componentName,
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
  }, [session?.id, currentComponent, isStreaming]);

  // ==================== 键盘事件 ====================
  
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  }, [handleSendMessage]);

  // ==================== 渲染消息内容 ====================
  
  const renderMessageContent = (msg: Message) => {
    if (msg.messageType === 'explanation' && msg.structuredContent) {
      return (
        <div className="teaching-sections">
          <h4 className="explanation-title">{msg.componentName}</h4>
          {msg.structuredContent.map((section, index) => (
            <div key={index} className="teaching-section-card">
              <div className="teaching-section-header">
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
    
    if (msg.messageType === 'exercise_question') {
      return (
        <div className="exercise-question-message">
          <div className="exercise-content">{msg.content}</div>
        </div>
      );
    }
    
    if (msg.messageType === 'exercise_grading') {
      return (
        <div className="exercise-grading-message">
          <div className="grading-content" dangerouslySetInnerHTML={{ 
            __html: msg.content.replace(/\n/g, '<br/>') 
          }} />
        </div>
      );
    }
    
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
        {currentComponent && (
          <span className="current-component">{currentComponent.componentName}</span>
        )}
      </div>

      {/* 消息列表 */}
      <div className="teaching-panel-messages">
        {messages.length === 0 && (
          <div className="welcome-message">
            <div className="welcome-icon">👋</div>
            <h4>欢迎使用对话式学习！</h4>
            <p>点击"下一个"开始学习，或直接提问。</p>
          </div>
        )}
        
        {messages.map((msg) => (
          <div 
            key={msg.id} 
            className={`message message--${msg.role} message--${msg.messageType}`}
          >
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

      {/* 按钮行 */}
      <div className="action-buttons-row">
        <button
          className="action-btn next-btn"
          onClick={handleNext}
          disabled={!hasNextComponent || isStreaming}
        >
          下一个
        </button>
        <button
          className="action-btn exercise-btn"
          onClick={handleExercise}
          disabled={isStreaming || !currentComponent}
        >
          练习题
        </button>
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
            {currentIndex + 1} / {components.length} | Session: {session?.id?.slice(0, 8)}...
          </span>
        </div>
      </div>
    </div>
  );
};

export default ChatTeachingPanel;
