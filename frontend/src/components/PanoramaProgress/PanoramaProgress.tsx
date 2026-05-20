/**
 * 全景知识进度组件
 *
 * 功能：
 * - 使用知识图谱可视化展示三层知识体系
 * - 支持缩放、拖拽、点击交互
 * - 显示学习进度统计
 * - 点击知识点可跳转到学习页
 */

import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { KnowledgeBlock, KnowledgePoint, KnowledgeComponent } from '../../types';
import { getComponentProgress } from '../../utils/progressStorage';
import './styles.css';

// ==================== 类型定义 ====================

interface PanoramaProgressProps {
  blocks: KnowledgeBlock[];
  topicName: string;
  topicId: string;
}

interface NodeData {
  id: string;
  name: string;
  type: 'block' | 'point' | 'component';
  status: string;
  isKeyPoint?: boolean;
  difficulty?: string;
  x: number;
  y: number;
  parentId?: string;
  data: KnowledgeBlock | KnowledgePoint | KnowledgeComponent;
}

// ==================== 组件 ====================

export const PanoramaProgress: React.FC<PanoramaProgressProps> = ({
  blocks,
  topicName,
  topicId
}) => {
  const navigate = useNavigate();
  const [selectedPoint, setSelectedPoint] = useState<KnowledgePoint | null>(null);

  // 处理节点点击
  const handleNodeClick = useCallback((node: NodeData) => {
    if (node.type === 'component') {
      const component = node.data as KnowledgeComponent;
      const pointId = node.parentId;
      if (pointId) {
        navigate(`/learn?topicId=${topicId}&componentId=${component.component_id}`);
      }
    }
  }, [navigate, topicId]);

  // 处理知识点点击
  const handlePointClick = useCallback((point: KnowledgePoint) => {
    setSelectedPoint(point);
  }, []);

  // 跳转到学习
  const handleStartLearning = useCallback(() => {
    navigate(`/learn?topicId=${topicId}`);
  }, [navigate, topicId]);

  // 跳转到具体组件
  const handleComponentClick = useCallback((component: KnowledgeComponent) => {
    navigate(`/learn?topicId=${topicId}&componentId=${component.component_id}`);
  }, [navigate, topicId]);

  // 如果没有数据，显示空状态
  if (!blocks || blocks.length === 0) {
    return (
      <div className="panorama-progress">
        <div className="panorama-header">
          <h2 className="panorama-title">📊 {topicName} - 知识全景图</h2>
          <button className="panorama-back-btn" onClick={handleStartLearning}>
            返回学习
          </button>
        </div>
        <div className="panorama-empty">
          <div className="panorama-empty-icon">🗺️</div>
          <p className="panorama-empty-text">知识图谱加载中...</p>
          <p className="panorama-empty-subtext">请先开始学习以生成知识图谱</p>
        </div>
      </div>
    );
  }

  return (
    <div className="panorama-progress">
      {/* 头部 */}
      <div className="panorama-header">
        <h2 className="panorama-title">📊 {topicName} - 知识全景图</h2>
        <button className="panorama-back-btn" onClick={handleStartLearning}>
          返回学习
        </button>
      </div>

      {/* 主内容区 - 列表视图 */}
      <div className="panorama-list-container">
        {blocks.map((block, blockIndex) => (
          <div key={block.block_id} className="panorama-block">
            <div className="panorama-block-header">
              <span className="panorama-block-number">板块 {blockIndex + 1}</span>
              <span className="panorama-block-name">{block.block_name}</span>
              <span className={`panorama-block-status panorama-block-status--${block.status}`}>
                {block.status === 'completed' ? '✓' : block.status === 'in_progress' ? '▶' : '○'}
              </span>
            </div>
            <div className="panorama-points">
              {block.points.map((point, pointIndex) => (
                <div 
                  key={point.point_id} 
                  className={`panorama-point ${point.is_key_point ? 'panorama-point--key' : ''}`}
                >
                  <div className="panorama-point-header">
                    <span className="panorama-point-number">{pointIndex + 1}</span>
                    <span className="panorama-point-name">{point.point_name}</span>
                  </div>
                  <div className="panorama-components">
                    {point.components.map((comp) => {
                      const progress = getComponentProgress(comp.component_id);
                      return (
                        <button
                          key={comp.component_id}
                          className="panorama-component-btn"
                          onClick={() => handleComponentClick(comp)}
                        >
                          <span className="component-name">{comp.component_name}</span>
                          <span className="component-progress-tags">
                            {progress.learnStatus === 'learning' && <span className="progress-tag progress-tag--learning">学习中</span>}
                            {progress.learnStatus === 'completed' && <span className="progress-tag progress-tag--learn-completed">完成</span>}
                            {progress.exerciseStatus === 'practicing' && <span className="progress-tag progress-tag--practicing">做题中</span>}
                            {progress.exerciseStatus === 'passed' && <span className="progress-tag progress-tag--passed">练习通过</span>}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* 选中知识点详情 */}
      {selectedPoint && (
        <div className="point-detail-modal" onClick={() => setSelectedPoint(null)}>
          <div className="point-detail-content" onClick={e => e.stopPropagation()}>
            <div className="point-detail-header">
              <h3 className="point-detail-title">
                {selectedPoint.point_name}
                {selectedPoint.is_key_point && (
                  <span className="point-detail-badge">重点</span>
                )}
              </h3>
              <button 
                className="point-detail-close"
                onClick={() => setSelectedPoint(null)}
              >
                ×
              </button>
            </div>
            <div className="point-detail-body">
              <div className="point-detail-info">
                <div className="point-detail-item">
                  <span className="point-detail-label">难度：</span>
                  <span className={`point-detail-value point-detail-value--${selectedPoint.difficulty}`}>
                    {selectedPoint.difficulty === 'hard' ? '困难' : 
                     selectedPoint.difficulty === 'medium' ? '中等' : '简单'}
                  </span>
                </div>
                <div className="point-detail-item">
                  <span className="point-detail-label">状态：</span>
                  <span className={`point-detail-value point-detail-value--${selectedPoint.status}`}>
                    {selectedPoint.status === 'completed' ? '已完成' : 
                     selectedPoint.status === 'in_progress' ? '学习中' : '未开始'}
                  </span>
                </div>
                <div className="point-detail-item">
                  <span className="point-detail-label">组件数：</span>
                  <span className="point-detail-value">{selectedPoint.components.length} 个</span>
                </div>
              </div>
              <div className="point-detail-components">
                <h4 className="point-detail-subtitle">知识组件</h4>
                <div className="point-detail-component-list">
                  {selectedPoint.components.map(comp => (
                    <button
                      key={comp.component_id}
                      className={`point-detail-component-btn point-detail-component-btn--${comp.status}`}
                      onClick={() => handleComponentClick(comp)}
                    >
                      <span className="component-btn-status">
                        {comp.status === 'completed' ? '✓' : 
                         comp.status === 'in_progress' ? '▶' : '○'}
                      </span>
                      <span>{comp.component_name}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PanoramaProgress;
