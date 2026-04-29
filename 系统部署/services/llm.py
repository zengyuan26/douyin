"""
LLM 服务模块 - 支持多种模型接入
"""
import re
import os
import json
import logging
from typing import Generator, Dict, Optional

logger = logging.getLogger(__name__)


# ========== 模型上下文窗口配置 ==========
# 支持的模型列表（根据 .env 配置）
MODEL_CONTEXT_LIMITS: Dict[str, Dict] = {
    # ========== 硅基流动 (siliconflow) ==========
    # Qwen 系列（通义千问）
    'Qwen/Qwen2.5-7B-Instruct': {
        'context': 8192, 'output': 2000, 'description': 'Qwen2.5-7B 轻量模型'
    },
    'Qwen/Qwen2.5-14B-Instruct': {
        'context': 8192, 'output': 2000, 'description': 'Qwen2.5-14B 标准模型'
    },
    'Qwen/Qwen2.5-72B-Instruct': {
        'context': 32768, 'output': 4000, 'description': 'Qwen2.5-72B 大模型'
    },
    'Qwen/Qwen2.5-32B-Instruct': {
        'context': 32768, 'output': 4000, 'description': 'Qwen2.5-32B 中大模型'
    },
    'Qwen/Qwen2-Max': {
        'context': 8192, 'output': 2000, 'description': 'Qwen-Max 高性能模型'
    },
    'Qwen/Qwen2.5-7B-Instruct-A03': {
        'context': 8192, 'output': 2000, 'description': 'Qwen2.5-7B-A03'
    },
    # DeepSeek 系列
    'deepseek-ai/DeepSeek-V3': {
        'context': 64000, 'output': 8000, 'description': 'DeepSeek-V3 最新模型'
    },
    'deepseek-ai/DeepSeek-V2.5': {
        'context': 8192, 'output': 4000, 'description': 'DeepSeek-V2.5'
    },
    'deepseek-ai/DeepSeek-R1': {
        'context': 8192, 'output': 4000, 'description': 'DeepSeek-R1 推理模型'
    },
    # GLM 系列
    'THUDM/GLM-4-9B-Chat': {
        'context': 8192, 'output': 2000, 'description': 'GLM-4-9B 轻量模型'
    },
    # ========== 阿里云百炼 (百炼系列，仅 base_url 不同) ==========
    'qwen-turbo': {'context': 8192, 'output': 1500, 'description': '百炼-Turbo快速模型'},
    'qwen-plus': {'context': 32768, 'output': 4000, 'description': '百炼-Plus标准模型'},
    'qwen-max': {'context': 8192, 'output': 2000, 'description': '百炼-Max高精度模型'},
    'qwen-max-longcontext': {'context': 262144, 'output': 8192, 'description': '百炼-Max长上下文'},
    # ========== OpenAI 系列 ==========
    'gpt-4o': {'context': 128000, 'output': 4096, 'description': 'GPT-4o'},
    'gpt-4o-mini': {'context': 128000, 'output': 4096, 'description': 'GPT-4o-mini'},
    'gpt-4-turbo': {'context': 128000, 'output': 4096, 'description': 'GPT-4 Turbo'},
    'gpt-3.5-turbo': {'context': 16385, 'output': 4096, 'description': 'GPT-3.5'},
}

