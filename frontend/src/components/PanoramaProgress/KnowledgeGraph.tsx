/**
 * 知识图谱可视化组件
 * 
 * 使用SVG绘制三层知识体系的树形结构图
 * - L1 知识板块：根节点，大圆形
 * - L2 知识点：子节点，中等圆形/矩形
 * - L3 知识组件：叶子节点，小圆点
 * 
 * 特性：
 * - 力导向布局或树形布局
 * - 节点间有连线表示层级关系
 * - 不同状态用不同颜色区分
 * - 支持缩放、拖拽、点击交互
 */

import React, { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import { KnowledgeBlock, KnowledgePoint, KnowledgeComponent, KnowledgeComponentStatus } from '../../types';
import './KnowledgeGraph.css';

// ==================== 类型定义 ====================

interface NodeData {
  id: string;
  name: string;
  type: 'block' | 'point' | 'component';
  status: KnowledgeComponentStatus;
  isKeyPoint?: boolean;
  difficulty?: string;
  x: number;
  y: number;
  parentId?: string;
  data: KnowledgeBlock | KnowledgePoint | KnowledgeComponent;
}

interface LinkData {
  source: string;
  target: string;
}

interface KnowledgeGraphProps {
  blocks: KnowledgeBlock[];
  onNodeClick: (node: NodeData) => void;
  onPointClick?: (point: KnowledgePoint) => void;
  className?: string;
}

// ==================== 常量配置 ====================

const CONFIG = {
  width: 1200,
  height: 800,
  nodeRadius: {
    block: 45,
    point: 30,
    component: 12
  },
  colors: {
    block: '#5B6CF0',
    point: '#818CF8',
    component: '#A5B4FC',
    completed: '#059669',
    inProgress: '#5B6CF0',
    notStarted: '#94A3B8',
    locked: '#CBD5E1',
    keyPoint: '#D97706',
    link: '#E2E8F0'
  },
  levels: {
    block: 150,
    point: 350,
    component: 550
  }
};

// ==================== 辅助函数 ====================

function getStatusColor(status: KnowledgeComponentStatus): string {
  switch (status) {
    case 'completed': return CONFIG.colors.completed;
    case 'in_progress': return CONFIG.colors.inProgress;
    case 'locked': return CONFIG.colors.locked;
    case 'not_started':
    default: return CONFIG.colors.notStarted;
  }
}

function getNodeColor(node: NodeData): string {
  // 优先使用状态颜色
  const statusColor = getStatusColor(node.status);
  if (node.status !== 'not_started' && node.status !== 'locked') {
    return statusColor;
  }
  // 默认使用类型颜色
  switch (node.type) {
    case 'block': return CONFIG.colors.block;
    case 'point': return CONFIG.colors.point;
    case 'component': return CONFIG.colors.component;
  }
}

// ==================== 组件 ====================

export const KnowledgeGraph: React.FC<KnowledgeGraphProps> = ({
  blocks,
  onNodeClick,
  onPointClick,
  className = ''
}) => {
  // ===== 状态 =====
  const [scale, setScale] = useState(1);
  const [translate, setTranslate] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  
  const svgRef = useRef<SVGSVGElement>(null);

  // ===== 计算节点布局 =====
  const { nodes, links } = useMemo(() => {
    const nodeList: NodeData[] = [];
    const linkList: LinkData[] = [];
    
    let blockIndex = 0;
    const totalBlocks = blocks.length;
    const blockSpacing = CONFIG.width / (totalBlocks + 1);
    
    blocks.forEach((block, bIdx) => {
      // L1: 知识板块节点
      const blockX = blockSpacing * (bIdx + 1);
      const blockY = CONFIG.levels.block;
      const blockId = block.block_id;
      
      nodeList.push({
        id: blockId,
        name: block.block_name,
        type: 'block',
        status: block.status,
        x: blockX,
        y: blockY,
        data: block
      });
      
      // L2: 知识点节点
      const totalPoints = block.points.length;
      const pointSpacing = blockSpacing / (totalPoints + 1);
      
      block.points.forEach((point, pIdx) => {
        const pointX = blockX - blockSpacing / 2 + pointSpacing * (pIdx + 1);
        const pointY = CONFIG.levels.point;
        const pointId = point.point_id;
        
        nodeList.push({
          id: pointId,
          name: point.point_name,
          type: 'point',
          status: point.status,
          isKeyPoint: point.is_key_point,
          difficulty: point.difficulty,
          x: pointX,
          y: pointY,
          parentId: blockId,
          data: point
        });
        
        linkList.push({ source: blockId, target: pointId });
        
        // L3: 知识组件节点（只在展开时显示）
        if (expandedNodes.has(pointId)) {
          const totalComponents = point.components.length;
          const compSpacing = pointSpacing / (totalComponents + 1);
          
          point.components.forEach((comp, cIdx) => {
            const compX = pointX - pointSpacing / 2 + compSpacing * (cIdx + 1);
            const compY = CONFIG.levels.component;
            const compId = comp.component_id;
            
            nodeList.push({
              id: compId,
              name: comp.component_name,
              type: 'component',
              status: comp.status,
              x: compX,
              y: compY,
              parentId: pointId,
              data: comp
            });
            
            linkList.push({ source: pointId, target: compId });
          });
        }
      });
    });
    
    return { nodes: nodeList, links: linkList };
  }, [blocks, expandedNodes]);

  // ===== 事件处理 =====
  
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setScale(prev => Math.max(0.5, Math.min(2, prev * delta)));
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.target === svgRef.current) {
      setIsDragging(true);
      setDragStart({ x: e.clientX - translate.x, y: e.clientY - translate.y });
    }
  }, [translate]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (isDragging) {
      setTranslate({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y
      });
    }
  }, [isDragging, dragStart]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleNodeClick = useCallback((node: NodeData) => {
    if (node.type === 'point') {
      // 切换展开/收起
      setExpandedNodes(prev => {
        const next = new Set(prev);
        if (next.has(node.id)) {
          next.delete(node.id);
        } else {
          next.add(node.id);
        }
        return next;
      });
      onPointClick?.(node.data as KnowledgePoint);
    }
    onNodeClick(node);
  }, [onNodeClick, onPointClick]);

  const handleResetView = useCallback(() => {
    setScale(1);
    setTranslate({ x: 0, y: 0 });
  }, []);

  const handleZoomIn = useCallback(() => {
    setScale(prev => Math.min(2, prev * 1.2));
  }, []);

  const handleZoomOut = useCallback(() => {
    setScale(prev => Math.max(0.5, prev / 1.2));
  }, []);

  // ===== 渲染 =====
  
  return (
    <div className={`knowledge-graph-container ${className}`}>
      {/* 控制栏 */}
      <div className="knowledge-graph-controls">
        <button className="graph-control-btn" onClick={handleZoomIn} title="放大">
          <svg viewBox="0 0 24 24" width="18" height="18">
            <path fill="currentColor" d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
          </svg>
        </button>
        <button className="graph-control-btn" onClick={handleZoomOut} title="缩小">
          <svg viewBox="0 0 24 24" width="18" height="18">
            <path fill="currentColor" d="M19 13H5v-2h14v2z"/>
          </svg>
        </button>
        <button className="graph-control-btn" onClick={handleResetView} title="重置视图">
          <svg viewBox="0 0 24 24" width="18" height="18">
            <path fill="currentColor" d="M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z"/>
          </svg>
        </button>
      </div>

      {/* 图例 */}
      <div className="knowledge-graph-legend">
        <div className="graph-legend-item">
          <span className="graph-legend-dot" style={{ background: CONFIG.colors.block }} />
          <span>知识板块</span>
        </div>
        <div className="graph-legend-item">
          <span className="graph-legend-dot" style={{ background: CONFIG.colors.point }} />
          <span>知识点</span>
        </div>
        <div className="graph-legend-item">
          <span className="graph-legend-dot" style={{ background: CONFIG.colors.component }} />
          <span>知识组件</span>
        </div>
        <div className="graph-legend-divider" />
        <div className="graph-legend-item">
          <span className="graph-legend-dot" style={{ background: CONFIG.colors.completed }} />
          <span>已完成</span>
        </div>
        <div className="graph-legend-item">
          <span className="graph-legend-dot" style={{ background: CONFIG.colors.inProgress }} />
          <span>进行中</span>
        </div>
        <div className="graph-legend-item">
          <span className="graph-legend-dot" style={{ background: CONFIG.colors.notStarted }} />
          <span>未开始</span>
        </div>
      </div>

      {/* SVG 画布 */}
      <svg
        ref={svgRef}
        className="knowledge-graph-svg"
        viewBox={`0 0 ${CONFIG.width} ${CONFIG.height}`}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
      >
        <defs>
          {/* 渐变定义 */}
          <linearGradient id="blockGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#5B6CF0" />
            <stop offset="100%" stopColor="#818CF8" />
          </linearGradient>
          <linearGradient id="pointGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#818CF8" />
            <stop offset="100%" stopColor="#A5B4FC" />
          </linearGradient>
          <filter id="nodeShadow" x="-50%" y="-50%" width="200%" height="200%">
            <feDropShadow dx="0" dy="2" stdDeviation="3" floodOpacity="0.2"/>
          </filter>
          <filter id="nodeGlow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="4" result="coloredBlur"/>
            <feMerge>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
        </defs>

        <g transform={`translate(${translate.x}, ${translate.y}) scale(${scale})`}>
          {/* 连线 */}
          {links.map((link, index) => {
            const sourceNode = nodes.find(n => n.id === link.source);
            const targetNode = nodes.find(n => n.id === link.target);
            if (!sourceNode || !targetNode) return null;
            
            return (
              <line
                key={`link-${index}`}
                x1={sourceNode.x}
                y1={sourceNode.y}
                x2={targetNode.x}
                y2={targetNode.y}
                stroke={CONFIG.colors.link}
                strokeWidth={2}
                strokeDasharray={targetNode.type === 'component' ? '4,4' : undefined}
                opacity={0.6}
              />
            );
          })}

          {/* 节点 */}
          {nodes.map(node => {
            const isHovered = hoveredNode === node.id;
            const radius = CONFIG.nodeRadius[node.type];
            const color = getNodeColor(node);
            
            return (
              <g
                key={node.id}
                transform={`translate(${node.x}, ${node.y})`}
                className={`graph-node graph-node--${node.type}`}
                onClick={() => handleNodeClick(node)}
                onMouseEnter={() => setHoveredNode(node.id)}
                onMouseLeave={() => setHoveredNode(null)}
                style={{ cursor: 'pointer' }}
              >
                {/* 外圈光晕（悬停或重点） */}
                {(isHovered || node.isKeyPoint) && (
                  <circle
                    r={radius + 8}
                    fill={node.isKeyPoint ? 'rgba(217, 119, 6, 0.15)' : 'rgba(91, 108, 240, 0.1)'}
                    className="graph-node-halo"
                  />
                )}
                
                {/* 主节点 */}
                <circle
                  r={radius}
                  fill={node.type === 'block' ? 'url(#blockGradient)' : 
                       node.type === 'point' ? 'url(#pointGradient)' : color}
                  stroke={isHovered ? '#5B6CF0' : '#FFFFFF'}
                  strokeWidth={isHovered ? 3 : 2}
                  filter="url(#nodeShadow)"
                  className="graph-node-circle"
                />
                
                {/* 重点标记 */}
                {node.isKeyPoint && (
                  <>
                    <circle
                      r={radius + 4}
                      fill="none"
                      stroke={CONFIG.colors.keyPoint}
                      strokeWidth={2}
                      strokeDasharray="4,2"
                    />
                    <text
                      y={-radius - 10}
                      textAnchor="middle"
                      fill={CONFIG.colors.keyPoint}
                      fontSize="10"
                      fontWeight="bold"
                    >
                      重点
                    </text>
                  </>
                )}
                
                {/* 节点文字 */}
                <text
                  y={radius + 20}
                  textAnchor="middle"
                  fill="#1E293B"
                  fontSize={node.type === 'block' ? 14 : node.type === 'point' ? 12 : 10}
                  fontWeight={node.type === 'block' ? 'bold' : 'normal'}
                  className="graph-node-label"
                >
                  {node.name.length > 8 && node.type !== 'block' 
                    ? node.name.slice(0, 8) + '...' 
                    : node.name}
                </text>
                
                {/* 状态指示器 */}
                {node.status === 'completed' && (
                  <g transform={`translate(${radius - 5}, ${-radius + 5})`}>
                    <circle r={8} fill={CONFIG.colors.completed} />
                    <text textAnchor="middle" dy="3" fill="white" fontSize="8">✓</text>
                  </g>
                )}
                
                {/* 展开指示器（知识点） */}
                {node.type === 'point' && (
                  <g transform={`translate(0, ${radius + 5})`}>
                    <circle r={8} fill="#FFFFFF" stroke="#CBD5E1" strokeWidth={1} />
                    <text textAnchor="middle" dy="3" fill="#64748B" fontSize="10">
                      {expandedNodes.has(node.id) ? '−' : '+'}
                    </text>
                  </g>
                )}
              </g>
            );
          })}
        </g>
      </svg>

      {/* 提示信息 */}
      <div className="knowledge-graph-hint">
        <span>💡 滚轮缩放 · 拖拽移动 · 点击知识点展开/收起</span>
      </div>
    </div>
  );
};

export default KnowledgeGraph;
