/**
 * 全景知识图谱 - 分层架构图风格
 * Panoramic Knowledge Graph - Layered Architecture Style
 *
 * 设计参考：蓝色系分层堆叠架构图
 * - L1 知识块：最外层大色块（深蓝），横向排列
 * - L2 知识点：嵌套在中蓝色块中，包含技术标签
 * - L3 知识元：最内层小色块（浅蓝），显示状态
 * - 左侧垂直标注：知识体系名称
 * - 右侧面板：学习进度与统计
 */

import React, { useState, useMemo, useCallback } from 'react';
import { KnowledgeBlock, KnowledgePoint, KnowledgeComponent } from '../../types';
import './KnowledgeGraphArch.css';

// ==================== 类型定义 ====================

interface KnowledgeGraphArchProps {
  blocks: KnowledgeBlock[];
  onNodeClick?: (node: {
    id: string;
    name: string;
    type: 'block' | 'point' | 'component';
    status: string;
    data: KnowledgeBlock | KnowledgePoint | KnowledgeComponent;
    parentId?: string;
  }) => void;
  onPointClick?: (point: KnowledgePoint) => void;
}

interface BlockProgress {
  total: number;
  completed: number;
  inProgress: number;
  percentage: number;
}

// ==================== 辅助函数 ====================

function getBlockProgress(block: KnowledgeBlock): BlockProgress {
  let total = 0, completed = 0, inProgress = 0;
  block.points.forEach(point => {
    point.components.forEach(comp => {
      total++;
      if (comp.status === 'completed') completed++;
      else if (comp.status === 'in_progress') inProgress++;
    });
  });
  return {
    total,
    completed,
    inProgress,
    percentage: total > 0 ? Math.round((completed / total) * 100) : 0,
  };
}

function getPointProgress(point: KnowledgePoint): BlockProgress {
  const total = point.components.length;
  const completed = point.components.filter(c => c.status === 'completed').length;
  const inProgress = point.components.filter(c => c.status === 'in_progress').length;
  return {
    total,
    completed,
    inProgress,
    percentage: total > 0 ? Math.round((completed / total) * 100) : 0,
  };
}

function getStatusLabel(status: string): string {
  switch (status) {
    case 'completed': return '已完成';
    case 'in_progress': return '学习中';
    default: return '未开始';
  }
}

function getStatusIcon(status: string): string {
  switch (status) {
    case 'completed': return '✓';
    case 'in_progress': return '▶';
    default: return '○';
  }
}

function getDifficultyLabel(difficulty: string): string {
  switch (difficulty) {
    case 'hard': return '困难';
    case 'medium': return '中等';
    default: return '基础';
  }
}

function getDifficultyClass(difficulty: string): string {
  switch (difficulty) {
    case 'hard': return 'diff-hard';
    case 'medium': return 'diff-medium';
    default: return 'diff-easy';
  }
}

// ==================== 组件 ====================

