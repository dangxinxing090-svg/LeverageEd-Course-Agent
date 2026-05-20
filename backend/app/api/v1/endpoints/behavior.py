"""
行为记录API
接收前端发送的用户行为数据，存储到数据库
集成BKT算法计算知识掌握度
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

from app.db.database import get_db
from app.models.behavior import BehaviorLog
from app.models.user import UserProfile
from app.models.exercise import ExerciseHistory
from app.api.v1.middleware.response import format_response
from app.services.bkt_service import BKTService
from app.services.user_profile_service import UserProfileService
from app.services.dkt_service import DKTService
from app.services.compression_service import CompressionService

router = APIRouter(prefix="/behavior", tags=["行为记录"])


class BehaviorRecordRequest(BaseModel):
    """行为记录请求模型"""
    user_id: str = Field(..., description="用户ID")
    session_id: Optional[str] = Field(None, description="会话ID")
    behavior_type: str = Field(..., description="行为类型: learn/question/practice/skip/interact")
    topic_id: Optional[str] = Field(None, description="主题ID")
    point_id: Optional[str] = Field(None, description="知识点ID")
    component_id: Optional[str] = Field(None, description="知识组件ID")
    details: Optional[dict] = Field(default={}, description="详细数据")


class BehaviorRecordResponse(BaseModel):
    """行为记录响应模型"""
    log_id: str
    message: str


@router.post("/record", response_model=dict)
async def record_behavior(
    request: BehaviorRecordRequest,
    db: Session = Depends(get_db)
):
    """
    记录用户行为
    
    接收前端发送的行为数据，保存到数据库，并触发BKT掌握度更新
    """
    try:
        # 创建行为日志
        behavior_log = BehaviorLog(
            log_id=f"log-{uuid.uuid4().hex[:16]}",
            user_id=request.user_id,
            session_id=request.session_id,
            behavior_type=request.behavior_type,
            topic_id=request.topic_id,
            point_id=request.point_id,
            component_id=request.component_id,
            details=request.details,
            timestamp=datetime.now()
        )
        
        db.add(behavior_log)
        db.commit()
        
        # 如果是练习行为，更新BKT掌握度
        if request.behavior_type == "practice" and request.details:
            bkt_service = BKTService(db)
            bkt_service.update_progress_after_attempt(
                user_id=request.user_id,
                component_id=request.component_id or "",
                is_correct=request.details.get("is_correct", False),
                attempt_time=request.details.get("time_spent", 0),
                topic_id=request.topic_id,
                point_id=request.point_id
            )
        
        return format_response(data={
            "log_id": behavior_log.log_id,
            "message": "行为记录成功"
        })
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"行为记录失败: {str(e)}")


@router.get("/stats/{user_id}", response_model=dict)
async def get_user_behavior_stats(
    user_id: str,
    days: int = 30,
    db: Session = Depends(get_db)
):
    """
    获取用户行为统计
    
    返回指定天数内的行为类型分布统计
    """
    try:
        from sqlalchemy import func
        
        # 计算起始日期
        from datetime import timedelta
        start_date = datetime.now() - timedelta(days=days)
        
        # 查询行为统计
        stats = db.query(
            BehaviorLog.behavior_type,
            func.count(BehaviorLog.log_id).label('count')
        ).filter(
            BehaviorLog.user_id == user_id,
            BehaviorLog.timestamp >= start_date
        ).group_by(BehaviorLog.behavior_type).all()
        
        return format_response(data={
            "user_id": user_id,
            "stats": {stat.behavior_type: stat.count for stat in stats}
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取行为统计失败: {str(e)}")


@router.get("/mastery/{user_id}/{component_id}", response_model=dict)
async def get_component_mastery(
    user_id: str,
    component_id: str,
    db: Session = Depends(get_db)
):
    """
    获取知识组件掌握度
    
    返回BKT计算后的掌握度信息
    """
    try:
        bkt_service = BKTService(db)
        mastery = bkt_service.get_component_mastery(user_id, component_id)
        
        if not mastery:
            return format_response(data={
                "user_id": user_id,
                "component_id": component_id,
                "bkt_p_known": 0.0,
                "is_mastered": False,
                "mastery_level": 1,
                "status": "not_started"
            })
        
        return format_response(data=mastery)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取掌握度失败: {str(e)}")


@router.get("/mastery/summary/{user_id}", response_model=dict)
async def get_mastery_summary(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    获取用户掌握度汇总
    
    返回用户在所有知识组件上的掌握情况统计
    """
    try:
        bkt_service = BKTService(db)
        summary = bkt_service.get_user_mastery_summary(user_id)
        
        return format_response(data=summary)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取掌握度汇总失败: {str(e)}")


