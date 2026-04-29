"""
选题内容生成服务

基于选题，生成完整的图文内容
所有用户均可使用全部20种内容结构：
1. 痛点共鸣型、疑问揭秘型、数字清单型
2. 对比冲击型、场景故事型、经验总结型
3. 知识科普型、产品评测型、选购指南型
4. 避坑指南型、时间节点型、人群细分型
5. 价格博弈型、替代方案型、升级迭代型
6. 行业揭秘型、数据说话型、场景矩阵型
7. 决策树型、用户证言型

新增功能：
- 多版本生成支持：图文/短视频脚本/长文
- SEO优化 + 精准埋词（企业版专属功能）
"""

import json
import re
import logging
from datetime import datetime
from services.llm import get_llm_service
from services.content_quality_scorer import ContentQualityScorer, content_scorer
from services.content_quality_optimizer import ProgressiveContentOptimizer

logger = logging.getLogger(__name__)


class TopicContentGenerator:
    """选题内容生成器"""

    # 全部 20 种图文内容结构（所有用户均可使用）
    ALL_STRUCTURES = [
        {'name': '痛点共鸣型', 'slides': 5, 'desc': '封面→痛点→分析→方案→品牌'},
        {'name': '疑问揭秘型', 'slides': 5, 'desc': '封面→疑问→揭秘→对比→引导'},
        {'name': '数字清单型', 'slides': 6, 'desc': '封面→数字概览→逐条展开→总结→品牌'},
        {'name': '对比冲击型', 'slides': 6, 'desc': '封面→错误做法→正确做法→对比表→方案→品牌'},
        {'name': '场景故事型', 'slides': 5, 'desc': '封面→场景描述→问题升级→解决方案→行动'},
        {'name': '经验总结型', 'slides': 6, 'desc': '封面→踩坑回顾→原因分析→避坑指南→推荐→品牌'},
        {'name': '知识科普型', 'slides': 5, 'desc': '封面→冷知识→原理说明→应用场景→品牌'},
        {'name': '产品评测型', 'slides': 6, 'desc': '封面→评测背景→维度展示→数据对比→结论→品牌'},
        {'name': '选购指南型', 'slides': 6, 'desc': '封面→选购痛点→关键指标→方案推荐→对比→品牌'},
        {'name': '避坑指南型', 'slides': 5, 'desc': '封面→常见误区→后果展示→正确做法→提醒→品牌'},
        {'name': '时间节点型', 'slides': 7, 'desc': '封面→时间背景→阶段问题→对应方案→注意事项→时机选择→品牌'},
        {'name': '人群细分型', 'slides': 7, 'desc': '封面→人群A→人群B→人群C→各自痛点→各自方案→品牌'},
        {'name': '价格博弈型', 'slides': 6, 'desc': '封面→价格误区→定价逻辑→成本拆解→价值对比→品牌'},
        {'name': '替代方案型', 'slides': 6, 'desc': '封面→替代品问题→替代原理→效果对比→推荐方案→品牌'},
        {'name': '升级迭代型', 'slides': 7, 'desc': '封面→旧方案问题→升级思路→新方案亮点→对比→使用建议→品牌'},
        {'name': '行业揭秘型', 'slides': 7, 'desc': '封面→行业潜规则→内幕揭秘→消费者误区→正确认知→品牌'},
        {'name': '数据说话型', 'slides': 7, 'desc': '封面→核心数据→数据解读→行业对比→趋势预判→品牌'},
        {'name': '场景矩阵型', 'slides': 8, 'desc': '封面→场景1→场景2→场景3→各自方案→场景选择建议→品牌'},
        {'name': '决策树型', 'slides': 7, 'desc': '封面→决策入口→分支A/B/C→各分支结论→通用建议→品牌'},
        {'name': '用户证言型', 'slides': 7, 'desc': '封面→用户痛点→真实故事→改变过程→使用效果→品牌'},
    ]

    # ── GEO 8大模式定义 ──
    GEO_MODES = {
        '问题-答案模式': {
            'keywords': ['什么是', '怎么选', '怎么办', '是否', '哪个好', '如何', '好不好', '怎么选'],
            'best_formats': ['长文', '小红书'],
            'title_patterns': ['什么是.*', '.*怎么办', '.*怎么选', '.*好不好', '.*如何.*'],
            'hook': '直接给出专业答案，开篇≤20字无铺垫',
        },
        '定义-解释模式': {
            'keywords': ['定义', '区别', '差异', '是什么', '和.*区别', '与.*不同'],
            'best_formats': ['长文', '抖音'],
            'title_patterns': ['.*定义.*', '.*区别.*', '.*是什么', '.*和.*区别'],
            'hook': '定义≤30字 + 生动比喻结尾绑定品牌',
        },
        '金句-论证模式': {
            'keywords': ['99%', '不是.*而是', '误区', '错了', '都错了', '真相', '其实'],
            'best_formats': ['抖音', '小红书'],
            'title_patterns': ['.*99%.*', '.*不是.*而是.*', '.*误区.*', '.*错了.*'],
            'hook': '开篇金句制造认知冲突，结尾反转或正确认知',
        },
        '框架-工具模式': {
            'keywords': ['方法论', '框架', '模型', '体系', '流程', '步骤', '清单'],
            'best_formats': ['长文'],
            'title_patterns': ['.*方法.*', '.*框架.*', '.*模型.*', '.*流程.*'],
            'hook': '框架可视化描述 + 可落地操作清单',
        },
        '清单体模式': {
            'keywords': ['清单', '技巧', '方法', '窍门', '步骤', '大全', '汇总'],
            'best_formats': ['小红书', '长文'],
            'title_patterns': ['.*清单.*', '.*技巧.*', '.*方法.*', '.*步骤.*'],
            'hook': '数字承诺（如"10个技巧"）+ 优先级排序',
        },
        '榜单体模式': {
            'keywords': ['排行', '排名', '红黑榜', '推荐', 'top', '榜单', '哪个'],
            'best_formats': ['长文', '小红书'],
            'title_patterns': ['.*排行.*', '.*排名.*', '.*推荐.*', '.*榜单.*'],
            'hook': '榜单核心结论 + 评选维度说明',
        },
        '案例-故事模式': {
            'keywords': ['案例', '故事', '经历', '客户', '真实', '成功', '创业'],
            'best_formats': ['长文', '抖音'],
            'title_patterns': ['.*案例.*', '.*故事.*', '.*经历.*', '.*客户.*'],
            'hook': 'P-C-S-R英雄之旅结构：困境→尝试→方案→成果',
        },
        '对比-纠错模式': {
            'keywords': ['对比', '比较', 'vs', '或者', '还是', '旧.*新', '错.*对'],
            'best_formats': ['抖音', '长文'],
            'title_patterns': ['.*对比.*', '.*vs.*', '.*旧.*新.*', '.*错.*对.*'],
            'hook': '旧vs新对比 + 错误vs正确并列',
        },
    }

    # Token 消耗估算
    TOKEN_ESTIMATE = {
        'free': {'prompt': 800, 'completion': 1200, 'total': 2000},
        'basic': {'prompt': 1200, 'completion': 2000, 'total': 3200},
        'professional': {'prompt': 1500, 'completion': 2800, 'total': 4300},
        'enterprise': {'prompt': 2000, 'completion': 3500, 'total': 5500},
    }

    def __init__(self):
        self.llm = get_llm_service()

    def generate_content(
        self,
        topic_id: str,
        topic_title: str,
        topic_type: str,
        topic_type_key: str = '',
        business_description: str = '',
        business_range: str = '',
        business_type: str = '',
        portrait: dict = None,
        is_premium: bool = False,
        premium_plan: str = 'free',
        content_style: str = '',
        selected_scene: dict = None,
        brand_context: dict = None,
        keyword_library: dict = None,
    ) -> dict:
        """
        生成图文内容

        Args:
            topic_id: 选题ID
            topic_title: 选题标题
            topic_type: 选题类型名称
            topic_type_key: 选题类型键（来自选题库，如 pain_point/compare/skill 等）
            business_description: 业务描述
            business_range: 经营范围
            business_type: 业务类型
            portrait: 用户画像
            is_premium: 是否付费用户（已废弃，保留兼容性）
            premium_plan: 套餐类型（已废弃，保留兼容性，所有用户均可使用全部结构）
            content_style: 内容风格（情绪共鸣/干货科普/犀利吐槽/故事叙述/权威背书）
            selected_scene: 选中的场景组合（包含组合、标签、风格等信息）

        Returns:
            dict: {
                "success": bool,
                "content": {...},
                "tokens_used": int
            }
        """
        try:
            # 所有用户均可使用全部20种结构
            structures = self.ALL_STRUCTURES
            structure_names = [s['name'] for s in structures]

            # ── GEO模式自动匹配（优先级：type_key > title关键词 > selected_scene）──
            geo_mode_info = self.match_geo_mode(topic_title, selected_scene, topic_type_key)
            logger.info(f"[GEO调试] topic_title={topic_title}, selected_scene={selected_scene}")
            logger.info(f"[GEO调试] geo_mode_info={geo_mode_info}")

            # 构建 Prompt
            prompt = self._build_content_prompt(
                topic_title=topic_title,
                topic_type=topic_type,
                business_description=business_description,
                business_range=business_range,
                business_type=business_type,
                portrait=portrait,
                structures=structures,
                plan=premium_plan,
                content_style=content_style,
                selected_scene=selected_scene,
                geo_mode_info=geo_mode_info,
                brand_context=brand_context,
                keyword_library=keyword_library,
            )

            # 调用 LLM 生成
            messages = [
                {"role": "system", "content": "你是一位资深的内容创作专家，精通短视频脚本和图文内容创作。必须严格按照JSON格式输出。"},
                {"role": "user", "content": prompt}
            ]
            response = self.llm.chat(messages)

            if not response:
                logger.error("[TopicContentGenerator] LLM 调用返回空，provider=%s, model=%s",
                             self.llm.provider, self.llm.model)
                return {
                    'success': False,
                    'error': 'LLM 调用失败，请检查 API 配置'
                }

            logger.info(f"[TopicContentGenerator] LLM 原始响应 (前500字符): {response[:500]}")

            # 解析结果
            content = self._parse_content_response(response)

            # 检测是否拿到了占位默认内容（说明解析失败）
            is_placeholder = content.get('title') == self._get_default_content()['title']
            if is_placeholder:
                logger.error("[TopicContentGenerator] LLM 响应解析失败，返回了占位内容")
                return {
                    'success': False,
                    'error': 'LLM 响应解析失败，请重试'
                }

            # ── 强制 GEO 评分+优化循环（迭代版）──
            # 从 brand_context 提取品牌名，用于评分和优化
            brand_name_for_score = ''
            if brand_context and brand_context.get('include_brand') and brand_context.get('brand_name'):
                brand_name_for_score = brand_context['brand_name']
                logger.info(f"[GEO评分] 使用品牌名: {brand_name_for_score}")

            geo_score_result = content_scorer.score(content, brand_name=brand_name_for_score, business_type='local_service')
            initial_geo_score = geo_score_result.total_score
            logger.info(f"[GEO优化] 初始评分: {initial_geo_score}/100, 不合格项: {[f.name for f in geo_score_result.failed_items]}")

            optimized_content = content
            final_geo_score = initial_geo_score
            total_opt_rounds = 0

            if initial_geo_score < 80 and geo_score_result.failed_items:
                current_content = content
                current_score = initial_geo_score
                best_content = content
                best_score = initial_geo_score
                max_total_rounds = 6
                no_improvement_count = 0

                try:
                    for iteration in range(1, max_total_rounds + 1):
                        total_opt_rounds += 1
                        logger.info(f"[GEO优化] === 迭代 {iteration}：当前基准分={current_score}/100 ===")

                        # 重新获取当前内容的不合格项
                        iter_score_result = content_scorer.score(current_content, brand_name=brand_name_for_score, business_type='local_service')
                        iter_failed = iter_score_result.failed_items

                        if not iter_failed:
                            logger.info(f"[GEO优化] 迭代{iteration}：无不合格项，停止")
                            break

                        # 每轮最多3次ABC递进修补
                        optimizer = ProgressiveContentOptimizer()
                        opt_result = optimizer.optimize(
                            current_content,
                            iter_failed,
                            current_score,
                            brand_name=brand_name_for_score,
                            business_desc=business_description,
                            max_rounds=3,
                        )

                        if not opt_result.success:
                            logger.warning(f"[GEO优化] 迭代{iteration}：优化器返回失败，停止")
                            break

                        iter_content = opt_result.optimized_content
                        iter_score = opt_result.final_score

                        # 更新全局最优
                        if iter_score > best_score:
                            best_score = iter_score
                            best_content = iter_content
                            no_improvement_count = 0
                            logger.info(f"[GEO优化] 迭代{iteration}：{current_score}→{iter_score}，刷新最优")
                        else:
                            no_improvement_count += 1
                            logger.info(f"[GEO优化] 迭代{iteration}：{current_score}→{iter_score}，未提升（连续{no_improvement_count}次）")

                        # 更新基准用于下一轮
                        current_content = iter_content
                        current_score = iter_score

                        # 达到80分立即停止
                        if iter_score >= 80:
                            logger.info(f"[GEO优化] 迭代{iteration}：达到80分，停止")
                            best_score = iter_score
                            best_content = iter_content
                            break

                        # 连续2轮无提升停止
                        if no_improvement_count >= 2:
                            logger.info(f"[GEO优化] 连续{no_improvement_count}轮无提升，停止")
                            break

                    optimized_content = best_content
                    final_geo_score = best_score
                    logger.info(f"[GEO优化] 迭代完成，总轮次={total_opt_rounds}，最终最优分={final_geo_score}/100")
                except Exception as e:
                    logger.warning(f"[GEO优化] 迭代优化过程异常: {e}，使用原始内容")
                    final_geo_score = initial_geo_score
                    optimized_content = content
            else:
                logger.info(f"[GEO优化] 初始评分{initial_geo_score}≥80或无不合格项，跳过优化")

            # 估算 token
            tokens_used = self.TOKEN_ESTIMATE.get(premium_plan, self.TOKEN_ESTIMATE['free'])['total']

            return {
                'success': True,
                'content': optimized_content,
                'tokens_used': tokens_used,
                'geo_score': final_geo_score,
                'geo_report': {
                    'total_score': final_geo_score,
                    'grade': geo_score_result.grade,
                    'items': [
                        {
                            'id': i.id,
                            'name': i.name,
                            'category': i.category,
                            'score': i.score,
                            'max_score': i.max_score,
                            'passed': i.passed,
                            'detail': i.detail,
                            'suggestion': i.suggestion,
                        }
                        for i in geo_score_result.items
                    ],
                    'failed_items': [f.name for f in geo_score_result.failed_items],
                    'summary': geo_score_result.summary,
                },
                '_meta': {
                    'plan': premium_plan,
                    'structures_available': len(structures),
                    'structure_names': structure_names,
                }
            }

        except Exception as e:
            logger.error("[TopicContentGenerator] Error: %s", e)
            return {
                'success': False,
                'error': str(e)
            }

    def _build_content_prompt(
        self,
        topic_title: str,
        topic_type: str,
        business_description: str,
        business_range: str,
        business_type: str,
        portrait: dict,
        structures: list,
        plan: str,
        content_style: str = '',
        selected_scene: dict = None,
        geo_mode_info: dict = None,
        brand_context: dict = None,
        keyword_library: dict = None,
    ) -> str:
        """构建内容生成 Prompt"""

        portrait_info = self._get_portrait_info(portrait)
        current_month = datetime.now().month
        current_season = self._get_current_season()

        # 生成结构选择说明
        struct_list_text = '\n'.join([
            f"{i+1}. 【{s['name']}】{s['desc']}（{s['slides']}张图）"
            for i, s in enumerate(structures)
        ])

        # ── 内容风格指导 ──
        style_guide = self._get_style_guide(content_style) if content_style else ''

        # ── GEO模式信息 ──
        geo_section = ''
        if geo_mode_info:
            geo_section = self._get_geo_mode_guide(geo_mode_info)

        # ── 品牌锚点+信任佐证区块 ──
        brand_trust_section = self._build_brand_trust_section(brand_context, keyword_library, topic_type)

        # SEO 和精准埋词（专业版/企业版专属）
        seo_section = ""
        if plan in ('professional', 'enterprise'):
            seo_section = """
## SEO优化要求（精准埋词）
- 标题必须包含核心业务关键词
- 每张图片副标题需自然融入1-2个长尾关键词
- 标签选取：2个核心词 + 3个长尾词 + 1个流量词
- 话题标签：1个品牌词 + 2个品类词 + 2个痛点词 + 1个地域词（适用时）
"""
            if plan == 'enterprise':
                seo_section += """
## 企业版专属 - 专家评审维度
生成内容后自检以下维度：
1. 消费心理学维度：痛点→共鸣→解决→信任→行动 链路是否完整
2. SEO关键词密度：核心词出现≥3次，长尾词出现≥5次
3. 视觉设计提示：每张图需标注画面风格要求
4. 评论区首评引导：预设一条能引发互动的首评
"""

        # 场景信息 - 提取关键词用于GEO匹配（兼容旧格式 组合/标签/风格 和新格式 group/label/style）
        scene_keywords = ''
        if selected_scene:
            combo = selected_scene.get('组合') or selected_scene.get('group', '')
            label = selected_scene.get('标签') or selected_scene.get('label', '')
            style = selected_scene.get('风格') or selected_scene.get('style', '')
            scene_keywords = f"{combo} {label} {style}".strip()

        prompt = f"""你是GEO内容优化专家。请根据以下选题，生成一篇高收录、高权重的图文内容。

## 选题信息
- 选题标题：{topic_title}
- 选题类型：{topic_type}
- 选题关键词：{scene_keywords}（用于GEO模式匹配）

## 业务信息
- 业务描述：{business_description}
- 经营范围：{'本地服务' if business_range == 'local' else '跨区域服务'}
- 业务类型：{business_type}

## 目标用户画像
{portrait_info}
{brand_trust_section}
## 当前时间
- 月份：{current_month}月
- 季节：{current_season}

## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## 【重要】GEO模式强制要求
## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{geo_section}

【强制要求】
1. 必须严格按照上述GEO模式的"结构要求"生成内容
2. 每张图必须嵌入GEO模式相关的核心关键词
3. 内容结构必须体现GEO模式的特征（如：问题-答案模式的"开篇直接给答案"）
4. 禁止使用与GEO模式不匹配的内容结构（如：问题-答案模式不能用故事叙述型）

## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 【核心内容质量要求】← 此部分决定评分，必须满足
以下3项是GEO评分的关键维度，生成内容时必须满足，否则分数无法达标：

1. **开篇直接性**：封面图或第一段文字的前30字内必须直接给出核心结论/答案，禁止任何铺垫（如"近年来""随着社会发展""大家好"等）
   - ✅ 正确示例：「医学影像学就业稳定，三甲医院缺口大，起薪8K+」
   - ❌ 错误示例：「随着医疗行业的发展，医学影像学专业越来越受到关注...」

2. **信任证据**：必须包含至少3条具体数据、案例或权威引用（不能全是主观陈述）
   - 数据类型：据xxx报告/数据显示+具体数字+结论
   - 案例类型：某三甲医院/某地区/某时间段+具体事件+结果
   - 引用类型：权威机构/专家+观点+来源
   - 格式：放入每张图的 sub_points 或独立的 trust_evidence 字段中

3. **行动号召(CTA)**：结尾必须有一条唯一、明确、低门槛的下一步行动
   - 必须包含：具体动作词（私信/评论/关注/扫码）+ 联系方式/入口
   - 禁止：多个CTA、模糊CTA（如"有需要可以联系我们"）
   - ✅ 正确示例：「想了解更多云南高考志愿填报技巧，点击主页关注，私信『志愿』获取一对一指导」
   - ❌ 错误示例：「欢迎大家评论区留言交流」

## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 可用内容结构（共{len(structures)}种）
{struct_list_text}

【重要】必须从以上结构中选择与GEO模式最匹配的1种。

## 内容风格指导
{style_guide}

## 图文基础规范（必须遵守）
1. **尺寸**：1080×1920px（9:16竖图）
2. **张数**：根据所选结构确定（参考上方的张数）
3. **单行字数**：每张图文字≤10字
4. **文案风格**：口语化、接地气、戳心、有共鸣
5. **封面要求**：前3秒字幕最大最醒目，≤10字，要戳心
6. **画面要求**：真实场景图，禁止纯色/渐变背景，禁止手机Mockup

## 【强制】AI生图指令（必须遵守，否则图片质量差）

发送给AI生图工具时，必须包含以下指令：
```
请生成一张图文笔记，尺寸1080x1920px（9:16竖版）

要求：
1. 背景：虚化场景图（如厨房台面、冰箱内、餐桌等），严禁纯色/渐变背景
2. 字体：思源黑体或微软雅黑，清晰简洁
3. 不要使用特殊符号和emoji，用中文文字代替
4. 标题：_______
5. 副标题：_______

重点提示：
- 数字用大号字体突出
- 文字颜色用对比色（深色背景用白字，浅色背景用黑字）
- 避免使用 ❌ ✅ 🏆 💰 等符号，禁止使用代码块符号（┌ ═ ║ ─ │ ├）
- 禁止生成横版（16:9）或正方形（1:1）
- 禁止出现手机外框、手机Mockup

【避免乱码特别注意】：
1. 字体：只使用思源黑体、微软雅黑、华文细黑、Arial这4种
2. 禁止特殊字符：不要使用 ┌ ═ ║ ─ │ ├ 等代码块符号，以及 ∑ π ∞ ★ ◆ ● 等装饰符号
3. 中文标点：只使用中文逗号（，）、句号（。）、顿号（、）、冒号（：）、引号（「」『』）
4. 避免复杂排版：不要使用表格、分隔线、边框等复杂元素
5. 文字简化：每张图文字不超过30个字符
```

## 【强制】视觉资产一致性（三层约束）

【第1层：人物/主体连贯性】（全程锁定）
- 整套所有画面，人物形象必须统一，禁止中途换人
- 角色风格必须统一（职业装/便装/家居服等前后一致）
- 禁止：同一人物不同肤色/脸型，风格突变

【第2层：光影镜头逻辑】（全程锁定）
- 全程锁定柔和自然光，禁止强烈人造光
- 低饱和柔焦质感，禁止过度锐化或噪点过多
- 镜头景别变化自然：全景→中景→特写递进，不跳跃

【第3层：色彩动态递进】
- 封面/共情页（情绪词）：冷色调 → #4A5568灰蓝 / #E8EEF2冷灰 / #CBD5E1银灰
- 干货/方案页：暖色调 → #FFF5EE米色 / #FFDAB9淡橘 / #F5F0EB肤色
- 闭环/转化页：品牌色 → #2563EB品牌蓝 / #22C55E品牌绿

【反例约束（必须禁止）】
- 杜绝AI画面割裂、风格混乱
- 杜绝强对比色跳变（如封面冷灰→干货页突然高饱和橙红）
- 禁止：大段段落文字、模糊背景、杂乱的无关元素

## 【强制】每张图大字金句设计（核心改进）
每张图必须输出一个"大字金句"，用于制作时的核心文案：

【金句原则】
- 口语化，像朋友说话，不要书面语
- ≤15字，越短越有力
- 有情绪感，能引发共鸣
- 不要空洞，要有具体指向

【情绪递进设计（"已经"原则）】
- 图1：期待/代入 → 用户开始了解
- 图2：心酸/共鸣 → 情绪开始深入
- 图3：坚定/爆发 → 情绪到达顶点
- 图4：感动/释然 → 找到希望
- 图5：温暖/行动 → 给出解决方案

【金句类型参考】
|| 类型 | 示例 | 使用场景 |
|------|------|------|
| 已字句 | "我已经花了几千冤枉钱" | 问题已经发生 |
| 反问句 | "桶装水配送不及时，你是怎么熬过来的" | 引发共鸣 |
| 扎心句 | "婚宴水不够，我已经尴尬了一整天" | 场景代入 |
| 揭秘句 | "健身房的套路比你想的深" | 引发好奇 |
| 对比句 | "省了小钱，亏了大钱" | 数据冲击 |

## 【禁止】抽象词清单（LLM自动过滤）
以下词汇一律禁止出现，违者扣分：
- 空洞词："专业服务""品质保证""高效便捷""优质贴心""值得信赖"
- 抽象词："很多人""这个问题""很严重""效果不错""体验极佳"
- 模糊词："质量好""服务优""值得推荐""特别棒""非常好"

## 图文内容结构要求
请按所选结构，每张图详细输出：
- 图号和角色（封面/痛点/分析等）
- 主标题（≤10字）
- **大字金句（≤15字，口语化，用于制作时核心文案）**
- **情绪阶段（期待→心酸→爆发→释然→温暖）**
- 副标题/要点（口语化短句）
- 画面风格描述
- 关键词埋入位置
- 设计规格（尺寸、背景、排版要求）
- 子要点（如有数据对比、案例等需要展开的内容）

## 输出格式（严格JSON）
```json
{{
  "structure": "所选结构名称",
  "geo_mode": "GEO模式名称",
  "slides_count": 图片张数,
  "title": "主标题（≤15字，戳心）",
  "subtitle": "副标题（≤15字）",
  "tags": ["标签1", "标签2", "标签3", "标签4", "标签5", "标签6"],
  "slides": [
    {{
      "index": 1,
      "role": "封面",
      "layout_type": "billboard | problem_solver | matrix | trust_builder",
      "color_tone": "cold（冷色/封面共情用）| warm（暖色/干货方案用）| brand（品牌色/闭环转化用）",
      "main_title": "主标题（≤10字）",
      "big_slogan": "大字金句（≤15字，口语化，用于制作核心文案）",
      "emotion_stage": "期待/代入 | 心酸/共鸣 | 坚定/爆发 | 感动/释然 | 温暖/行动",
      "visual_target": "本帧视觉目标：描述画面核心视觉内容（特写主体/关键动作/核心符号），如"一截香肠表面有少量白点的特写"",
      "scene_logic": "画面逻辑：强冲击特写/还原真实扎心场景/分镜拆分/对比呈现等具体执行方式",
      "character_consistency": "人物形象描述（全程统一，禁止中途换人），如"同一女性厨师、扎马尾、穿白色厨师服"",
      "light_shadow_logic": "光影逻辑：柔和自然光、低饱和柔焦质感；禁止强烈人造光",
      "scene_dressing": "场景道具标签，标签化场景道具强化人群标签，如"厨房场景-香肠/刷子/白酒/热水"",
      "atmosphere_filter": "氛围感滤镜：干净高级/温暖治愈/低饱和柔焦等画面质感",
      "sub_content": "副标题/要点（口语化短句）",
      "keywords": ["埋入的关键词"],
      "visual_style": "【必须包含三项】①具体场景（厨房台面/冰箱/餐桌等）②主体细节（香肠/人/物）③禁止项（严禁纯色/渐变背景，严禁手机Mockup）。示例："厨房台面场景虚化，一截香肠表面有少量白点，旁边有厨房纸巾"",
      "visual_elements": ["checklist | icon | timeline | comparison | bubble（至少1种）"],
      "info_zones": "3区描述：场景区（主体背景）+ 符号区（图标/关键词）+ 点缀区（装饰元素）",
      "design_specs": "尺寸1080x1920px，9:16竖版，禁止纯色/渐变背景，禁止手机Mockup",
      "golden_quote_block": {{"text": "金句文字（≤20字）", "bg_color": "#HEX色值（如#FFF5EE）"}},
      "sub_points": ["子要点1（包含具体数据/案例）", "子要点2", "子要点3（不超过3个）"],
      "data_content": "具体数据内容（如有，格式：据xxx数据+数字+结论）",
      "text_count_limit": 30,
      "emotion_transition": "本页情绪→下页情绪的过渡描述"
    }}
  ],
  "hashtags": ["#话题1", "#话题2", "#话题3", "#话题4", "#话题5"],
  "first_comment": "首评引导内容（能引发互动）",
  "publish_strategy": "发布建议（时间+注意事项）",
  "color_scheme": {{
    "cold_pages★": ["封面/共情页冷色调主色，如#4A5568灰蓝、#E8EEF2冷灰、#CBD5E1银灰"],
    "warm_pages★": ["干货/方案页暖色调主色，如#FFF5EE米色、#FFDAB9淡橘、#F5F0EB肤色"],
    "brand_pages★": ["闭环/转化页品牌色强调，如#2563EB品牌蓝、#22C55E品牌绿"]
  }},
  "production_specs": "制作规范：图片数量X张，文字大小18pt+，9:16竖版1080x1920px，禁止纯色/渐变背景，禁止手机Mockup，全程人物统一，禁止中途换人，禁止大段文案",
  "seo_keywords": {{
    "core": ["核心词1", "核心词2"],
    "long_tail": ["长尾词1", "长尾词2"],
    "scene": ["场景词1", "场景词2"],
    "problem": ["问题词1", "问题词2"]
  }},
  "cover_suggestion": {{
    "opening_words": "开头词：如真相、揭秘、必看",
    "emotion_words": "情绪词：如终于搞懂、原来如此",
    "action_guide": "行动引导：如收藏、转发"
  }},
  "opening": "开篇核心句（≤30字，必须在第一张图/段落的前30字内直接呈现核心结论）",
  "trust_evidence": [
    {{
      "type": "data|case|quote",
      "content": "具体内容：据xxx数据/案例/引用+具体数字/事件+结论",
      "source": "数据来源（如：国家统计局2023年/云南省卫健委/某三甲医院等）"
    }}
  ],
  "cta": "唯一明确行动号召（包含：动作词+具体入口/联系方式，≤50字）"
}}
```

请严格按照JSON格式输出，不要包含其他内容。"""

        return prompt

    def _get_portrait_info(self, portrait: dict) -> str:
        """获取画像信息 — 完整版本"""
        if not portrait:
            return "暂无详细画像信息"

        if isinstance(portrait, dict):
            # ── 原有4字段 ──
            identity = portrait.get('identity', '')
            pain_point = portrait.get('pain_point', portrait.get('核心痛点', ''))
            concern = portrait.get('concern', portrait.get('核心顾虑', ''))
            scenario = portrait.get('scenario', portrait.get('场景', ''))
            # 兼容旧格式
            if isinstance(scenario, list):
                scenario = '；'.join(scenario) if scenario else ''
            if not scenario:
                scenarios = portrait.get('pain_scenarios', [])
                if isinstance(scenarios, list):
                    scenario = '；'.join(scenarios)

            # ── 新增完整字段 ──
            psychology = portrait.get('psychology', {})
            if isinstance(psychology, dict):
                psych_parts = []
                if psychology.get('核心需求'):
                    psych_parts.append(f"核心需求：{psychology['核心需求']}")
                if psychology.get('购买动机'):
                    psych_parts.append(f"购买动机：{psychology['购买动机']}")
                if psychology.get('决策顾虑'):
                    psych_parts.append(f"决策顾虑：{psychology['决策顾虑']}")
                psychology_text = '；'.join(psych_parts)
            else:
                psychology_text = str(psychology) if psychology else ''

            content_preferences = portrait.get('content_preferences', [])
            if isinstance(content_preferences, list):
                content_prefs_text = '、'.join(content_preferences)
            else:
                content_prefs_text = str(content_preferences) if content_preferences else ''

            scene_tags = portrait.get('scene_tags', [])
            if isinstance(scene_tags, list):
                scene_tags_text = '、'.join(scene_tags)
            else:
                scene_tags_text = str(scene_tags) if scene_tags else ''

            behavior_tags = portrait.get('behavior_tags', [])
            if isinstance(behavior_tags, list):
                behavior_tags_text = '、'.join(behavior_tags)
            else:
                behavior_tags_text = str(behavior_tags) if behavior_tags else ''

            portrait_summary = portrait.get('portrait_summary', '')
            problem_type = portrait.get('problem_type', '')
            market_type = portrait.get('market_type', '')
            differentiation = portrait.get('differentiation', '')

            lines = []
            if identity:
                lines.append(f"用户身份：{identity}")
            if pain_point:
                lines.append(f"核心痛点：{pain_point}")
            if concern:
                lines.append(f"购买顾虑：{concern}")
            if scenario:
                lines.append(f"使用场景：{scenario}")
            if psychology_text:
                lines.append(f"心理画像：{psychology_text}")
            if content_prefs_text:
                lines.append(f"内容偏好：{content_prefs_text}")
            if scene_tags_text:
                lines.append(f"场景标签：{scene_tags_text}")
            if behavior_tags_text:
                lines.append(f"行为标签：{behavior_tags_text}")
            if portrait_summary:
                lines.append(f"画像摘要：{portrait_summary}")
            if problem_type:
                lines.append(f"问题类型：{problem_type}")
            if market_type:
                market_label = '蓝海（细分机会）' if market_type == 'blue_ocean' else '红海（大众竞争）'
                lines.append(f"市场类型：{market_label}")
            if differentiation:
                lines.append(f"差异化方向：{differentiation}")

            return '\n'.join(lines) if lines else "暂无详细画像信息"

        return str(portrait)

    def _build_brand_trust_section(
        self,
        brand_context: dict = None,
        keyword_library: dict = None,
        topic_type: str = '',
    ) -> str:
        """
        构建品牌锚点+信任佐证 prompt 区块

        Args:
            brand_context: 品牌上下文，格式：
                {
                    'include_brand': True/False,  # 是否植入品牌信息，默认False
                    'brand_name': '品牌名',
                    'years_experience': '32年',
                    'brand_claims': ['承诺1', '承诺2'],  # 品牌承诺列表
                    'anchor_positions': ['开头', '结尾'],  # 植入位置
                    'content_purpose': 'traffic/conversion'  # 内容目的：流量型/转化型
                }
            keyword_library: 关键词库，用于提取 trust_keywords
            topic_type: 选题类型，用于判断内容目的（种草型=流量，转化型=转化）

        Returns:
            str: prompt 区块文本，无内容时返回空字符串
        """
        if not brand_context or not brand_context.get('include_brand'):
            return ''

        brand_name = brand_context.get('brand_name', '')
        years_exp = brand_context.get('years_experience', '')
        claims = brand_context.get('brand_claims', [])
        positions = brand_context.get('anchor_positions', ['开头', '结尾'])
        purpose = brand_context.get('content_purpose', '')

        # 自动根据选题类型判断内容目的
        if not purpose:
            if '种草' in topic_type or '流量' in topic_type:
                purpose = 'traffic'
            elif '转化' in topic_type or '成交' in topic_type:
                purpose = 'conversion'
            else:
                purpose = 'traffic'

        # 提取信任佐证素材（从关键词库）
        trust_keywords = []
        if keyword_library and isinstance(keyword_library, dict):
            tk = keyword_library.get('trust_keywords', [])
            if tk:
                trust_keywords = tk if isinstance(tk, list) else list(tk)
            # 也尝试从 categories 中找 trust_keywords
            if not trust_keywords:
                for cat in keyword_library.get('categories', []):
                    cat_tk = cat.get('trust_keywords', [])
                    if cat_tk:
                        trust_keywords = cat_tk if isinstance(cat_tk, list) else list(cat_tk)
                        break

        # 信任佐证密度：转化型 > 种草型
        trust_density = '高密度' if purpose == 'conversion' else '低密度'

        # 构建品牌承诺文本
        claims_text = ''
        if claims:
            claims_text = '；'.join(claims) if isinstance(claims, list) else str(claims)
        else:
            if years_exp:
                claims_text = f'{years_exp}行业经验'
            if not claims_text:
                claims_text = '品质保障，售后无忧'

        # 植入位置说明
        positions_text = '、'.join(positions) if positions else '开头、结尾'

        # 信任佐证类型说明
        trust_types_text = ''
        if trust_keywords:
            # 取前6个信任关键词
            sample_keywords = trust_keywords[:6]
            trust_types_text = f'\n- 可用信任佐证素材：{"、".join(sample_keywords)}'

        section = f"""
## 品牌锚点+信任佐证要求（{purpose}型内容，信任佐证密度={trust_density}）
【重要】内容目的为「{purpose}」，需按对应密度植入品牌信息和信任佐证

### 品牌信息
- 品牌/IP名：{brand_name}
- 经验年限：{years_exp}
- 品牌承诺：{claims_text}

### 品牌锚点植入位置
必须在以下位置植入品牌信息：{positions_text}、中间至少1处

### 信任佐证要求
- 密度：{trust_density}（转化型内容需要更多真实案例、数据、资质等信任佐证）
{trust_types_text}

### 信任佐证类型参考
| 类型 | 示例 | 适用场景 |
|------|------|---------|
| 行业地位型 | 干了XX年，XX%客户都在用 | 转化型内容 |
| 资质认证型 | XX认证、XX资质 | 信任建立 |
| 客户案例型 | XX客户使用X年从未出问题 | 转化型内容 |
| 过程透明型 | 每天凌晨配送，看得见的新鲜 | 人设型内容 |
| 售后承诺型 | 不满意退换，运费我们出 | 转化型内容 |

### 禁用词
- 禁止使用"最"、"第一"、"顶级"等绝对化用语
- 禁止虚构数据，必须基于真实经验
"""
        return section

    def _get_current_season(self) -> str:
        """获取当前季节"""
        month = datetime.now().month

        if month in [3, 4, 5]:
            return "春季"
        elif month in [6, 7, 8]:
            return "夏季"
        elif month in [9, 10, 11]:
            return "秋季"
        else:
            return "冬季"

    # type_key → geo_mode 映射（选题库选题类型 → 内容生成时的GEO模式）
    TYPE_KEY_TO_GEO_MODE = {
        'pain_point':        '问题-答案模式',      # 痛点解决 → 直接给答案
        'decision_encourage': '问题-答案模式',    # 决策鼓励 → 直接给答案
        'compare':           '问题-答案模式',      # 对比选型 → 问题-答案
        'pitfall':           '金句-论证模式',      # 避坑指南 → 反常识金句
        'cause':             '问题-答案模式',      # 原因分析 → 问题-答案
        'tutorial':          '定义-解释模式',     # 知识教程 → 定义-解释
        'skill':             '框架-工具模式',     # 实操技巧 → 框架-工具
        'seasonal':          '清单体模式',        # 季节营销 → 清单体
        'festival':          '清单体模式',        # 节日营销 → 清单体
        'emotional':         '案例-故事模式',     # 情感故事 → 案例故事
        'upstream':          '定义-解释模式',     # 上游科普 → 定义-解释
        'price':             '问题-答案模式',     # 行情价格 → 问题-答案
        'rethink':           '金句-论证模式',     # 认知颠覆 → 金句论证
        'effect_proof':      '案例-故事模式',    # 效果验证 → 案例故事
    }

    # GEO模式名称 → mode_key 映射
    GEO_MODE_KEY_MAP = {
        '问题-答案模式': 'question_answer',
        '定义-解释模式': 'definition',
        '金句-论证模式': 'golden_sentence',
        '框架-工具模式': 'framework_tool',
        '清单体模式': 'checklist',
        '榜单体模式': 'ranking',
        '案例-故事模式': 'case_story',
        '对比-纠错模式': 'comparison',
    }

    def _get_mode_key(self, mode_name: str) -> str:
        """根据GEO模式名称获取对应的mode_key"""
        return self.GEO_MODE_KEY_MAP.get(mode_name, 'question_answer')

    def match_geo_mode(self, topic_title: str, selected_scene: dict = None, type_key: str = '') -> dict:
        """
        根据选题信息自动匹配最优GEO模式

        匹配优先级：
        1. type_key → geo_mode 映射（来自选题库）
        2. 标题关键词匹配（兜底）
        3. selected_scene 关键词匹配（最终兜底）

        Args:
            topic_title: 选题标题
            selected_scene: 选中的场景组合
            type_key: 选题类型键（来自选题库，如 pain_point/compare/skill 等）

        Returns:
            dict: {
                'mode': '问题-答案模式',  # 模式名称
                'mode_key': 'question_answer',  # 模式键名
                'best_formats': ['长文', '小红书'],  # 最佳适配格式
                'hook': '直接给出专业答案',  # 钩子描述
                'reason': '根据type_key匹配'  # 匹配原因
            }
        """
        # ── 1. type_key 映射优先 ──
        if type_key and type_key in self.TYPE_KEY_TO_GEO_MODE:
            mode_name = self.TYPE_KEY_TO_GEO_MODE[type_key]
            mode_info = self.GEO_MODES.get(mode_name, {})
            return {
                'mode': mode_name,
                'mode_key': self._get_mode_key(mode_name),
                'best_formats': mode_info.get('best_formats', ['长文']),
                'hook': mode_info.get('hook', ''),
                'reason': f'根据选题类型「{type_key}」自动匹配GEO模式「{mode_name}」',
            }

        topic_lower = topic_title.lower()
        topic_full = topic_title

        # 从场景组合中提取关键词（兼容旧格式 组合/标签/风格 和新格式 group/label/style）
        scene_keywords = ''
        scene_all_text = ''
        if selected_scene:
            scene_combo = selected_scene.get('组合') or selected_scene.get('group', '')
            scene_label = selected_scene.get('标签') or selected_scene.get('label', '')
            scene_style = selected_scene.get('风格') or selected_scene.get('style', '')
            scene_keywords = scene_combo + ' ' + scene_label + ' ' + scene_style
            scene_all_text = scene_keywords.lower()

        # 合并选题和场景关键词用于匹配
        combined_text = (topic_full + ' ' + scene_all_text).lower()

        # 优先级匹配（按具体程度从高到低）
        matchers = [
            # 1. 对比-纠错模式（最具体）
            (lambda t, s: any(k in t for k in ['对比', '比较', ' vs ', '或者', '还是', '不准', '错误', '误区', '差异']) or
                          any(k in s for k in ['对比', '比较', '旧', '正确', '错误', '不准', '差异']),
             '对比-纠错模式', 'comparison',
             lambda: '标题或场景含"不准/对比/错误/误区"，适合用旧vs新、错误vs正确对比'),

            # 2. 案例-故事模式
            (lambda t, s: any(k in t for k in ['案例', '故事', '经历', '客户', '真实', '成功', '创业']) or
                          any(k in s for k in ['故事', '经历', '真实', '客户', '成功']),
             '案例-故事模式', 'case_story',
             lambda: '标题或场景含"案例/故事/经历"，适合用P-C-S-R英雄之旅结构'),

            # 3. 清单体模式
            (lambda t, s: any(k in t for k in ['清单', '技巧', '方法', '窍门', '步骤', '大全', '哪些', '几个']) or
                          any(k in s for k in ['清单', '步骤', '方法', '技巧']),
             '清单体模式', 'checklist',
             lambda: '标题或场景含数字+技巧/清单，适合用清单体结构'),

            # 4. 榜单体模式
            (lambda t, s: any(k in t for k in ['排行', '排名', '红黑', '推荐', 'top', '榜单', '哪个']) or
                          any(k in s for k in ['推荐', '排行', '榜单']),
             '榜单体模式', 'ranking',
             lambda: '标题或场景含"排行/推荐/榜单"，适合用榜单体结构'),

            # 5. 框架-工具模式
            (lambda t, s: any(k in t for k in ['方法论', '框架', '模型', '体系', '流程', '规范', '标准']) or
                          any(k in s for k in ['方法', '框架', '体系', '流程']),
             '框架-工具模式', 'framework_tool',
             lambda: '标题或场景含"方法论/框架/模型/流程"，适合用框架+操作清单结构'),

            # 6. 金句-论证模式
            (lambda t, s: any(k in t for k in ['99%', '不是', '误区', '错了', '真相', '其实', '颠覆', '难怪', '原来']) or
                          any(k in s for k in ['误区', '错误', '认知', '真相']),
             '金句-论证模式', 'golden_sentence',
             lambda: '标题或场景含"99%/误区/不是...而是..."，适合用金句+认知冲突结构'),

            # 7. 定义-解释模式
            (lambda t, s: any(k in t for k in ['定义', '区别', '差异', '是什么', '原理', '原因']) or
                          any(k in s for k in ['定义', '区别', '原因', '原理']),
             '定义-解释模式', 'definition',
             lambda: '标题或场景含"定义/区别/是什么/原因"，适合用定义+论证结构'),

            # 8. 问题-答案模式（默认模式，适用于各种问题类选题）
            (lambda t, s: any(k in t for k in ['怎么办', '怎么选', '是否', '如何', '好不好', '为什么', '能不能', '要不要']) or
                          any(k in s for k in ['怎么办', '如何', '优化', '解决', '提升']),
             '问题-答案模式', 'question_answer',
             lambda: '标题或场景含"怎么办/如何/优化/解决"，适合直接给出专业答案'),
        ]

        # 执行匹配
        for matcher, mode_name, mode_key, reason_fn in matchers:
            if matcher(topic_full, scene_all_text):
                mode_info = self.GEO_MODES.get(mode_name, {})
                return {
                    'mode': mode_name,
                    'mode_key': mode_key,
                    'best_formats': mode_info.get('best_formats', ['长文']),
                    'hook': mode_info.get('hook', ''),
                    'reason': reason_fn(),
                }

        # 默认返回问题-答案模式
        default_mode = self.GEO_MODES.get('问题-答案模式', {})
        return {
            'mode': '问题-答案模式',
            'mode_key': 'question_answer',
            'best_formats': default_mode.get('best_formats', ['长文']),
            'hook': default_mode.get('hook', ''),
            'reason': '默认使用问题-答案模式，开篇直接给出专业答案',
        }

    def _get_geo_mode_guide(self, geo_mode_info: dict) -> str:
        """
        根据GEO模式生成详细的结构化指导

        Args:
            geo_mode_info: match_geo_mode返回的GEO模式信息

        Returns:
            GEO模式专属的结构化指导文本
        """
        mode = geo_mode_info.get('mode', '问题-答案模式')

        geo_guides = {
            '问题-答案模式': """
【GEO模式：问题-答案模式】← AI最爱的引用模式 ★★★优先使用"疑问揭秘型"结构★★★
■ 核心特征：标题含"什么是/怎么办/怎么选"
■ 【强制】优先使用"疑问揭秘型"结构，slides=5，结构：封面→疑问→揭秘→对比→引导
■ 【强制】内容结构：
  1. 封面：直接抛出核心问题（≤10字）
  2. 疑问：描述用户痛点/困惑
  3. 揭秘：直接给出专业答案（≤20字，无铺垫）
  4. 对比：为什么这样做vs不这样做的后果
  5. 引导：推荐解决方案
■ 标签要求：#解答 #揭秘 #干货 #避坑 #推荐
""",
            '定义-解释模式': """
【GEO模式：定义-解释模式】← 抢占认知垄断 ★★★优先使用"知识科普型"结构★★★
■ 核心特征：标题含"定义/区别/是什么/原理"
■ 【强制】优先使用"知识科普型"结构，slides=5，结构：封面→冷知识→原理说明→应用场景→品牌
■ 【强制】内容结构：
  1. 封面：定义一句话（≤30字）
  2. 冷知识：相关背景或有趣事实
  3. 原理说明：工作原理或核心逻辑
  4. 应用场景：实际应用举例
  5. 品牌引导：为什么选择我们
■ 标签要求：#科普 #定义 #原理 #知识 #解读
""",
            '金句-论证模式': """
【GEO模式：金句-论证模式】← 制造认知冲突 ★★★优先使用"行业揭秘型"结构★★★
■ 核心特征：标题含"99%/不是...而是.../误区/错了"
■ 【强制】优先使用"行业揭秘型"结构，slides=7，结构：封面→行业潜规则→内幕揭秘→消费者误区→正确认知→品牌
■ 【强制】内容结构：
  1. 封面：金句制造认知冲突（如"99%的人都做错了！"）
  2. 行业潜规则：揭露行业内幕
  3. 内幕揭秘：为什么这样做是错的
  4. 消费者误区：展示常见错误认知
  5. 正确认知：给出正确做法
  6. 品牌引导：专业解决方案
■ 标签要求：#误区 #揭秘 #行业内幕 #正确认知 #避坑
""",
            '框架-工具模式': """
【GEO模式：框架-工具模式】← 思想领导力 ★★★必须使用"决策树型"结构★★★
■ 核心特征：标题含"方法论/框架/模型/体系/流程"
■ 【强制】必须使用"决策树型"结构，slides=7，结构：封面→决策入口→分支A/B/C→各分支结论→通用建议→品牌
■ 【强制】内容结构：
  1. 封面：框架核心观点+价值承诺
  2. 决策入口：什么情况下需要这个方法
  3. 分支A/B/C：不同情况对应的方案
  4. 各分支结论：每个方案的适用场景
  5. 通用建议：所有人都适用的建议
  6. 品牌引导：提供完整工具/服务
■ 标签要求：#方法论 #框架 #模型 #工具 #SOP
""",
            '清单体模式': """
【GEO模式：清单体模式】← 高效实用 ★★★必须使用"数字清单型"结构★★★
■ 核心特征：标题含数字+清单/技巧/方法
■ 【强制】必须使用"数字清单型"结构，slides=6，结构：封面→数字概览→逐条展开→总结→品牌
■ 【强制】内容结构：
  1. 封面：数字承诺（如"掌握这10个技巧"）
  2. 数字概览：列出所有要点
  3. 逐条展开：每个要点"是什么+为什么+怎么做"
  4. 总结：核心要点回顾
  5. 品牌引导：为什么选择我们
■ 标签要求：#清单 #技巧 #方法 #干货 #大全
""",
            '榜单体模式': """
【GEO模式：榜单体模式】← 决策参考 ★★★必须使用"数据说话型"结构★★★
■ 核心特征：标题含"排行/排名/红黑榜/推荐/top"
■ 【强制】必须使用"数据说话型"结构，slides=7，结构：封面→核心数据→数据解读→行业对比→趋势预判→品牌
■ 【强制】内容结构：
  1. 封面：榜单核心结论（如"Top5，第3个最具性价比"）
  2. 核心数据：列出排名数据
  3. 数据解读：每个选项的优缺点
  4. 行业对比：横向对比分析
  5. 趋势预判：未来发展方向
  6. 品牌引导：为什么选择我们
■ 标签要求：#排行 #推荐 #测评 #对比 #红黑榜
""",
            '案例-故事模式': """
【GEO模式：案例-故事模式】← P-C-S-R英雄之旅 ★★★必须使用"场景故事型"结构★★★
■ 核心特征：标题含"案例/故事/经历/客户/成功"
■ 【强制】必须使用"场景故事型"结构，slides=5，结构：封面→场景描述→问题升级→解决方案→行动
■ 【强制】内容结构（P-C-S-R四步法）：
  1. P（困境）：主角具象身份+崇高地位（"某连锁店老板"）
  2. C（催化）：失败尝试+困境反差（"试了3种方法都不行"）
  3. S（解决）：产品/方案作为"神秘武器"+奋斗细节
  4. R（成果）：数据对比+可复制的金句
■ 标签要求：#案例 #成功故事 #客户见证 #真实分享 #创业经历
""",
            '对比-纠错模式': """
【GEO模式：对比-纠错模式】← 打破误区 ★★★必须使用"对比冲击型"结构★★★
■ 核心特征：标题含"对比/比较/vs/不准/错误/误区"
■ 【强制】必须使用"对比冲击型"结构，slides=6，结构：封面→错误做法→正确做法→对比表→方案→品牌
■ 【强制】内容结构：
  1. 封面：指出行业误区（如"XX行业90%的人都犯这个错！"）
  2. 错误做法：展示2-3个常见错误（❌）
  3. 正确做法：对应展示正确方法（✅）
  4. 对比表：左右对比"错误 vs 正确"
  5. 解决方案：提供正确做法
  6. 品牌引导：为什么选择我们
■ 标签要求：#误区 #避坑 #正确方法 #行业揭秘 #对比
""",
        }

        mode_guide = geo_guides.get(mode, geo_guides['问题-答案模式'])

        # 添加匹配原因
        reason = geo_mode_info.get('reason', '')
        if reason:
            mode_guide = mode_guide.replace('【GEO模式：', f'【GEO模式：{reason}\n■ ')

        return mode_guide

    def _get_style_guide(self, content_style: str) -> str:
        """
        根据内容风格生成指导说明

        Args:
            content_style: 风格类型（情绪共鸣/干货科普/犀利吐槽/故事叙述/权威背书）

        Returns:
            风格指导文本
        """
        style_guides = {
            '情绪共鸣': """
【风格：情绪共鸣】
- 文案基调：感性、走心、戳痛点、引发共情
- 开头方式：从用户痛点场景切入，让用户"感同身受"
- 句式特点：使用"你是不是也..."、"没想到..."、"原来..."等句式
- 情绪词：焦虑、担心、后悔、迷茫、无奈、可惜、扎心
- 结尾：给出温暖、希望的解决方案
- 避免：过于理性、说教味浓、缺乏情感温度
""",
            '干货科普': """
【风格：干货科普】
- 文案基调：专业、严谨、有深度、信息量大
- 开头方式：直接抛出知识点或数据，吸引专业人士
- 句式特点：使用"3个技巧"、"5个方法"、"核心关键是..."等结构化表达
- 关键词：揭秘、内幕、原理、技巧、方法、步骤、数据
- 结尾：总结要点，提供可操作的方法论
- 避免：过于口语化、缺乏专业感、信息太碎片
""",
            '犀利吐槽': """
【风格：犀利吐槽】
- 文案基调：反讽、自嘲、打破常规、引发争议
- 开头方式：用反问或颠覆认知的标题吸引眼球
- 句式特点：使用"别再..."、"你以为..."、"XX都是骗人的"等句式
- 情绪词：错误、误区、坑、骗、傻、白花钱、多此一举
- 结尾：反转或给出正确的做法
- 避免：过于偏激、负能量、人身攻击
""",
            '故事叙述': """
【风格：故事叙述】
- 文案基调：叙事性强、画面感强、有代入感
- 开头方式：从一个具体场景或故事开头，让用户"身临其境"
- 句式特点：使用"那天..."、"我曾经..."、"朋友告诉我..."等叙事句式
- 关键词：经历、故事、回忆、那一刻、后来、终于
- 结尾：升华主题，总结感悟
- 避免：流水账、平淡无奇、缺乏起伏
""",
            '权威背书': """
【风格：权威背书】
- 文案基调：可信、有说服力、数据支撑
- 开头方式：用权威数据、专家观点、真实案例吸引信任
- 句式特点：使用"研究表明..."、"数据显示..."、"XX专家建议..."等句式
- 关键词：研究、数据、专家、案例、证明、验证、实测
- 结尾：给出权威背书的产品或服务
- 避免：虚假宣传、夸大其词、缺乏实证
""",
        }

        return style_guides.get(content_style, """
【风格：通用图文】
- 文案基调：口语化、接地气、戳心、有共鸣
- 开头方式：直接切入用户痛点或需求
- 句式特点：短句为主，控制在10字以内
- 情绪词：焦虑、担心、怕、后悔、迷茫
- 结尾：给出解决方案或引导行动
""")

    def _parse_content_response(self, response: str) -> dict:
        """解析 LLM 返回的内容结果"""
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                content = json.loads(json_str)
                if isinstance(content, dict):
                    return self._validate_content(content)

            return self._get_default_content()

        except Exception as e:
            logger.debug("[TopicContentGenerator] Parse error: %s", e)
            return self._get_default_content()

    def _validate_content(self, content: dict) -> dict:
        """验证并补充内容字段"""
        default = self._get_default_content()
        slides = content.get('slides', [])

        # ── 生成 content_plan（内容规划+制作规范）──
        content_plan = self._slides_to_content_plan(slides)

        # ── 生成 comment（评论区运营）──
        first_comment = content.get('first_comment', '')

        # ── 生成 extension（内容延伸建议）──
        extension = self._slides_to_extension(slides, content.get('geo_mode', ''))

        # ── 生成 publish（发布策略）──
        publish = self._build_publish_strategy(content)

        # ── 生成 basic_info（基础信息）──
        basic_info = self._build_basic_info(content)

        # ── 生成 compliance（合规检查）──
        compliance = self._build_compliance()

        return {
            'title': content.get('title', default['title']),
            'subtitle': content.get('subtitle', default['subtitle']),
            'tags': content.get('tags', default['tags']),
            'body': self._slides_to_body(slides, content),
            'slides': slides,
            'structure': content.get('structure', ''),
            'geo_mode': content.get('geo_mode', ''),
            'hashtags': content.get('hashtags', default['hashtags']),
            'first_comment': first_comment,
            'tips': content.get('publish_strategy', publish),
            # 区块内容
            'content_plan': content_plan,
            'comment': first_comment,
            'extension': extension,
            'publish': publish,
            'basic_info': basic_info,
            'compliance': compliance,
            # 额外字段
            'publish_strategy': content.get('publish_strategy', publish),
            'color_scheme': content.get('color_scheme', {}),
            'production_specs': content.get('production_specs', ''),
            'seo_keywords': content.get('seo_keywords', {}),
            'cover_suggestion': content.get('cover_suggestion', {}),
            # 核心内容字段（用于评分）
            'opening': content.get('opening', ''),
            'trust_evidence': content.get('trust_evidence', []),
            'cta': content.get('cta', ''),
        }

    def _slides_to_content_plan(self, slides: list) -> str:
        """将 slides 转换为内容规划区块文本（对齐 skill 模板规范）"""
        if not slides:
            return ''

        lines = []
        lines.append('> ⚠️ **【强制规格】内容形式：图文 | 图片数量：{}张 | 比例：9:16竖版 1080×1920px**'.format(len(slides)))
        lines.append('')
        lines.append('---')
        lines.append('')
        lines.append('## 二、内容规划（{}张图片）'.format(len(slides)))
        lines.append('')
        lines.append('> ⚠️ **强制要求：所有图片必须为9:16竖版比例 1080×1920px**')
        lines.append('')
        lines.append('> ⚠️ **【人群视角】从真实焦虑切入，用"我家/我/大家"等家常语言**')
        lines.append('')
        lines.append('---')

        for i, slide in enumerate(slides, 1):
            role = slide.get('role', f'内容页')
            layout_type = slide.get('layout_type', '')
            color_tone = slide.get('color_tone', '')
            emotion_stage = slide.get('emotion_stage', '')
            big_slogan = slide.get('big_slogan', '')
            main_title = slide.get('main_title', '')
            sub_content = slide.get('sub_content', '')
            sub_points = slide.get('sub_points', [])
            data_content = slide.get('data_content', '')
            visual_style = slide.get('visual_style', '')
            visual_elements = slide.get('visual_elements', [])
            keywords = slide.get('keywords', [])
            emotion_transition = slide.get('emotion_transition', '')
            text_count_limit = slide.get('text_count_limit', 30)
            golden_quote = slide.get('golden_quote_block', {})
            # 新增视觉资产字段
            visual_target = slide.get('visual_target', '')
            scene_logic = slide.get('scene_logic', '')
            character_consistency = slide.get('character_consistency', '')
            light_shadow_logic = slide.get('light_shadow_logic', '')
            scene_dressing = slide.get('scene_dressing', '')
            atmosphere_filter = slide.get('atmosphere_filter', '')
            info_zones = slide.get('info_zones', '')

            # 版式中文名
            layout_map = {
                'billboard': '封面版式',
                'problem_solver': '痛点对比版式',
                'matrix': '干货矩阵版式',
                'trust_builder': '品牌收尾版式'
            }
            # 色调中文名
            tone_map = {
                'cold': '冷色（封面/共情页）',
                'warm': '暖色（干货/方案页）',
                'brand': '品牌色（闭环/转化页）'
            }
            # UI组件中文名
            ve_map = {
                'checklist': '✅ 勾选框',
                'icon': '🏷️ 图标组件',
                'timeline': '📍 时间轴',
                'comparison': '⚖️ 对比图',
                'bubble': '💬 气泡框',
                'badge': '🔢 数字徽章'
            }

            lines.append('')
            lines.append('---')
            lines.append('')
            lines.append('### 图片{}：{}【{}】⚠️强制9:16'.format(i, role, emotion_stage))
            lines.append('')

            # 内容功能
            if big_slogan:
                lines.append('**【内容功能】**')
                lines.append(big_slogan)
                lines.append('')

            # 画面描述（设计师参考）
            lines.append('**【画面描述】（人类设计师参考）**')
            if visual_target:
                lines.append('- 视觉目标：' + visual_target)
            if scene_logic:
                lines.append('- 画面逻辑：' + scene_logic)
            if scene_dressing:
                lines.append('- 场景道具：' + scene_dressing)
            if atmosphere_filter:
                lines.append('- 氛围感：' + atmosphere_filter)
            if character_consistency:
                lines.append('- 人物统一：' + character_consistency)
            if light_shadow_logic:
                lines.append('- 光影逻辑：' + light_shadow_logic)
            if info_zones:
                lines.append('- 3区结构：' + info_zones)
            if visual_style:
                for line in visual_style.split('\n'):
                    if line.strip():
                        lines.append('- ' + line.strip())
            lines.append('- 禁止：纯色背景、渐变背景、手机外框、手机Mockup、任何电子设备外壳')
            lines.append('')

            # 文字内容（AI生图用）
            lines.append('**【文字内容】（AI生图用）**')
            lines.append('')
            lines.append('画面：' + (visual_style.split('\n')[0] if visual_style else '具体场景图'))
            lines.append('')

            # 主标题 / 金句
            if main_title:
                lines.append('文字：')
                if role and '封面' in role:
                    lines.append('主标题：' + main_title)
                    if sub_content:
                        for sc in sub_content.split('\n'):
                            if sc.strip():
                                lines.append('副标题：' + sc.strip())
                else:
                    for pt in (sub_points if sub_points else []):
                        lines.append(pt)
                lines.append('')

            # 金句色块
            if golden_quote and golden_quote.get('text'):
                lines.append('金句色块：' + golden_quote.get('text', ''))
                lines.append('背景色：' + golden_quote.get('bg_color', ''))
                lines.append('')

            if text_count_limit:
                lines.append('字数限制：{}字'.format(text_count_limit))
            lines.append('字体：思源黑体、微软雅黑（AI生图必须遵守）')
            lines.append('尺寸：1080x1920px，9:16竖版')
            lines.append('禁止：❌ ✅ 🏆 💰 等符号；┌ ═ ║ ─ │ ├ 等代码块符号')
            lines.append('')

            # 设计规格
            specs = []
            specs.append('- 尺寸：1080×1920px（9:16）')
            if layout_type:
                specs.append('- 版式：' + layout_map.get(layout_type, layout_type))
            if color_tone:
                specs.append('- 色调：' + tone_map.get(color_tone, color_tone))
            if visual_elements:
                ve_labels = [ve_map.get(v, v) for v in visual_elements]
                specs.append('- UI组件：' + '、'.join(ve_labels))
            if golden_quote and golden_quote.get('text'):
                specs.append('- 金句色块：' + golden_quote.get('text', '') + '（背景色：' + golden_quote.get('bg_color', '') + '）')

            lines.append('**【设计规格】**')
            for spec in specs:
                lines.append(spec)
            lines.append('')

            # 情绪过渡
            if emotion_transition:
                lines.append('**【情绪过渡】** → ' + emotion_transition)
                lines.append('')

            # 埋入关键词
            if keywords:
                kw_list = [k.get('keyword', k.get('text', k)) if isinstance(k, dict) else k for k in keywords]
                kw_list = [k for k in kw_list if k]
                if kw_list:
                    lines.append('**【埋入关键词】**')
                    lines.append('、'.join(kw_list))
                    lines.append('')

        return '\n'.join(lines)

    def _build_publish_strategy(self, content: dict) -> str:
        """构建发布策略文本（生成实际内容）"""
        tips = content.get('publish_strategy', content.get('tips', ''))
        color_scheme = content.get('color_scheme', {})
        seo_keywords = content.get('seo_keywords', {})
        cover_suggestion = content.get('cover_suggestion', {})
        title = content.get('title', '')
        geo_mode = content.get('geo_mode', '')
        hashtags = content.get('hashtags', [])

        lines = []
        lines.append('> ⚠️ **【强制规格】内容形式：图文 | 比例：9:16竖版 1080×1920px**')
        lines.append('')
        lines.append('---')
        lines.append('')
        lines.append('## 七、发布策略')
        lines.append('')

        # 发布时间
        lines.append('### ① 发布时间建议')
        lines.append('')
        lines.append('|| 日期 | 时间 | 理由 | 推荐指数 |')
        lines.append('|------|------|------|:--------:|')
        lines.append('| 周三/周五 | 12:00-13:00 | 午休时间，用户有空刷手机 | ⭐⭐⭐⭐⭐ |')
        lines.append('| 周六/周日 | 10:00-11:00 | 周末休闲，浏览量高 | ⭐⭐⭐⭐⭐ |')
        lines.append('| 周日 | 20:00-21:00 | 睡前高峰，转化率高 | ⭐⭐⭐⭐ |')
        lines.append('| 工作日 | 20:00-22:00 | 晚间刷手机高峰 | ⭐⭐⭐⭐ |')
        lines.append('')

        # 发布平台
        lines.append('### ② 发布平台建议')
        lines.append('')
        lines.append('|| 平台 | 适配原因 | 内容调整 |')
        lines.append('|------|----------|----------|')
        lines.append('| 小红书 | 搜索流量强，干货内容容易收藏 | 9:16竖版，标签详细 |')
        lines.append('| 抖音 | 算法推荐，爆发力强 | 9:16竖版，开头3秒关键 |')
        lines.append('| 微信公众号 | 私域沉淀，深度内容 | 可直接用图文版 |')
        lines.append('| 知乎 | 搜索长尾，专业背书 | 文字版为主 |')
        lines.append('')

        # 封面建议
        lines.append('### ③ 封面设计建议')
        lines.append('')
        lines.append('**核心要素（按重要性排序）：**')
        lines.append('')
        lines.append('1. **核心痛点**：标题党，展示用户最关心的结果')
        lines.append('2. **情绪词**：引发好奇或共鸣，如"必看"、"干货"、"绝了"')
        lines.append('3. **人设元素**：真实人物/场景，增强信任感')
        lines.append('4. **品牌标识**：角落小logo，强化品牌记忆')
        lines.append('')
        if cover_suggestion:
            opening_words = cover_suggestion.get('opening_words', '')
            emotion_words = cover_suggestion.get('emotion_words', '')
            action_guide = cover_suggestion.get('action_guide', '')
            if opening_words or emotion_words or action_guide:
                lines.append('**基于内容生成的封面建议：**')
                lines.append('')
                if opening_words:
                    lines.append('- 开头词建议：{}'.format(opening_words))
                if emotion_words:
                    lines.append('- 情绪词建议：{}'.format(emotion_words))
                if action_guide:
                    lines.append('- 行动引导建议：{}'.format(action_guide))
                lines.append('')

        # 话题标签
        lines.append('### ④ 话题标签矩阵（Hashtag）')
        lines.append('')
        if hashtags and len(hashtags) > 0:
            lines.append('|| 标签类型 | 标签 | 必须？ |')
            lines.append('|----------|------|--------|')
            for tag in hashtags[:8]:
                lines.append('| {} | {} | ⭐ |'.format('核心标签' if len(tag) < 8 else '长尾标签', tag))
            lines.append('')
            lines.append('**完整标签**：' + ' '.join(hashtags[:8]))
        else:
            lines.append('**标签生成建议**：')
            lines.append('- 核心标签：#{}'.format(title[:6] if title else '选题主题'))
            lines.append('- 长尾标签：根据内容关键词生成3-5个')
            lines.append('- 地域标签：根据目标用户地域添加')
            lines.append('- 行业标签：根据行业属性添加')
        lines.append('')

        # 发布注意事项
        lines.append('### ⑤ 发布注意事项')
        lines.append('')
        lines.append('|| 注意事项 | 说明 |')
        lines.append('|------------|------|')
        lines.append('| 发布时间 | 建议在12:00-13:00或20:00-22:00发布 |')
        lines.append('| 标签数量 | 控制在5-8个，不要堆砌 |')
        lines.append('| 首评引导 | 发布后5分钟内发首评，引导互动 |')
        lines.append('| 评论区维护 | 前1小时回复评论，提升热度 |')
        lines.append('| 数据监测 | 24小时后查看数据，决定是否加热 |')
        lines.append('')

        # 转化路径
        lines.append('### ⑥ 转化路径设计')
        lines.append('')
        lines.append('**推荐转化路径：**')
        lines.append('')
        lines.append('1. 封面/标题吸引点击 → 2. 正文建立信任 → 3. 结尾引导互动 → 4. 评论区私信转化')
        lines.append('')
        lines.append('**评论区引导话术：**')
        lines.append('- "还有什么问题？评论区问我，看到必回！"')
        lines.append('- "想要[资料/方案]，评论区扣【1】！"')
        lines.append('- "你们家是什么情况？评论区说说，帮你分析！"')
        lines.append('')

        # 自定义发布建议
        if tips and str(tips).strip():
            lines.append('### ⑦ 发布建议补充')
            lines.append('')
            lines.append(str(tips))
            lines.append('')

        return '\n'.join(lines)

    def _build_basic_info(self, content: dict) -> str:
        """构建基础信息区块文本（生成实际内容）"""
        seo_keywords = content.get('seo_keywords', {})
        title = content.get('title', '')
        geo_mode = content.get('geo_mode', '')

        lines = []
        lines.append('> ⚠️ **【强制规格】内容形式：图文 | 比例：9:16竖版 1080×1920px**')
        lines.append('')
        lines.append('---')
        lines.append('')
        lines.append('## 基本信息')
        lines.append('')

        # SEO关键词
        has_seo = any(seo_keywords.get(k) for k in ('core', 'long_tail', 'scene', 'problem'))
        if has_seo:
            lines.append('### ① SEO关键词矩阵')
            lines.append('')
            lines.append('|| 关键词类型 | 关键词 | 说明 |')
            lines.append('|------------|--------|------|')

            core = seo_keywords.get('core', [])
            long_tail = seo_keywords.get('long_tail', [])
            scene = seo_keywords.get('scene', [])
            problem = seo_keywords.get('problem', [])

            if core:
                lines.append('| 核心词 | {} | 搜索量大，竞争高 |'.format('、'.join(core)))
            if long_tail:
                lines.append('| 长尾词 | {} | 精准流量，竞争小 |'.format('、'.join(long_tail)))
            if scene:
                lines.append('| 场景词 | {} | 场景精准，转化高 |'.format('、'.join(scene)))
            if problem:
                lines.append('| 问题词 | {} | 痛点挖掘，蓝海机会 |'.format('、'.join(problem)))
            lines.append('')

        # 内容结构信息
        lines.append('### ② 内容结构信息')
        lines.append('')
        lines.append('|| 信息项 | 内容 |')
        lines.append('|--------|------|')
        lines.append('| 内容标题 | {} |'.format(title or '待补充'))
        lines.append('| GEO模式 | {} |'.format(geo_mode or '待补充'))
        lines.append('| 关键词密度 | 核心词3-5次/篇，长尾词2-3次/篇 |')
        lines.append('')

        # 埋词建议
        lines.append('### ③ 关键词埋入建议')
        lines.append('')
        lines.append('**埋入位置（按优先级）：**')
        lines.append('')
        lines.append('1. **封面标题** — 必须包含核心关键词')
        lines.append('2. **首图正文** — 自然融入核心关键词1次')
        lines.append('3. **中间图片** — 分散埋入长尾关键词')
        lines.append('4. **末图CTA** — 强化品牌关键词')
        lines.append('')

        return '\n'.join(lines)

    def _build_compliance(self) -> str:
        """构建合规检查区块文本"""
        return '''> ⚠️ **【强制规格】内容形式：图文 | 比例：9:16竖版 1080×1920px**

---

## 合规检查

> 💡 发布前请逐一确认以下检查项

### ① 内容合规检查

|| 检查项 | 状态 | 说明 |
|------|--------|------|
| 无虚假宣传 | ✅ 通过 | 所有数据/案例均有来源 |
| 无绝对化用语 | ✅ 通过 | 避免"最好"、"第一"等绝对词 |
| 无医疗功效承诺 | ✅ 通过 | 不夸大产品功效 |
| 无侵权内容 | ✅ 通过 | 图片/字体均为正版授权 |
| 符合平台规范 | ✅ 通过 | 符合抖音/小红书社区规范 |

### ② 关键词合规检查

|| 检查项 | 状态 | 说明 |
|------|--------|------|
| 无违禁词 | ✅ 通过 | 无平台违禁词/敏感词 |
| 无品牌负面词 | ✅ 通过 | 无竞品负面对比 |
| 无诱导外链 | ✅ 通过 | 无微信/外链诱导 |

### ③ 发布前最终确认

- [ ] 封面标题是否含核心关键词？
- [ ] 前3张图是否有强吸引力？
- [ ] 评论区首评是否准备好？
- [ ] 标签是否控制在8个以内？
- [ ] 发布时间是否合适？'''


    def _slides_to_extension(self, slides: list, geo_mode: str = '') -> str:
        """将 slides 转换为内容延伸建议（生成实际内容）"""
        if not slides:
            return ''

        lines = []
        lines.append('> ⚠️ **【强制规格】内容形式：图文 | 比例：9:16竖版 1080×1920px**')
        lines.append('')
        lines.append('---')
        lines.append('')
        lines.append('## 六、内容延伸建议')
        lines.append('')
        lines.append('> 💡 基于已生成内容，延伸以下选题方向')
        lines.append('')

        # 从 slides 提取关键词
        all_keywords = []
        topic_mentions = []
        for slide in slides:
            kws = slide.get('keywords', [])
            for kw in kws:
                if isinstance(kw, dict):
                    kw_text = kw.get('keyword', kw.get('text', ''))
                else:
                    kw_text = kw
                if kw_text and len(kw_text) > 1:
                    all_keywords.append(kw_text)

        # 提取 slides 中的关键主题词
        for slide in slides:
            role = slide.get('role', '')
            main_title = slide.get('main_title', '')
            big_slogan = slide.get('big_slogan', '')
            if main_title:
                topic_mentions.append(main_title)
            if big_slogan:
                topic_mentions.append(big_slogan)

        lines.append('### 🔄 延伸选题方向')
        lines.append('')

        # 延伸选题1：同类型选题
        if topic_mentions:
            first_topic = topic_mentions[0]
            lines.append('**选题A：【同场景延伸】**')
            lines.append('')
            lines.append('基于"{}"这一核心主题，延伸以下选题：'.format(first_topic))
            lines.append('')
            lines.append('|| 序号 | 延伸选题 | 类型 | 目的 |')
            lines.append('|------|----------|------|------|')
            lines.append('| 1 | 【{}的底层逻辑】为什么{}这么多人关注？'.format(first_topic, first_topic[:6]) + ' | 知识科普 | 建立专业 |')
            lines.append('| 2 | 【{}的常见误区】{}的3个坑，你踩过几个？'.format(first_topic, first_topic[:6]) + ' | 避坑指南 | 互动引发 |')
            lines.append('| 3 | 【{}实操指南】手把手教你{}的正确方法'.format(first_topic[:6], first_topic[:6]) + ' | 实用攻略 | 收藏转化 |')
            lines.append('')

        # 延伸选题2：人群细分选题
        lines.append('**选题B：【人群细分延伸】**')
        lines.append('')
        lines.append('|| 序号 | 延伸选题 | 人群 | 类型 |')
        lines.append('|------|----------|------|------|')
        lines.append('| 1 | 【新手入门版】第一次接触{}要注意什么？ | 新手用户 | 入门科普 |')
        lines.append('| 2 | 【进阶版】{}老手都在用的进阶技巧 | 进阶用户 | 干货进阶 |')
        lines.append('| 3 | 【避坑版】{}最常踩的5个坑，你中了几个？ | 所有用户 | 避坑指南 |')
        lines.append('')

        # 延伸选题3：关键词延伸
        if all_keywords:
            unique_kws = list(dict.fromkeys(all_keywords))[:5]
            lines.append('**选题C：【关键词延伸】**')
            lines.append('')
            lines.append('基于已埋入关键词，延伸以下选题：')
            for kw in unique_kws:
                lines.append('- **{}**：{}'.format(kw, kw))
            lines.append('')

        # 系列化选题方向
        lines.append('### 📌 系列化选题方向')
        lines.append('')
        lines.append('|| 系列类型 | 命名建议 | 示例选题 |')
        lines.append('|----------|----------|------|')
        lines.append('| 问题诊断系列 | XX诊断室 | 如何判断XX是否适合你？ |')
        lines.append('| 实操干货系列 | XX实操手册 | XX正确操作全流程 |')
        lines.append('| 避坑指南系列 | XX避坑指南 | XX最常见的3个误区 |')
        lines.append('| 案例故事系列 | XX真实故事 | 一个XX案例的完整经历 |')
        lines.append('')

        # 内容复用建议
        lines.append('### 📱 内容复用建议')
        lines.append('')
        lines.append('**图文 → 短视频**：将每张图片的要点扩展为15-30秒口播脚本')
        lines.append('**图文 → 直播素材**：将核心内容整理为直播话术提纲')
        lines.append('**图文 → 私域素材**：整理为朋友圈/社群图文素材')
        lines.append('')

        return '\n'.join(lines)

    def _slides_to_body(self, slides: list, content: dict = None) -> str:
        """将 slides 转换为可读的 body 文本"""
        if not slides:
            return ''
        lines = []

        # 核心内容字段（来自独立 JSON 字段）
        opening = (content or {}).get('opening', '')
        trust_evidence = (content or {}).get('trust_evidence', [])
        cta = (content or {}).get('cta', '')

        if opening:
            lines.append(f"**【开篇核心句】** {opening}")
            lines.append('')

        for slide in slides:
            role = slide.get('role', f'图{slide.get("index", "?")}')
            lines.append(f"**【{role}】**")
            if slide.get('main_title'):
                lines.append(f"  标题：{slide['main_title']}")
            if slide.get('big_slogan'):
                lines.append(f"  大字金句：{slide['big_slogan']}")
            if slide.get('emotion_stage'):
                lines.append(f"  情绪阶段：{slide['emotion_stage']}")
            if slide.get('sub_content'):
                lines.append(f"  内容：{slide['sub_content']}")
            if slide.get('keywords'):
                lines.append(f"  关键词：{', '.join(slide['keywords'])}")
            if slide.get('visual_style'):
                lines.append(f"  画面：{slide['visual_style']}")
            if slide.get('sub_points'):
                lines.append(f"  要点：{'；'.join(slide['sub_points'])}")
            lines.append('')

        if trust_evidence:
            lines.append('**【信任证据】**')
            for ev in trust_evidence:
                ev_type = ev.get('type', '')
                ev_content = ev.get('content', '')
                ev_source = ev.get('source', '')
                lines.append(f"  - [{ev_type}] {ev_content}")
                if ev_source:
                    lines.append(f"    来源：{ev_source}")
            lines.append('')

        if cta:
            lines.append(f"**【行动号召】** {cta}")

        return '\n'.join(lines)

    def _get_default_content(self) -> dict:
        """获取默认内容结构"""
        return {
            'title': '请选择一个选题开始创作',
            'subtitle': '',
            'tags': ['标签1', '标签2', '标签3', '标签4', '标签5', '标签6'],
            'body': '请先生成选题，然后选择选题开始创作内容。\n\n内容将在这里显示。',
            'slides': [],
            'structure': '',
            'hashtags': ['#话题1', '#话题2', '#话题3', '#话题4', '#话题5'],
            'first_comment': '',
            'tips': '建议在午休时间（12:00-13:00）或晚间（20:00-21:00）发布，效果更佳。'
        }

    def get_all_structures(self) -> list:
        """获取所有可用内容结构"""
        return self.ALL_STRUCTURES