# ========== 任务类型与推荐 max_tokens ==========
# 注意：硅基流动 Qwen2.5-7B 的 output 限制约 2000 tokens
# 如果用 Premium 模型 (DeepSeek-V3)，可以设置更高
TASK_MAX_TOKENS: Dict[str, Dict] = {
    # 简单任务
    'classification': {'max_tokens': 500, 'temperature': 0.3, 'description': '分类任务'},
    'keyword_extract': {'max_tokens': 800, 'temperature': 0.3, 'description': '关键词提取'},
    'sentiment': {'max_tokens': 500, 'temperature': 0.3, 'description': '情感分析'},

    # 中等任务（适配 7B 模型）
    'summary': {'max_tokens': 1500, 'temperature': 0.5, 'description': '摘要生成'},
    'rewrite': {'max_tokens': 1500, 'temperature': 0.7, 'description': '内容改写'},
    'dimension_analysis': {'max_tokens': 1500, 'temperature': 0.5, 'description': '维度分析'},
    'nickname_analysis': {'max_tokens': 1500, 'temperature': 0.5, 'description': '昵称分析'},
    'bio_analysis': {'max_tokens': 1500, 'temperature': 0.5, 'description': '简介分析'},

    # 复杂任务（用 Premium 模型效果更好）
    'persona_generate': {'max_tokens': 2500, 'temperature': 0.8, 'description': '人群画像生成'},
    'content_create': {'max_tokens': 4000, 'temperature': 0.8, 'description': '图文内容创作（7帧slides）'},
    'market_analysis': {'max_tokens': 2500, 'temperature': 0.7, 'description': '市场分析'},
    'deep_analysis': {'max_tokens': 2500, 'temperature': 0.6, 'description': '深度分析'},

    # SkillBridge 各 skill 专用任务类型
    'title_generate': {'max_tokens': 1500, 'temperature': 0.8, 'description': 'H-V-F标题生成'},
    'tag_generate': {'max_tokens': 1000, 'temperature': 0.7, 'description': '金字塔标签生成'},
    'quality_validate': {'max_tokens': 2000, 'temperature': 0.3, 'description': '内容质量评分'},
    # SkillBridge skill 名称映射（executor 传入 task_type=skill_name）
    'content_generator': {'max_tokens': 4000, 'temperature': 0.8, 'description': '图文内容生成（7帧slides）'},
    'market_analyzer': {'max_tokens': 3000, 'temperature': 0.7, 'description': '市场分析'},
    'keyword_library_generator': {'max_tokens': 3000, 'temperature': 0.7, 'description': '关键词库生成'},
    'topic_library_generator': {'max_tokens': 3000, 'temperature': 0.7, 'description': '选题库生成'},
    'portrait_generator': {'max_tokens': 3000, 'temperature': 0.8, 'description': '画像生成'},
    'video_script_generator': {'max_tokens': 4000, 'temperature': 0.8, 'description': '短视频脚本生成'},
    'long_text_generator': {'max_tokens': 4000, 'temperature': 0.8, 'description': '长文内容生成'},
    'psychology_reviewer': {'max_tokens': 2000, 'temperature': 0.3, 'description': '心理学审核'},
    'title_generator': {'max_tokens': 1500, 'temperature': 0.8, 'description': 'H-V-F标题生成'},
    'tag_generator': {'max_tokens': 1000, 'temperature': 0.7, 'description': '金字塔标签生成'},

    # 超长任务（需要 Premium 模型）
    'full_report': {'max_tokens': 4000, 'temperature': 0.7, 'description': '完整报告'},
    'multi_persona': {'max_tokens': 4000, 'temperature': 0.8, 'description': '多画像生成'},
}


