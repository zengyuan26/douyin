# -*- coding: utf-8 -*-
"""
内容素材库维度配置
爆款拆解的分析维度 与 素材库的映射关系
"""

# 爆款拆解所有分析维度
ANALYSIS_DIMENSIONS = {
    'title': {
        'name': '标题',
        'icon': 'bi-card-heading',
        'description': '标题分析',
    },
    'cover': {
        'name': '封面',
        'icon': 'bi-image',
        'description': '封面分析',
    },
    'topic': {
        'name': '选题',
        'icon': 'bi-lightbulb',
        'description': '选题分析',
    },
    'content': {
        'name': '内容',
        'icon': 'bi-text-paragraph',
        'description': '内容结构',
    },
    'psychology': {
        'name': '心理',
        'icon': 'bi-brain',
        'description': '心理分析',
    },
    'commercial': {
        'name': '商业',
        'icon': 'bi-currency-dollar',
        'description': '商业目的',
    },
    'why_popular': {
        'name': '爆款',
        'icon': 'bi-fire',
        'description': '爆款原因',
    },
    'ending': {
        'name': '结尾',
        'icon': 'bi-flag',
        'description': '结尾分析',
    },
    'tags': {
        'name': '标签',
        'icon': 'bi-tags',
        'description': '标签分析',
    },
    'character': {
        'name': '人物',
        'icon': 'bi-person',
        'description': '人物设计',
    },
    'content_form': {
        'name': '形式',
        'icon': 'bi-layout-text-window-reverse',
        'description': '内容形式',
    },
    'interaction': {
        'name': '互动',
        'icon': 'bi-hand-thumbs-up',
        'description': '互动数据',
    },
}

# 分析维度 -> 素材库类型 映射
# 键：分析维度值，值：素材库类型
DIMENSION_TO_MATERIAL_TYPE = {
    'title': 'title',           # 标题 -> 标题库
    'hook': 'hook',             # 钩子（需要单独分析维度） -> 钩子库
    'cover': 'cover',           # 封面 -> 封面库
    'topic': 'topic',           # 选题 -> 选题库
    'content': 'structure',     # 内容 -> 结构库
    'psychology': 'psychology', # 心理 -> 心理库
    'commercial': 'commercial', # 商业 -> 商业库
    'why_popular': 'why_popular', # 爆款 -> 爆款库
    'ending': 'ending',         # 结尾 -> 结尾库
    'tags': 'tags',             # 标签 -> 标签库
    'character': 'character',  # 人物 -> 人物库
    'content_form': 'content_form', # 形式 -> 形式库
    'interaction': 'interaction', # 互动 -> 互动库
}

# 素材库类型配置
MATERIAL_TYPES = {
    'title': {
        'name': '标题库',
        'icon': 'bi-card-heading',
        'table': 'content_titles',
        'model': 'ContentTitle',
        'main_field': 'title',
        'type_field': 'title_type',
        'type_options': ['疑问', '数字', '对比', '情感', '悬念', '命令', '蹭热点', '干货', '故事'],
    },
    'hook': {
        'name': '钩子库',
        'icon': 'bi-lightning',
        'table': 'content_hooks',
        'model': 'ContentHook',
        'main_field': 'hook_content',
        'type_field': 'hook_type',
        'type_options': ['提问', '悬念', '冲突', '数字', '故事', '痛点', '好奇', '否定', '对比'],
    },
    'cover': {
        'name': '封面库',
        'icon': 'bi-image',
        'table': 'content_covers',
        'model': 'ContentCover',
        'main_field': 'cover_content',
        'type_field': 'cover_type',
        'type_options': ['图文', '纯文字', '人物', '产品', '场景', '对比', '情绪', '合集'],
    },
    'topic': {
        'name': '选题库',
        'icon': 'bi-lightbulb',
        'table': 'content_topics',
        'model': 'ContentTopic',
        'main_field': 'topic_content',
        'type_field': 'topic_type',
        'type_options': ['痛点', '痒点', '热点', '干货', '娱乐', '情感', '知识', '评测', '教程', '测评'],
    },
    'structure': {
        'name': '结构库',
        'icon': 'bi-diagram-3',
        'table': 'content_structures',
        'model': 'ContentStructure',
        'main_field': 'structure_name',
        'type_field': 'content_type',
        'type_options': ['视频', '图文', '长文', '直播', '短剧'],
    },
    'psychology': {
        'name': '心理库',
        'icon': 'bi-brain',
        'table': 'content_psychologies',
        'model': 'ContentPsychology',
        'main_field': 'psychology_content',
        'type_field': 'psychology_type',
        'type_options': ['恐惧', '贪婪', '好奇', '从众', '权威', '稀缺', '损失', '认同', '攀比', '情感'],
    },
    'commercial': {
        'name': '商业库',
        'icon': 'bi-currency-dollar',
        'table': 'content_commercials',
        'model': 'ContentCommercial',
        'main_field': 'commercial_content',
        'type_field': 'commercial_type',
        'type_options': ['种草', '带货', '品牌', '引流', '转化', '口碑', '促销', '招商', '加盟'],
    },
    'why_popular': {
        'name': '爆款库',
        'icon': 'bi-fire',
        'table': 'content_why_populars',
        'model': 'ContentWhyPopular',
        'main_field': 'reason_content',
        'type_field': 'reason_type',
        'type_options': ['内容好', '选题好', '时机好', '平台推', '互动高', '转化高', '复盘'],
    },
    'ending': {
        'name': '结尾库',
        'icon': 'bi-flag',
        'table': 'content_endings',
        'model': 'ContentEnding',
        'main_field': 'ending_content',
        'type_field': 'ending_type',
        'type_options': ['引导评论', '引导关注', '引导购买', '引导点赞', '引导收藏', '引导转发', '互动'],
    },
    'tags': {
        'name': '标签库',
        'icon': 'bi-tags',
        'table': 'content_tags',
        'model': 'ContentTag',
        'main_field': 'tag_content',
        'type_field': 'tag_type',
        'type_options': ['话题', '关键词', '品牌', '人物', '场景', '情感', '行为'],
    },
    'character': {
        'name': '人物库',
        'icon': 'bi-person',
        'table': 'content_characters',
        'model': 'ContentCharacter',
        'main_field': 'character_content',
        'type_field': 'character_type',
        'type_options': ['人设', '身份', '角色', '形象', '性格', '语气', '背景'],
    },
    'content_form': {
        'name': '形式库',
        'icon': 'bi-layout-text-window-reverse',
        'table': 'content_forms',
        'model': 'ContentForm',
        'main_field': 'form_content',
        'type_field': 'form_type',
        'type_options': ['口播', '剧情', 'Vlog', '测评', '教程', '知识', '娱乐', '直播', '图文'],
    },
    'interaction': {
        'name': '互动库',
        'icon': 'bi-hand-thumbs-up',
        'table': 'content_interactions',
        'model': 'ContentInteraction',
        'main_field': 'interaction_content',
        'type_field': 'interaction_type',
        'type_options': ['问答', '投票', '挑战', '抽奖', '评论', '连麦', '合拍', '回应'],
    },
}

