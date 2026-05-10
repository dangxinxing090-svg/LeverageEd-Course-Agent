# 三层知识结构全景知识图谱设计规范

## 一、设计概述

### 1.1 设计理念
采用**树形放射状布局**，以学习主题为中心，向外逐层展开知识体系。通过视觉层次清晰呈现知识的从属关系，帮助学习者建立完整的知识框架认知。

### 1.2 适用场景
- AI教育平台的全景知识展示
- 在线课程的知识体系可视化
- 学习路径规划和进度追踪

---

## 二、三层层级规范

### 2.1 L1 - 知识板块 (Knowledge Block)

| 属性 | 规范 |
|------|------|
| **定位** | 知识体系的顶层分类，相当于"章节"或"大模块" |
| **数量** | 3-7个为宜，建议5个左右 |
| **命名** | 简洁有力，2-6个汉字，如"基础语法"、"进阶应用" |
| **视觉权重** | 最高，作为根节点 |

**设计规范：**
- 节点形状：圆形
- 节点大小：直径 90px
- 字体大小：16px，加粗
- 颜色：渐变填充 #5B6CF0 → #818CF8
- 阴影：外发光效果，rgba(91, 108, 240, 0.3)

### 2.2 L2 - 知识点 (Knowledge Point)

| 属性 | 规范 |
|------|------|
| **定位** | 知识板块下的核心概念，相当于"小节" |
| **数量** | 每个板块下 3-8个 |
| **命名** | 具体概念名称，如"变量定义"、"函数传参" |
| **视觉权重** | 中等，连接L1和L3 |

**设计规范：**
- 节点形状：圆角矩形（圆角半径 20px）
- 节点大小：宽度 120px，高度 60px
- 字体大小：13px，中等字重
- 颜色：渐变填充 #818CF8 → #A5B4FC
- 特殊标记：重点/难点知识点有橙色虚线边框

### 2.3 L3 - 知识组件 (Knowledge Component)

| 属性 | 规范 |
|------|------|
| **定位** | 最细粒度的学习内容，可独立学习的最小单元 |
| **数量** | 每个知识点下 2-6个 |
| **命名** | 具体操作或概念，如"变量命名规则"、"全局变量" |
| **视觉权重** | 最低，叶子节点 |

**设计规范：**
- 节点形状：小圆点 + 标签
- 节点大小：圆点直径 24px
- 字体大小：11px，常规字重
- 颜色：纯色填充 #A5B4FC
- 状态指示：完成状态用对勾图标表示

---

## 三、配色方案

### 3.1 主色调

```css
:root {
  /* 主品牌色 */
  --primary-500: #5B6CF0;
  --primary-400: #818CF8;
  --primary-300: #A5B4FC;
  --primary-200: #C7D2FE;
  
  /* 状态色 */
  --status-completed: #059669;  /* 已完成 - 翠绿 */
  --status-progress: #5B6CF0;   /* 进行中 - 品牌蓝 */
  --status-pending: #94A3B8;    /* 未开始 - 灰蓝 */
  --status-locked: #CBD5E1;     /* 锁定 - 浅灰 */
  
  /* 重点标记 */
  --highlight-key: #D97706;     /* 重点 - 琥珀橙 */
  --highlight-difficult: #DC2626; /* 难点 - 红 */
  
  /* 背景 */
  --bg-canvas: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  --bg-node: #ffffff;
  
  /* 连线 */
  --link-primary: #E2E8F0;
  --link-active: #818CF8;
}
```

### 3.2 节点配色表

| 层级 | 正常状态 | 已完成 | 进行中 | 未开始 | 重点标记 |
|------|----------|--------|--------|--------|----------|
| L1 | #5B6CF0渐变 | #059669 | #5B6CF0 | #94A3B8 | 橙色外圈 |
| L2 | #818CF8渐变 | #059669 | #5B6CF0 | #94A3B8 | 橙色虚线框 |
| L3 | #A5B4FC | #059669 | #5B6CF0 | #94A3B8 | - |