class LLMService:
    """LLM 服务类"""
    
    def __init__(self, provider='qwen', model=None):
        """
        初始化 LLM 服务
        
        Args:
            provider: 模型提供商 ('ollama', 'openai', 'qwen', 'azure', 'siliconflow')
            model: 模型名称
        """
        self.provider = provider
        self.model = model or os.environ.get('LLM_MODEL', 'Qwen/Qwen2.5-14B-Instruct')
        self.base_url = os.environ.get('LLM_BASE_URL', 'https://api.siliconflow.cn/v1')
        self.api_key = os.environ.get('LLM_API_KEY', '')
        
    def chat(self, messages, temperature=0.7, max_tokens=None, task_type=None):
        """
        发送聊天请求

        Args:
            messages: 消息列表 [{"role": "user/assistant/system", "content": "..."}]，
                      也支持直接传字符串（自动包装成 user 消息）
            temperature: 温度参数
            max_tokens: 最大令牌数（未指定时根据 task_type 自动查表）
            task_type: 任务类型，可选 ('content_create', 'market_analysis', 'title_generate', 'tag_generate', ...)
                        用于自动选择合适的 max_tokens

        Returns:
            回复文本或 None
        """
        # 兼容直接传字符串的场景
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        # 自动根据 task_type 查表 max_tokens
        if max_tokens is None:
            if task_type:
                cfg = get_task_config(task_type)
                max_tokens = cfg.get('max_tokens', 2000)
            else:
                max_tokens = 2000

        try:
            if self.provider == 'ollama':
                return self._chat_ollama(messages, temperature, max_tokens)
            elif self.provider == 'openai':
                return self._chat_openai(messages, temperature, max_tokens)
            elif self.provider == 'qwen':
                return self._chat_qwen(messages, temperature, max_tokens)
            elif self.provider == 'siliconflow':
                return self._chat_siliconflow(messages, temperature, max_tokens)
            elif self.provider == 'azure':
                return self._chat_azure(messages, temperature, max_tokens)
            else:
                logger.error(f"Unknown provider: {self.provider}")
                return None
        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            return None
    
    def _chat_ollama(self, messages, temperature, max_tokens):
        """Ollama API 调用"""
        import requests
        
        # 转换消息格式
        ollama_messages = []
        for msg in messages:
            ollama_messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })
        
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "temperature": temperature,
            "stream": False
        }
        
        response = requests.post(url, json=payload, timeout=300)
        response.raise_for_status()
        
        result = response.json()
        return result.get("message", {}).get("content", "")
    
    def _chat_openai(self, messages, temperature, max_tokens):
        """OpenAI API 调用"""
        import requests
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=300)
        response.raise_for_status()

        try:
            result = response.json()
        except Exception as e:
            logger.error(f"[LLM] OpenAI 响应 JSON 解析失败: {e}, body={response.text[:200]}")
            return None

        try:
            return result["choices"][0]["message"]["content"]
        except (KeyError, TypeError, IndexError) as e:
            logger.error(f"[LLM] OpenAI 响应格式异常: {e}, result={str(result)[:300]}")
            return None

    def _chat_qwen(self, messages, temperature, max_tokens):
        """阿里云百炼 (Qwen) API 调用 - 兼容 OpenAI 格式"""
        import requests
        import urllib3
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,  # qwen-plus, qwen-turbo, qwen-max 等
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        # 禁用 SSL 警告
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # 创建 session，明确禁用代理
        session = requests.Session()
        session.trust_env = False
        
        try:
            response = session.post(
                url, 
                headers=headers, 
                json=payload, 
                timeout=300, 
                verify=False
            )
        except requests.exceptions.SSLError as e:
            logger.warning(f"SSL error in Qwen API, retrying: {e}")
            session = requests.Session()
            session.trust_env = False
            response = session.post(
                url, 
                headers=headers, 
                json=payload, 
                timeout=300, 
                verify=True
            )
        
        response.raise_for_status()

        try:
            result = response.json()
        except Exception as e:
            logger.error(f"[LLM] Qwen 响应 JSON 解析失败: {e}, body={response.text[:200]}")
            return None

        try:
            return result["choices"][0]["message"]["content"]
        except (KeyError, TypeError, IndexError) as e:
            logger.error(f"[LLM] Qwen 响应格式异常: {e}, result={str(result)[:300]}")
            return None

    def _chat_siliconflow(self, messages, temperature, max_tokens):
        """硅基流动 API 调用 - 兼容 OpenAI 格式"""
        import requests
        import urllib3
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,  # Qwen/Qwen2.5-7B-Instruct 等
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        # 禁用 SSL 警告（避免控制台输出大量警告）
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # 尝试创建 session，明确禁用代理
        session = requests.Session()
        session.trust_env = False  # 不从环境变量读取代理配置
        
        # 先尝试不验证 SSL（有些代理环境下验证会失败）
        try:
            response = session.post(
                url, 
                headers=headers, 
                json=payload, 
                timeout=300, 
                verify=False  # 禁用 SSL 验证，避免 SSL 错误
            )
        except requests.exceptions.SSLError as e:
            # SSL 错误时，尝试使用系统默认证书
            logger.warning(f"SSL error, retrying with system certificates: {e}")
            session = requests.Session()
            session.trust_env = False
            response = session.post(
                url, 
                headers=headers, 
                json=payload, 
                timeout=300, 
                verify=True
            )
        
        # 检查响应状态
        if response.status_code != 200:
            logger.error(f"[LLM] SiliconFlow API 错误: {response.status_code} - {response.text[:500]}")
            return None

        try:
            result = response.json()
        except Exception as e:
            logger.error(f"[LLM] SiliconFlow 响应 JSON 解析失败: {e}, body={response.text[:200]}")
            return None

        try:
            return result["choices"][0]["message"]["content"]
        except (KeyError, TypeError, IndexError) as e:
            logger.error(f"[LLM] SiliconFlow 响应格式异常: {e}, result={str(result)[:300]}")
            return None
    
    def _chat_azure(self, messages, temperature, max_tokens):
        """Azure OpenAI API 调用"""
        import requests
        
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        # Azure 需要不同的端点格式
        url = f"{self.base_url}/openai/deployments/{self.model}/chat/completions?api-version=2024-02-01"
        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=300)
        response.raise_for_status()

        try:
            result = response.json()
        except Exception as e:
            logger.error(f"[LLM] Azure 响应 JSON 解析失败: {e}, body={response.text[:200]}")
            return None

        try:
            return result["choices"][0]["message"]["content"]
        except (KeyError, TypeError, IndexError) as e:
            logger.error(f"[LLM] Azure 响应格式异常: {e}, result={str(result)[:300]}")
            return None

    def list_models(self):
        """列出可用模型"""
        try:
            import requests
            response = requests.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            return response.json().get("models", [])
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []

    def chat_stream(self, messages, temperature=0.7, max_tokens=2000) -> Generator[str, None, None]:
        """
        流式聊天请求

        Args:
            messages: 消息列表 [{"role": "user/assistant/system", "content": "..."}]
            temperature: 温度参数
            max_tokens: 最大令牌数

        Yields:
            回复文本片段
        """
        try:
            if self.provider == 'ollama':
                yield from self._chat_stream_ollama(messages, temperature, max_tokens)
            elif self.provider == 'openai':
                yield from self._chat_stream_openai(messages, temperature, max_tokens)
            elif self.provider == 'qwen':
                yield from self._chat_stream_openai(messages, temperature, max_tokens)  # 兼容 OpenAI 格式
            elif self.provider == 'siliconflow':
                yield from self._chat_stream_openai(messages, temperature, max_tokens)
            elif self.provider == 'azure':
                yield from self._chat_stream_azure(messages, temperature, max_tokens)
            else:
                logger.error(f"Unknown provider: {self.provider}")
        except Exception as e:
            logger.error(f"LLM stream request failed: {e}")

    def _chat_stream_ollama(self, messages, temperature, max_tokens) -> Generator[str, None, None]:
        """Ollama 流式 API 调用"""
        import requests

        ollama_messages = []
        for msg in messages:
            ollama_messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })

        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "temperature": temperature,
            "stream": True
        }

        response = requests.post(url, json=payload, timeout=300, stream=True)
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    content = data.get("message", {}).get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue

    def _chat_stream_openai(self, messages, temperature, max_tokens) -> Generator[str, None, None]:
        """OpenAI 流式 API 调用"""
        import requests

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }

        response = requests.post(url, headers=headers, json=payload, timeout=300, stream=True)
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data_str = line[6:]
                    if data_str == '[DONE]':
                        break
                    try:
                        data = json.loads(data_str)
                        content = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue

    def _chat_stream_azure(self, messages, temperature, max_tokens) -> Generator[str, None, None]:
        """Azure OpenAI 流式 API 调用"""
        import requests

        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json"
        }

        url = f"{self.base_url}/openai/deployments/{self.model}/chat/completions?api-version=2024-02-01"
        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }

        response = requests.post(url, headers=headers, json=payload, timeout=300, stream=True)
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data_str = line[6:]
                    if data_str == '[DONE]':
                        break
                    try:
                        data = json.loads(data_str)
                        content = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue


