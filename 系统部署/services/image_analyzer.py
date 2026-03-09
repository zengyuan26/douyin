"""
图片识别服务 - 使用 GPT Vision API 分析图片
"""
import os
import json
import base64
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ImageAnalyzer:
    """图片分析服务类"""
    
    def __init__(self, provider='openai'):
        """
        初始化图片分析服务
        
        Args:
            provider: 模型提供商 ('openai', 'azure')
        """
        self.provider = provider
        self.api_key = os.environ.get('OPENAI_API_KEY', '')
        self.base_url = os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')
        self.model = os.environ.get('VISION_MODEL', 'gpt-4o')
        
    def analyze_account_image(self, image_data: str) -> Dict:
        """
        分析账号主页截图，提取账号信息
        
        Args:
            image_data: 图片数据（base64 编码或 URL）
            
        Returns:
            账号信息字典
        """
        prompt = """请分析这张社交媒体账号主页截图，提取以下信息：
        1. 账号名称
        2. 平台类型（抖音、小红书、B站等）
        3. 粉丝数
        4. 关注数
        5. 获赞数
        6. IP 属地
        7. 账号简介
        8. 视频数（如果有）
        
        请以 JSON 格式返回结果，字段如下：
        {
            "name": "账号名称",
            "platform": "平台类型",
            "followers": 粉丝数,
            "following": 关注数,
            "likes": 获赞数,
            "ip_location": "IP属地",
            "bio": "账号简介",
            "video_count": 视频数,
            "other_info": {}  // 其他有用信息
        }"""
        
        return self._analyze_image(image_data, prompt)
    
    def analyze_content_image(self, image_data: str) -> Dict:
        """
        分析内容截图，提取内容信息
        
        Args:
            image_data: 图片数据（base64 编码或 URL）
            
        Returns:
            内容信息字典
        """
        prompt = """请分析这张社交媒体内容截图（可能是视频封面、图文内容、评论区等），提取以下信息：
        1. 内容类型（video, image_text, plain_text）
        2. 标题
        3. 内容描述/文案
        4. 点赞数
        5. 评论数
        6. 收藏数
        7. 分享数
        8. 发布时间（如果可见）
        9. 话题标签
        10. 账号名称（发布者）
        
        请以 JSON 格式返回结果，字段如下：
        {
            "content_type": "内容类型",
            "title": "标题",
            "description": "内容描述/文案",
            "likes": 点赞数,
            "comments": 评论数,
            "collects": 收藏数,
            "shares": 分享数,
            "publish_time": "发布时间",
            "hashtags": ["话题标签列表"],
            "author": "账号名称",
            "other_info": {}  // 其他有用信息
        }"""
        
        return self._analyze_image(image_data, prompt)
    
    def _analyze_image(self, image_data: str, prompt: str) -> Dict:
        """
        调用 Vision API 分析图片
        
        Args:
            image_data: 图片数据（base64 编码或 URL）
            prompt: 分析提示词
            
        Returns:
            分析结果字典
        """
        try:
            if self.provider == 'openai':
                return self._analyze_openai(image_data, prompt)
            elif self.provider == 'azure':
                return self._analyze_azure(image_data, prompt)
            else:
                logger.error(f"Unknown provider: {self.provider}")
                return {"error": f"Unknown provider: {self.provider}"}
        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            return {"error": str(e)}
    
    def _analyze_openai(self, image_data: str, prompt: str) -> Dict:
        """OpenAI Vision API 调用"""
        import requests
        
        # 处理图片数据格式
        if image_data.startswith('data:image'):
            # base64 编码的图片
            image_url = image_data
        elif image_data.startswith('http'):
            # URL
            image_url = image_data
        else:
            # 假设是文件路径
            with open(image_data, 'rb') as f:
                base64_image = base64.b64encode(f.read()).decode('utf-8')
            image_url = f"data:image/jpeg;base64,{base64_image}"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}/chat/completions"
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ]
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 2000
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        
        # 尝试解析 JSON
        try:
            # 尝试提取 JSON 部分
            if '```json' in content:
                json_str = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                json_str = content.split('```')[1].split('```')[0]
            else:
                json_str = content
            
            return json.loads(json_str.strip())
        except json.JSONDecodeError:
            # 如果解析失败，返回原始内容
            return {"raw_content": content}
    
    def _analyze_azure(self, image_data: str, prompt: str) -> Dict:
        """Azure OpenAI Vision API 调用"""
        import requests
        
        # 处理图片数据格式
        if image_data.startswith('data:image'):
            image_url = image_data
        elif image_data.startswith('http'):
            image_url = image_data
        else:
            with open(image_data, 'rb') as f:
                base64_image = base64.b64encode(f.read()).decode('utf-8')
            image_url = f"data:image/jpeg;base64,{base64_image}"
        
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        # Azure 端点格式
        deployment_name = os.environ.get('AZURE_VISION_DEPLOYMENT', 'gpt-4o')
        url = f"{self.base_url}/openai/deployments/{deployment_name}/chat/completions?api-version=2024-02-01"
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ]
        
        payload = {
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 2000
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        
        try:
            if '```json' in content:
                json_str = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                json_str = content.split('```')[1].split('```')[0]
            else:
                json_str = content
            
            return json.loads(json_str.strip())
        except json.JSONDecodeError:
            return {"raw_content": content}


# 全局实例
_image_analyzer = None

def get_image_analyzer() -> ImageAnalyzer:
    """获取图片分析服务实例"""
    global _image_analyzer
    if _image_analyzer is None:
        provider = os.environ.get('VISION_PROVIDER', 'openai')
        _image_analyzer = ImageAnalyzer(provider=provider)
    return _image_analyzer


def analyze_account_image(image_data: str) -> Dict:
    """
    快捷函数：分析账号主页图片
    
    Args:
        image_data: 图片数据
        
    Returns:
        账号信息
    """
    analyzer = get_image_analyzer()
    return analyzer.analyze_account_image(image_data)


def analyze_content_image(image_data: str) -> Dict:
    """
    快捷函数：分析内容图片
    
    Args:
        image_data: 图片数据
        
    Returns:
        内容信息
    """
    analyzer = get_image_analyzer()
    return analyzer.analyze_content_image(image_data)