# 行业选项
INDUSTRY_OPTIONS = [
    '美妆护肤',
    '服装配饰',
    '食品饮料',
    '家居生活',
    '数码电器',
    '母婴育儿',
    '运动健身',
    '医疗健康',
    '教育培训',
    '金融财经',
    '房产汽车',
    '旅游出行',
    '娱乐影视',
    '游戏电竞',
    '宠物萌宠',
    '三农',
    '情感心理',
    '职场社交',
    '知识付费',
    '本地生活',
    '其他',
]

# 分析维度分类体系
# 一级分类：account(账号分析) / content(内容分析) / methodology(方法论)
ANALYSIS_DIMENSION_CATEGORIES = {
    'account': {
        'name': '账号分析',
        'icon': 'bi-person-badge',
        'description': '账号定位、市场分析、运营规划等相关维度',
        'sub_categories': {
            'account_positioning': {
                'name': '账号定位',
                'description': '昵称、头像、简介、背景图等'
            },
            'market_analysis': {
                'name': '市场分析',
                'description': '目标人群、竞品分析、市场趋势'
            },
            'operation_planning': {
                'name': '运营规划',
                'description': '内容策略、发布频率、变现模式'
            },
            'keyword_library': {
                'name': '关键词库',
                'description': '核心关键词、长尾关键词'
            }
        }
    },
    'content': {
        'name': '内容分析',
        'icon': 'bi-file-text',
        'description': '标题、封面、内容结构、视觉设计等相关维度',
        'sub_categories': {
            'title': {
                'name': '标题',
                'description': '标题结构、关键词、情绪词'
            },
            'hook': {
                'name': '开头钩子',
                'description': '悬念型、痛点型、收益型'
            },
            'content_body': {
                'name': '内容',
                'description': '选题、框架、情绪、节奏'
            },
            'visual_design': {
                'name': '视觉设计',
                'description': '封面、构图、配色、字幕'
            },
            'ending': {
                'name': '结尾',
                'description': 'CTA、引导互动'
            }
        }
    },
    'methodology': {
        'name': '方法论',
        'icon': 'bi-book',
        'description': '适用场景、适用人群等方法论相关维度',
        'sub_categories': {
            'applicable_scenario': {
                'name': '适用场景',
                'description': '方法的适用场景'
            },
            'applicable_audience': {
                'name': '适用人群',
                'description': '方法的目标人群'
            }
        }
    }
}

# 分析维度 -> 素材库类型 映射（扩展版）
DIMENSION_TO_MATERIAL_TYPE = {
    'title': 'title',
    'hook': 'hook',
    'cover': 'cover',
    'topic': 'topic',
    'content': 'structure',
    'psychology': 'psychology',
    'commercial': 'commercial',
    'why_popular': 'why_popular',
    'ending': 'ending',
    'tags': 'tags',
    'character': 'character',
    'content_form': 'content_form',
    'interaction': 'interaction',
    # 账号分析维度映射
    'account_positioning': None,
    'market_analysis': None,
    'operation_planning': None,
    'keyword_library': 'tags',
}