# 全局实例
llm_service = None

def get_llm_service():
    """获取 LLM 服务实例"""
    global llm_service
    if llm_service is None:
        # 优先读取 Flask app config，否则读环境变量
        try:
            from flask import current_app
            provider = current_app.config.get('LLM_PROVIDER', 'siliconflow')
            model = current_app.config.get('LLM_MODEL', 'Qwen/Qwen2.5-14B-Instruct')
            base_url = current_app.config.get('LLM_BASE_URL', 'https://api.siliconflow.cn/v1')
            api_key = current_app.config.get('LLM_API_KEY', '')
        except Exception:
            provider = os.environ.get('LLM_PROVIDER', 'siliconflow')
            model = os.environ.get('LLM_MODEL', 'Qwen/Qwen2.5-14B-Instruct')
            base_url = os.environ.get('LLM_BASE_URL', 'https://api.siliconflow.cn/v1')
            api_key = os.environ.get('LLM_API_KEY', '')

        llm_service = LLMService(provider=provider, model=model)
        # 注入 base_url 和 api_key（LLMService 默认只读环境变量）
        llm_service.base_url = base_url
        llm_service.api_key = api_key
    return llm_service


def chat_with_llm(messages, temperature=0.7):
    """
    快捷函数：与 LLM 对话

    Args:
        messages: 消息列表
        temperature: 温度

    Returns:
        回复文本
    """
    service = get_llm_service()
    return service.chat(messages, temperature=temperature) or "抱歉，我现在无法回答，请稍后再试。"


