"""
LLM 服务模块 - 支持多种模型接入
"""
import os
import json
import logging
from typing import Generator

logger = logging.getLogger(__name__)


class LLMService:
    """LLM 服务类"""
    
    def __init__(self, provider='qwen', model=None):
        """
        初始化 LLM 服务
        
        Args:
            provider: 模型提供商 ('ollama', 'openai', 'qwen', 'azure')
            model: 模型名称
        """
        self.provider = provider
        self.model = model or os.environ.get('LLM_MODEL', 'qwen-plus')
        self.base_url = os.environ.get('LLM_BASE_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
        self.api_key = os.environ.get('LLM_API_KEY', '')
        
    def chat(self, messages, temperature=0.7, max_tokens=2000):
        """
        发送聊天请求

        Args:
            messages: 消息列表 [{"role": "user/assistant/system", "content": "..."}]，
                      也支持直接传字符串（自动包装成 user 消息）
            temperature: 温度参数
            max_tokens: 最大令牌数

        Returns:
            回复文本或 None
        """
        # 兼容直接传字符串的场景
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        try:
            if self.provider == 'ollama':
                return self._chat_ollama(messages, temperature, max_tokens)
            elif self.provider == 'openai':
                return self._chat_openai(messages, temperature, max_tokens)
            elif self.provider == 'qwen':
                return self._chat_qwen(messages, temperature, max_tokens)
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
        
        result = response.json()
        return result["choices"][0]["message"]["content"]

    def _chat_qwen(self, messages, temperature, max_tokens):
        """阿里云百炼 (Qwen) API 调用 - 兼容 OpenAI 格式"""
        import requests
        
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
        
        response = requests.post(url, headers=headers, json=payload, timeout=300)
        response.raise_for_status()
        
        result = response.json()
        return result["choices"][0]["message"]["content"]
    
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
        
        result = response.json()
        return result["choices"][0]["message"]["content"]
    
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
        provider = os.environ.get('LLM_PROVIDER', 'qwen')
        model = os.environ.get('LLM_MODEL', 'qwen-plus')
        llm_service = LLMService(provider=provider, model=model)
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
