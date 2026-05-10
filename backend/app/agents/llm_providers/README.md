# LLM Provider 多模型支持模块

## 概述

本模块为AI智能教育课程平台提供多LLM模型支持，统一封装了OpenAI、智谱GLM、Kimi、Qwen、豆包等主流模型的API接口。

## 支持的模型

| Provider | 类型 | 默认模型 | API文档 |
|---------|------|---------|---------|
| OpenAI | 国际 | gpt-3.5-turbo | https://platform.openai.com/docs |
| 智谱GLM | 国产 | glm-4 | https://open.bigmodel.cn/dev/howuse/glm-4 |
| Kimi | 国产 | moonshot-v1-8k | https://platform.moonshot.cn/docs |
| Qwen | 国产 | qwen-turbo | https://help.aliyun.com/zh/dashscope |
| 豆包 | 国产 | doubao-pro-4k | https://www.volcengine.com/docs/82379 |

## 配置方式

### 1. 环境变量配置（推荐）

```bash
# OpenAI
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="gpt-3.5-turbo"

# 智谱GLM
export ZHIPU_API_KEY="your-api-key"
export ZHIPU_MODEL="glm-4"

# Kimi
export KIMI_API_KEY="your-api-key"
export KIMI_MODEL="moonshot-v1-8k"

# Qwen
export QWEN_API_KEY="your-api-key"
export QWEN_MODEL="qwen-turbo"

# 豆包
export DOUBAO_API_KEY="your-api-key"
export DOUBAO_MODEL="doubao-pro-4k"
```

### 2. 配置文件

创建 `config/llm_config.json`:

```json
{
  "global": {
    "default_provider": "zhipu",
    "fallback_provider": "openai"
  },
  "providers": {
    "zhipu": {
      "api_key": "your-api-key",
      "model": "glm-4"
    }
  }
}
```

## 使用方式

### 基础使用

```python
from app.agents.llm_providers import get_provider, ProviderType

# 获取默认Provider
provider = get_provider()

# 获取指定Provider
zhipu = get_provider(ProviderType.ZHIPU)
kimi = get_provider(ProviderType.KIMI)

# 生成文本
from app.agents.llm_providers import LLMMessage

messages = [
    LLMMessage(role="system", content="你是一个教学助手"),
    LLMMessage(role="user", content="解释什么是Python")
]

response = await provider.generate(messages)
print(response.content)
```

### Agent中使用

```python
from app.agents import KnowledgeSplitAgent
from app.agents.llm_providers import get_provider, ProviderType

# 使用智谱GLM
zhipu = get_provider(ProviderType.ZHIPU)
agent = KnowledgeSplitAgent(llm_client=zhipu)

# 或使用OpenAI
openai = get_provider(ProviderType.OPENAI)
agent = KnowledgeSplitAgent(llm_client=openai)
```

### 便捷函数

```python
from app.agents.llm_providers import create_llm_client

# 创建指定Provider的客户端
client = create_llm_client("zhipu")

# 生成文本
text = await client.generate("解释什么是Python")
```

## 模型能力

| 能力 | OpenAI | 智谱GLM | Kimi | Qwen | 豆包 |
|-----|--------|---------|------|------|------|
| 对话 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 函数调用 | ✅ | ✅ | ✅ | ✅ | ✅ |
| JSON输出 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 流式输出 | ✅ | ✅ | ✅ | ✅ | ✅ |

## 注意事项

1. **API Key安全**: 不要将API Key硬编码在代码中，使用环境变量或配置文件
2. **模型选择**: 根据任务复杂度选择合适的模型
   - 简单任务：qwen-turbo、doubao-lite-4k
   - 复杂任务：glm-4、gpt-4
   - 长文本：moonshot-v1-128k
3. **错误处理**: 所有Provider都有重试机制和降级到模拟响应的功能
