/**
 * AI智能教育课程平台 - 根组件
 * 
 * 导航精简为：首页、学习、全景知识图谱
 * 学习页面整合知识讲解、练习题、问答、学习进度等功能
 */

import React, { useState, useEffect, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';

// 组件导入
import { TopicInput } from './components/TopicInput';
import { TopicRecommendations } from './components/TopicRecommendations';
import { TeachingPanel } from './components/TeachingPanel';
import { ExercisePanel } from './components/ExercisePanel';
import { QAPanel } from './components/QAPanel';
import { ProgressPanel } from './components/ProgressPanel';
import { PanoramaProgress } from './components/PanoramaProgress';
import { LearningPathPanel } from './components/LearningPathPanel';
import { LearningHistory } from './components/LearningHistory';
import { SkipTest } from './components/SkipTest';

import { getTopicStructure, getTopicOverview, getTopicStatus } from './services/api';
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

  // 判断是否有真实的topicId（来自URL或sessionStorage）
  const sessionTopicId = sessionStorage.getItem('currentTopicId') || '';
  const sessionTopicName = sessionStorage.getItem('currentTopicName') || '';
  const hasTopic = !!(topicId || sessionTopicId);

  const [knowledgeBlocks, setKnowledgeBlocks] = useState<KnowledgeBlock[]>([]);
  const [currentComponentIndex, setCurrentComponentIndex] = useState(0);
  const [exerciseMode, setExerciseMode] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [overview, setOverview] = useState('');
  // 如果URL有componentId，直接进入讲解模式；否则保持sessionStorage中的模式
  const [overviewMode, setOverviewMode] = useState(!urlComponentId);

  // 获取所有知识组件的扁平列表
  const allComponents = knowledgeBlocks.flatMap(block =>
    block.points.flatMap(point =>
      point.components.map(comp => ({
        componentId: comp.component_id,
        componentName: comp.component_name,
        pointId: point.point_id,
        pointName: point.point_name,
        blockName: block.block_name,
        isKeyDifficulty: point.is_key_point || false,
      }))
    )
  );

  const currentComponent = allComponents[currentComponentIndex];
  const currentPointId = currentComponent?.pointId || '';
  const effectiveTopicId = topicId || sessionTopicId;
  const effectiveTopicName = topicName || sessionTopicName;

  // 加载知识结构（轮询模式：后端异步处理LLM，前端每2秒查询状态）
  useEffect(() => {
    if (!effectiveTopicId) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    const pollInterval = setInterval(async () => {
      try {
        const status = await getTopicStatus(effectiveTopicId);

        if (status.overview_ready && !overview) {
          const overviewData = await getTopicOverview(effectiveTopicId);
          setOverview(overviewData.overview);
        }

        if (status.structure_ready && knowledgeBlocks.length === 0) {
          const blocks = await getTopicStructure(effectiveTopicId, 'anonymous');
          setKnowledgeBlocks(blocks);
        }

        if (status.status === 'completed') {
          clearInterval(pollInterval);
          sessionStorage.setItem('currentTopicId', effectiveTopicId);
          sessionStorage.setItem('currentTopicName', effectiveTopicName);
          setLoading(false);
        }
      } catch (err) {
        console.error('轮询状态失败:', err);
      }
    }, 2000);

    return () => clearInterval(pollInterval);
  }, [effectiveTopicId]);

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

  // Handle URL componentId (from panorama page click)
  useEffect(() => {
    if (urlComponentId && allComponents.length > 0) {
      const idx = allComponents.findIndex(c => c.componentId === urlComponentId);
      if (idx >= 0) {
        setCurrentComponentIndex(idx);
        setOverviewMode(false);
      }
    }
  }, [urlComponentId, allComponents.length]);

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
          <div style={{ fontSize: '14px', color: '#94A3B8' }}>
            <Link to="/" style={{ color: '#5B6CF0' }}>返回首页</Link>
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
        {/* 左侧：教学面板 */}
        <div className="learn-grid-left">
          {overviewMode ? (
            // Show overview
            <div className="teaching-panel">
              <div className="teaching-panel-header">
                <h3 className="teaching-panel-title">📚 {effectiveTopicName} — 全景介绍</h3>
              </div>
              <div className="teaching-panel-messages" style={{ padding: '20px', whiteSpace: 'pre-wrap', lineHeight: '1.8', color: '#334155' }}>
                {overview || '正在加载全景介绍...'}
              </div>
              <div className="teaching-panel-actions">
                <button className="teaching-action-btn teaching-action-next" onClick={() => { setCurrentComponentIndex(0); setOverviewMode(false); }} disabled={allComponents.length === 0}>
                  <span>开始学习第一个知识组件</span>
                </button>
              </div>
            </div>
          ) : (
            <>
              <TeachingPanel
                componentId={currentComponent?.componentId || ''}
                onNext={handleNext}
                onExercise={() => setExerciseMode(true)}
              />
              {exerciseMode && (
                <ExercisePanel pointId={currentPointId} totalQuestions={3} />
              )}
            </>
          )}
        </div>

        {/* 右侧：学习路径面板 + 问答面板 */}
        <div className="learn-grid-right">
          <LearningPathPanel userId="anonymous" topicId={effectiveTopicId} />
          <QAPanel userId="anonymous" pointId={currentPointId} />
        </div>
      </div>
    </div>
  );
};

// 全景知识图谱页面包装器 - 从URL或sessionStorage读取topicId
const PanoramaPageWrapper: React.FC = () => {
  const [searchParams] = useSearchParams();
  const urlTopicId = searchParams.get('topicId') || '';
  const sessionTopicId = sessionStorage.getItem('currentTopicId') || '';
  const topicId = urlTopicId || sessionTopicId || '';
  const sessionTopicName = sessionStorage.getItem('currentTopicName') || '';
  const urlTopicName = searchParams.get('topicName') || '';
  const topicName = urlTopicName || sessionTopicName || '未知主题';

  const [blocks, setBlocks] = useState<KnowledgeBlock[]>([]);

  useEffect(() => {
    if (!topicId) return;
    // 尝试从 sessionStorage 恢复，或从 API 获取
    const cached = sessionStorage.getItem(`knowledgeBlocks_${topicId}`);
    if (cached) {
      try {
        setBlocks(JSON.parse(cached));
        return;
      } catch { /* ignore */ }
    }
    getTopicStructure(topicId, 'anonymous').then(data => {
      if (Array.isArray(data) && data.length > 0) {
        setBlocks(data);
        sessionStorage.setItem(`knowledgeBlocks_${topicId}`, JSON.stringify(data));
      }
    }).catch(() => {});
  }, [topicId]);

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
            <Route path="/qa" element={<QAPanel userId="u1" pointId="p1" />} />
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
