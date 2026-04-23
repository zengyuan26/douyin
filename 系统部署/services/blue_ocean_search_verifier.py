"""
蓝海机会搜索验证服务

功能：通过实时搜索验证 LLM 提出的蓝海机会假设

Phase 1: LLM 提出候选方向（含搜索假设句）
Phase 2: 对每个方向并行搜索验证（4个维度）
Phase 3: 合并数据 + LLM 综合判断

使用方式：
from services.blue_ocean_search_verifier import BlueOceanSearchVerifier

verifier = BlueOceanSearchVerifier()
result = verifier.verify_candidates(candidates, business_info)

注意：
- 如果代理不可用，搜索会自动降级跳过，不影响主流程
- 可以通过环境变量 DISABLE_SEARCH_VERIFICATION=1 禁用搜索验证
"""

import json
import logging
import os
import socket
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)


# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class SearchResult:
    """单次搜索结果"""
    query: str
    search_engine: str  # baidu / google / bing
    result_count: int = 0          # 结果数量（估算）
    top_results: List[Dict] = field(default_factory=list)  # 前几条结果摘要
    content_summary: str = ""      # 内容摘要（用于判断质量）
    is_valid: bool = True          # 搜索是否成功


@dataclass
class VerificationData:
    """验证数据"""
    demand_score: float = 0.0      # 需求真实性：0-1，越高说明需求越真实
    competition_score: float = 0.0  # 竞争强度：0-1，越高说明竞争越激烈
    scarcity_score: float = 0.0     # 解决方案稀缺度：0-1，越高说明解决方案越少
    content_gap_score: float = 0.0  # 内容缺口：0-1，越高说明内容越不完善
    overall_score: float = 0.0      # 综合评分：0-1，越高说明越可能是蓝海

    # 搜索证据
    demand_evidence: List[str] = field(default_factory=list)
    competition_evidence: List[str] = field(default_factory=list)
    scarcity_evidence: List[str] = field(default_factory=list)
    content_gap_evidence: List[str] = field(default_factory=list)


@dataclass
class CandidateDirection:
    """LLM 提出的候选方向"""
    opportunity_name: str
    business_direction: str
    target_audience: str = ""
    pain_points: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    content_direction: str = ""
    confidence: float = 0.8

    # LLM 提出的搜索假设句
    search_hypotheses: Dict[str, str] = field(default_factory=dict)

    # 验证数据（Phase 2 填充）
    verification: Optional[VerificationData] = None

    # 最终综合判断（Phase 3 填充）
    final_verdict: str = ""        # 综合判断结论
    final_confidence: float = 0.0  # 最终置信度
    search_evidence: List[str] = field(default_factory=list)  # 搜索证据摘要


@dataclass
class VerificationResult:
    """验证结果"""
    success: bool = False
    error_message: str = ""
    candidates: List[CandidateDirection] = field(default_factory=list)
    summary: str = ""  # 综合总结


# =============================================================================
# 搜索验证器
# =============================================================================