export const KnowledgeGraphArch: React.FC<KnowledgeGraphArchProps> = ({
  blocks,
  onNodeClick,
  onPointClick,
}) => {
  const [expandedBlocks, setExpandedBlocks] = useState<Set<string>>(new Set(blocks.map(b => b.block_id)));
  const [expandedPoints, setExpandedPoints] = useState<Set<string>>(new Set());
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  // 全局统计
  const globalStats = useMemo(() => {
    let total = 0, completed = 0, inProgress = 0, keyTotal = 0, keyCompleted = 0;
    blocks.forEach(block => {
      block.points.forEach(point => {
        if (point.is_key_point) {
          keyTotal++;
          if (point.components.every(c => c.status === 'completed')) keyCompleted++;
        }
        point.components.forEach(comp => {
          total++;
          if (comp.status === 'completed') completed++;
          else if (comp.status === 'in_progress') inProgress++;
        });
      });
    });
    return {
      total, completed, inProgress,
      percentage: total > 0 ? Math.round((completed / total) * 100) : 0,
      keyTotal, keyCompleted,
      keyPercentage: keyTotal > 0 ? Math.round((keyCompleted / keyTotal) * 100) : 0,
    };
  }, [blocks]);

  // 展开/折叠 L1 知识块
  const toggleBlock = useCallback((blockId: string) => {
    setExpandedBlocks(prev => {
      const next = new Set(prev);
      if (next.has(blockId)) next.delete(blockId);
      else next.add(blockId);
      return next;
    });
  }, []);

  // 展开/折叠 L2 知识点
  const togglePoint = useCallback((pointId: string) => {
    setExpandedPoints(prev => {
      const next = new Set(prev);
      if (next.has(pointId)) next.delete(pointId);
      else next.add(pointId);
      return next;
    });
  }, []);

  // 处理 L3 知识元点击
  const handleComponentClick = useCallback((comp: KnowledgeComponent, pointId: string, blockId: string) => {
    onNodeClick?.({
      id: comp.component_id,
      name: comp.component_name,
      type: 'component',
      status: comp.status,
      data: comp,
      parentId: pointId,
    });
  }, [onNodeClick]);

  // 处理 L2 知识点点击
  const handlePointClick = useCallback((point: KnowledgePoint) => {
    onPointClick?.(point);
  }, [onPointClick]);

  if (!blocks || blocks.length === 0) {
    return (
      <div className="arch-empty">
        <div className="arch-empty-icon">📊</div>
        <p>知识图谱数据加载中...</p>
      </div>
    );
  }

  return (
    <div className="arch-container">
      {/* 左侧垂直标注 */}
      <div className="arch-sidebar">
        <div className="arch-sidebar-label">
          <span className="arch-sidebar-text">三层知识体系架构</span>
          <span className="arch-sidebar-sub">Knowledge Architecture</span>
        </div>
        <div className="arch-sidebar-layers">
          <div className="arch-sidebar-layer">
            <span className="arch-layer-dot l1"></span>
            <span>L1 知识块</span>
          </div>
          <div className="arch-sidebar-layer">
            <span className="arch-layer-dot l2"></span>
            <span>L2 知识点</span>
          </div>
          <div className="arch-sidebar-layer">
            <span className="arch-layer-dot l3"></span>
            <span>L3 知识元</span>
          </div>
        </div>
      </div>

      {/* 主内容区 - 分层架构 */}
      <div className="arch-main">
        {/* 顶部：L1 知识块层 */}
        <div className="arch-layer arch-layer-l1">
          <div className="arch-layer-header">
            <div className="arch-layer-title">
              <span className="arch-layer-icon">🏗️</span>
              知识块层 (L1)
            </div>
            <div className="arch-layer-desc">核心知识模块划分</div>
          </div>
          <div className="arch-layer-content">
            {blocks.map((block, index) => {
              const progress = getBlockProgress(block);
              const isExpanded = expandedBlocks.has(block.block_id);
              const isHovered = hoveredId === block.block_id;

              return (
                <div
                  key={block.block_id}
                  className={`arch-block ${block.status} ${isHovered ? 'hovered' : ''}`}
                  onMouseEnter={() => setHoveredId(block.block_id)}
                  onMouseLeave={() => setHoveredId(null)}
                >
                  {/* L1 块头部 */}
                  <div className="arch-block-header" onClick={() => toggleBlock(block.block_id)}>
                    <div className="arch-block-left">
                      <span className="arch-block-index">B{index + 1}</span>
                      <span className="arch-block-name">{block.block_name}</span>
                      <span className={`arch-block-status ${block.status}`}>
                        {getStatusIcon(block.status)} {getStatusLabel(block.status)}
                      </span>
                    </div>
                    <div className="arch-block-right">
                      <div className="arch-block-progress">
                        <div className="arch-progress-bar">
                          <div
                            className="arch-progress-fill"
                            style={{ width: `${progress.percentage}%` }}
                          />
                        </div>
                        <span className="arch-progress-text">{progress.percentage}%</span>
                      </div>
                      <span className={`arch-expand-icon ${isExpanded ? 'expanded' : ''}`}>
                        ▼
                      </span>
                    </div>
                  </div>

                  {/* L2 知识点层 - 嵌套在 L1 内 */}
                  {isExpanded && (
                    <div className="arch-layer arch-layer-l2">
                      <div className="arch-layer-content arch-layer-l2-content">
                        {block.points.map((point, pIndex) => {
                          const pProgress = getPointProgress(point);
                          const isPExpanded = expandedPoints.has(point.point_id);
                          const isPHovered = hoveredId === point.point_id;

                          return (
                            <div
                              key={point.point_id}
                              className={`arch-point ${point.status} ${point.is_key_point ? 'key-point' : ''} ${isPHovered ? 'hovered' : ''}`}
                              onMouseEnter={() => setHoveredId(point.point_id)}
                              onMouseLeave={() => setHoveredId(null)}
                            >
                              {/* L2 点头部 */}
                              <div className="arch-point-header" onClick={() => togglePoint(point.point_id)}>
                                <div className="arch-point-left">
                                  <span className="arch-point-index">P{pIndex + 1}</span>
                                  <span className="arch-point-name">{point.point_name}</span>
                                  {point.is_key_point && (
                                    <span className="arch-badge arch-badge-key">⭐ 重点</span>
                                  )}
                                  <span className={`arch-badge arch-badge-diff ${getDifficultyClass(point.difficulty)}`}>
                                    {getDifficultyLabel(point.difficulty)}
                                  </span>
                                </div>
                                <div className="arch-point-right">
                                  <span className="arch-point-progress">
                                    {pProgress.completed}/{pProgress.total}
                                  </span>
                                  <span className={`arch-expand-icon small ${isPExpanded ? 'expanded' : ''}`}>
                                    ▼
                                  </span>
                                </div>
                              </div>

                              {/* L3 知识元层 - 嵌套在 L2 内 */}
                              {isPExpanded && (
                                <div className="arch-layer arch-layer-l3">
                                  <div className="arch-layer-content arch-layer-l3-content">
                                    {point.components.map((comp, cIndex) => (
                                      <div
                                        key={comp.component_id}
                                        className={`arch-component ${comp.status} ${hoveredId === comp.component_id ? 'hovered' : ''}`}
                                        onClick={() => handleComponentClick(comp, point.point_id, block.block_id)}
                                        onMouseEnter={() => setHoveredId(comp.component_id)}
                                        onMouseLeave={() => setHoveredId(null)}
                                      >
                                        <span className="arch-component-index">C{cIndex + 1}</span>
                                        <span className="arch-component-name">{comp.component_name}</span>
                                        <span className={`arch-component-status ${comp.status}`}>
                                          {getStatusIcon(comp.status)}
                                        </span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* 右侧统计面板 */}
      <div className="arch-stats-panel">
        <div className="arch-stats-title">学习统计</div>
        <div className="arch-stats-item">
          <div className="arch-stats-value">{globalStats.percentage}%</div>
          <div className="arch-stats-label">总体进度</div>
          <div className="arch-stats-bar">
            <div className="arch-stats-bar-fill" style={{ width: `${globalStats.percentage}%` }} />
          </div>
        </div>
        <div className="arch-stats-row">
          <div className="arch-stats-mini">
            <div className="arch-stats-mini-value completed">{globalStats.completed}</div>
            <div className="arch-stats-mini-label">已完成</div>
          </div>
          <div className="arch-stats-mini">
            <div className="arch-stats-mini-value in-progress">{globalStats.inProgress}</div>
            <div className="arch-stats-mini-label">进行中</div>
          </div>
          <div className="arch-stats-mini">
            <div className="arch-stats-mini-value total">{globalStats.total}</div>
            <div className="arch-stats-mini-label">总组件</div>
          </div>
        </div>
        <div className="arch-stats-divider" />
        <div className="arch-stats-item">
          <div className="arch-stats-value key">{globalStats.keyPercentage}%</div>
          <div className="arch-stats-label">重点掌握</div>
          <div className="arch-stats-sub">{globalStats.keyCompleted}/{globalStats.keyTotal} 个重点</div>
        </div>
        <div className="arch-stats-divider" />
        <div className="arch-stats-legend">
          <div className="arch-stats-legend-title">状态图例</div>
          <div className="arch-legend-row">
            <span className="arch-legend-dot completed"></span>
            <span>已完成</span>
          </div>
          <div className="arch-legend-row">
            <span className="arch-legend-dot in-progress"></span>
            <span>进行中</span>
          </div>
          <div className="arch-legend-row">
            <span className="arch-legend-dot not-started"></span>
            <span>未开始</span>
          </div>
          <div className="arch-legend-row">
            <span className="arch-legend-badge">⭐</span>
            <span>重点知识点</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default KnowledgeGraphArch;