---

## 四、布局规则

### 4.1 整体布局 - 水平分层

```
┌─────────────────────────────────────────────────────────┐
│  Y=100px                                                │
│    ● L1-1    ● L1-2    ● L1-3    ● L1-4    ● L1-5      │
│      │          │          │          │          │      │
│  Y=300px       │          │          │          │      │
│    □ L2-1    □ L2-2    □ L2-3    □ L2-4    □ L2-5      │
│    □ L2-6    □ L2-7      │        □ L2-8               │
│      │          │          │          │                │
│  Y=500px       │          │          │                │
│    ○ L3-1    ○ L3-2    ○ L3-3    ○ L3-4               │
│    ○ L3-5    ○ L3-6    ○ L3-7                          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**垂直分层：**
- L1 层：Y = 100px（顶部）
- L2 层：Y = 300px（中部）
- L3 层：Y = 500px（底部，可展开/收起）

### 4.2 水平分布算法

**L1 层均匀分布：**
```javascript
// 画布宽度 1200px，边距 100px
const availableWidth = 1200 - 200; // 1000px
const spacing = availableWidth / (blockCount + 1);
blockX = 100 + spacing * (index + 1);
```

**L2 层基于父节点分布：**
```javascript
// 每个L1节点下方分布其子L2节点
const parentX = parentBlock.x;
const pointSpacing = 140; // L2节点间距
const startX = parentX - (pointCount - 1) * pointSpacing / 2;
pointX = startX + index * pointSpacing;
```

**L3 层基于父节点分布：**
```javascript
// 类似L2，更紧凑
const componentSpacing = 100;
const startX = parentPoint.x - (componentCount - 1) * componentSpacing / 2;
componentX = startX + index * componentSpacing;
```

### 4.3 响应式适配

| 屏幕宽度 | 布局调整 |
|----------|----------|
| ≥1200px | 完整三列布局 |
| 768-1199px | 双列布局，L2/L3垂直堆叠 |
| <768px | 单列布局，可横向滚动 |

---

## 五、连线设计

### 5.1 连线类型

| 连接关系 | 线型 | 颜色 | 粗细 |
|----------|------|------|------|
| L1 → L2 | 实线 | #E2E8F0 | 2px |
| L2 → L3 | 虚线 | #CBD5E1 | 1.5px |
| 选中高亮 | 实线 | #5B6CF0 | 3px |

### 5.2 贝塞尔曲线

使用二次贝塞尔曲线连接节点，使连线更自然：

```javascript
// 从父节点底部到子节点顶部
const path = `M ${parentX} ${parentY + parentRadius}
              Q ${parentX} ${(parentY + childY) / 2}
                ${childX} ${childY - childRadius}`;
```

---

## 六、交互设计

### 6.1 鼠标交互

| 操作 | 效果 |
|------|------|
| 悬停节点 | 放大1.1倍，显示光晕阴影 |
| 点击L2节点 | 展开/收起其L3子节点 |
| 点击L3节点 | 跳转到对应学习页面 |
| 拖拽画布 | 平移整个图谱 |
| 滚轮 | 缩放（0.5x - 2x） |

### 6.2 动画效果

| 动画 | 时长 | 缓动函数 |
|------|------|----------|
| 节点入场 | 400ms | ease-out |
| 连线绘制 | 600ms | ease-in-out |
| 展开/收起 | 300ms | ease |
| 悬停放大 | 200ms | ease |

### 6.3 状态反馈

- **已完成**：节点右下角显示绿色对勾 ✓
- **进行中**：节点边框高亮，轻微脉动动画
- **重点知识**：橙色虚线边框，标签显示"重点"
- **难点知识**：红色边框，学习前显示提示

---

## 七、组件实现规范

### 7.1 React组件结构

```typescript
interface KnowledgeGraphProps {
  blocks: KnowledgeBlock[];      // L1数据
  onNodeClick: (node: NodeData) => void;
  onPointClick?: (point: KnowledgePoint) => void;
}

