"""
温度词库服务

提供内容温度提升所需的词库支持：
1. 情绪词库（按强度分级）
2. 人设专属词库
3. 人设角度模板
4. 金句模板库
"""

from typing import Dict, List, Optional, Any


class TemperatureWordLibrary:
    """温度词库管理器"""

    # ── 情绪词库（按强度分级）──
    HIGH_EMOTION = [
        '崩溃', '哭死', '救命', '扎心', '破防', '笑死',
        '炸裂', '绝了', '太牛了', '惊艳', '神了', '跪了',
        '哭晕', '笑抽', '裂开', '逆天', 'YYDS', '绝绝子'
    ]

    MEDIUM_EMOTION = [
        '太难了', '没想到', '幸好', '其实', '终于',
        '终于知道了', '没想到', '突然发现', '才发现',
        '原来如此', '真的太', '简直', '居然', '竟然'
    ]

    LOW_EMOTION = [
        '有点', '可能', '建议', '可以', '试试',
        '大概', '也许', '基本上', '通常', '一般'
    ]

    # ── 人设专属词库 ──
    PERSONA_WORDS = {
        '陪伴者': {
            'keywords': ['焦虑', '迷茫', '担心', '崩溃', '扎心', '破防', '纠结', '困扰', '压力', '疲惫'],
            'phrases': [
                '我懂你的焦虑',
                '别担心，有我在',
                '你是不是也这样',
                '感同身受',
                '抱抱你',
                '真的不容易'
            ],
            'opening_hooks': [
                '你最近是不是也有点{}',
                '有没有觉得{}',
                '{}的困扰，你中招了吗',
                '如果你也{}，看过来'
            ]
        },
        '教导者': {
            'keywords': ['干货', '技巧', '秘诀', '方法', '指南', '攻略', '步骤', '诀窍', '要点', '核心'],
            'phrases': [
                '今天分享{}个技巧',
                '学会这{}招，{}',
                '{}的正确姿势',
                '保姆级{}教程',
                '{}必看指南'
            ],
            'opening_hooks': [
                '手把手教你{}',
                '{}的正确方法',
                '只需{}步，{}',
                '学会这{}点，{}'
            ]
        },
        '崇拜者': {
            'keywords': ['种草', '强推', '绝了', '太牛了', '惊艳', '神了', '宝藏', 'YYDS', '封神', '炸裂'],
            'phrases': [
                '我真的太爱了',
                '救命{}也太绝了吧',
                '姐妹们给我冲',
                '用了{}之后真的',
                '这{}谁用谁知道',
                '不允许你们不知道'
            ],
            'opening_hooks': [
                '救命！这个{}也太',
                '姐妹们！发现了一个宝藏',
                '我宣布{}是yyds',
                '用了{}，真的绝'
            ]
        },
        '陪衬者': {
            'keywords': ['笑死', '哈哈', '太真实', '我也有过', '社死', '翻车', '踩雷', '打脸', '破功', '翻车'],
            'phrases': [
                '笑死，这个{}太真实了',
                '我当初也{}',
                '没想到{}，直接社死',
                '踩了{}的坑',
                '说出来你可能不信，我{}'
            ],
            'opening_hooks': [
                '笑死，我之前{}',
                '家人们，{}了怎么办',
                '说出来你可能不信，我{}',
                '踩坑{}，求安慰'
            ]
        },
        '搞笑者': {
            'keywords': ['笑死', '绝了', '炸裂', '破防', '笑到', '离谱', '搞笑', '段子', '反转', '意外'],
            'phrases': [
                '笑到肚子疼',
                '这也太{}了吧',
                '{}到怀疑人生',
                '谁能想到{}',
                '这波{}在大气层'
            ],
            'opening_hooks': [
                '{}，结果{}',
                '我以为{}，没想到',
                '当我{}的时候',
                '{}，反转来了'
            ]
        }
    }

    # ── 五种人设角度模板 ──
    PERSONA_ANGLES = {
        '陪伴者': [
            '{target}的困扰，我懂你',
            '别慌，{target}问题其实可以这样解决',
            '{target}的焦虑，我感同身受',
            '和{target}一样迷茫过，现在终于明白了'
        ],
        '教导者': [
            '{target}的正确姿势，收藏这一篇就够了',
            '{target}指南（建议收藏）',
            '{target}干货分享，看完少走弯路',
            '关于{target}，你必须知道的{}件事'
        ],
        '崇拜者': [
            '{target}真的太绝了，必须分享给你们',
            '救命！发现了一个{target}宝藏',
            '{target}yyds！用完再也离不开了',
            '求求你们试试这个{target}，绝了'
        ],
        '陪衬者': [
            '{target}翻车实录，笑死我了',
            '我当初也是这么想的，结果{target}',
            '关于{target}，我踩过的坑你们别踩',
            '说出来你可能不信，我{target}了'
        ],
        '搞笑者': [
            '{target}，结果反转来了',
            '当我以为自己{target}的时候',
            '这{target}，离谱到家了',
            '{target}迷惑行为大赏'
        ]
    }

    # ── 金句模板库（按人设分类）──
    GOLDEN_QUOTE_TEMPLATES = {
        '陪伴者': [
            '别怕，你不是一个人',
            '我懂你的不容易',
            '慢慢来，一切都会好的',
            '你已经很棒了',
            '抱抱，辛苦了'
        ],
        '教导者': [
            '记住这{}点，你就是专家',
            '这{}个方法，{}人都在用',
            '学会了你也能{}',
            '{}的正确姿势，建议收藏'
        ],
        '崇拜者': [
            '这个{}我要吹爆！',
            '真的绝绝子，太爱了',
            '宝藏{}必须分享给你们',
            '用完{}，再也离不开了'
        ],
        '陪衬者': [
            '笑死，说的是不是你',
            '我当初也是这样',
            '太真实了，膝盖给你',
            '感同身受，抱抱'
        ],
        '搞笑者': [
            '笑不活了家人们',
            '这波操作在大气层',
            '离谱他妈给离谱开门',
            '笑到打鸣'
        ]
    }

    # ── 三要素词库 ──
    ELEMENTS_WORDS = {
        '有趣': {
            'adjectives': ['搞笑', '幽默', '意外', '反转', '离谱', '奇葩', '神转折'],
            'patterns': ['笑死', '绝了', '没想到', '炸裂', '破防'],
            'emotions': ['惊喜', '意外', '搞笑', '调侃']
        },
        '有用': {
            'adjectives': ['实用', '干货', '有效', '高效', '简单', '详细'],
            'patterns': ['收藏', '干货', '攻略', '指南', '教程', '技巧'],
            'emotions': ['收获感', '满足感', '成就感']
        },
        '有共鸣': {
            'adjectives': ['真实', '扎心', '共情', '感同身受', '戳心'],
            'patterns': ['我懂', '感同身受', '太真实', '破防', '戳心窝'],
            'emotions': ['被理解', '被认同', '温暖', '治愈']
        }
    }

    # ── 开篇5秒切入模板 ──
    OPENING_HOOKS = {
        'direct_answer': [
            '直接告诉你答案：{}',
            '{}的正确方法只有这一个',
            '关于{}，看这一篇就够了'
        ],
        'question': [
            '{}的人，有多少？',
            '你是不是也有{}的困扰',
            '{}了怎么办'
        ],
        'shock': [
            '没想到{}竟然能{}',
            '{}了这么多年，今天才知道',
            '这个{}，我后悔没早点知道'
        ],
        'empathy': [
            '{}的痛苦，我懂',
            '如果你也{}，看过来',
            '曾经{}的我，现在终于{}'
        ]
    }

    # ── CTA情感强度模板 ──
    CTA_TEMPLATES = {
        'strong': [
            '赶紧收藏！不然找不到了',
            '强烈建议收藏+转发',
            '求求你们一定要试试',
            '错过真的会后悔！'
        ],
        'medium': [
            '觉得有用就点个赞吧',
            '收藏起来慢慢看',
            '你们觉得怎么样？'
        ],
        'soft': [
            '仅供参考哦',
            '大家可以试试看',
            '有其他想法评论区见'
        ]
    }

    @classmethod
    def get_persona_keywords(cls, persona_type: str) -> List[str]:
        """获取指定人设的情绪关键词"""
        persona_data = cls.PERSONA_WORDS.get(persona_type, {})
        return persona_data.get('keywords', [])

    @classmethod
    def get_persona_phrases(cls, persona_type: str) -> List[str]:
        """获取指定人设的常用短语"""
        persona_data = cls.PERSONA_WORDS.get(persona_type, {})
        return persona_data.get('phrases', [])

    @classmethod
    def get_persona_hooks(cls, persona_type: str) -> List[str]:
        """获取指定人设的开篇钩子"""
        persona_data = cls.PERSONA_WORDS.get(persona_type, {})
        return persona_data.get('opening_hooks', [])

    @classmethod
    def get_persona_angles(cls, persona_type: str) -> List[str]:
        """获取指定人设的角度模板"""
        return cls.PERSONA_ANGLES.get(persona_type, [])

    @classmethod
    def get_golden_quotes(cls, persona_type: str) -> List[str]:
        """获取指定人设的金句模板"""
        return cls.GOLDEN_QUOTE_TEMPLATES.get(persona_type, [])

    @classmethod
    def get_emotion_words_by_intensity(cls, intensity: str) -> List[str]:
        """按强度获取情绪词"""
        intensity_map = {
            'high': cls.HIGH_EMOTION,
            'medium': cls.MEDIUM_EMOTION,
            'low': cls.LOW_EMOTION
        }
        return intensity_map.get(intensity, cls.MEDIUM_EMOTION)

    @classmethod
    def get_element_words(cls, element: str) -> Dict[str, List[str]]:
        """获取指定要素的词库"""
        return cls.ELEMENTS_WORDS.get(element, {})

    @classmethod
    def get_opening_hooks(cls, hook_type: str = None) -> List[str]:
        """获取开篇钩子，支持指定类型"""
        if hook_type:
            return cls.OPENING_HOOKS.get(hook_type, [])
        all_hooks = []
        for hooks in cls.OPENING_HOOKS.values():
            all_hooks.extend(hooks)
        return all_hooks

    @classmethod
    def get_cta_templates(cls, intensity: str = 'medium') -> List[str]:
        """获取CTA模板，支持指定强度"""
        return cls.CTA_TEMPLATES.get(intensity, cls.CTA_TEMPLATES['medium'])

    @classmethod
    def build_temperature_prompt_context(
        cls,
        persona_type: str,
        target_elements: List[str],
        intensity: str = 'high'
    ) -> str:
        """
        构建温度Prompt上下文

        Args:
            persona_type: 人设类型
            target_elements: 目标要素列表 ["有趣", "有用", "有共鸣"]
            intensity: 情绪强度 high/medium/low

        Returns:
            str: 温度Prompt上下文
        """
        context_parts = []

        # 人设词库
        keywords = cls.get_persona_keywords(persona_type)
        phrases = cls.get_persona_phrases(persona_type)
        context_parts.append(f"人设【{persona_type}】关键词：{', '.join(keywords[:5])}")
        context_parts.append(f"人设【{persona_type}】常用语：{', '.join(phrases[:3])}")

        # 三要素词库
        element_words = []
        for element in target_elements:
            words = cls.get_element_words(element)
            if words:
                element_words.append(f"{element}：{', '.join(words.get('patterns', [])[:5])}")
        if element_words:
            context_parts.append("三要素词库：" + " | ".join(element_words))

        # 情绪词
        emotion_words = cls.get_emotion_words_by_intensity(intensity)
        context_parts.append(f"情绪词（{intensity}强度）：{', '.join(emotion_words[:10])}")

        return "\n".join(context_parts)

    @classmethod
    def get_all_persona_types(cls) -> List[Dict[str, str]]:
        """获取所有可选人设类型"""
        return [
            {'key': '陪伴者', 'icon': '👥', 'desc': '温暖、理解、共情', 'color': '#FF9EAA'},
            {'key': '教导者', 'icon': '📚', 'desc': '专业、权威、可复制', 'color': '#7EC8E3'},
            {'key': '崇拜者', 'icon': '✨', 'desc': '展示优越感、强烈推荐', 'color': '#FFD93D'},
            {'key': '陪衬者', 'icon': '😂', 'desc': '自嘲、低姿态、共鸣', 'color': '#C9B1FF'},
            {'key': '搞笑者', 'icon': '🎭', 'desc': '幽默、反转、娱乐', 'color': '#98DDCA'}
        ]

    @classmethod
    def get_all_element_types(cls) -> List[Dict[str, Any]]:
        """获取所有可选要素类型"""
        return [
            {
                'key': '有趣',
                'icon': '🎉',
                'desc': '意外感+快乐',
                'keywords': cls.ELEMENTS_WORDS.get('有趣', {}).get('patterns', []),
                'color': '#FF6B6B'
            },
            {
                'key': '有用',
                'icon': '💡',
                'desc': '干货+可执行',
                'keywords': cls.ELEMENTS_WORDS.get('有用', {}).get('patterns', []),
                'color': '#4ECDC4'
            },
            {
                'key': '有共鸣',
                'icon': '💕',
                'desc': '被理解+情感连接',
                'keywords': cls.ELEMENTS_WORDS.get('有共鸣', {}).get('patterns', []),
                'color': '#FFE66D'
            }
        ]


# 全局实例
temperature_word_library = TemperatureWordLibrary()
