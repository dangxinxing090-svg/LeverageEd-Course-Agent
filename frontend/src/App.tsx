/**
 * AI智能教育课程平台 - 根组件
 * 
 * 导航精简为：首页、学习、全景知识图谱
 * 学习页面整合知识讲解、练习题、问答、学习进度等功能
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';

// 组件导入
import { TopicInput } from './components/TopicInput';
import { TopicRecommendations } from './components/TopicRecommendations';
import { TeachingPanel } from './components/TeachingPanel';
import { ChatTeachingPanel } from './components/TeachingPanel/ChatTeachingPanel';
import { ExercisePanel } from './components/ExercisePanel';
import { ProgressPanel } from './components/ProgressPanel';
import { PanoramaProgress } from './components/PanoramaProgress';
import { LearningPathPanel } from './components/LearningPathPanel';
import { LearningHistory } from './components/LearningHistory';
import { SkipTest } from './components/SkipTest';

import { getTopicStructure, getTopicOverview, getTopicStatus } from './services/api';
import { recordLearnStart, recordLearnEnd, recordPracticeComplete } from './api/behavior';
import { markLearning, getComponentProgress } from './utils/progressStorage';
import { ComponentSkipSuggestion } from './types';
import { KnowledgeBlock } from './types';

import './App.css';

// 导航组件 - 精简为3个入口
const Navigation: React.FC = () => {
  const location = useLocation();

  const navItems = [
    { path: '/', label: '首页' },
    { path: '/learn', label: '学习' },
    { path: '/panorama', label: '全景知识图谱' },
  ];

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  return (
    <nav className="app-nav">
      <div className="app-nav-inner">
        <Link to="/" className="app-nav-brand">
          <span className="brand-icon">AI</span>
          <span className="brand-text">智能教育课程平台</span>
        </Link>
        <ul className="app-nav-list">
          {navItems.map(item => (
            <li key={item.path}>
              <Link
                to={item.path}
                className={`app-nav-link ${isActive(item.path) ? 'active' : ''}`}
              >
                {item.label}
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  );
};

// 首页组件
const Home: React.FC = () => {
  const navigate = useNavigate();
  
  const handleSubmit = (result: { topic_id: string; topic_name: string; status: string }) => {
    // 提交成功后跳转到学习页
    navigate(`/learn?topicId=${result.topic_id}&topicName=${encodeURIComponent(result.topic_name)}`);
  };

  return (
    <div className="home-page">
      <TopicInput onTopicSubmit={handleSubmit} />
    </div>
  );
};

// 学习聚合页面 - 四面板并排布局
const LearnPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const topicId = searchParams.get('topicId') || '';
  const topicName = searchParams.get('topicName') || '';
  // Also support componentId from URL (when coming from panorama page)
  const urlComponentId = searchParams.get('componentId') || '';

  // 判断是否有真实的topicId（来自URL或localStorage）
  const storedTopicId = localStorage.getItem('currentTopicId') || '';
  const storedTopicName = localStorage.getItem('currentTopicName') || '';
  const hasTopic = !!(topicId || storedTopicId);

  const [knowledgeBlocks, setKnowledgeBlocks] = useState<KnowledgeBlock[]>(() => {
    const tid = topicId || localStorage.getItem('currentTopicId') || '';
    if (!tid) return [];
    const cached = localStorage.getItem(`knowledgeBlocks_${tid}`);
    if (cached) {
      try { return JSON.parse(cached); } catch { /* ignore */ }
    }
    return [];
  });
  const [exerciseMode, setExerciseMode] = useState(false);
  const [activeTab, setActiveTab] = useState<'teaching' | 'exercise'>('teaching');
  const [loading, setLoading] = useState(() => {
    const tid = topicId || localStorage.getItem('currentTopicId') || '';
    if (!tid) return true;
    // 如果已有缓存的知识结构或全景介绍，不需要loading
    const hasBlocks = !!localStorage.getItem(`knowledgeBlocks_${tid}`);
    const hasOverview = !!localStorage.getItem(`learnPage_overview_${tid}`);
    return !(hasBlocks || hasOverview);
  });
  const [error, setError] = useState<string | null>(null);
  const [isTimeout, setIsTimeout] = useState(false);  // SSE超时状态
  const [retryCount, setRetryCount] = useState(0);    // 重试次数
  const [overview, setOverview] = useState(() => {
    const tid = topicId || localStorage.getItem('currentTopicId') || '';
    if (!tid) return '';
    return localStorage.getItem(`learnPage_overview_${tid}`) || '';
  });
  // 从localStorage恢复状态，无保存值时根据urlComponentId决定默认值
  // 有urlComponentId时默认显示对应组件，否则默认显示全景介绍
  const [overviewMode, setOverviewMode] = useState(() => {
    const tid = topicId || localStorage.getItem('currentTopicId') || '';
    if (tid) {
      const savedMode = localStorage.getItem(`learnPage_overviewMode_${tid}`);
      if (savedMode !== null) {
        return savedMode === 'true';
      }
    }
    // 无保存值时：有urlComponentId则显示组件，否则显示全景介绍
    return !urlComponentId;
  });
  // 用于触发学习路径面板刷新
  const [learningPathRefreshKey, setLearningPathRefreshKey] = useState(0);

  // 从localStorage恢复组件索引，无保存值时默认从第一个开始
  const [currentComponentIndex, setCurrentComponentIndex] = useState(() => {
    const tid = topicId || localStorage.getItem('currentTopicId') || '';
    if (tid) {
      const savedIndex = localStorage.getItem(`learnPage_componentIndex_${tid}`);
      if (savedIndex !== null) {
        const idx = parseInt(savedIndex, 10);
        if (!isNaN(idx) && idx >= 0) {
          return idx;
        }
      }
    }
    return 0;
  });

  // 学习行为记录：追踪学习开始时间
  const learnStartTimeRef = useRef<number>(0);
  const lastComponentIdRef = useRef<string>('');

  // 获取所有知识组件的扁平列表
  const allComponents = knowledgeBlocks.flatMap(block =>
    block.points.flatMap(point =>
      point.components.map(comp => ({
        componentId: comp.component_id,
        componentName: comp.component_name,
        pointId: point.point_id,
        pointName: point.point_name,
        blockName: block.block_name,
        is_key_point: point.is_key_point || false,
        difficulty: point.difficulty || 'medium',
      }))
    )
  );

  const currentComponent = allComponents[currentComponentIndex];
  const nextComponent = allComponents[currentComponentIndex + 1];
  const currentPointId = currentComponent?.pointId || '';
  const effectiveTopicId = topicId || storedTopicId;
  const effectiveTopicName = topicName || storedTopicName;

  // 计算跳级建议（基于重要性+难度二维矩阵）
  const evaluateSkipSuggestion = (component: { is_key_point: boolean; difficulty: string } | undefined): ComponentSkipSuggestion | undefined => {
    if (!component) return undefined;
    
    const is_key_point = component.is_key_point;
    const difficulty = component.difficulty.toLowerCase();
    
    // 标准化难度值
    const isEasy = difficulty === 'easy' || difficulty === 'low';
    const isHard = difficulty === 'hard' || difficulty === 'high';
    
    // 基于二维矩阵决策
    if (is_key_point) {
      // 重要知识点
      if (isEasy) {
        return {
          componentId: component.componentId || '',
          componentName: component.componentName || '',
          pointName: component.pointName || '',
          is_key_point,
          difficulty: 'easy',
          skip_suggestion: 'USER_DECISION',
          risk_warning: ''
        };
      } else {
        return {
          componentId: component.componentId || '',
          componentName: component.componentName || '',
          pointName: component.pointName || '',
          is_key_point,
          difficulty: isHard ? 'hard' : 'medium',
          skip_suggestion: 'NOT_RECOMMENDED',
          risk_warning: '该知识点为核心重点内容，跳过可能影响后续学习'
        };
      }
    } else {
      // 不重要知识点
      if (isEasy) {
        return {
          componentId: component.componentId || '',
          componentName: component.componentName || '',
          pointName: component.pointName || '',
          is_key_point,
          difficulty: 'easy',
          skip_suggestion: 'SUGGESTED',
          risk_warning: ''
        };
      } else {
        return {
          componentId: component.componentId || '',
          componentName: component.componentName || '',
          pointName: component.pointName || '',
          is_key_point,
          difficulty: isHard ? 'hard' : 'medium',
          skip_suggestion: 'USER_DECISION',
          risk_warning: '该知识点有一定难度，跳过前请确认您是否已掌握相关基础'
        };
      }
    }
  };

  const currentComponentSkipSuggestion = evaluateSkipSuggestion(currentComponent);
  const nextComponentSkipSuggestion = evaluateSkipSuggestion(nextComponent);

  // 跳过当前组件
  const handleSkipComponent = useCallback((componentId: string) => {
    const skipIndex = allComponents.findIndex(c => c.componentId === componentId);
    if (skipIndex >= 0 && skipIndex < allComponents.length - 1) {
      // 跳到下一个组件
      setCurrentComponentIndex(skipIndex + 1);
      setOverviewMode(false);
    }
  }, [allComponents]);

  // 加载知识结构（SSE模式：后端异步处理LLM，服务器推送完成通知）
  useEffect(() => {
    if (!effectiveTopicId) {
      setLoading(false);
      return;
    }

    // 如果已有缓存数据，跳过SSE连接，直接标记完成
    const cachedBlocks = localStorage.getItem(`knowledgeBlocks_${effectiveTopicId}`);
    const cachedOverview = localStorage.getItem(`learnPage_overview_${effectiveTopicId}`);
    if (cachedBlocks && cachedOverview) {
      setLoading(false);
      localStorage.setItem('currentTopicId', effectiveTopicId);
      localStorage.setItem('currentTopicName', effectiveTopicName);
      return;
    }

    setLoading(true);
    setError(null);
    setIsTimeout(false);

    // 建立 SSE 连接
    const eventSource = new EventSource(
      `${import.meta.env.VITE_API_URL || ''}/api/v1/topics/${effectiveTopicId}/progress`
    );

    let isCompleted = false;

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.completed) {
          // 处理完成
          isCompleted = true;
          if (data.overview) {
            setOverview(data.overview);
            localStorage.setItem(`learnPage_overview_${effectiveTopicId}`, data.overview);
          }
          if (data.structure) {
            setKnowledgeBlocks(data.structure.blocks || []);
            localStorage.setItem(`knowledgeBlocks_${effectiveTopicId}`, JSON.stringify(data.structure.blocks || []));
          }
          localStorage.setItem('currentTopicId', effectiveTopicId);
          localStorage.setItem('currentTopicName', effectiveTopicName);
          setLoading(false);
          eventSource.close();
        } else if (data.timeout) {
          // 120秒超时
          setIsTimeout(true);
          setLoading(false);
          eventSource.close();
        }
      } catch (err) {
        console.error('SSE消息解析失败:', err);
      }
    };

    eventSource.onerror = (err) => {
      if (!isCompleted) {
        console.error('SSE连接错误:', err);
        setError('连接失败，请重试');
        setLoading(false);
      }
      eventSource.close();
    };

    return () => {
      // 用户离开页面，关闭连接但不中断后端处理
      eventSource.close();
    };
  }, [effectiveTopicId, retryCount]);

  // 保存学习状态到localStorage（当状态变化时）
  useEffect(() => {
    if (effectiveTopicId) {
      localStorage.setItem(`learnPage_overviewMode_${effectiveTopicId}`, String(overviewMode));
      localStorage.setItem(`learnPage_componentIndex_${effectiveTopicId}`, String(currentComponentIndex));
      if (overview) {
        localStorage.setItem(`learnPage_overview_${effectiveTopicId}`, overview);
      }
    }
  }, [overviewMode, currentComponentIndex, effectiveTopicId, overview]);

  const handleNext = useCallback(() => {
    const current = allComponents[currentComponentIndex];
    const isDifficult = current?.isKeyDifficulty === true;

    if (isDifficult && !exerciseMode) {
      const confirmed = window.confirm(
        '该知识点难度较高，建议做练习题加深理解。\n\n' +
        '点击「确定」继续下一个知识点\n' +
        '点击「取消」留在当前知识点'
      );
      if (!confirmed) return;
    }

    if (currentComponentIndex < allComponents.length - 1) {
      setCurrentComponentIndex(prev => prev + 1);
      setExerciseMode(false);
    }
  }, [currentComponentIndex, allComponents.length, exerciseMode]);

  // Handle clicking a component from panorama
  const handleComponentSelect = useCallback((componentId: string) => {
    const idx = allComponents.findIndex(c => c.componentId === componentId);
    if (idx >= 0) {
      setCurrentComponentIndex(idx);
      setOverviewMode(false);
      setExerciseMode(false);
    }
  }, [allComponents]);

  // Handle exercise completed - refresh knowledge blocks and learning path
  const handleExerciseCompleted = useCallback(async (completedPointId: string, score: number) => {
    // 记录练习完成行为
    if (effectiveTopicId && currentComponent) {
      try {
        await recordPracticeComplete(
          'anonymous',
          effectiveTopicId,
          currentPointId,
          currentComponent.componentId,
          score >= 60,  // 60分以上视为正确
          score
        );
      } catch (err) {
        console.error('记录练习行为失败:', err);
      }
    }
    
    // 重新获取知识结构（后端已更新status）
    if (effectiveTopicId) {
      try {
        const blocks = await getTopicStructure(effectiveTopicId, 'anonymous');
        setKnowledgeBlocks(blocks);
        // 同步更新localStorage（全景知识图谱页面使用）
        localStorage.setItem(`knowledgeBlocks_${effectiveTopicId}`, JSON.stringify(blocks));
        // 设置全局刷新标记，通知全景知识页更新
        localStorage.setItem('knowledgeBlocks_refresh_timestamp', Date.now().toString());
      } catch (err) {
        console.error('刷新知识结构失败:', err);
      }
    }
    // 触发学习路径面板刷新
    setLearningPathRefreshKey(prev => prev + 1);
  }, [effectiveTopicId, currentComponent, currentPointId]);

  // Handle URL componentId (from panorama page click) - 定位到具体组件
  useEffect(() => {
    if (!effectiveTopicId || knowledgeBlocks.length === 0 || !urlComponentId) return;

    // 从全景页点击具体知识点：使用URL参数定位
    const idx = allComponents.findIndex(c => c.componentId === urlComponentId);
    if (idx >= 0) {
      setCurrentComponentIndex(idx);
      setOverviewMode(false);
    }
  }, [urlComponentId, knowledgeBlocks.length, effectiveTopicId, allComponents]);

  // 学习行为记录：进入/离开知识点时记录
  useEffect(() => {
    if (overviewMode || !currentComponent || !effectiveTopicId) {
      // 如果进入全景模式或没有当前组件，记录之前组件的学习结束
      if (lastComponentIdRef.current && learnStartTimeRef.current > 0) {
        const duration = Math.floor((Date.now() - learnStartTimeRef.current) / 1000);
        recordLearnEnd('anonymous', effectiveTopicId, currentPointId, lastComponentIdRef.current, duration).catch(() => {});
        learnStartTimeRef.current = 0;
        lastComponentIdRef.current = '';
      }
      return;
    }

    // 进入新的知识点讲解
    const componentId = currentComponent.componentId;
    const pointId = currentComponent.pointId;

    // 如果切换到不同的组件，记录之前组件的学习结束
    if (lastComponentIdRef.current && lastComponentIdRef.current !== componentId && learnStartTimeRef.current > 0) {
      const duration = Math.floor((Date.now() - learnStartTimeRef.current) / 1000);
      recordLearnEnd('anonymous', effectiveTopicId, currentPointId, lastComponentIdRef.current, duration).catch(() => {});
    }

    // 记录新组件的学习开始
    if (lastComponentIdRef.current !== componentId) {
      recordLearnStart('anonymous', effectiveTopicId, pointId, componentId).catch(() => {});
      // 只在未完成学习时才标记为"学习中"，避免覆盖已完成的组件
      const currentProgress = getComponentProgress(componentId);
      if (currentProgress.learnStatus !== 'completed') {
        markLearning(componentId);
      }
      learnStartTimeRef.current = Date.now();
      lastComponentIdRef.current = componentId;
    }
  }, [overviewMode, currentComponent, effectiveTopicId, currentPointId]);

  // 组件卸载时记录学习结束
  useEffect(() => {
    return () => {
      if (lastComponentIdRef.current && learnStartTimeRef.current > 0 && effectiveTopicId) {
        const duration = Math.floor((Date.now() - learnStartTimeRef.current) / 1000);
        recordLearnEnd('anonymous', effectiveTopicId, currentPointId, lastComponentIdRef.current, duration).catch(() => {});
      }
    };
  }, [effectiveTopicId, currentPointId]);

  if (loading) {
    return (
      <div className="learn-page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
        <div style={{ textAlign: 'center', color: '#64748B' }}>
          <div style={{ fontSize: '18px', marginBottom: '8px' }}>正在加载知识体系...</div>
          <div style={{ fontSize: '14px', color: '#94A3B8' }}>AI正在为你拆分知识结构，请稍候</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="learn-page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
        <div style={{ textAlign: 'center', color: '#EF4444' }}>
          <div style={{ fontSize: '18px', marginBottom: '8px' }}>{error}</div>
          <div style={{ fontSize: '14px', color: '#94A3B8', marginBottom: '16px' }}>
            连接失败，请检查网络后重试
          </div>
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
            <button
              onClick={() => {
                if (retryCount < 3) {
                  setRetryCount(prev => prev + 1);
                }
              }}
              disabled={retryCount >= 3}
              style={{
                padding: '10px 24px',
                background: retryCount >= 3 ? '#CBD5E1' : '#5B6CF0',
                color: '#fff',
                borderRadius: '8px',
                border: 'none',
                fontSize: '14px',
                fontWeight: 500,
                cursor: retryCount >= 3 ? 'not-allowed' : 'pointer',
              }}
            >
              {retryCount >= 3 ? '重试次数已用完' : '重试'}
            </button>
            <Link to="/" style={{ display: 'inline-block', padding: '10px 24px', background: '#F1F5F9', color: '#64748B', borderRadius: '8px', textDecoration: 'none', fontSize: '14px', fontWeight: 500 }}>
              返回首页
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // SSE超时提示
  if (isTimeout) {
    return (
      <div className="learn-page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
        <div style={{ textAlign: 'center', color: '#64748B', maxWidth: '400px' }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>⏰</div>
          <div style={{ fontSize: '20px', fontWeight: 600, color: '#1E293B', marginBottom: '12px' }}>处理时间较长</div>
          <div style={{ fontSize: '14px', lineHeight: '1.8', color: '#64748B', marginBottom: '24px' }}>
            AI正在努力生成知识结构，但还需要一些时间。您可以稍后再来查看，或者重试。
          </div>
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
            <button
              onClick={() => {
                if (retryCount < 3) {
                  setRetryCount(prev => prev + 1);
                  setIsTimeout(false);
                }
              }}
              disabled={retryCount >= 3}
              style={{
                padding: '10px 24px',
                background: retryCount >= 3 ? '#CBD5E1' : '#5B6CF0',
                color: '#fff',
                borderRadius: '8px',
                border: 'none',
                fontSize: '14px',
                fontWeight: 500,
                cursor: retryCount >= 3 ? 'not-allowed' : 'pointer',
              }}
            >
              {retryCount >= 3 ? '重试次数已用完' : '重试'}
            </button>
            <Link to="/" style={{ display: 'inline-block', padding: '10px 24px', background: '#F1F5F9', color: '#64748B', borderRadius: '8px', textDecoration: 'none', fontSize: '14px', fontWeight: 500 }}>
              返回首页
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // 无主题且无内容时，显示引导页面
  if (!hasTopic && allComponents.length === 0) {
    return (
      <div className="learn-page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
        <div style={{ textAlign: 'center', color: '#64748B', maxWidth: '400px' }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>📚</div>
          <div style={{ fontSize: '20px', fontWeight: 600, color: '#1E293B', marginBottom: '12px' }}>开始你的学习之旅</div>
          <div style={{ fontSize: '14px', lineHeight: '1.8', color: '#64748B', marginBottom: '24px' }}>
            请先在首页输入你想学习的主题，AI将为你构建完整的知识体系和学习路径。
          </div>
          <Link to="/" style={{ display: 'inline-block', padding: '10px 24px', background: '#5B6CF0', color: '#fff', borderRadius: '8px', textDecoration: 'none', fontSize: '14px', fontWeight: 500 }}>
            前往首页选择主题
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="learn-page">
      <div className="learn-grid">
        {/* 左侧：Tab 按钮栏 */}
        <div className="learn-tab-bar">
          <button
            className={`learn-tab-btn ${activeTab === 'teaching' ? 'active' : ''}`}
            onClick={() => setActiveTab('teaching')}
          >
            📖 教学
          </button>
          <button
            className={`learn-tab-btn ${activeTab === 'exercise' ? 'active' : ''}`}
            onClick={() => setActiveTab('exercise')}
          >
            📝 综合练习
          </button>
        </div>

        {/* 右侧：内容区域 */}
        <div className="learn-content">
          {activeTab === 'teaching' ? (
            // 对话式教学面板（包含全景介绍和知识讲解）
            <ChatTeachingPanel
              topicId={effectiveTopicId}
              topicName={effectiveTopicName}
              userId="anonymous"
              components={allComponents}
              currentComponentIndex={currentComponentIndex}
              onComponentChange={setCurrentComponentIndex}
              initialComponentId={urlComponentId}  // 传递来自全景页的组件ID
            />
          ) : (
            // 综合练习面板
            <LearningPathPanel
              blocks={knowledgeBlocks}
            />
          )}
        </div>
      </div>
    </div>
  );
};

// 全景知识图谱页面包装器 - 从URL或localStorage读取topicId
const PanoramaPageWrapper: React.FC = () => {
  const [searchParams] = useSearchParams();
  const urlTopicId = searchParams.get('topicId') || '';
  const storedTopicId = localStorage.getItem('currentTopicId') || '';
  const topicId = urlTopicId || storedTopicId || '';
  const storedTopicName = localStorage.getItem('currentTopicName') || '';
  const urlTopicName = searchParams.get('topicName') || '';
  const topicName = urlTopicName || storedTopicName || '未知主题';

  const [blocks, setBlocks] = useState<KnowledgeBlock[]>([]);
  // 用于触发刷新（当学习页完成学习时）
  const [refreshKey, setRefreshKey] = useState(0);

  // 加载知识结构
  useEffect(() => {
    if (!topicId) return;
    // 尝试从 localStorage 恢复，或从 API 获取
    const cached = localStorage.getItem(`knowledgeBlocks_${topicId}`);
    if (cached) {
      try {
        setBlocks(JSON.parse(cached));
      } catch { /* ignore */ }
    }
    // 如果没有缓存，从API获取
    if (!cached) {
      getTopicStructure(topicId, 'anonymous').then(data => {
        if (Array.isArray(data) && data.length > 0) {
          setBlocks(data);
          localStorage.setItem(`knowledgeBlocks_${topicId}`, JSON.stringify(data));
        }
      }).catch(() => {});
    }
  }, [topicId, refreshKey]);

  // 监听 storage 事件，当学习页更新进度时刷新
  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'knowledgeBlocks_refresh_timestamp') {
        setRefreshKey(prev => prev + 1);
      }
    };
    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  // 定时检查刷新标记（同一标签页内storage事件不会触发，需要轮询）
  useEffect(() => {
    let lastTimestamp = localStorage.getItem('knowledgeBlocks_refresh_timestamp') || '0';
    const interval = setInterval(() => {
      const currentTimestamp = localStorage.getItem('knowledgeBlocks_refresh_timestamp') || '0';
      if (currentTimestamp !== lastTimestamp) {
        lastTimestamp = currentTimestamp;
        setRefreshKey(prev => prev + 1);
      }
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  return <PanoramaProgress blocks={blocks} topicName={topicName} topicId={topicId} />;
};

// App组件
const App: React.FC = () => {
  return (
    <Router>
      <div className="app">
        <Navigation />
        <main className="app-main">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/learn" element={<LearnPage />} />
            <Route path="/panorama" element={<PanoramaPageWrapper />} />
            {/* 保留子路由以便直接访问 */}
            <Route path="/recommend" element={<TopicRecommendations />} />
            <Route path="/teaching" element={<TeachingPanel componentId="p1" />} />
            <Route path="/exercise" element={<ExercisePanel pointId="p1" totalQuestions={5} />} />
            <Route path="/progress" element={<ProgressPanel userId="u1" topicId="t1" />} />
            <Route path="/path" element={<LearningPathPanel userId="u1" topicId="t1" />} />
            <Route path="/history" element={<LearningHistory userId="u1" />} />
            <Route path="/skip" element={<SkipTest userId="u1" topicId="t1" />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
};

export default App;
