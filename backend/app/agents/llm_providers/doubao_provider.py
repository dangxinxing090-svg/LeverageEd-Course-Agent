"""
豆包 (Doubao) Provider 实现

支持字节跳动火山引擎的豆包系列模型
API文档: https://www.volcengine.com/docs/82379/1263512
"""

import logging
from typing import Any, Dict, List, Optional, AsyncGenerator

from .base import LLMProvider, LLMResponse, LLMMessage, ProviderConfig, ProviderType, ModelCapability

logger = logging.getLogger(__name__)

# 尝试导入openai库（豆包使用OpenAI兼容API）
try:
    from openai import AsyncOpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    logger.warning("未安装openai库，DoubaoProvider将使用模拟模式")


class DoubaoProvider(LLMProvider):
    """
    豆包 Provider实现

    支持doubao-pro-4k、doubao-pro-32k、doubao-lite-4k等模型
    """

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._client: Optional[Any] = None

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.DOUBAO

    @property
    def supported_capabilities(self) -> List[ModelCapability]:
        return [
            ModelCapability.CHAT,
            ModelCapability.FUNCTION_CALLING,
            ModelCapability.JSON_MODE,
            ModelCapability.STREAMING,
        ]

    async def initialize(self) -> None:
        """初始化豆包客户端"""
        if not HAS_OPENAI:
            logger.warning("openai库未安装，使用模拟模式")
            self._initialized = True
            return

        try:
            # 豆包使用OpenAI兼容API
            api_base = self.config.api_base or "https://ark.cn-beijing.volces.com/api/v3"
            # 使用更长的超时时间（LLM生成可能需要较长时间）
            timeout = max(self.config.timeout or 60, 180)
            self._client = AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=api_base,
                timeout=timeout,
                max_retries=self.config.max_retries,
            )
            self._initialized = True
            logger.info(f"豆包 Provider已初始化，模型: {self.config.model}")
        except Exception as e:
            logger.error(f"豆包 Provider初始化失败: {e}")
            raise

    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        生成文本

        Args:
            messages: 消息列表
            temperature: 温度
            max_tokens: 最大token数
            **kwargs: 额外参数

        Returns:
            LLMResponse对象
        """
        if not self._initialized:
            await self.initialize()

        # 模拟模式
        if not HAS_OPENAI or self._client is None:
            return self._mock_generate(messages)

        # 转换消息格式
        doubao_messages = [msg.to_dict() for msg in messages]

        # 获取生成参数
        params = self._get_generation_params(temperature, max_tokens)

        try:
            response = await self._client.chat.completions.create(
                model=self.config.model,
                messages=doubao_messages,
                temperature=params["temperature"],
                max_tokens=params["max_tokens"],
                **self.config.extra_params,
                **kwargs
            )

            # 解析响应
            choice = response.choices[0]
            content = choice.message.content or ""

            return LLMResponse(
                content=content,
                model=response.model,
                provider=self.provider_type,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
                finish_reason=choice.finish_reason,
                raw_response=response if kwargs.get("return_raw") else None,
            )

        except Exception as e:
            logger.error(f"豆包 API调用失败: {e}")
            raise

    async def generate_stream(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        流式生成文本

        Args:
            messages: 消息列表
            temperature: 温度
            max_tokens: 最大token数
            **kwargs: 额外参数

        Yields:
            生成的文本片段
        """
        if not self._initialized:
            await self.initialize()

        if not HAS_OPENAI or self._client is None:
            response = self._mock_generate(messages)
            yield response.content
            return

        doubao_messages = [msg.to_dict() for msg in messages]
        params = self._get_generation_params(temperature, max_tokens)

        try:
            stream = await self._client.chat.completions.create(
                model=self.config.model,
                messages=doubao_messages,
                temperature=params["temperature"],
                max_tokens=params["max_tokens"],
                stream=True,
                **self.config.extra_params,
                **kwargs
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"豆包流式生成失败: {e}")
            raise

    def _mock_generate(self, messages: List[LLMMessage]) -> LLMResponse:
        """模拟生成 - 返回正确的JSON格式"""
        import json
        import re

        user_message = ""
        for msg in reversed(messages):
            if msg.role == "user":
                user_message = msg.content
                break

        # 根据prompt内容生成对应的模拟响应
        prompt = user_message

        # 模式定义：(名称, 强关键字列表, 弱关键字列表, 处理函数)
        def find_best_pattern():
            patterns = [
                ("exercise",    ["练习题", "出题", "生成.*题"],       ["题目"],         self._mock_exercise),
                ("grade",       ["批改", "评分", "判卷"],             [],               self._mock_grade),
                ("split",       ["拆解", "拆分", "知识体系"],         [],               self._mock_knowledge_split),
                ("encouragement",["鼓励", "奖励", "激励"],            [],               self._mock_encouragement),
                ("qa",          ["用户问题", "回答用户", "追问建议", "问答", "答疑"], ["问题"], self._mock_qa),
                ("difficulty",  ["难度标注", "标注难度"],             ["难度"],          self._mock_difficulty),
                ("explain",     ["讲解内容", "通俗易懂", "讲解"],     ["解释"],          self._mock_content_explain),
            ]

            best_match = None
            best_score = 0

            for name, strong_kw, weak_kw, handler in patterns:
                score = 0
                # 强关键字：每个 +10 分
                for kw in strong_kw:
                    if re.search(kw, prompt):
                        score += 10
                # 弱关键字：每个 +1 分
                for kw in weak_kw:
                    if kw in prompt:
                        score += 1
                if score > best_score:
                    best_score = score
                    best_match = handler

            return best_match if best_score >= 10 else None

        handler = find_best_pattern()
        if handler:
            mock_content = handler(prompt)
        else:
            # 默认响应
            mock_content = json.dumps({
                "message": "这是一个模拟响应",
                "prompt_preview": prompt[:100]
            }, ensure_ascii=False)

        return LLMResponse(
            content=mock_content,
            model=self.config.model,
            provider=self.provider_type,
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            finish_reason="stop",
        )

    def _mock_knowledge_split(self, prompt: str) -> str:
        """模拟知识拆分响应"""
        import json
        import re

        match = re.search(r'【([^】]+)】', prompt)
        topic = match.group(1) if match else "学习主题"

        return json.dumps({
            "blocks": [
                {
                    "block_name": f"{topic}基础概念",
                    "points": [
                        {
                            "point_name": "核心概念",
                            "difficulty": "easy",
                            "is_key_point": True,
                            "components": [
                                {"component_name": "基本定义"},
                                {"component_name": "关键特性"}
                            ]
                        },
                        {
                            "point_name": "基本原理",
                            "difficulty": "medium",
                            "is_key_point": True,
                            "components": [
                                {"component_name": "原理说明"},
                                {"component_name": "应用场景"}
                            ]
                        }
                    ]
                },
                {
                    "block_name": f"{topic}实践应用",
                    "points": [
                        {
                            "point_name": "操作方法",
                            "difficulty": "medium",
                            "is_key_point": False,
                            "components": [
                                {"component_name": "步骤流程"},
                                {"component_name": "注意事项"}
                            ]
                        }
                    ]
                }
            ]
        }, ensure_ascii=False)

    def _mock_content_explain(self, prompt: str) -> str:
        """模拟知识讲解响应 - 返回纯文本"""
        import re
        match = re.search(r'【([^】]+)】', prompt)
        point_name = match.group(1).strip() if match else "知识点"

        return f"""1. 先用一句通俗人话，给知识点下定义，讲清它核心是什么、解决什么问题
{point_name}是一个重要的概念，帮助我们理解和处理特定类型的问题。

2. 再讲底层本质原理，挖到深度层面，不只讲表面
{point_name}的核心原理是基于几个关键概念构建的。

3. 给出极简入门示例 + 实操案例
举个简单例子：比如我们在做XX的时候，就会用到{point_name}。

4. 拆解核心/结构/组成要素，逐条解释每一部分作用
核心要素包括：
- 要素1：基础组成部分
- 要素2：关键功能
- 要素3：交互方式

5. 对比易混淆知识点，做异同区分，帮我避坑
{point_name}和类似概念的区别在于...

6. 列出新手高频错误、典型误区
常见误区：
- 误区1：理解片面
- 误区2：忽略边界条件

7. 给出适用场景、什么时候该用、什么时候不该用
适用场景：
- 场景1：适合使用
- 场景2：不适合使用

8. 最后总结一句核心口诀，方便记忆
口诀：理解本质，灵活运用。"""

    def _mock_exercise(self, prompt: str) -> str:
        """模拟练习题生成响应"""
        import json
        import re

        # 提取参数
        component_match = re.search(r'知识组件[：:]\s*([^\n]+)', prompt)
        knowledge_match = re.search(r'所属知识点[：:]\s*([^\n]+)', prompt)
        block_match = re.search(r'所属板块[：:]\s*([^\n]+)', prompt)

        component_name = component_match.group(1).strip() if component_match else "知识点组件"
        knowledge_name = knowledge_match.group(1).strip() if knowledge_match else "知识点"
        block_name = block_match.group(1).strip() if block_match else "知识板块"

        return json.dumps({
            "questions": [
                {
                    "id": "q-1",
                    "type": "practical_qa",
                    "category": "故障排查",
                    "content": f"你正在开发一个使用{knowledge_name}的项目，遇到了一个问题：{component_name}没有按预期工作。请分析可能的原因并给出排查步骤。",
                    "hints": ["提示1：先检查基本配置", "提示2：查看日志信息", "提示3：验证输入数据"],
                    "reference_answer": "排查步骤：\n1. 检查配置是否正确\n2. 查看详细日志输出\n3. 验证输入数据格式\n4. 简化场景复现问题\n5. 对比正常工作的案例",
                    "key_points": [f"{component_name}的使用方法", "问题排查思路", "调试技巧"],
                    "difficulty": "medium"
                }
            ]
        }, ensure_ascii=False)

    def _mock_grade(self, prompt: str) -> str:
        """模拟批改响应"""
        import json
        return json.dumps({
            "total_score": 100,
            "correct_count": 3,
            "total_count": 5,
            "details": [
                {"question_id": "q-1", "is_correct": True, "user_answer": "A", "correct_answer": "A"},
                {"question_id": "q-2", "is_correct": False, "user_answer": "B", "correct_answer": "A"}
            ],
            "feedback": "整体评价和改进建议"
        }, ensure_ascii=False)

    def _mock_qa(self, prompt: str) -> str:
        """模拟问答响应"""
        import re
        match = re.search(r'用户问题[：:]\s*([^\n]+)', prompt)
        question = match.group(1).strip() if match else "这个问题"
        return f"关于{question[:20]}，核心在于理解基本概念。简单来说，我们需要从定义出发，逐步深入理解。在学习中，掌握好基础知识是关键。"

    def _mock_difficulty(self, prompt: str) -> str:
        """模拟难度标注响应"""
        import json
        return json.dumps({
            "annotations": [
                {
                    "point_name": "核心概念",
                    "difficulty": "MEDIUM",
                    "importance": "HIGH",
                    "reason": "是后续学习的基础"
                }
            ]
        }, ensure_ascii=False)

    def _mock_encouragement(self, prompt: str) -> str:
        """模拟鼓励文案响应"""
        import json
        return json.dumps({
            "title": "做得好！",
            "message": "你的努力值得肯定，继续加油！"
        }, ensure_ascii=False)


# 注册Provider
from .factory import register_provider
register_provider(ProviderType.DOUBAO, DoubaoProvider)