# ========== Token 计算和上下文管理辅助函数 ==========

def estimate_tokens(text: str) -> int:
    """
    简单估算文本的 token 数量。

    估算方法：
    - 中文：每个字符约 1.5-2 tokens（按 2 估算偏保守）
    - 英文：每个单词约 1.3 tokens
    - 混合：按平均每 2 字符 = 1 token

    Args:
        text: 待估算文本

    Returns:
        估算的 token 数量
    """
    if not text:
        return 0

    # 中文字符数
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    # 非中文字符数（英文、空格、标点等）
    other_chars = len(text) - chinese_chars

    # 估算：中文 2 tokens/字，英文 1 token/2字符
    return chinese_chars * 2 + other_chars // 2


def estimate_messages_tokens(messages) -> int:
    """
    估算消息列表的总 token 数量。

    Args:
        messages: 消息列表 [{"role": "...", "content": "..."}]

    Returns:
        估算的总 token 数
    """
    total = 0
    # 消息格式开销（每条消息约 4 tokens）
    total += len(messages) * 4

    for msg in messages:
        if isinstance(msg, dict):
            content = msg.get('content', '')
        else:
            content = str(msg)
        total += estimate_tokens(content)

    return total


def get_model_context_limit(model: str = None) -> Dict:
    """
    获取模型上下文限制。

    Args:
        model: 模型名称，默认从环境变量读取

    Returns:
        包含 context 和 output 限制的字典
    """
    if model is None:
        model = os.environ.get('LLM_MODEL', 'Qwen/Qwen2.5-14B-Instruct')

    # 精确匹配
    if model in MODEL_CONTEXT_LIMITS:
        return MODEL_CONTEXT_LIMITS[model].copy()

    # 前缀匹配（如 'qwen-plus-2025' 匹配 'qwen-plus'）
    for known_model, limits in MODEL_CONTEXT_LIMITS.items():
        if model.startswith(known_model) or known_model.startswith(model):
            return limits.copy()

    # 未知模型，返回保守默认值
    logger.warning(f"Unknown model '{model}', using conservative defaults")
    return {'context': 8192, 'output': 2000, 'description': '未知模型'}


