/**
 * 三层知识结构全景知识图谱组件 V2
 *
 * 设计规范：
 * - L1: 圆形节点，直径90px，渐变填充 #5B6CF0 → #818CF8
 * - L2: 圆角矩形，120x60px，渐变填充 #818CF8 → #A5B4FC
 * - L3: 小圆点+标签，直径24px，纯色 #A5B4FC
 * - 布局：水平分层，Y轴固定，X轴动态计算
 * - 连线：L1→L2实线，L2→L3虚线
 */

import React, { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import { KnowledgeBlock, KnowledgePoint, KnowledgeComponent, KnowledgeComponentStatus } from '../../types';
import './KnowledgeGraphV2.css';

// ==================== 设计常量 ====================

const DESIGN = {
  // 画布尺寸
  canvas: {
    width: 1200,
    height: 650,
    paddingX: 100,
  },
  // 层级Y坐标
  levels: {
    l1: 100,
    l2: 300,
    l3: 520,
  },
  // 节点尺寸
  nodeSize: {
    l1: 90,      // 直径
    l2: { w: 120, h: 60 },
    l3: 24,      // 直径
  },
  // 间距
  spacing: {
    l1: 200,
    l2: 140,
    l3: 100,
  },
  // 颜色系统
  colors: {
    // 品牌色渐变
    l1Gradient: ['#5B6CF0', '#818CF8'],
    l2Gradient: ['#818CF8', '#A5B4FC'],
    l3Fill: '#A5B4FC',
    // 状态色
    completed: '#059669',
    inProgress: '#5B6CF0',
    notStarted: '#94A3B8',
    locked: '#CBD5E1',
    // 强调色
    keyPoint: '#D97706',
    difficult: '#DC2626',
    // 连线
    linkL1: '#E2E8F0',
    linkL2: '#CBD5E1',
    linkActive: '#5B6CF0',
  },
  // 字体
  font: {
    l1: { size: 16, weight: 700 },
    l2: { size: 13, weight: 600 },
    l3: { size: 11, weight: 400 },
  },
};

// ==================== 类型定义 ====================

interface NodePosition {
  x: number;
  y: number;
}

interface GraphNode {
  id: string;
  name: string;
  type: 'block' | 'point' | 'component';
  level: 1 | 2 | 3;
  status: KnowledgeComponentStatus;
  isKeyPoint?: boolean;
  isDifficult?: boolean;
  position: NodePosition;
  parentId?: string;
  data: KnowledgeBlock | KnowledgePoint | KnowledgeComponent;
  children?: string[];
}

interface GraphLink {
  source: string;
  target: string;
  type: 'l1-l2' | 'l2-l3';
}

interface KnowledgeGraphV2Props {
  blocks: KnowledgeBlock[];
  onNodeClick: (node: GraphNode) => void;
  onPointClick?: (point: KnowledgePoint) => void;
  className?: string;
}

// ==================== 辅助函数 ====================

function getStatusColor(status: KnowledgeComponentStatus): string {
  switch (status) {
    case 'completed': return DESIGN.colors.completed;
    case 'in_progress': return DESIGN.colors.inProgress;
    case 'locked': return DESIGN.colors.locked;
    default: return DESIGN.colors.notStarted;
  }
}

function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength - 1) + '…';
}

// ==================== 组件 ====================

