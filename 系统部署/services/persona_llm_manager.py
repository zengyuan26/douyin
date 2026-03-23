"""
人群画像生成 - 分级模型管理器

功能：
1. 根据用户等级选择模型（免费=turbo，付费=plus）
2. 管理分步生成流程
3. 记录成本统计
"""

import os
import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from models.public_models import PublicUser, PublicLLMCallLog
from models.models import db
from services.llm import LLMService

logger = logging.getLogger(__name__)


@dataclass
class GenerationLimits:
    """用户生成限制"""
    max_problem_types: int      # 最多问题类型数
    portraits_per_type: int      # 每类型画像数
    max_portrait_fields: int    # 画像最大字段数
    model: str                  # 使用的模型

    # 默认限制（免费用户）
    @classmethod
    def free_limits(cls):
        return cls(
            max_problem_types=2,
            portraits_per_type=2,
            max_portrait_fields=4,
            model=os.environ.get('LLM_MODEL_TURBO', 'Qwen/Qwen2.5-7B-Instruct')
        )

    # 付费用户限制
    @classmethod
    def paid_limits(cls):
        return cls(
            max_problem_types=6,
            portraits_per_type=5,
            max_portrait_fields=8,
            model=os.environ.get('LLM_MODEL_PLUS', 'Qwen/Qwen2.5-14B-Instruct')
        )


class PersonaLLMManager:
    """
    人群画像 LLM 管理器

    支持分步生成策略：
    - 步骤1：快速识别问题类型（轻量级）
    - 步骤2：分批生成画像（每批一个类型）
    """

    # 模型价格（元/千tokens）- 硅基流动定价
    MODEL_PRICES = {
        'Qwen/Qwen2.5-7B-Instruct': {'input': 0.001, 'output': 0.001},  # turbo
        'Qwen/Qwen2.5-14B-Instruct': {'input': 0.002, 'output': 0.006},  # plus
        'Qwen/Qwen3-8B': {'input': 0.001, 'output': 0.001},
        'gpt-4o-mini': {'input': 0.0015, 'output': 0.006},
    }

    @classmethod
    def get_user_limits(cls, user: PublicUser) -> GenerationLimits:
        """根据用户等级获取生成限制"""
        if user and user.is_paid_user():
            return GenerationLimits.paid_limits()
        return GenerationLimits.free_limits()

    @classmethod
    def get_model_for_user(cls, user: PublicUser) -> str:
        """根据用户等级获取模型名称"""
        limits = cls.get_user_limits(user)
        return limits.model

    @classmethod
    def create_llm_service(cls, user: PublicUser = None) -> LLMService:
        """创建适合用户的 LLM 服务"""
        if user:
            model = cls.get_model_for_user(user)
        else:
            model = os.environ.get('LLM_MODEL_DEFAULT', 'Qwen/Qwen2.5-7B-Instruct')

        return LLMService(
            provider='siliconflow',
            model=model
        )

    @classmethod
    def log_llm_call(
        cls,
        user_id: int,
        call_type: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        duration_ms: int,
        status: str = 'success',
        error_message: str = None
    ) -> Optional[PublicLLMCallLog]:
        """记录 LLM 调用日志"""
        try:
            total_tokens = input_tokens + output_tokens
            cost = cls.calculate_cost(model, input_tokens, output_tokens)

            log = PublicLLMCallLog(
                user_id=user_id,
                call_type=call_type,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost=cost,
                duration_ms=duration_ms,
                status=status,
                error_message=error_message
            )
            db.session.add(log)
            db.session.commit()
            return log
        except Exception as e:
            logger.error(f"Failed to log LLM call: {e}")
            db.session.rollback()
            return None

    @classmethod
    def calculate_cost(cls, model: str, input_tokens: int, output_tokens: int) -> float:
        """计算调用成本"""
        prices = cls.MODEL_PRICES.get(model, {'input': 0.001, 'output': 0.001})
        return (input_tokens * prices['input'] + output_tokens * prices['output']) / 1000

    @classmethod
    def count_tokens_estimate(cls, text: str) -> int:
        """估算 token 数量（中文约 2 字符 = 1 token）"""
        if not text:
            return 0
        return len(text) // 2

    @classmethod
    def call_llm(
        cls,
        user: PublicUser,
        prompt: str,
        call_type: str,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        调用 LLM 并记录日志

        Returns:
            (response_text, stats)
            stats = {
                'model': str,
                'input_tokens': int,
                'output_tokens': int,
                'duration_ms': int,
                'cost': float
            }
        """
        service = cls.create_llm_service(user)
        model = service.model
        start_time = time.time()

        try:
            response = service.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )

            duration_ms = int((time.time() - start_time) * 1000)
            input_tokens = cls.count_tokens_estimate(prompt)
            output_tokens = cls.count_tokens_estimate(response or '')
            cost = cls.calculate_cost(model, input_tokens, output_tokens)

            # 记录日志
            if user:
                cls.log_llm_call(
                    user_id=user.id,
                    call_type=call_type,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    duration_ms=duration_ms,
                    status='success'
                )

            stats = {
                'model': model,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'duration_ms': duration_ms,
                'cost': cost
            }

            return response, stats

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"LLM call failed: {e}")

            if user:
                cls.log_llm_call(
                    user_id=user.id,
                    call_type=call_type,
                    model=model,
                    input_tokens=cls.count_tokens_estimate(prompt),
                    output_tokens=0,
                    duration_ms=duration_ms,
                    status='failed',
                    error_message=str(e)
                )

            return None, {'error': str(e), 'model': model}

    @classmethod
    def batch_call_llm(
        cls,
        user: PublicUser,
        prompts: List[Tuple[str, str]],
        # List of (prompt, call_type)
        max_concurrent: int = 3
    ) -> List[Tuple[Optional[str], Dict[str, Any]]]:
        """
        批量调用 LLM（用于并行生成多个画像）

        目前简单串行实现，未来可改为异步
        """
        results = []
        for prompt, call_type in prompts:
            result = cls.call_llm(user, prompt, call_type)
            results.append(result)
        return results


# 全局实例
persona_llm_manager = PersonaLLMManager()