def calculate_safe_max_tokens(
    messages,
    model: str = None,
    reserved_tokens: int = 500,
    min_tokens: int = 500,
    max_tokens: int = None
) -> int:
    """
    根据上下文窗口计算安全的 max_tokens 值。

    工作原理：
    1. 估算输入消息的 token 数
    2. 从模型上下文窗口中减去输入和预留空间
    3. 确保返回值在合理范围内

    Args:
        messages: 消息列表
        model: 模型名称
        reserved_tokens: 为系统响应预留的 token 数（默认 500）
        min_tokens: 最小返回值（默认 500）
        max_tokens: 最大限制（如果指定，优先级最高）

    Returns:
        安全的 max_tokens 值
    """
    model_limits = get_model_context_limit(model)

    # 如果指定了 max_tokens 且在安全范围内，直接返回
    if max_tokens is not None:
        safe_limit = model_limits['context'] - reserved_tokens
        return min(max_tokens, safe_limit)

    # 估算输入 token
    input_tokens = estimate_messages_tokens(messages)

    # 计算可用空间
    context_limit = model_limits['context']
    available = context_limit - input_tokens - reserved_tokens

    # 确保在合理范围内
    result = max(min_tokens, available)

    # 不能超过模型默认 output 限制
    result = min(result, model_limits['output'])

    logger.debug(
        f"[TokenCalc] model={model}, input={input_tokens}, "
        f"context={context_limit}, available={available}, result={result}"
    )

    return result


def get_task_config(task_type: str = None) -> Dict:
    """
    获取任务类型的推荐配置。

    Args:
        task_type: 任务类型 ('classification', 'content_create', 'market_analysis' 等)

    Returns:
        包含 max_tokens 和 temperature 的字典
    """
    if task_type and task_type in TASK_MAX_TOKENS:
        return TASK_MAX_TOKENS[task_type].copy()

    # 默认配置
    return {
        'max_tokens': 2000,
        'temperature': 0.7,
        'description': '默认配置'
    }


def smart_chat(
    messages,
    task_type: str = None,
    model: str = None,
    temperature: float = None,
    max_tokens: int = None,
    check_context: bool = True
):
    """
    智能聊天函数 - 自动计算合适的 max_tokens。

    用法示例：
    ```
    # 自动根据任务类型和上下文计算
    result = smart_chat(messages, task_type='content_create')

    # 指定温度和 max_tokens（跳过自动计算）
    result = smart_chat(messages, temperature=0.9, max_tokens=5000)

    # 只检查上下文不发送
    safe_max = calculate_safe_max_tokens(messages)
    ```

    Args:
        messages: 消息列表
        task_type: 任务类型，用于自动配置
        model: 模型名称
        temperature: 温度参数（如果为 None 则用任务默认值）
        max_tokens: 最大 token 数（如果为 None 则自动计算）
        check_context: 是否检查上下文限制

    Returns:
        LLM 回复文本
    """
    service = get_llm_service()

    # 如果没指定模型，用当前服务的模型
    if model is None:
        model = service.model

    # 确定 temperature
    if temperature is None:
        task_cfg = get_task_config(task_type)
        temperature = task_cfg.get('temperature', 0.7)

    # 确定 max_tokens
    if max_tokens is None:
        # 先用任务默认值
        task_cfg = get_task_config(task_type)
        default_max = task_cfg.get('max_tokens', 2000)

        if check_context:
            # 动态计算安全值（取任务默认值和计算值的较小值）
            calculated = calculate_safe_max_tokens(messages, model=model)
            max_tokens = min(default_max, calculated)
        else:
            max_tokens = default_max
    else:
        # 用户指定了 max_tokens，进行安全检查
        if check_context:
            max_tokens = calculate_safe_max_tokens(
                messages, model=model, max_tokens=max_tokens
            )

    logger.info(
        f"[SmartChat] task={task_type}, model={model}, "
        f"temp={temperature}, max_tokens={max_tokens}"
    )

    return service.chat(
        messages,
        temperature=temperature,
        max_tokens=max_tokens
    )