class BlueOceanSearchVerifier:
    """
    蓝海机会搜索验证器

    通过实时搜索验证 LLM 提出的候选方向，返回带置信度的验证结果。
    """

    # 搜索源配置
    SEARCH_SOURCES = {
        'baidu': {
            'base_url': 'https://www.baidu.com/s',
            'encoding': 'utf-8',
            'weight': 0.4,  # 权重
        },
        'bing': {
            'base_url': 'https://cn.bing.com/search',
            'encoding': 'utf-8',
            'weight': 0.3,
        },
        'google': {
            'base_url': 'https://www.google.com/search',
            'encoding': 'utf-8',
            'weight': 0.3,
        },
    }

    # 验证维度配置
    VERIFICATION_DIMENSIONS = {
        'demand': {
            'description': '需求真实性',
            'indicators': ['多少人', '怎么解决', '怎么办', '为什么'],
            'score_rule': 'positive',  # 结果越多/讨论越热越高
        },
        'competition': {
            'description': '竞争强度',
            'indicators': ['推荐', '哪个好', '排行榜', '评测'],
            'score_rule': 'negative',  # 结果越多/质量越高越低
        },
        'scarcity': {
            'description': '解决方案稀缺度',
            'indicators': ['没有', '找不到', '怎么选', '哪个牌子'],
            'score_rule': 'positive',  # 解决方案越少越高
        },
        'content_gap': {
            'description': '内容缺口',
            'indicators': ['指南', '攻略', '教程', '全面'],
            'score_rule': 'negative',  # 完整内容越多越低
        },
    }

    # 搜索验证已禁用的标志（用于缓存检测结果）
    _search_disabled: Optional[bool] = None

    def __init__(self, max_workers: int = 8, timeout: int = 5):
        """
        Args:
            max_workers: 最大并发搜索数
            timeout: 每次搜索超时时间（秒），默认5秒，超过则自动降级跳过
        """
        self.max_workers = max_workers
        self.timeout = timeout
        self._session_lock = threading.Lock()
        self._session = None

    @classmethod
    def _check_search_available(cls) -> bool:
        """
        检测搜索功能是否可用

        检测逻辑：
        1. 检查环境变量 DISABLE_SEARCH_VERIFICATION
        2. 检查代理是否可用（如果有配置代理）
        3. 检测网络连通性

        Returns:
            bool: 搜索功能是否可用
        """
        if cls._search_disabled is not None:
            return not cls._search_disabled

        # 1. 检查环境变量禁用
        if os.environ.get('DISABLE_SEARCH_VERIFICATION', '').lower() in ('1', 'true', 'yes'):
            logger.info("[BlueOceanSearchVerifier] 搜索验证已被环境变量 DISABLE_SEARCH_VERIFICATION 禁用")
            cls._search_disabled = True
            return False

        # 2. 检查代理连通性（如果配置了代理）
        proxy_host = os.environ.get('https_proxy') or os.environ.get('http_proxy') or os.environ.get('HTTPS_PROXY') or os.environ.get('HTTP_PROXY')
        if proxy_host:
            # 提取代理地址
            proxy_addr = proxy_host.replace('http://', '').replace('https://', '').split(':')[0]
            proxy_port = 7890  # 默认端口
            if ':' in proxy_host.split('://')[-1]:
                try:
                    proxy_port = int(proxy_host.split(':')[-1])
                except ValueError:
                    pass

            if not cls._check_proxy_available(proxy_addr, proxy_port):
                logger.info(f"[BlueOceanSearchVerifier] 代理 {proxy_host} 不可用，跳过搜索验证")
                cls._search_disabled = True
                return False

        cls._search_disabled = False
        return True

    @staticmethod
    def _check_proxy_available(host: str, port: int, timeout: float = 1.0) -> bool:
        """检测代理是否可用"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False

    # =========================================================================
    # 公开接口
    # =========================================================================

    def verify_candidates(
        self,
        candidates: List[CandidateDirection],
        business_info: Dict[str, Any],
    ) -> VerificationResult:
        """
        验证候选方向（主入口）

        Args:
            candidates: LLM Phase 1 输出的候选方向列表
            business_info: 业务信息（包含 business_description, industry 等）

        Returns:
            VerificationResult: 验证结果（含搜索证据和最终置信度）
        """
        if not candidates:
            return VerificationResult(
                success=False,
                error_message="候选方向列表为空"
            )

        # 检测搜索功能是否可用
        if not self._check_search_available():
            logger.info("[BlueOceanSearchVerifier] 搜索功能不可用，跳过验证")
            result.success = True
            result.summary = "搜索验证已跳过（网络/代理不可用），使用默认置信度"
            return result

        logger.info(f"[BlueOceanSearchVerifier] 开始验证 {len(candidates)} 个候选方向")

        result = VerificationResult(candidates=candidates)

        try:
            # Phase 2: 并行搜索验证（timeout 已内置于各引擎）
            self._verify_all_candidates(candidates, business_info)

            # Phase 3: LLM 综合判断（可选，加超时保护，最坏 10 秒）
            try:
                import signal as _signal_module
                _synth_done = False
                _synth_error = [None]

                def _synthesize_with_timeout():
                    nonlocal _synth_done, _synth_error
                    try:
                        self._synthesize_verdicts(candidates, business_info)
                    except Exception as e:
                        _synth_error[0] = e
                    finally:
                        _synth_done = True

                t = threading.Timer(10.0, _synthesize_with_timeout)
                t.start()
                try:
                    while not _synth_done:
                        t.join(timeout=0.5)
                    if _synth_error[0]:
                        raise _synth_error[0]
                finally:
                    if not _synth_done:
                        t.cancel()
                    else:
                        t.join()
            except Exception:
                # LLM 合成失败不影响主流程
                logger.warning("[BlueOceanSearchVerifier] LLM 综合判断超时或不可用，跳过")

            result.success = True
            result.summary = self._generate_summary(candidates)

            logger.info(f"[BlueOceanSearchVerifier] 验证完成: {len(candidates)} 个候选方向")

        except Exception as e:
            logger.error(f"[BlueOceanSearchVerifier] 验证异常: {e}")
            result.success = False
            result.error_message = str(e)

        return result

    # =========================================================================
    # Phase 2: 并行搜索验证
    # =========================================================================

    def _verify_all_candidates(
        self,
        candidates: List[CandidateDirection],
        business_info: Dict[str, Any],
    ):
        """对所有候选方向并行搜索验证"""
        # 准备所有搜索任务（包含候选索引）
        tasks = []
        for idx, candidate in enumerate(candidates):
            tasks.extend(self._prepare_search_tasks(candidate, business_info, idx))

        # 并行执行
        search_results = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {
                executor.submit(self._execute_search, task['query'], task['engine']): task
                for task in tasks
            }

            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    search_result = future.result()
                    key = (task['candidate_idx'], task['dimension'], task['engine'])
                    search_results[key] = search_result
                except Exception as e:
                    logger.warning(f"[BlueOceanSearchVerifier] 搜索失败: {task['query']} - {e}")
                    key = (task['candidate_idx'], task['dimension'], task['engine'])
                    search_results[key] = SearchResult(
                        query=task['query'],
                        search_engine=task['engine'],
                        is_valid=False,
                    )

        # 聚合结果到每个候选方向
        for idx, candidate in enumerate(candidates):
            candidate.verification = self._aggregate_verification(candidate, idx, search_results)

    def _prepare_search_tasks(
        self,
        candidate: CandidateDirection,
        business_info: Dict[str, Any],
        candidate_idx: int,
    ) -> List[Dict]:
        """
        为候选方向准备搜索任务

        Returns:
            List[Dict]: 搜索任务列表，每个任务包含 query, engine, candidate_idx, dimension
        """
        tasks = []
        business_desc = business_info.get('business_description', '')

        # 每个维度的搜索假设
        dimensions = {
            'demand': candidate.search_hypotheses.get('demand', ''),
            'competition': candidate.search_hypotheses.get('competition', ''),
            'scarcity': candidate.search_hypotheses.get('scarcity', ''),
            'content_gap': candidate.search_hypotheses.get('content_gap', ''),
        }

        # 如果 LLM 没有提供搜索假设，自动生成
        if not any(dimensions.values()):
            dimensions = self._generate_search_hypotheses(candidate, business_desc)

        # 每个维度搜多个引擎
        engines = list(self.SEARCH_SOURCES.keys())
        for dimension, query in dimensions.items():
            if not query:
                continue
            for engine in engines:
                tasks.append({
                    'query': query,
                    'engine': engine,
                    'candidate_idx': candidate_idx,
                    'dimension': dimension,
                })

        return tasks

    def _generate_search_hypotheses(
        self,
        candidate: CandidateDirection,
        business_desc: str,
    ) -> Dict[str, str]:
        """自动生成搜索假设（当 LLM 未提供时）"""
        direction = candidate.business_direction
        audience = candidate.target_audience

        return {
            'demand': f"{direction} {audience} 痛点问题",
            'competition': f"{direction} 推荐 哪个牌子好",
            'scarcity': f"{direction} 怎么选 哪里买",
            'content_gap': f"{direction} 喂养指南 攻略",
        }

    def _execute_search(self, query: str, engine: str) -> SearchResult:
        """执行单次搜索"""
        import requests

        result = SearchResult(query=query, search_engine=engine)

        try:
            if engine == 'baidu':
                return self._search_baidu(query)
            elif engine == 'bing':
                return self._search_bing(query)
            elif engine == 'google':
                return self._search_google(query)
            else:
                return self._search_bing(query)  # 默认用 bing

        except Exception as e:
            logger.warning(f"[BlueOceanSearchVerifier] {engine} 搜索失败: {query} - {e}")
            result.is_valid = False
            return result

    def _search_baidu(self, query: str) -> SearchResult:
        """百度搜索"""
        import requests

        result = SearchResult(query=query, search_engine='baidu')

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9',
            }

            params = {'wd': query, 'rn': 10}
            response = requests.get(
                'https://www.baidu.com/s',
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
            response.encoding = 'utf-8'

            # 估算结果数量
            text = response.text
            result.result_count = self._estimate_baidu_count(text)

            # 提取前几条结果摘要
            result.top_results = self._extract_baidu_snippets(text)
            result.content_summary = ' '.join([r.get('title', '') + r.get('abstract', '') for r in result.top_results[:5]])

        except Exception as e:
            logger.warning(f"[BlueOceanSearchVerifier] 百度搜索失败: {e}")
            result.is_valid = False

        return result

    def _search_bing(self, query: str) -> SearchResult:
        """Bing 搜索"""
        import requests

        result = SearchResult(query=query, search_engine='bing')

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }

            params = {'q': query, 'count': 10}
            response = requests.get(
                'https://cn.bing.com/search',
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
            response.encoding = 'utf-8'

            text = response.text
            result.result_count = self._estimate_bing_count(text)
            result.top_results = self._extract_bing_snippets(text)
            result.content_summary = ' '.join([r.get('title', '') + r.get('abstract', '') for r in result.top_results[:5]])

        except Exception as e:
            logger.warning(f"[BlueOceanSearchVerifier] Bing 搜索失败: {e}")
            result.is_valid = False

        return result

    def _search_google(self, query: str) -> SearchResult:
        """Google 搜索（可能需要代理）"""
        import requests

        result = SearchResult(query=query, search_engine='google')

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }

            params = {'q': query, 'num': 10}
            response = requests.get(
                'https://www.google.com/search',
                params=params,
                headers=headers,
                timeout=self.timeout,
            )

            text = response.text
            result.result_count = self._estimate_google_count(text)
            result.top_results = self._extract_google_snippets(text)
            result.content_summary = ' '.join([r.get('title', '') + r.get('abstract', '') for r in result.top_results[:5]])

        except Exception as e:
            logger.warning(f"[BlueOceanSearchVerifier] Google 搜索失败: {e}")
            result.is_valid = False

        return result

    # =========================================================================
    # 搜索结果提取
    # =========================================================================

    def _estimate_baidu_count(self, text: str) -> int:
        """从百度搜索页面估算结果数量"""
        import re
        # 百度结果数量格式：约 xxx,xxx 个结果
        match = re.search(r'约([\d,]+)', text)
        if match:
            return int(match.group(1).replace(',', ''))
        # 备选：数一下结果条目
        matches = re.findall(r'<h3 class="t">', text)
        return len(matches) * 10  # 粗略估算

    def _estimate_bing_count(self, text: str) -> int:
        """从 Bing 搜索页面估算结果数量"""
        import re
        # Bing 结果数量格式：xxx,xxx 结果
        match = re.search(r'([\d,]+)\s*个结果', text)
        if match:
            return int(match.group(1).replace(',', ''))
        matches = re.findall(r'<li class="b_algo"', text)
        return len(matches) * 10

    def _estimate_google_count(self, text: str) -> int:
        """从 Google 搜索页面估算结果数量"""
        import re
        match = re.search(r'([\d,]+)\s*(?:results|条)', text, re.IGNORECASE)
        if match:
            return int(match.group(1).replace(',', ''))
        matches = re.findall(r'<h3 class="LC20lb"', text)
        return len(matches) * 10

    def _extract_baidu_snippets(self, text: str) -> List[Dict]:
        """提取百度搜索结果摘要"""
        import re

        results = []
        # 提取标题和摘要
        pattern = r'<h3 class="t">.*?<a[^>]*>(.*?)</a>.*?<div class="c-abstract"[^>]*>(.*?)</div>'
        matches = re.findall(pattern, text, re.DOTALL)

        for title_raw, abstract_raw in matches[:10]:
            # 清理 HTML 标签
            title = re.sub(r'<[^>]+>', '', title_raw).strip()
            abstract = re.sub(r'<[^>]+>', '', abstract_raw).strip()
            if title:
                results.append({'title': title, 'abstract': abstract})

        return results

    def _extract_bing_snippets(self, text: str) -> List[Dict]:
        """提取 Bing 搜索结果摘要"""
        import re

        results = []
        # 提取标题和摘要
        pattern = r'<li class="b_algo".*?<h2>(.*?)</h2>.*?<p>(.*?)</p>'
        matches = re.findall(pattern, text, re.DOTALL)

        for title_raw, abstract_raw in matches[:10]:
            title = re.sub(r'<[^>]+>', '', title_raw).strip()
            abstract = re.sub(r'<[^>]+>', '', abstract_raw).strip()
            if title:
                results.append({'title': title, 'abstract': abstract})

        return results

    def _extract_google_snippets(self, text: str) -> List[Dict]:
        """提取 Google 搜索结果摘要"""
        import re

        results = []
        # 提取标题和摘要
        pattern = r'<h3 class="zBAu7l">(.*?)</h3>.*?<span class="aCOpRe">(.*?)</span>'
        matches = re.findall(pattern, text, re.DOTALL)

        for title_raw, abstract_raw in matches[:10]:
            title = re.sub(r'<[^>]+>', '', title_raw).strip()
            abstract = re.sub(r'<[^>]+>', '', abstract_raw).strip()
            if title:
                results.append({'title': title, 'abstract': abstract})

        # 备选模式
        if not results:
            pattern = r'<h3 class="zBAu7l">(.*?)</h3>'
            matches = re.findall(pattern, text, re.DOTALL)
            for title_raw in matches[:10]:
                title = re.sub(r'<[^>]+>', '', title_raw).strip()
                if title:
                    results.append({'title': title, 'abstract': ''})

        return results

    # =========================================================================
    # 验证数据聚合
    # =========================================================================

    def _aggregate_verification(
        self,
        candidate: CandidateDirection,
        candidate_idx: int,
        search_results: Dict,
    ) -> VerificationData:
        """聚合搜索结果为验证数据"""
        verification = VerificationData()

        # 收集各维度的结果
        dimension_results = {dim: [] for dim in self.VERIFICATION_DIMENSIONS.keys()}

        for (idx, dimension, engine), result in search_results.items():
            if idx == candidate_idx and result.is_valid:
                dimension_results[dimension].append(result)

        # 计算各维度评分
        demand_results = dimension_results.get('demand', [])
        verification.demand_score = self._score_demand(demand_results)
        verification.demand_evidence = self._extract_evidence(demand_results, 'demand')

        competition_results = dimension_results.get('competition', [])
        verification.competition_score = self._score_competition(competition_results)
        verification.competition_evidence = self._extract_evidence(competition_results, 'competition')

        scarcity_results = dimension_results.get('scarcity', [])
        verification.scarcity_score = self._score_scarcity(scarcity_results, competition_results)
        verification.scarcity_evidence = self._extract_evidence(scarcity_results, 'scarcity')

        content_gap_results = dimension_results.get('content_gap', [])
        verification.content_gap_score = self._score_content_gap(content_gap_results)
        verification.content_gap_evidence = self._extract_evidence(content_gap_results, 'content_gap')

        # 综合评分：需求强 × 竞争弱 × 方案少 × 内容缺口大
        verification.overall_score = (
            verification.demand_score * 0.3 +
            (1 - verification.competition_score) * 0.3 +
            verification.scarcity_score * 0.2 +
            verification.content_gap_score * 0.2
        )

        return verification

    def _score_demand(self, results: List[SearchResult]) -> float:
        """
        需求真实性评分

        逻辑：结果数量越多/讨论越热 → 需求越真实
        """
        if not results:
            return 0.3  # 无数据，保守估计

        total_count = sum(r.result_count for r in results)
        total_results = sum(len(r.top_results) for r in results)

        # 归一化：假设 1000+ 结果为满分
        count_score = min(total_count / 1000, 1.0) * 0.5
        result_score = min(total_results / 30, 1.0) * 0.3

        # 检查内容中是否包含需求指示词
        demand_indicators = ['怎么办', '怎么解决', '为什么', '为什么宝宝', '急']
        indicator_score = 0.0
        for r in results:
            text = r.content_summary.lower()
            for indicator in demand_indicators:
                if indicator in text:
                    indicator_score += 0.05
        indicator_score = min(indicator_score, 0.2)

        return min(count_score + result_score + indicator_score, 1.0)

    def _score_competition(self, results: List[SearchResult]) -> float:
        """
        竞争强度评分

        逻辑：结果数量越多/前排内容越专业 → 竞争越激烈
        """
        if not results:
            return 0.5  # 无数据，中等竞争

        total_count = sum(r.result_count for r in results)
        total_results = sum(len(r.top_results) for r in results)

        # 归一化
        count_score = min(total_count / 500, 1.0) * 0.4
        result_score = min(total_results / 30, 1.0) * 0.3

        # 检查内容中是否有品牌/产品推荐（竞争激烈的信号）
        competition_indicators = ['推荐', '哪个好', '测评', '排行', '对比']
        indicator_score = 0.0
        for r in results:
            text = r.content_summary.lower()
            for indicator in competition_indicators:
                if indicator in text:
                    indicator_score += 0.05
        indicator_score = min(indicator_score, 0.3)

        return min(count_score + result_score + indicator_score, 1.0)

    def _score_scarcity(self, scarcity_results: List[SearchResult], competition_results: List[SearchResult]) -> float:
        """
        解决方案稀缺度评分

        逻辑：解决方案相关内容越少 → 越稀缺
        """
        if not scarcity_results:
            return 0.5  # 无数据，中等

        total_count = sum(r.result_count for r in scarcity_results)
        total_results = sum(len(r.top_results) for r in scarcity_results)

        # 稀缺度 = 1 - (结果数量 / 基准线)
        count_score = max(0, 1 - total_count / 200) * 0.5
        result_score = max(0, 1 - total_results / 20) * 0.3

        # 稀缺信号词：找不到、没有、怎么选
        scarcity_signals = ['找不到', '没有', '怎么选', '哪种', '怎么判断']
        signal_score = 0.0
        for r in scarcity_results:
            text = r.content_summary.lower()
            for signal in scarcity_signals:
                if signal in text:
                    signal_score += 0.1
        signal_score = min(signal_score, 0.2)

        return min(count_score + result_score + signal_score, 1.0)

    def _score_content_gap(self, results: List[SearchResult]) -> float:
        """
        内容缺口评分

        逻辑：系统性内容（指南/攻略/教程）越少 → 缺口越大
        """
        if not results:
            return 0.5  # 无数据，中等

        total_count = sum(r.result_count for r in results)

        # 归一化
        count_score = max(0, 1 - total_count / 300) * 0.5

        # 检查是否有系统性内容
        content_indicators = ['指南', '攻略', '教程', '全面', '完整', '一文']
        content_score = 0.0
        for r in results:
            text = r.content_summary.lower()
            for indicator in content_indicators:
                if indicator in text:
                    content_score += 0.1
        content_score = min(content_score, 0.5)

        return min(count_score + content_score, 1.0)

    def _extract_evidence(self, results: List[SearchResult], dimension: str) -> List[str]:
        """从搜索结果中提取证据"""
        evidence = []

        for r in results:
            if not r.is_valid:
                continue

            # 取前几条结果的标题作为证据
            for result in r.top_results[:3]:
                title = result.get('title', '')
                if title and len(title) > 5:
                    evidence.append(title)

        return evidence[:5]  # 最多5条

    # =========================================================================
    # Phase 3: LLM 综合判断
    # =========================================================================

    def _synthesize_verdicts(
        self,
        candidates: List[CandidateDirection],
        business_info: Dict[str, Any],
    ):
        """LLM 综合判断（生成最终结论）"""
        try:
            from services.llm import get_llm_service
            llm = get_llm_service()

            # 构建上下文
            context = self._build_synthesis_context(candidates, business_info)

            # 构建 Prompt
            prompt = self._build_synthesis_prompt(context)

            # 调用 LLM
            response = llm.chat([{"role": "user", "content": prompt}])

            if not response:
                logger.warning("[BlueOceanSearchVerifier] LLM 综合判断失败，使用默认结论")
                self._apply_default_verdicts(candidates)
                return

            # 解析 LLM 响应
            self._parse_synthesis_response(response, candidates)

        except Exception as e:
            logger.warning(f"[BlueOceanSearchVerifier] 综合判断异常: {e}，使用默认结论")
            self._apply_default_verdicts(candidates)

    def _build_synthesis_context(
        self,
        candidates: List[CandidateDirection],
        business_info: Dict[str, Any],
    ) -> str:
        """构建综合判断上下文"""
        lines = [f"# 业务信息\n业务描述：{business_info.get('business_description', '')}"]
        lines.append(f"行业：{business_info.get('industry', '')}\n")

        lines.append("# 候选方向及搜索验证结果\n")

        for i, c in enumerate(candidates):
            lines.append(f"## 方向 {i+1}: {c.opportunity_name}")
            lines.append(f"- 业务方向：{c.business_direction}")
            lines.append(f"- 目标人群：{c.target_audience}")
            lines.append(f"- 痛点：{', '.join(c.pain_points[:3])}")

            if c.verification:
                v = c.verification
                lines.append(f"- 需求真实性：{v.demand_score:.2f}（证据：{', '.join(v.demand_evidence[:2])}）")
                lines.append(f"- 竞争强度：{v.competition_score:.2f}（证据：{', '.join(v.competition_evidence[:2])}）")
                lines.append(f"- 解决方案稀缺度：{v.scarcity_score:.2f}（证据：{', '.join(v.scarcity_evidence[:2])}）")
                lines.append(f"- 内容缺口：{v.content_gap_score:.2f}")
                lines.append(f"- **综合蓝海指数：{v.overall_score:.2f}**")
            lines.append("")

        return '\n'.join(lines)

    def _build_synthesis_prompt(self, context: str) -> str:
        """构建综合判断 Prompt"""
        return f"""你是市场蓝海分析专家。请根据以下搜索验证数据，对每个候选方向给出最终判断。

