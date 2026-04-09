"""
短视频脚本生成服务

支持10种短视频脚本结构：
1. 痛点共鸣型 - 开场戳痛点，引发共鸣
2. 疑问揭秘型 - 提出问题，逐步揭秘
3. 故事叙述型 - 讲述真实经历/故事
4. 对比冲击型 - 错误vs正确，强烈对比
5. 知识科普型 - 专业内容趣味化
6. 场景演示型 - 现场展示/操作
7. 效果展示型 - 前后对比/使用效果
8. 数字清单型 - 数字抓眼球，逐条讲解
9. 情感共鸣型 - 情感触动，引发转发
10. 时效热点型 - 蹭热点，引关注
"""

import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from services.llm import get_llm_service


class VideoScriptGenerator:
    """短视频脚本生成器"""

    # 10种短视频脚本结构
    SCRIPT_STRUCTURES = [
        {
            'id': 'pain_resonance',
            'name': '痛点共鸣型',
            'duration': '30-60秒',
            'slides': 4,
            'desc': '开场戳痛点→引发共鸣→分析原因→解决方案',
            'structure': '痛点开场(3秒) → 痛点描述(15秒) → 原因分析(15秒) → 解决方案(15秒) → CTA(3秒)',
            'best_for': ['痛点解决', '经验分享'],
            'keywords': ['崩溃', '扎心', '终于', '终于明白', '太难了'],
            'hook_type': '痛点钩子',
            'template': '''
【痛点共鸣型脚本模板】

开场钩子（0-3秒）：
- 口播：直接说出用户痛点
- 画面：真人出镜，表情凝重

痛点描述（3-18秒）：
- 口播：描述具体场景和感受
- 画面：真实场景或素材混剪

原因分析（18-33秒）：
- 口播：分析为什么会有这个问题
- 画面：字幕配合讲解

解决方案（33-48秒）：
- 口播：给出具体解决方法
- 画面：产品/服务展示

行动引导（48-60秒）：
- 口播：引导关注/点赞/评论
- 画面：品牌露出
'''
        },
        {
            'id': 'question_reveal',
            'name': '疑问揭秘型',
            'duration': '45-90秒',
            'slides': 5,
            'desc': '抛出疑问→制造悬念→逐步揭秘→给出答案',
            'structure': '提问(5秒) → 悬念(10秒) → 揭秘(20秒) → 分析(15秒) → 总结(10秒)',
            'best_for': ['知识科普', '原因分析', '行业揭秘'],
            'keywords': ['为什么', '真相', '揭秘', '原来', '才知道'],
            'hook_type': '疑问钩子',
            'template': '''
【疑问揭秘型脚本模板】

抛出问题（0-5秒）：
- 口播：你知道XXX吗？
- 画面：疑问表情或字幕

制造悬念（5-15秒）：
- 口播：很多人都在问这个问题
- 画面：评论区截图或搜索截图

逐步揭秘（15-35秒）：
- 口播：今天我来告诉你真相
- 画面：素材配合讲解

深入分析（35-50秒）：
- 口播：背后的原理是这样
- 画面：图解或数据展示

总结收尾（50-60秒）：
- 口播：记住了吗？关注我了解更多
- 画面：品牌露出
'''
        },
        {
            'id': 'story_narrative',
            'name': '故事叙述型',
            'duration': '60-120秒',
            'slides': 6,
            'desc': '背景铺垫→冲突升级→转折点→解决方案→感悟总结',
            'structure': '引入(10秒) → 冲突(20秒) → 转折(15秒) → 解决(20秒) → 感悟(15秒)',
            'best_for': ['经验分享', '情感故事', '效果展示'],
            'keywords': ['我的', '真实经历', '分享', '故事', '曾经'],
            'hook_type': '故事钩子',
            'template': '''
【故事叙述型脚本模板】

背景引入（0-10秒）：
- 口播：我是怎么接触到这件事的
- 画面：时间线或环境交代

冲突升级（10-30秒）：
- 口播：遇到了什么问题，有多严重
- 画面：情景再现或素材展示

转折点（30-45秒）：
- 口播：直到我发现了/用了XXX
- 画面：产品/方法出现

解决方案（45-65秒）：
- 口播：具体是怎么做的，效果如何
- 画面：操作过程或效果展示

感悟总结（65-80秒）：
- 口播：我的感悟和建议
- 画面：总结字幕或金句

行动引导（80-90秒）：
- 口播：你们有没有类似经历？评论区聊聊
- 画面：引导互动
'''
        },
        {
            'id': 'comparison_shock',
            'name': '对比冲击型',
            'duration': '30-60秒',
            'slides': 5,
            'desc': '错误做法→后果展示→正确做法→效果对比→推荐引导',
            'structure': '错误展示(10秒) → 后果(10秒) → 正确做法(15秒) → 对比(10秒) → CTA(5秒)',
            'best_for': ['对比选型', '避坑指南', '选购指南'],
            'keywords': ['千万别', '别再', '错', '区别', '对比'],
            'hook_type': '警告钩子',
            'template': '''
【对比冲击型脚本模板】

错误展示（0-10秒）：
- 口播：90%的人都在用这种方法
- 画面：错误操作或产品展示

后果展示（10-20秒）：
- 口播：但这样做的后果是XXX
- 画面：负面效果展示

正确做法（20-35秒）：
- 口播：正确的方式应该是这样
- 画面：正确操作演示

效果对比（35-45秒）：
- 口播：对比一下，效果差距有多大
- 画面：分屏对比展示

推荐引导（45-50秒）：
- 口播：按照这个方法，你也能做到
- 画面：产品/服务推荐

行动引导（50-60秒）：
- 口播：收藏起来慢慢看
- 画面：引导收藏
'''
        },
        {
            'id': 'knowledge_popularize',
            'name': '知识科普型',
            'duration': '45-90秒',
            'slides': 5,
            'desc': '冷知识引入→原理讲解→实际应用→误区提醒→总结收藏',
            'structure': '引入(5秒) → 原理(20秒) → 应用(15秒) → 误区(10秒) → 总结(10秒)',
            'best_for': ['知识科普', '原因分析'],
            'keywords': ['冷知识', '真相', '原理', '秘密', '大多数人不知道'],
            'hook_type': '知识钩子',
            'template': '''
【知识科普型脚本模板】

冷知识引入（0-5秒）：
- 口播：你知道吗？90%的人都不知道这个
- 画面：惊讶表情或数据图

原理解释（5-25秒）：
- 口播：它背后的原理是XXX
- 画面：图解、动画或白板讲解

实际应用（25-40秒）：
- 口播：知道了这个原理，你可以XXX
- 画面：实际应用场景

常见误区（40-50秒）：
- 口播：但要注意，大多数人都会犯这个错
- 画面：错误示例

总结收藏（50-60秒）：
- 口播：觉得有用的点个赞，收藏起来
- 画面：总结要点
'''
        },
        {
            'id': 'scene_demo',
            'name': '场景演示型',
            'duration': '30-90秒',
            'slides': 4,
            'desc': '场景还原→问题痛点→解决方案→效果展示',
            'structure': '场景(10秒) → 问题(15秒) → 方案(20秒) → 效果(15秒)',
            'best_for': ['效果展示', '痛点解决', '实操技巧'],
            'keywords': ['现场', '操作', '教你', '演示', '手把手'],
            'hook_type': '实操钩子',
            'template': '''
【场景演示型脚本模板】

场景还原（0-10秒）：
- 口播：这个问题是不是也困扰着你？
- 画面：真实场景拍摄

问题痛点（10-25秒）：
- 口播：很多人都会遇到这种情况
- 画面：问题展示

解决方案（25-45秒）：
- 口播：看我怎么操作的
- 画面：一镜到底的操作演示

效果展示（45-60秒）：
- 口播：看，这就是最终效果
- 画面：前后对比或成品展示

行动引导（60秒+）：
- 口播：学会了就给我点个赞
- 画面：引导互动
'''
        },
        {
            'id': 'effect_showcase',
            'name': '效果展示型',
            'duration': '30-60秒',
            'slides': 4,
            'desc': 'Before展示→问题严重→After展示→对比震撼→推荐',
            'structure': 'Before(10秒) → 问题(10秒) → After(15秒) → 对比(10秒) → CTA(5秒)',
            'best_for': ['效果验证', '效果展示', '痛点解决'],
            'keywords': ['前后对比', '变化', '效果', '见证', '真实'],
            'hook_type': '效果钩子',
            'template': '''
【效果展示型脚本模板】

Before展示（0-10秒）：
- 口播：这是之前XXX的样子
- 画面：使用前状态展示

问题严重（10-20秒）：
- 口播：当时有多严重，你看看
- 画面：问题细节特写

After展示（20-35秒）：
- 口播：用了这个方法之后，变成了这样
- 画面：使用后状态展示

对比震撼（35-45秒）：
- 口播：前后对比，差距太大了
- 画面：分屏对比

推荐引导（45-50秒）：
- 口播：这个方法我推荐给你们
- 画面：产品/方法露出
'''
        },
        {
            'id': 'number_list',
            'name': '数字清单型',
            'duration': '45-90秒',
            'slides': 6,
            'desc': '数字抓眼球→逐条讲解→总结升华→行动引导',
            'structure': '开场(5秒) → 第N条(10秒×N) → 总结(10秒) → CTA(5秒)',
            'best_for': ['数字清单', '步骤流程', '知识科普'],
            'keywords': ['技巧', '方法', '清单', '注意', '学会'],
            'hook_type': '数字钩子',
            'template': '''
【数字清单型脚本模板】

开场抓眼球（0-5秒）：
- 口播：学会这N个技巧，XXX轻松搞定
- 画面：数字放大字幕

逐条讲解（5-X秒）：
- 口播：第1个，XXX（具体内容）
- 画面：序号字幕 + 内容展示
- 循环：第2个...第3个...

总结升华（最后15秒）：
- 口播：记住这几点，你也能XXX
- 画面：要点总结

行动引导（最后5秒）：
- 口播：收藏起来慢慢学
- 画面：引导收藏
'''
        },
        {
            'id': 'emotional_resonance',
            'name': '情感共鸣型',
            'duration': '45-120秒',
            'slides': 5,
            'desc': '情感触发→场景共鸣→情绪释放→温暖收尾',
            'structure': '情感触发(10秒) → 场景共鸣(25秒) → 情绪释放(20秒) → 温暖收尾(15秒)',
            'best_for': ['情感故事', '经验分享'],
            'keywords': ['扎心', '泪目', '感动', '破防', '共鸣'],
            'hook_type': '情感钩子',
            'template': '''
【情感共鸣型脚本模板】

情感触发（0-10秒）：
- 口播：（稍停顿）你有没有经历过XXX
- 画面：慢镜头或情感素材

场景共鸣（10-35秒）：
- 口播：那种感觉，只有经历过的人才懂
- 画面：情感场景还原

情绪释放（35-55秒）：
- 口播：但是，现在不一样了，因为我遇到了XXX
- 画面：情绪转折

温暖收尾（55-70秒）：
- 口播：希望每一个XXX的人，都能XXX
- 画面：金句字幕 + 温暖画面

行动引导（70秒+）：
- 口播：说出你的故事，评论区聊聊
- 画面：引导评论
'''
        },
        {
            'id': 'hot_topic',
            'name': '时效热点型',
            'duration': '30-60秒',
            'slides': 4,
            'desc': '热点切入→观点输出→专业分析→价值提供',
            'structure': '热点(5秒) → 观点(15秒) → 分析(15秒) → 价值(10秒)',
            'best_for': ['节日营销', '季节营销', '热点事件'],
            'keywords': ['最新', '刚刚', '突发', '热搜', '爆了'],
            'hook_type': '热点钩子',
            'template': '''
【时效热点型脚本模板】

热点切入（0-5秒）：
- 口播：刚刚热搜上的XXX，你看到了吗？
- 画面：热搜截图或新闻画面

观点输出（5-20秒）：
- 口播：我觉得，这件事背后反映的是XXX
- 画面：本人出镜讲解

专业分析（20-35秒）：
- 口播：从专业角度分析，原因是这样的
- 画面：数据或案例展示

价值提供（35-45秒）：
- 口播：对你来说，这意味着XXX，你应该XXX
- 画面：建议字幕

行动引导（45-50秒）：
- 口播：对这个话题你怎么看？评论区说说
- 画面：引导评论
'''
        }
    ]

    # Token消耗估算
    TOKEN_ESTIMATE = {
        'prompt': 1500,
        'completion': 2500,
        'total': 4000
    }

    def __init__(self):
        self.llm = get_llm_service()

    def generate_script(
        self,
        topic_title: str,
        topic_type: str,
        business_description: str,
        portrait: dict,
        content_direction: str = '种草型',
        structure_id: str = None,
        content_style: str = ''
    ) -> dict:
        """
        生成短视频脚本

        Args:
            topic_title: 选题标题
            topic_type: 选题类型
            business_description: 业务描述
            portrait: 用户画像
            content_direction: 内容方向（种草型/转化型）
            structure_id: 指定结构ID（可选，默认AI自动选择）
            content_style: 内容风格

        Returns:
            {
                "success": bool,
                "script": {...},
                "tokens_used": int
            }
        """
        try:
            # 确定使用哪种结构
            if structure_id:
                structure = self._get_structure_by_id(structure_id)
            else:
                structure = self._select_best_structure(topic_type, content_direction)

            # 构建Prompt
            prompt = self._build_script_prompt(
                topic_title=topic_title,
                topic_type=topic_type,
                business_description=business_description,
                portrait=portrait,
                structure=structure,
                content_direction=content_direction,
                content_style=content_style
            )

            # 调用LLM生成
            messages = [
                {"role": "system", "content": "你是一位资深的短视频编导，精通抖音/快手/视频号内容创作。必须严格按照JSON格式输出。"},
                {"role": "user", "content": prompt}
            ]
            response = self.llm.chat(messages)

            # 解析结果
            script = self._parse_script_response(response)

            # 合并结构信息
            script['structure'] = structure
            script['structure_name'] = structure['name']

            return {
                'success': True,
                'script': script,
                'tokens_used': self.TOKEN_ESTIMATE['total']
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def generate_content(
        self,
        topic_title: str,
        topic_type: str,
        business_description: str,
        portrait: dict,
        content_style: str = ''
    ) -> dict:
        """
        生成短视频脚本（generate_script 的别名，支持 content_style 参数）

        Args:
            topic_title: 选题标题
            topic_type: 选题类型
            business_description: 业务描述
            portrait: 用户画像
            content_style: 内容风格（情绪共鸣/干货科普/犀利吐槽/故事叙述/权威背书）

        Returns:
            {
                "success": bool,
                "content": {...},
                "tokens_used": int
            }
        """
        # 根据 content_style 推导 content_direction
        style_to_direction = {
            '情绪共鸣': '种草型',
            '干货科普': '种草型',
            '犀利吐槽': '种草型',
            '故事叙述': '种草型',
            '权威背书': '转化型',
        }
        content_direction = style_to_direction.get(content_style, '种草型')

        result = self.generate_script(
            topic_title=topic_title,
            topic_type=topic_type,
            business_description=business_description,
            portrait=portrait,
            content_direction=content_direction,
        )

        # 统一返回格式
        if result.get('success'):
            return {
                'success': True,
                'content': result.get('script', {}),
                'tokens_used': result.get('tokens_used', 0),
            }
        else:
            return {
                'success': False,
                'error': result.get('error', '生成失败'),
            }

    def _select_best_structure(self, topic_type: str, content_direction: str) -> Dict:
        """根据选题类型和内容方向选择最佳结构"""
        # 先找最匹配的结构
        for structure in self.SCRIPT_STRUCTURES:
            if topic_type in structure['best_for']:
                return structure

        # 默认返回痛点共鸣型
        return self.SCRIPT_STRUCTURES[0]

    def _get_structure_by_id(self, structure_id: str) -> Optional[Dict]:
        """根据ID获取结构"""
        for structure in self.SCRIPT_STRUCTURES:
            if structure['id'] == structure_id:
                return structure
        return None

    def _build_script_prompt(
        self,
        topic_title: str,
        topic_type: str,
        business_description: str,
        portrait: dict,
        structure: Dict,
        content_direction: str,
        content_style: str = ''
    ) -> str:
        """构建脚本生成Prompt"""

        portrait_info = self._get_portrait_info(portrait)
        current_month = datetime.now().month
        current_season = self._get_current_season()

        # 风格指导
        style_guide = self._get_style_guide(content_style) if content_style else ''

        prompt = f"""你是一位资深的短视频编导。请根据以下信息，生成一个完整的短视频脚本。

## 选题信息
- 选题标题：{topic_title}
- 选题类型：{topic_type}
- 内容方向：{content_direction}

## 业务信息
- 业务描述：{business_description}

## 目标用户画像
{portrait_info}

## 当前时间
- 月份：{current_month}月
- 季节：{current_season}

## 脚本结构：{structure['name']}
{structure['desc']}
结构详情：{structure['structure']}

{style_guide}

## 脚本基础规范
1. **时长**：{structure['duration']}
2. **格式**：竖屏 9:16（1080×1920px）
3. **风格**：口语化、有感染力、真实自然
4. **封面**：前3秒必须最大最醒目，直接抓眼球
5. **BGM建议**：根据内容类型推荐背景音乐风格

## 脚本输出格式（严格JSON）
```json
{{
  "title": "短视频标题（≤20字，戳心）",
  "hook": "开场钩子（3-5秒，吸引停留）",
  "scenes": [
    {{
      "scene": "场景名称",
      "duration": "时长",
      "script": "口播台词/字幕内容",
      "visual": "画面描述",
      "key_point": "关键信息点"
    }},
    ...
  ],
  "cta": "行动号召（关注/评论/收藏）",
  "bgm_suggestion": "背景音乐建议",
  "tips": "拍摄/剪辑注意事项"
}}
```

请严格按照JSON格式输出，不要包含其他内容。"""

        return prompt

    def _get_portrait_info(self, portrait: dict) -> str:
        """获取画像信息"""
        if not portrait:
            return "暂无详细画像信息"

        if isinstance(portrait, dict):
            identity = portrait.get('identity', '')
            pain_point = portrait.get('pain_point', portrait.get('核心痛点', ''))
            concern = portrait.get('concern', portrait.get('核心顾虑', ''))
            scenario = portrait.get('scenario', portrait.get('场景', ''))
            age = portrait.get('age', portrait.get('年龄段', ''))

            info = f"用户身份：{identity}" if identity else ""
            info += f"\n年龄段：{age}" if age else ""
            info += f"\n核心痛点：{pain_point}" if pain_point else ""
            info += f"\n核心顾虑：{concern}" if concern else ""
            info += f"\n使用场景：{scenario}" if scenario else ""

            return info or "暂无详细画像信息"

        return str(portrait)

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
- 开头方式：前3秒用情绪化表达抓住用户
- 句式特点：使用"你是不是也..."、"没想到..."、"原来..."等句式
- 情绪词：焦虑、担心、后悔、迷茫、无奈、可惜、扎心
- 结尾：温暖、希望的解决方案
""",
            '干货科普': """
【风格：干货科普】
- 文案基调：专业、严谨、有深度，信息量大
- 开头方式：用知识点或数据吸引眼球
- 句式特点：使用"3个技巧"、"5个方法"、"核心关键是..."等结构化表达
- 关键词：揭秘、内幕、原理、技巧、方法、步骤、数据
- 结尾：总结要点，提供可操作的方法论
""",
            '犀利吐槽': """
【风格：犀利吐槽】
- 文案基调：反讽、自嘲、打破常规、引发争议
- 开头方式：用反问或颠覆认知的标题吸引眼球
- 句式特点：使用"别再..."、"你以为..."、"XX都是骗人的"等句式
- 情绪词：错误、误区、坑、骗、傻，白花钱、多此一举
- 结尾：反转或给出正确的做法
""",
            '故事叙述': """
【风格：故事叙述】
- 文案基调：叙事性强、画面感强、有代入感
- 开头方式：从一个具体场景或故事开头
- 句式特点：使用"那天..."、"我曾经..."、"朋友告诉我..."等叙事句式
- 关键词：经历、故事、回忆、那一刻、后来、终于
- 结尾：升华主题，总结感悟
""",
            '权威背书': """
【风格：权威背书】
- 文案基调：可信、有说服力、数据支撑
- 开头方式：用权威数据、专家观点、真实案例吸引信任
- 句式特点：使用"研究表明..."、"数据显示..."、"XX专家建议..."等句式
- 关键词：研究、数据、专家、案例、证明、验证、实测
- 结尾：给出权威背书的产品或服务
""",
        }

        return style_guides.get(content_style, '')

    def _parse_script_response(self, response: str) -> dict:
        """解析LLM返回的脚本结果"""
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                script = json.loads(json_str)
                if isinstance(script, dict):
                    return self._validate_script(script)

            return self._get_default_script()

        except Exception as e:
            return self._get_default_script()

    def _validate_script(self, script: dict) -> dict:
        """验证并补充脚本字段"""
        default = self._get_default_script()

        return {
            'title': script.get('title', default['title']),
            'hook': script.get('hook', ''),
            'scenes': script.get('scenes', []),
            'cta': script.get('cta', '觉得有用就点个赞吧！'),
            'bgm_suggestion': script.get('bgm_suggestion', '轻快/励志/温暖'),
            'tips': script.get('tips', ''),
        }

    def _get_default_script(self) -> dict:
        """获取默认脚本结构"""
        return {
            'title': '短视频标题',
            'hook': '开场钩子',
            'scenes': [],
            'cta': '觉得有用就点个赞吧！',
            'bgm_suggestion': '轻快励志',
            'tips': '注意光线和收音'
        }

    def get_structures(self) -> List[Dict]:
        """获取所有脚本结构"""
        return [{
            'id': s['id'],
            'name': s['name'],
            'duration': s['duration'],
            'desc': s['desc'],
            'best_for': s['best_for'],
            'keywords': s['keywords']
        } for s in self.SCRIPT_STRUCTURES]

    def recommend_structure(self, topic_type: str, content_direction: str) -> List[Dict]:
        """推荐适合某选题类型的脚本结构"""
        recommendations = []

        for structure in self.SCRIPT_STRUCTURES:
            if topic_type in structure['best_for']:
                recommendations.append({
                    'id': structure['id'],
                    'name': structure['name'],
                    'duration': structure['duration'],
                    'desc': structure['desc'],
                    'match_score': 0.95
                })
            else:
                recommendations.append({
                    'id': structure['id'],
                    'name': structure['name'],
                    'duration': structure['duration'],
                    'desc': structure['desc'],
                    'match_score': 0.6
                })

        # 按匹配度排序
        recommendations.sort(key=lambda x: x['match_score'], reverse=True)
        return recommendations[:3]


# 全局实例
video_script_generator = VideoScriptGenerator()
