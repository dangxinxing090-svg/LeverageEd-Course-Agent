"""
BKT (Bayesian Knowledge Tracing) 算法核心实现

BKT是一种用于追踪学生知识掌握度的概率模型，基于隐马尔可夫模型(HMM)。
使用4个参数：
- p_init (P(L0)): 初始掌握概率
- p_transit (P(T)): 学习概率（从未掌握到掌握）
- p_slip (P(S)): 失误概率（已掌握但答错）
- p_guess (P(G)): 猜测概率（未掌握但猜对）

参考论文: Corbett, A. T., & Anderson, J. R. (1994). Knowledge tracing.
"""
from dataclasses import dataclass
from typing import List, Tuple, Optional


@dataclass
class BKTParams:
    """BKT模型参数"""
    p_init: float = 0.3      # P(L0): 初始掌握概率
    p_transit: float = 0.1   # P(T): 学习概率
    p_slip: float = 0.1      # P(S): 失误概率
    p_guess: float = 0.2     # P(G): 猜测概率
    
    def __post_init__(self):
        """验证参数范围"""
        for name, value in self.__dict__.items():
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be in [0, 1], got {value}")


@dataclass
class BKTState:
    """BKT状态"""
    p_known: float  # 当前掌握概率 P(L_n)
    params: BKTParams  # 模型参数
    
    def __post_init__(self):
        """确保掌握概率在有效范围内"""
        self.p_known = max(0.0, min(1.0, self.p_known))


class BKTModel:
    """
    BKT模型
    
    用于追踪单个知识组件的掌握度变化
    """
    
    # 默认参数（可根据数据训练优化）
    DEFAULT_PARAMS = BKTParams(
        p_init=0.3,      # 初始掌握概率30%
        p_transit=0.1,   # 每次练习有10%概率从未掌握变为掌握
        p_slip=0.1,      # 已掌握时有10%概率失误
        p_guess=0.2      # 未掌握时有20%概率猜对
    )
    
    # 掌握阈值
    MASTERY_THRESHOLD = 0.95
    
    def __init__(self, params: Optional[BKTParams] = None):
        """
        初始化BKT模型
        
        Args:
            params: BKT参数，默认使用DEFAULT_PARAMS
        """
        self.params = params or self.DEFAULT_PARAMS
        self.state = BKTState(p_known=self.params.p_init, params=self.params)
    
    def update(self, is_correct: bool) -> float:
        """
        根据答题结果更新掌握概率
        
        Args:
            is_correct: 是否答对
            
        Returns:
            更新后的掌握概率 P(L_n|obs)
        """
        p_known = self.state.p_known
        params = self.params
        
        # 计算 P(obs|L_n=1) 和 P(obs|L_n=0)
        if is_correct:
            # 答对了
            p_obs_given_known = 1 - params.p_slip      # 已掌握且没失误
            p_obs_given_unknown = params.p_guess       # 未掌握但猜对
        else:
            # 答错了
            p_obs_given_known = params.p_slip          # 已掌握但失误
            p_obs_given_unknown = 1 - params.p_guess   # 未掌握且没猜对
        
        # 计算 P(obs) = P(obs|L_n=1)*P(L_n=1) + P(obs|L_n=0)*P(L_n=0)
        p_obs = (p_obs_given_known * p_known + 
                 p_obs_given_unknown * (1 - p_known))
        
        # 贝叶斯更新: P(L_n|obs) = P(obs|L_n) * P(L_n) / P(obs)
        if p_obs > 0:
            p_known_given_obs = (p_obs_given_known * p_known) / p_obs
        else:
            p_known_given_obs = p_known
        
        # 学习转移: P(L_{n+1}) = P(L_n|obs) + (1 - P(L_n|obs)) * P(T)
        p_known_next = p_known_given_obs + (1 - p_known_given_obs) * params.p_transit
        
        # 更新状态
        self.state.p_known = max(0.0, min(1.0, p_known_next))
        
        return self.state.p_known
    
    def predict(self) -> float:
        """
        预测当前答题正确的概率
        
        Returns:
            P(correct) = P(L_n)*(1-P(S)) + (1-P(L_n))*P(G)
        """
        p_known = self.state.p_known
        params = self.params
        
        return p_known * (1 - params.p_slip) + (1 - p_known) * params.p_guess
    
    def is_mastered(self) -> bool:
        """
        判断是否已掌握
        
        Returns:
            True if P(L_n) >= MASTERY_THRESHOLD
        """
        return self.state.p_known >= self.MASTERY_THRESHOLD
    
    def get_mastery_level(self) -> int:
        """
        获取掌握等级（1-5）
        
        Returns:
            掌握等级: 1=初学, 2=了解, 3=熟悉, 4=掌握, 5=精通
        """
        p = self.state.p_known
        if p < 0.2:
            return 1  # 初学
        elif p < 0.4:
            return 2  # 了解
        elif p < 0.6:
            return 3  # 熟悉
        elif p < 0.8:
            return 4  # 掌握
        else:
            return 5  # 精通
    
    def reset(self):
        """重置到初始状态"""
        self.state.p_known = self.params.p_init
    
    @classmethod
    def from_history(cls, attempts: List[bool], params: Optional[BKTParams] = None) -> 'BKTModel':
        """
        从历史答题记录创建BKT模型
        
        Args:
            attempts: 答题历史，True表示答对，False表示答错
            params: BKT参数
            
        Returns:
            更新后的BKT模型
        """
        model = cls(params)
        for is_correct in attempts:
            model.update(is_correct)
        return model
    
    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            'p_known': self.state.p_known,
            'params': {
                'p_init': self.params.p_init,
                'p_transit': self.params.p_transit,
                'p_slip': self.params.p_slip,
                'p_guess': self.params.p_guess
            },
            'is_mastered': self.is_mastered(),
            'mastery_level': self.get_mastery_level()
        }


def calculate_bkt_params_from_data(attempts: List[bool]) -> BKTParams:
    """
    从答题历史数据估算BKT参数（简化版EM算法）
    
    这是一个启发式方法，用于在没有大量数据时提供合理的参数估计。
    生产环境应使用完整的EM算法或梯度下降优化。
    
    Args:
        attempts: 答题历史
        
    Returns:
        估算的BKT参数
    """
    if not attempts:
        return BKTModel.DEFAULT_PARAMS
    
    n = len(attempts)
    correct_count = sum(attempts)
    accuracy = correct_count / n
    
    # 启发式估计
    # 如果准确率高，说明p_init可能较高或学习效果好
    if accuracy > 0.8:
        p_init = min(0.5, accuracy - 0.3)
        p_transit = 0.15
    elif accuracy > 0.5:
        p_init = 0.3
        p_transit = 0.12
    else:
        p_init = 0.2
        p_transit = 0.08
    
    # 失误和猜测概率相对稳定
    p_slip = 0.1
    p_guess = max(0.1, min(0.3, 1 - accuracy))
    
    return BKTParams(
        p_init=p_init,
        p_transit=p_transit,
        p_slip=p_slip,
        p_guess=p_guess
    )