interface NodeData {
  id: string;
  name: string;
  type: 'block' | 'point' | 'component';
  level: 1 | 2 | 3;
  status: 'completed' | 'in_progress' | 'not_started' | 'locked';
  isKeyPoint?: boolean;
  isDifficult?: boolean;
  x: number;
  y: number;
  children?: NodeData[];
}
```

### 7.2 SVG元素规范

```svg
<!-- L1 节点示例 -->
<g class="node node-l1" transform="translate(200, 100)">
  <!-- 外发光 -->
  <circle r="50" fill="rgba(91, 108, 240, 0.1)" class="glow"/>
  <!-- 主节点 -->
  <circle r="45" fill="url(#gradient-l1)" filter="url(#shadow)"/>
  <!-- 文字 -->
  <text y="5" text-anchor="middle" font-size="16" font-weight="bold">
    基础语法
  </text>
</g>

<!-- 连线示例 -->
<path d="M 200 145 Q 200 222 200 270" 
      stroke="#E2E8F0" stroke-width="2" fill="none"/>
```

### 7.3 CSS变量定义

```css
.knowledge-graph {
  /* 画布尺寸 */
  --canvas-width: 1200px;
  --canvas-height: 600px;
  
  /* 节点尺寸 */
  --l1-size: 90px;
  --l2-width: 120px;
  --l2-height: 60px;
  --l3-size: 24px;
  
  /* 层级位置 */
  --l1-y: 100px;
  --l2-y: 300px;
  --l3-y: 500px;
  
  /* 间距 */
  --l1-spacing: 200px;
  --l2-spacing: 140px;
  --l3-spacing: 100px;
}
```

---

## 八、设计示例

### 8.1 Python编程知识图谱示例

```
                    Python编程
                        │
    ┌──────────┬────────┼────────┬──────────┐
    │          │        │        │          │
 基础语法   数据类型  控制流   函数      面向对象
    │          │        │        │          │
  ├─变量     ├─数字   ├─if    ├─定义    ├─类
  ├─命名     ├─字符串 ├─for   ├─参数    ├─对象
  ├─类型     ├─列表   ├─while ├─返回值  ├─继承
  └─作用域   └─字典   └─break └─作用域  └─多态
```

### 8.2 视觉预览

```
        ● 基础语法        ● 数据类型        ● 控制流
           │                 │                │
    ┌──────┴──────┐   ┌─────┴─────┐   ┌─────┴─────┐
    │             │   │           │   │           │
   □ 变量       □ 命名规则    □ 数字      □ 字符串    □ if语句   □ for循环
    │             │   │           │   │           │
   ○ 定义       ○ 规范      ○ int     ○ str     ○ 语法    ○ 迭代
   ○ 类型       ○ 惯例      ○ float   ○ 方法    ○ 嵌套    ○ range
```

---

## 九、技术实现要点

### 9.1 性能优化

1. **虚拟渲染**：只渲染可视区域内的节点
2. **节点复用**：使用 React key 避免不必要的重渲染
3. **防抖处理**：缩放/拖拽操作防抖 16ms
4. **Web Worker**：复杂布局计算放入 Worker

### 9.2 无障碍支持

1. **键盘导航**：Tab 键在节点间切换
2. **屏幕阅读器**：aria-label 描述节点关系
3. **高对比度**：支持 prefers-contrast 媒体查询
4. **减少动画**：支持 prefers-reduced-motion

---

## 十、设计文件交付

### 10.1 交付物清单

- [x] 设计规范文档（本文档）
- [x] React组件代码（KnowledgeGraph.tsx）
- [x] CSS样式文件（KnowledgeGraph.css）
- [x] SVG图标资源
- [ ] Figma设计稿（可选）

### 10.2 后续优化建议

1. 增加力导向布局选项（使用 D3.js）
2. 支持自定义主题配色
3. 添加节点搜索功能
4. 实现知识图谱导出为图片/PDF