{context}

=== 任务 ===
请对每个候选方向输出 JSON 格式的综合判断：

{{
    "verdicts": [
        {{
            "direction_index": 0,  // 0-based 索引
            "final_verdict": "综合判断结论（1-2句话）",
            "final_confidence": 0.75,  // 最终置信度 0-1
            "search_evidence": ["证据1", "证据2"]  // 搜索证据摘要
        }}
    ],
    "summary": "整体总结（2-3句话）"
}}

注意：
1. 综合评分（蓝海指数）高的方向，置信度应该更高
2. 如果搜索发现某个方向竞争激烈但需求真实，可以调整为"红海中的细分蓝海"
3. 证据要从搜索结果中提取，不要编造
4. 只输出 JSON，不要有其他内容
"""

    def _parse_synthesis_response(self, response: str, candidates: List[CandidateDirection]):
        """解析 LLM 综合判断响应"""
        import json
        import re

        # 尝试提取 JSON
        match = re.search(r'\{[\s\S]*\}', response)
        if not match:
            logger.warning("[BlueOceanSearchVerifier] 无法解析 LLM 响应，使用默认结论")
            self._apply_default_verdicts(candidates)
            return

        try:
            data = json.loads(match.group())
            verdicts = data.get('verdicts', [])

            for verdict in verdicts:
                idx = verdict.get('direction_index', -1)
                if 0 <= idx < len(candidates):
                    candidates[idx].final_verdict = verdict.get('final_verdict', '')
                    candidates[idx].final_confidence = verdict.get('final_confidence', candidates[idx].verification.overall_score if candidates[idx].verification else 0.5)
                    candidates[idx].search_evidence = verdict.get('search_evidence', [])

            # 处理未覆盖的方向
            covered_indices = {v.get('direction_index', -1) for v in verdicts}
            for i, c in enumerate(candidates):
                if i not in covered_indices:
                    if c.verification:
                        c.final_confidence = c.verification.overall_score
                        c.final_verdict = "搜索数据不足以给出精确判断"
                        c.search_evidence = []

        except json.JSONDecodeError as e:
            logger.warning(f"[BlueOceanSearchVerifier] JSON 解析失败: {e}")
            self._apply_default_verdicts(candidates)

    def _apply_default_verdicts(self, candidates: List[CandidateDirection]):
        """应用默认结论（当 LLM 判断失败时）"""
        for c in candidates:
            if c.verification:
                c.final_confidence = c.verification.overall_score
                c.final_verdict = f"基于搜索数据综合判断，蓝海指数 {c.verification.overall_score:.2f}"
                c.search_evidence = (
                    c.verification.demand_evidence[:2] +
                    c.verification.competition_evidence[:2]
                )

    def _generate_summary(self, candidates: List[CandidateDirection]) -> str:
        """生成验证总结"""
        if not candidates:
            return "无候选方向"

        # 按置信度排序
        sorted_candidates = sorted(
            candidates,
            key=lambda c: c.final_confidence if c.final_confidence else (c.verification.overall_score if c.verification else 0),
            reverse=True
        )

        top = sorted_candidates[0]
        top_score = top.final_confidence if top.final_confidence else (top.verification.overall_score if top.verification else 0)

        return f"验证了 {len(candidates)} 个候选方向，最优方向为「{top.opportunity_name}」（蓝海指数 {top_score:.2f}），建议优先考虑置信度 > 0.5 的方向。"

    # =========================================================================
    # 工具方法
    # =========================================================================

    def to_dict(self, result: VerificationResult) -> Dict[str, Any]:
        """转换为字典格式（用于 API 响应）"""
        return {
            'success': result.success,
            'error_message': result.error_message,
            'summary': result.summary,
            'candidates': [
                {
                    'opportunity_name': c.opportunity_name,
                    'business_direction': c.business_direction,
                    'target_audience': c.target_audience,
                    'pain_points': c.pain_points,
                    'keywords': c.keywords,
                    'content_direction': c.content_direction,
                    'confidence': c.final_confidence if c.final_confidence else (c.verification.overall_score if c.verification else c.confidence),
                    'final_verdict': c.final_verdict,
                    'search_evidence': c.search_evidence,
                    'verification_data': {
                        'demand_score': c.verification.demand_score if c.verification else 0,
                        'competition_score': c.verification.competition_score if c.verification else 0,
                        'scarcity_score': c.verification.scarcity_score if c.verification else 0,
                        'content_gap_score': c.verification.content_gap_score if c.verification else 0,
                        'overall_score': c.verification.overall_score if c.verification else 0,
                        'demand_evidence': c.verification.demand_evidence if c.verification else [],
                        'competition_evidence': c.verification.competition_evidence if c.verification else [],
                        'scarcity_evidence': c.verification.scarcity_evidence if c.verification else [],
                    } if c.verification else None,
                }
                for c in result.candidates
            ]
        }
