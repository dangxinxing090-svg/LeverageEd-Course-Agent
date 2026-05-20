"""
DKT (Deep Knowledge Tracing) 模型核心实现

DKT是一种基于RNN的知识追踪模型，通过序列建模捕捉知识组件间的依赖关系，
预测学生在未来答题中的表现。

由于当前项目未安装PyTorch/TensorFlow，本实现采用简化版DKT：
- 基于知识组件依赖图的状态转移矩阵
- 利用历史答题序列进行预测
- 预留深度学习模型接口

参考论文: Piech, C. et al. (2015). Deep knowledge tracing.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from collections import defaultdict
import math


@dataclass
class DKTState:
    """DKT隐状态向量（简化版：每个知识组件的掌握概率向量）"""
    component_mastery: Dict[str, float] = field(default_factory=dict)
    sequence_length: int = 0
    
    def get_mastery(self, component_id: str) -> float:
        """获取指定知识组件的掌握概率"""
        return self.component_mastery.get(component_id, 0.0)
    
    def set_mastery(self, component_id: str, probability: float):
        """设置指定知识组件的掌握概率"""
        self.component_mastery[component_id] = max(0.0, min(1.0, probability))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_mastery": self.component_mastery,
            "sequence_length": self.sequence_length
        }


@dataclass
class AnswerRecord:
    """答题记录"""
    component_id: str
    is_correct: bool
    timestamp: int = 0  # 毫秒时间戳


@dataclass
class KnowledgeComponent:
    """知识组件"""
    component_id: str
    point_id: str = ""
    prerequisites: List[str] = field(default_factory=list)  # 前置知识组件ID列表
    related_components: List[str] = field(default_factory=list)  # 相关知识组件ID列表


class DKTModel:
    """
    DKT模型（简化版）
    
    基于知识组件依赖图和答题序列预测掌握度。
    核心思想：
    1. 答对一个组件会影响其前置和后续组件的掌握度
    2. 答错一个组件会降低其后续组件的掌握度预期
    3. 序列越长，预测越准确
    """
    
    # 默认参数
    DEFAULT_LEARNING_RATE = 0.15      # 学习率（答对时掌握度提升）
    DEFAULT_FORGETTING_RATE = 0.05   # 遗忘率（答错时掌握度下降）
    DEFAULT_TRANSFER_RATE = 0.1      # 知识迁移率（前置组件对后续组件的影响）
    DEFAULT_DECAY_RATE = 0.02        # 时间衰减率
    
    def __init__(
        self,
        learning_rate: float = None,
        forgetting_rate: float = None,
        transfer_rate: float = None,
        decay_rate: float = None
    ):
        self.learning_rate = learning_rate or self.DEFAULT_LEARNING_RATE
        self.forgetting_rate = forgetting_rate or self.DEFAULT_FORGETTING_RATE
        self.transfer_rate = transfer_rate or self.DEFAULT_TRANSFER_RATE
        self.decay_rate = decay_rate or self.DEFAULT_DECAY_RATE
        
        # 知识组件注册表
        self._components: Dict[str, KnowledgeComponent] = {}
        
        # 当前隐状态
        self.state = DKTState()
    
    def register_component(
        self,
        component_id: str,
        point_id: str = "",
        prerequisites: List[str] = None,
        related_components: List[str] = None
    ):
        """
        注册知识组件
        
        Args:
            component_id: 组件ID
            point_id: 知识点ID
            prerequisites: 前置组件ID列表
            related_components: 相关组件ID列表
        """
        self._components[component_id] = KnowledgeComponent(
            component_id=component_id,
            point_id=point_id,
            prerequisites=prerequisites or [],
            related_components=related_components or []
        )
    
    def register_from_blocks(self, blocks: List[Dict[str, Any]]):
        """
        从知识结构块注册组件
        
        Args:
            blocks: 知识结构数据（来自API）
        """
        for block in blocks:
            points = block.get("points", [])
            for i, point in enumerate(points):
                components = point.get("components", [])
                for comp in components:
                    comp_id = comp.get("componentId", "")
                    point_id = point.get("pointId", "")
                    
                    # 前置组件：同知识点的上一个组件
                    prerequisites = []
                    if i > 0:
                        prev_components = points[i-1].get("components", [])
                        if prev_components:
                            prerequisites.append(prev_components[-1].get("componentId", ""))
                    
                    # 相关组件：同知识点的其他组件
                    related = []
                    for c in components:
                        cid = c.get("componentId", "")
                        if cid != comp_id:
                            related.append(cid)
                    
                    if comp_id:
                        self.register_component(
                            component_id=comp_id,
                            point_id=point_id,
                            prerequisites=prerequisites,
                            related_components=related
                        )
    
    def update(self, record: AnswerRecord) -> DKTState:
        """
        根据答题记录更新DKT状态
        
        Args:
            record: 答题记录
            
        Returns:
            更新后的DKT状态
        """
        comp_id = record.component_id
        is_correct = record.is_correct
        
        # 获取当前组件的掌握度
        current_mastery = self.state.get_mastery(comp_id)
        
        # 1. 更新当前组件的掌握度
        if is_correct:
            # 答对：掌握度提升（学习曲线）
            new_mastery = current_mastery + (1 - current_mastery) * self.learning_rate
        else:
            # 答错：掌握度下降（但不会低于初始值的一定比例）
            new_mastery = current_mastery * (1 - self.forgetting_rate)
            new_mastery = max(new_mastery, 0.05)  # 最低保持5%
        
        self.state.set_mastery(comp_id, new_mastery)
        
        # 2. 知识迁移：更新前置和后续组件的掌握度
        comp = self._components.get(comp_id)
        if comp:
            # 答对时，前置组件的掌握度也得到巩固
            if is_correct:
                for prereq_id in comp.prerequisites:
                    prereq_mastery = self.state.get_mastery(prereq_id)
                    boosted = prereq_mastery + (1 - prereq_mastery) * self.transfer_rate * 0.5
                    self.state.set_mastery(prereq_id, boosted)
            
            # 答对/答错都会影响后续组件
            for related_id in comp.related_components:
                related_mastery = self.state.get_mastery(related_id)
                if is_correct:
                    # 前置掌握有助于后续学习
                    boosted = related_mastery + new_mastery * self.transfer_rate
                    self.state.set_mastery(related_id, boosted)
                else:
                    # 前置未掌握会降低后续预期
                    reduced = related_mastery * (1 - self.transfer_rate * 0.3)
                    self.state.set_mastery(related_id, reduced)
        
        # 3. 时间衰减（可选，基于序列长度）
        self.state.sequence_length += 1
        
        return self.state
    
    def update_sequence(self, records: List[AnswerRecord]) -> DKTState:
        """
        批量更新答题序列
        
        Args:
            records: 答题记录列表
            
        Returns:
            更新后的DKT状态
        """
        for record in records:
            self.update(record)
        return self.state
    
    def predict(self, component_id: str) -> float:
        """
        预测指定知识组件的答题正确概率
        
        Args:
            component_id: 知识组件ID
            
        Returns:
            预测正确概率
        """
        mastery = self.state.get_mastery(component_id)
        
        # 考虑前置组件的影响
        comp = self._components.get(component_id)
        if comp and comp.prerequisites:
            prereq_avg = 0
            for prereq_id in comp.prerequisites:
                prereq_avg += self.state.get_mastery(prereq_id)
            prereq_avg /= len(comp.prerequisites)
            
            # 综合当前掌握度和前置掌握度
            combined = mastery * 0.7 + prereq_avg * 0.3
        else:
            combined = mastery
        
        return max(0.0, min(1.0, combined))
    
    def predict_all(self) -> Dict[str, float]:
        """
        预测所有已注册组件的答题正确概率
        
        Returns:
            {component_id: predicted_correct_probability}
        """
        predictions = {}
        for comp_id in self._components:
            predictions[comp_id] = self.predict(comp_id)
        return predictions
    
    def get_weak_components(self, threshold: float = 0.5, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取薄弱知识组件
        
        Args:
            threshold: 掌握度阈值
            limit: 返回数量限制
            
        Returns:
            薄弱组件列表
        """
        weak = []
        for comp_id, mastery in self.state.component_mastery.items():
            if mastery < threshold:
                comp = self._components.get(comp_id)
                weak.append({
                    "component_id": comp_id,
                    "point_id": comp.point_id if comp else "",
                    "mastery": round(mastery, 3),
                    "predicted_accuracy": round(self.predict(comp_id), 3)
                })
        
        weak.sort(key=lambda x: x["mastery"])
        return weak[:limit]
    
    def get_learning_path_recommendation(self) -> List[str]:
        """
        基于DKT状态推荐学习路径
        
        推荐策略：
        1. 优先推荐掌握度最低且前置条件已满足的组件
        2. 未开始学习的组件优先
        
        Returns:
            推荐的组件ID列表
        """
        # 分类：未开始 vs 已学习
        not_started = []
        in_progress = []
        
        for comp_id, comp in self._components.items():
            mastery = self.state.get_mastery(comp_id)
            if mastery == 0:
                # 检查前置条件是否满足
                prereqs_met = all(
                    self.state.get_mastery(p) >= 0.3
                    for p in comp.prerequisites
                )
                if prereqs_met:
                    not_started.append(comp_id)
            elif mastery < 0.8:
                in_progress.append(comp_id)
        
        # 按掌握度排序
        in_progress.sort(key=lambda x: self.state.get_mastery(x))
        
        return in_progress + not_started
    
    def reset(self):
        """重置DKT状态"""
        self.state = DKTState()
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化"""
        return {
            "state": self.state.to_dict(),
            "registered_components": len(self._components),
            "predictions": self.predict_all(),
            "weak_components": self.get_weak_components(),
            "recommended_path": self.get_learning_path_recommendation()
        }