export const KnowledgeGraphV2: React.FC<KnowledgeGraphV2Props> = ({
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
  const [expandedPoints, setExpandedPoints] = useState<Set<string>>(new Set());
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);

  const svgRef = useRef<SVGSVGElement>(null);

  // ===== 计算节点布局 =====
  const { nodes, links } = useMemo(() => {
    const nodeMap = new Map<string, GraphNode>();
    const linkList: GraphLink[] = [];

    if (!blocks || blocks.length === 0) {
      return { nodes: nodeMap, links: linkList };
    }

    // L1 层 - 知识板块
    const l1Count = blocks.length;
    const l1AvailableWidth = DESIGN.canvas.width - 2 * DESIGN.canvas.paddingX;
    const l1Spacing = l1AvailableWidth / (l1Count + 1);

    blocks.forEach((block, bIndex) => {
      const l1X = DESIGN.canvas.paddingX + l1Spacing * (bIndex + 1);
      const l1Node: GraphNode = {
        id: block.block_id,
        name: block.block_name,
        type: 'block',
        level: 1,
        status: block.status,
        position: { x: l1X, y: DESIGN.levels.l1 },
        data: block,
        children: block.points.map(p => p.point_id),
      };
      nodeMap.set(block.block_id, l1Node);

      // L2 层 - 知识点
      const points = block.points;
      const l2Count = points.length;
      const l2TotalWidth = (l2Count - 1) * DESIGN.spacing.l2;
      const l2StartX = l1X - l2TotalWidth / 2;

      points.forEach((point, pIndex) => {
        const l2X = l2StartX + pIndex * DESIGN.spacing.l2;
        const l2Node: GraphNode = {
          id: point.point_id,
          name: point.point_name,
          type: 'point',
          level: 2,
          status: point.status,
          isKeyPoint: point.is_key_point,
          isDifficult: point.difficulty === 'hard',
          position: { x: l2X, y: DESIGN.levels.l2 },
          parentId: block.block_id,
          data: point,
          children: point.components.map(c => c.component_id),
        };
        nodeMap.set(point.point_id, l2Node);
        linkList.push({ source: block.block_id, target: point.point_id, type: 'l1-l2' });

        // L3 层 - 知识组件（只在展开时显示）
        if (expandedPoints.has(point.point_id)) {
          const components = point.components;
          const l3Count = components.length;
          const l3TotalWidth = (l3Count - 1) * DESIGN.spacing.l3;
          const l3StartX = l2X - l3TotalWidth / 2;

          components.forEach((comp, cIndex) => {
            const l3X = l3StartX + cIndex * DESIGN.spacing.l3;
            const l3Node: GraphNode = {
              id: comp.component_id,
              name: comp.component_name,
              type: 'component',
              level: 3,
              status: comp.status,
              position: { x: l3X, y: DESIGN.levels.l3 },
              parentId: point.point_id,
              data: comp,
            };
            nodeMap.set(comp.component_id, l3Node);
            linkList.push({ source: point.point_id, target: comp.component_id, type: 'l2-l3' });
          });
        }
      });
    });

    return { nodes: nodeMap, links: linkList };
  }, [blocks, expandedPoints]);

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

  const handleNodeClick = useCallback((node: GraphNode) => {
    setSelectedNode(node.id);

    if (node.type === 'point') {
      // 切换展开/收起
      setExpandedPoints(prev => {
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

  // ===== 渲染节点 =====

  const renderL1Node = (node: GraphNode) => {
    const isHovered = hoveredNode === node.id;
    const isSelected = selectedNode === node.id;
    const radius = DESIGN.nodeSize.l1 / 2;
    const statusColor = getStatusColor(node.status);

    return (
      <g
        key={node.id}
        transform={`translate(${node.position.x}, ${node.position.y})`}
        className="kg-node kg-node-l1"
        onClick={() => handleNodeClick(node)}
        onMouseEnter={() => setHoveredNode(node.id)}
        onMouseLeave={() => setHoveredNode(null)}
        style={{ cursor: 'pointer' }}
      >
        {/* 外发光 */}
        {(isHovered || isSelected) && (
          <circle
            r={radius + 12}
            fill="rgba(91, 108, 240, 0.15)"
            className="kg-node-glow"
          />
        )}

        {/* 主节点 - 渐变填充 */}
        <defs>
          <linearGradient id={`grad-${node.id}`} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={DESIGN.colors.l1Gradient[0]} />
            <stop offset="100%" stopColor={DESIGN.colors.l1Gradient[1]} />
          </linearGradient>
        </defs>
        <circle
          r={radius}
          fill={`url(#grad-${node.id})`}
          stroke={isSelected ? DESIGN.colors.linkActive : '#FFFFFF'}
          strokeWidth={isSelected ? 3 : 2}
          filter="url(#shadow)"
          className="kg-node-circle"
        />

        {/* 状态指示环 */}
        {node.status !== 'not_started' && (
          <circle
            r={radius + 4}
            fill="none"
            stroke={statusColor}
            strokeWidth={2}
            strokeDasharray={node.status === 'in_progress' ? '4,2' : undefined}
          />
        )}

        {/* 文字 */}
        <text
          y={4}
          textAnchor="middle"
          fill="#FFFFFF"
          fontSize={DESIGN.font.l1.size}
          fontWeight={DESIGN.font.l1.weight}
          className="kg-node-text"
        >
          {truncateText(node.name, 6)}
        </text>

        {/* 完成标记 */}
        {node.status === 'completed' && (
          <g transform={`translate(${radius - 8}, ${-radius + 8})`}>
            <circle r={10} fill={DESIGN.colors.completed} />
            <text textAnchor="middle" dy="3" fill="white" fontSize="10">✓</text>
          </g>
        )}
      </g>
    );
  };

  const renderL2Node = (node: GraphNode) => {
    const isHovered = hoveredNode === node.id;
    const isSelected = selectedNode === node.id;
    const isExpanded = expandedPoints.has(node.id);
    const { w, h } = DESIGN.nodeSize.l2;
    const rx = 20;
    const statusColor = getStatusColor(node.status);

    return (
      <g
        key={node.id}
        transform={`translate(${node.position.x}, ${node.position.y})`}
        className={`kg-node kg-node-l2 ${node.isKeyPoint ? 'kg-node-key' : ''}`}
        onClick={() => handleNodeClick(node)}
        onMouseEnter={() => setHoveredNode(node.id)}
        onMouseLeave={() => setHoveredNode(null)}
        style={{ cursor: 'pointer' }}
      >
        {/* 外发光 */}
        {isHovered && (
          <rect
            x={-w/2 - 6}
            y={-h/2 - 6}
            width={w + 12}
            height={h + 12}
            rx={rx + 6}
            fill="rgba(129, 140, 248, 0.15)"
            className="kg-node-glow"
          />
        )}

        {/* 重点标记 - 虚线外框 */}
        {node.isKeyPoint && (
          <rect
            x={-w/2 - 4}
            y={-h/2 - 4}
            width={w + 8}
            height={h + 8}
            rx={rx + 4}
            fill="none"
            stroke={DESIGN.colors.keyPoint}
            strokeWidth={2}
            strokeDasharray="4,2"
          />
        )}

        {/* 主节点 */}
        <defs>
          <linearGradient id={`grad-${node.id}`} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={DESIGN.colors.l2Gradient[0]} />
            <stop offset="100%" stopColor={DESIGN.colors.l2Gradient[1]} />
          </linearGradient>
        </defs>
        <rect
          x={-w/2}
          y={-h/2}
          width={w}
          height={h}
          rx={rx}
          fill={`url(#grad-${node.id})`}
          stroke={isSelected ? DESIGN.colors.linkActive : '#FFFFFF'}
          strokeWidth={isSelected ? 3 : 2}
          filter="url(#shadow)"
          className="kg-node-rect"
        />

        {/* 状态边框 */}
        {node.status !== 'not_started' && (
          <rect
            x={-w/2 - 2}
            y={-h/2 - 2}
            width={w + 4}
            height={h + 4}
            rx={rx + 2}
            fill="none"
            stroke={statusColor}
            strokeWidth={2}
            strokeDasharray={node.status === 'in_progress' ? '4,2' : undefined}
          />
        )}

        {/* 文字 */}
        <text
          y={-2}
          textAnchor="middle"
          fill="#1E293B"
          fontSize={DESIGN.font.l2.size}
          fontWeight={DESIGN.font.l2.weight}
          className="kg-node-text"
        >
          {truncateText(node.name, 8)}
        </text>

        {/* 重点标签 */}
        {node.isKeyPoint && (
          <text
            y={14}
            textAnchor="middle"
            fill={DESIGN.colors.keyPoint}
            fontSize="9"
            fontWeight="bold"
          >
            重点
          </text>
        )}

        {/* 展开指示器 */}
        <g transform={`translate(0, ${h/2 + 10})`}>
          <circle r={10} fill="#FFFFFF" stroke="#E2E8F0" strokeWidth={1} />
          <text textAnchor="middle" dy="3" fill="#64748B" fontSize="12">
            {isExpanded ? '−' : '+'}
          </text>
        </g>
      </g>
    );
  };

  const renderL3Node = (node: GraphNode) => {
    const isHovered = hoveredNode === node.id;
    const isSelected = selectedNode === node.id;
    const radius = DESIGN.nodeSize.l3 / 2;
    const statusColor = getStatusColor(node.status);

    return (
      <g
        key={node.id}
        transform={`translate(${node.position.x}, ${node.position.y})`}
        className="kg-node kg-node-l3"
        onClick={() => handleNodeClick(node)}
        onMouseEnter={() => setHoveredNode(node.id)}
        onMouseLeave={() => setHoveredNode(null)}
        style={{ cursor: 'pointer' }}
      >
        {/* 主节点 */}
        <circle
          r={radius}
          fill={statusColor}
          stroke={isSelected ? DESIGN.colors.linkActive : '#FFFFFF'}
          strokeWidth={isSelected ? 2 : 1}
          filter="url(#shadow)"
          className="kg-node-circle"
        />

        {/* 完成标记 */}
        {node.status === 'completed' && (
          <text textAnchor="middle" dy="3" fill="white" fontSize="10">✓</text>
        )}

        {/* 文字标签 */}
        <text
          y={radius + 14}
          textAnchor="middle"
          fill="#475569"
          fontSize={DESIGN.font.l3.size}
          fontWeight={DESIGN.font.l3.weight}
          className="kg-node-text"
        >
          {truncateText(node.name, 6)}
        </text>
      </g>
    );
  };

  // ===== 渲染连线 =====

  const renderLink = (link: GraphLink) => {
    const sourceNode = nodes.get(link.source);
    const targetNode = nodes.get(link.target);
    if (!sourceNode || !targetNode) return null;

    const { x: x1, y: y1 } = sourceNode.position;
    const { x: x2, y: y2 } = targetNode.position;

    // 贝塞尔曲线控制点
    const cy = (y1 + y2) / 2;
    const path = `M ${x1} ${y1 + (sourceNode.level === 1 ? DESIGN.nodeSize.l1/2 : DESIGN.nodeSize.l2.h/2)}
                  C ${x1} ${cy}, ${x2} ${cy}, ${x2} ${y2 - (targetNode.level === 3 ? 0 : DESIGN.nodeSize.l2.h/2)}`;

    const isL2L3 = link.type === 'l2-l3';
    const isHighlighted = hoveredNode === link.source || hoveredNode === link.target;

    return (
      <path
        key={`${link.source}-${link.target}`}
        d={path}
        fill="none"
        stroke={isHighlighted ? DESIGN.colors.linkActive : (isL2L3 ? DESIGN.colors.linkL2 : DESIGN.colors.linkL1)}
        strokeWidth={isHighlighted ? 2.5 : (isL2L3 ? 1.5 : 2)}
        strokeDasharray={isL2L3 ? '4,3' : undefined}
        opacity={isHighlighted ? 1 : 0.7}
        className="kg-link"
      />
    );
  };

  // ===== 主渲染 =====

  if (!blocks || blocks.length === 0) {
    return (
      <div className={`kg-container kg-empty ${className}`}>
        <div className="kg-empty-icon">🗺️</div>
        <div className="kg-empty-title">知识图谱加载中</div>
        <div className="kg-empty-desc">AI正在为你构建知识体系...</div>
      </div>
    );
  }

  return (
    <div className={`kg-container ${className}`}>
      {/* 控制栏 */}
      <div className="kg-controls">
        <button className="kg-control-btn" onClick={handleZoomIn} title="放大">
          <svg viewBox="0 0 24 24" width="18" height="18">
            <path fill="currentColor" d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
          </svg>
        </button>
        <button className="kg-control-btn" onClick={handleZoomOut} title="缩小">
          <svg viewBox="0 0 24 24" width="18" height="18">
            <path fill="currentColor" d="M19 13H5v-2h14v2z"/>
          </svg>
        </button>
        <button className="kg-control-btn" onClick={handleResetView} title="重置视图">
          <svg viewBox="0 0 24 24" width="18" height="18">
            <path fill="currentColor" d="M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z"/>
          </svg>
        </button>
      </div>

      {/* 图例 */}
      <div className="kg-legend">
        <div className="kg-legend-section">
          <div className="kg-legend-title">层级</div>
          <div className="kg-legend-item">
            <span className="kg-legend-dot" style={{ background: DESIGN.colors.l1Gradient[0] }} />
            <span>知识板块</span>
          </div>
          <div className="kg-legend-item">
            <span className="kg-legend-dot" style={{ background: DESIGN.colors.l2Gradient[0] }} />
            <span>知识点</span>
          </div>
          <div className="kg-legend-item">
            <span className="kg-legend-dot" style={{ background: DESIGN.colors.l3Fill }} />
            <span>知识组件</span>
          </div>
        </div>
        <div className="kg-legend-divider" />
        <div className="kg-legend-section">
          <div className="kg-legend-title">状态</div>
          <div className="kg-legend-item">
            <span className="kg-legend-dot" style={{ background: DESIGN.colors.completed }} />
            <span>已完成</span>
          </div>
          <div className="kg-legend-item">
            <span className="kg-legend-dot" style={{ background: DESIGN.colors.inProgress }} />
            <span>进行中</span>
          </div>
          <div className="kg-legend-item">
            <span className="kg-legend-dot" style={{ background: DESIGN.colors.notStarted }} />
            <span>未开始</span>
          </div>
        </div>
      </div>

      {/* SVG 画布 */}
      <svg
        ref={svgRef}
        className="kg-svg"
        viewBox={`0 0 ${DESIGN.canvas.width} ${DESIGN.canvas.height}`}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
      >
        <defs>
          {/* 阴影滤镜 */}
          <filter id="shadow" x="-50%" y="-50%" width="200%" height="200%">
            <feDropShadow dx="0" dy="2" stdDeviation="3" floodOpacity="0.15"/>
          </filter>
        </defs>

        <g transform={`translate(${translate.x}, ${translate.y}) scale(${scale})`}>
          {/* 连线层 */}
          {links.map(renderLink)}

          {/* 节点层 - 按层级排序渲染 */}
          {Array.from(nodes.values())
            .sort((a, b) => a.level - b.level)
            .map(node => {
              if (node.level === 1) return renderL1Node(node);
              if (node.level === 2) return renderL2Node(node);
              return renderL3Node(node);
            })}
        </g>
      </svg>

      {/* 提示信息 */}
      <div className="kg-hint">
        <span>💡 滚轮缩放 · 拖拽移动 · 点击知识点展开/收起</span>
      </div>
    </div>
  );
};

export default KnowledgeGraphV2;