@router.get("/profile/{user_id}", response_model=dict)
async def get_user_profile(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    获取用户画像
    
    返回用户的学习能力、风格标签、偏好设置等信息
    """
    try:
        service = UserProfileService(db)
        profile = service.get_profile(user_id)
        
        if not profile:
            return format_response(data={
                "user_id": user_id,
                "message": "用户画像不存在，请在产生行为数据后触发分析"
            })
        
        return format_response(data=profile)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取用户画像失败: {str(e)}")


@router.post("/profile/{user_id}/analyze", response_model=dict)
async def analyze_user_profile(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    触发用户画像分析
    
    从行为日志中分析用户学习行为，生成/更新用户画像
    """
    try:
        service = UserProfileService(db)
        result = service.analyze_and_update_profile(user_id)
        
        return format_response(data=result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析用户画像失败: {str(e)}")


@router.get("/dkt/{user_id}", response_model=dict)
async def get_dkt_predictions(
    user_id: str,
    topic_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    获取DKT知识状态转移预测
    
    基于用户答题序列，预测各知识组件的掌握度和正确概率
    """
    try:
        service = DKTService(db)
        result = service.get_dkt_predictions(user_id, topic_id or "")
        
        return format_response(data=result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取DKT预测失败: {str(e)}")


@router.get("/dkt/{user_id}/weak", response_model=dict)
async def get_dkt_weak_components(
    user_id: str,
    topic_id: Optional[str] = None,
    threshold: float = 0.5,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    获取DKT识别的薄弱知识组件
    """
    try:
        service = DKTService(db)
        weak = service.get_weak_components(user_id, topic_id or "", threshold, limit)
        
        return format_response(data={
            "user_id": user_id,
            "weak_components": weak,
            "total": len(weak)
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取薄弱组件失败: {str(e)}")


@router.get("/dkt/{user_id}/recommend", response_model=dict)
async def get_dkt_recommendation(
    user_id: str,
    topic_id: Optional[str] = None,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    获取DKT学习路径推荐
    """
    try:
        service = DKTService(db)
        recommended = service.get_learning_path_recommendation(user_id, topic_id or "", limit)
        
        return format_response(data={
            "user_id": user_id,
            "recommended_path": recommended
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取学习路径推荐失败: {str(e)}")


@router.get("/dkt/{user_id}/compare", response_model=dict)
async def get_bkt_dkt_comparison(
    user_id: str,
    topic_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    获取BKT与DKT的对比分析
    """
    try:
        service = DKTService(db)
        comparison = service.get_bkt_dkt_comparison(user_id, topic_id or "")
        
        return format_response(data=comparison)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取BKT/DKT对比失败: {str(e)}")


@router.get("/compression/stats", response_model=dict)
async def get_compression_stats(
    db: Session = Depends(get_db)
):
    """
    获取记忆压缩统计
    
    返回各温度数据量统计和压缩预估
    """
    try:
        service = CompressionService(db)
        stats = service.get_compression_stats()
        
        return format_response(data=stats)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取压缩统计失败: {str(e)}")


@router.post("/compression/execute", response_model=dict)
async def execute_compression(
    user_id: Optional[str] = None,
    dry_run: bool = True,
    db: Session = Depends(get_db)
):
    """
    执行记忆压缩
    
    扫描超过热数据期限的日志，聚合为摘要，归档原始数据。
    默认dry_run=True（试运行，不实际删除数据）。
    """
    try:
        service = CompressionService(db)
        result = service.execute_compression(
            user_id=user_id,
            dry_run=dry_run
        )
        
        return format_response(data=result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行记忆压缩失败: {str(e)}")


@router.get("/compression/summaries/{user_id}", response_model=dict)
async def get_user_daily_summaries(
    user_id: str,
    days: int = 30,
    db: Session = Depends(get_db)
):
    """
    获取用户每日学习摘要
    
    返回指定天数内的每日学习统计
    """
    try:
        service = CompressionService(db)
        summaries = service.get_user_daily_summaries(user_id, days)
        
        return format_response(data={
            "user_id": user_id,
            "days": days,
            "summaries": summaries,
            "total_days": len(summaries)
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取每日摘要失败: {str(e)}")


# ==================== 组件学习状态管理 ====================

class ComponentStatusRequest(BaseModel):
    """组件状态更新请求"""
    component_id: str = Field(..., description="知识组件ID")
    status: str = Field(..., description="状态: in_progress/learn_completed/practicing/exercise_passed")
    topic_id: Optional[str] = Field(None, description="主题ID")
    point_id: Optional[str] = Field(None, description="知识点ID")
    user_id: str = Field("anonymous", description="用户ID")


@router.post("/component/status", response_model=dict)
async def update_component_status(
    request: ComponentStatusRequest,
    db: Session = Depends(get_db)
):
    """
    更新知识组件的学习状态（写入数据库）

    状态值：
    - in_progress: 学习中（用户点击进入组件）
    - learn_completed: 完成学习（用户滚动讲解到底部）
    - practicing: 做题中（提交答案但不完全正确）
    - exercise_passed: 练习通过（提交答案完全正确）

    使用 upsert 逻辑：存在则更新 status，不存在则创建
    """
    from app.models.progress import LearningProgress

    valid_statuses = ["in_progress", "learn_completed", "practicing", "exercise_passed"]
    if request.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"无效状态值: {request.status}")

    # 查找现有记录
    progress = db.query(LearningProgress).filter(
        LearningProgress.user_id == request.user_id,
        LearningProgress.component_id == request.component_id
    ).first()

    if progress:
        # 更新状态
        progress.status = request.status
        progress.topic_id = request.topic_id or progress.topic_id
        progress.point_id = request.point_id or progress.point_id
    else:
        # 创建新记录
        progress = LearningProgress(
            progress_id=f"prog-{uuid.uuid4().hex[:16]}",
            user_id=request.user_id,
            component_id=request.component_id,
            point_id=request.point_id or "",
            topic_id=request.topic_id or "",
            status=request.status,
        )
        db.add(progress)

    db.commit()

    # 同步更新内存缓存（保持与 getTopicStructure 的一致性）
    from app.api.v1.endpoints.knowledge_cache import set_component_status
    set_component_status(
        component_id=request.component_id,
        status=request.status,
        topic_id=request.topic_id or "",
        point_id=request.point_id or ""
    )

    return format_response(data={
        "component_id": request.component_id,
        "status": request.status,
        "message": "状态更新成功"
    })
