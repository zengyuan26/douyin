"""
画像维度数据定义

供以下模块使用：
1. migrations/init_portrait_dimensions.py - 迁移脚本
2. routes/admin.py - 管理API
3. services/portrait_dimension_service.py - 维度服务

数据结构说明：
- category: 一级分类（固定为 super_positioning）
- sub_category: 子分类，对应不同的维度类型
- prompt_template: 对应内容方向（AI用于映射）
- applicable_audience: 障碍来源（内在/他人/环境）
"""

# 画像维度数据
PORTRAIT_DIMENSIONS_DATA = [
    # ========== 矛盾类型（核心元维度）==========
    {
        'name': '缺失型',
        'category': 'super_positioning',
        'sub_category': 'conflict_type',
        'description': '用户没有/不足某种资源、能力或条件，需要获得',
        'icon': 'bi-dash-circle',
        'examples': '没粉丝、没预算、没知识、没渠道',
        'usage_tips': '描述用户缺少什么 → 获得后能怎样',
        'prompt_template': '解决方案/获取路径'
    },
    {
        'name': '拥有型',
        'category': 'super_positioning',
        'sub_category': 'conflict_type',
        'description': '用户有资源/能力/条件，但不知道怎么有效利用',
        'icon': 'bi-lightning-charge',
        'examples': '1000万粉丝不知道怎么变现、有钱不知道怎么投资、有产品不知道怎么卖',
        'usage_tips': '描述用户拥有什么资源 → 激活/变现方法',
        'prompt_template': '激活路径/变现方法'
    },
    {
        'name': '冲突型',
        'category': 'super_positioning',
        'sub_category': 'conflict_type',
        'description': '用户想要但有顾虑/障碍，意愿和行动之间存在矛盾',
        'icon': 'bi-arrow-left-right',
        'examples': '想要健康但管不住嘴、想要省钱但忍不住花、想要学习但拖延',
        'usage_tips': '描述用户想要什么 + 障碍是什么',
        'prompt_template': '消除障碍/降低门槛'
    },
    {
        'name': '替代型',
        'category': 'super_positioning',
        'sub_category': 'conflict_type',
        'description': '用户有现有方案但效果不好，想要更好的替代',
        'icon': 'bi-arrow-repeat',
        'examples': '用旧奶粉但宝宝不长肉、用旧手机但太卡、换护肤品但没效果',
        'usage_tips': '描述现有方案的问题 + 更好的选择',
        'prompt_template': '升级替代/效果对比'
    },
    {
        'name': '减少型',
        'category': 'super_positioning',
        'sub_category': 'conflict_type',
        'description': '用户想要简化、降低、减少某些东西',
        'icon': 'bi-dash-lg',
        'examples': '太复杂想简化、太多想精简、太贵想降低、太高想减少',
        'usage_tips': '描述用户想减少什么 + 简化方案',
        'prompt_template': '简化方案/精简路径'
    },

    # ========== 转变类型 ==========
    {
        'name': '坏→好',
        'category': 'super_positioning',
        'sub_category': 'transformation_type',
        'description': '从问题状态到正常状态',
        'icon': 'bi-arrow-up-circle',
        'examples': '宝宝腹泻→肠胃健康、生病→康复',
        'prompt_template': '问题解决'
    },
    {
        'name': '无→有',
        'category': 'super_positioning',
        'sub_category': 'transformation_type',
        'description': '从缺失到拥有',
        'icon': 'bi-plus-circle',
        'examples': '不会说话→开口说话、没粉丝→有粉丝',
        'prompt_template': '获取路径'
    },
    {
        'name': '差→好',
        'category': 'super_positioning',
        'sub_category': 'transformation_type',
        'description': '从较差到较好',
        'icon': 'bi-graph-up-arrow',
        'examples': '普通奶粉→优质奶粉、低配→高配',
        'prompt_template': '升级方案'
    },
    {
        'name': '旧→新',
        'category': 'super_positioning',
        'sub_category': 'transformation_type',
        'description': '从旧状态到新状态',
        'icon': 'bi-arrow-right-circle',
        'examples': '旧奶粉→新奶粉、旧手机→新手机',
        'prompt_template': '切换引导'
    },
    {
        'name': '少→多',
        'category': 'super_positioning',
        'sub_category': 'transformation_type',
        'description': '从少到多',
        'icon': 'bi-plus-lg',
        'examples': '奶量不足→奶量充足、粉丝少→粉丝多',
        'prompt_template': '增量方案'
    },
    {
        'name': '高→低',
        'category': 'super_positioning',
        'sub_category': 'transformation_type',
        'description': '从高到低（减少）',
        'icon': 'bi-arrow-down-circle',
        'examples': '过敏严重→脱敏成功、血压高→降低',
        'prompt_template': '降低方案'
    },
    {
        'name': '闲置→激活',
        'category': 'super_positioning',
        'sub_category': 'transformation_type',
        'description': '有资源但不会用 → 有资源且会用',
        'icon': 'bi-lightning',
        'examples': '1000万粉丝不知道怎么变现、有钱不知道怎么投资',
        'prompt_template': '激活路径'
    },
    {
        'name': '模糊→清晰',
        'category': 'super_positioning',
        'sub_category': 'transformation_type',
        'description': '有但不知道怎么用 → 知道怎么用',
        'icon': 'bi-question-circle',
        'examples': '有资源但迷茫、有能力但不会展示',
        'prompt_template': '方法指导'
    },

    # ========== 转变障碍 - 内在 ==========
    {
        'name': '认知',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '不知道正确的方法/知识',
        'icon': 'bi-brain',
        'examples': '不知道怎么转奶、不知道选哪个',
        'applicable_audience': '内在',
        'prompt_template': '科普/教程'
    },
    {
        'name': '资源',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '金钱/时间/精力不足',
        'icon': 'bi-wallet2',
        'examples': '预算不够、太忙没时间',
        'applicable_audience': '内在',
        'prompt_template': '性价比/便捷方案'
    },
    {
        'name': '决策',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '信息太多不知道怎么选',
        'icon': 'bi-list-check',
        'examples': '牌子太多、不知道哪个好',
        'applicable_audience': '内在',
        'prompt_template': '对比/推荐'
    },
    {
        'name': '心理',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '害怕改变后更糟',
        'icon': 'bi-emoji-frown',
        'examples': '担心失败、怕换错了',
        'applicable_audience': '内在',
        'prompt_template': '案例/安慰'
    },
    {
        'name': '代理焦虑',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '买用分离，担心决策伤害使用人',
        'icon': 'bi-shield-exclamation',
        'examples': '不知道我的选择对不对、担心伤害宝宝',
        'applicable_audience': '内在',
        'prompt_template': '专家背书/安全性'
    },
    {
        'name': '拥有型',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '有资源但不知道怎么用',
        'icon': 'bi-lightning-charge',
        'examples': '粉丝多不知道怎么变现、有钱不知道怎么投资',
        'applicable_audience': '内在',
        'prompt_template': '变现方法/激活路径'
    },

    # ========== 转变障碍 - 他人 ==========
    {
        'name': '反对',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '家人觉得没必要/浪费',
        'icon': 'bi-person-x',
        'examples': '老公说不用、婆婆说浪费',
        'applicable_audience': '他人',
        'prompt_template': '权威背书/共识建立'
    },
    {
        'name': '口碑',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '周围人有负面经历',
        'icon': 'bi-megaphone',
        'examples': '朋友说不好用、网上有差评',
        'applicable_audience': '他人',
        'prompt_template': '真实案例/数据'
    },
    {
        'name': '分歧',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '家人之间意见不一致',
        'icon': 'bi-people',
        'examples': '老婆要买老公不让、父母意见不合',
        'applicable_audience': '他人',
        'prompt_template': '共识建立/沟通技巧'
    },
    {
        'name': '社交压力',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '怕被人说/跟别人不一样',
        'icon': 'bi-chat-left-dots',
        'examples': '不好意思、怕被邻居说',
        'applicable_audience': '他人',
        'prompt_template': '社群归属/正面引导'
    },
    {
        'name': '权威影响',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '专业人士/医生说不用',
        'icon': 'bi-bandaid',
        'examples': '医生说不用补、专家说没效果',
        'applicable_audience': '他人',
        'prompt_template': '专业内容/认证'
    },

    # ========== 转变障碍 - 环境 ==========
    {
        'name': '渠道',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '买不到/不方便买',
        'icon': 'bi-shop',
        'examples': '当地没有、不知道哪里买',
        'applicable_audience': '环境',
        'prompt_template': '购买指南/正品渠道'
    },
    {
        'name': '时间',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '没时间了解/行动',
        'icon': 'bi-clock',
        'examples': '工作太忙、没时间研究',
        'applicable_audience': '环境',
        'prompt_template': '便捷方案/省时'
    },
    {
        'name': '条件',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '产品/服务本身有限制',
        'icon': 'bi-slash-circle',
        'examples': '选择少、有门槛限制',
        'applicable_audience': '环境',
        'prompt_template': '替代方案说明'
    },
    {
        'name': '沉没成本',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '舍不得换旧方案',
        'icon': 'bi-hourglass-split',
        'examples': '旧的还剩很多、不想浪费',
        'applicable_audience': '环境',
        'prompt_template': '切换引导/优惠'
    },

    # ========== 转变阶段 ==========
    {
        'name': '转变前',
        'category': 'super_positioning',
        'sub_category': 'change_stage',
        'description': '还没开始，考虑要不要做',
        'icon': 'bi-compass',
        'examples': '时机焦虑、选择焦虑',
        'prompt_template': '时机选择/方案对比'
    },
    {
        'name': '转变中',
        'category': 'super_positioning',
        'sub_category': 'change_stage',
        'description': '正在执行，需要指导',
        'icon': 'bi-arrow-right',
        'examples': '操作焦虑、效果焦虑',
        'prompt_template': '操作指导/效果跟踪'
    },
    {
        'name': '转变后',
        'category': 'super_positioning',
        'sub_category': 'change_stage',
        'description': '已经完成，需要确认/持续',
        'icon': 'bi-check-circle',
        'examples': '效果焦虑、调整焦虑',
        'prompt_template': '效果确认/持续方案'
    },

    # ========== 买用关系 ==========
    {
        'name': '买用一体',
        'category': 'super_positioning',
        'sub_category': 'buyer_user_relationship',
        'description': '付费人和使用人是同一人',
        'icon': 'bi-person',
        'examples': '我给自己买、我自己用',
        'prompt_template': '个人利益导向'
    },
    {
        'name': '保护型',
        'category': 'super_positioning',
        'sub_category': 'buyer_user_relationship',
        'description': '付费人想保护使用人（买用分离）',
        'icon': 'bi-heart',
        'examples': '宝妈买给宝宝、家长买给孩子',
        'prompt_template': '安全性/关爱'
    },
    {
        'name': '孝心型',
        'category': 'super_positioning',
        'sub_category': 'buyer_user_relationship',
        'description': '晚辈给长辈买',
        'icon': 'bi-people-fill',
        'examples': '子女给父母买、孙子给爷爷奶奶买',
        'prompt_template': '孝心表达/健康'
    },
    {
        'name': '责任型',
        'category': 'super_positioning',
        'sub_category': 'buyer_user_relationship',
        'description': '因责任而购买',
        'icon': 'bi-briefcase',
        'examples': '公司给员工买福利、老板给客户买礼品',
        'prompt_template': '责任/便利'
    },

    # ========== 内容类型 ==========
    {
        'name': '科普',
        'category': 'super_positioning',
        'sub_category': 'content_type',
        'description': '告诉你为什么/是什么',
        'icon': 'bi-book',
        'examples': '为什么会这样、是什么原理',
        'prompt_template': '原因/原理'
    },
    {
        'name': '教程',
        'category': 'super_positioning',
        'sub_category': 'content_type',
        'description': '告诉你怎么做',
        'icon': 'bi-list-ol',
        'examples': '步骤1、步骤2、步骤3',
        'prompt_template': '方法/步骤'
    },
    {
        'name': '对比',
        'category': 'super_positioning',
        'sub_category': 'content_type',
        'description': '告诉你选哪个',
        'icon': 'bi-bar-chart',
        'examples': 'A和B哪个好、有什么区别',
        'prompt_template': '对比分析'
    },
    {
        'name': '推荐',
        'category': 'super_positioning',
        'sub_category': 'content_type',
        'description': '帮你做决定',
        'icon': 'bi-hand-thumbs-up',
        'examples': '推荐这个、直接选这个',
        'prompt_template': '决策支持'
    },
    {
        'name': '背书',
        'category': 'super_positioning',
        'sub_category': 'content_type',
        'description': '告诉你信谁',
        'icon': 'bi-award',
        'examples': '专家说好、明星都在用',
        'prompt_template': '权威认证'
    },
    {
        'name': '案例',
        'category': 'super_positioning',
        'sub_category': 'content_type',
        'description': '告诉你别人也这么做',
        'icon': 'bi-chat-quote',
        'examples': '某某也是这么做的、真实案例分享',
        'prompt_template': '真实故事'
    },
    {
        'name': '安慰',
        'category': 'super_positioning',
        'sub_category': 'content_type',
        'description': '消除你的顾虑',
        'icon': 'bi-emoji-smile',
        'examples': '别担心、这是正常的',
        'prompt_template': '情感支持'
    },
    {
        'name': '促销',
        'category': 'super_positioning',
        'sub_category': 'content_type',
        'description': '告诉你现在买划算',
        'icon': 'bi-tag',
        'examples': '限时优惠、先买有赠品',
        'prompt_template': '优惠信息'
    },

    # ========== 意图阶段 ==========
    {
        'name': '问题感知',
        'category': 'super_positioning',
        'sub_category': 'intent_stage',
        'description': '发现问题，但不明确',
        'icon': 'bi-exclamation-circle',
        'examples': '宝宝转奶、腹泻怎么办',
        'prompt_template': '问题识别'
    },
    {
        'name': '信息搜索',
        'category': 'super_positioning',
        'sub_category': 'intent_stage',
        'description': '寻找解决方案',
        'icon': 'bi-search',
        'examples': '转奶方法、奶粉推荐',
        'prompt_template': '方案寻找'
    },
    {
        'name': '方案评估',
        'category': 'super_positioning',
        'sub_category': 'intent_stage',
        'description': '对比多个方案',
        'icon': 'bi-scale',
        'examples': '哪款好、对比',
        'prompt_template': '方案对比'
    },
    {
        'name': '购买决策',
        'category': 'super_positioning',
        'sub_category': 'intent_stage',
        'description': '决定购买',
        'icon': 'bi-cart-check',
        'examples': '哪里买、正品',
        'prompt_template': '购买引导'
    },
    {
        'name': '购买后',
        'category': 'super_positioning',
        'sub_category': 'intent_stage',
        'description': '使用后的问题',
        'icon': 'bi-bag-check',
        'examples': '转奶成功、效果',
        'prompt_template': '使用指导'
    },

    # ========== 风险维度 ==========
    {
        'name': '风险厌恶',
        'category': 'super_positioning',
        'sub_category': 'risk_dimension',
        'description': '对风险的厌恶程度',
        'icon': 'bi-shield',
        'examples': '高风险厌恶=一定要保障、低风险厌恶=愿意尝试',
        'prompt_template': '保障/退路'
    },
    {
        'name': '财务风险',
        'category': 'super_positioning',
        'sub_category': 'risk_dimension',
        'description': '担心钱打水漂',
        'icon': 'bi-currency-dollar',
        'examples': '太贵了不敢买、怕买了没效果',
        'prompt_template': '性价比/省钱'
    },
    {
        'name': '健康风险',
        'category': 'super_positioning',
        'sub_category': 'risk_dimension',
        'description': '担心身体受伤害',
        'icon': 'bi-heart-pulse',
        'examples': '怕有副作用、怕不安全',
        'prompt_template': '安全性/成分'
    },
    {
        'name': '机会风险',
        'category': 'super_positioning',
        'sub_category': 'risk_dimension',
        'description': '担心错过更好的',
        'icon': 'bi-clock-history',
        'examples': '买了这个错过那个、选错了怎么办',
        'prompt_template': '对比/最优推荐'
    },

    # ========== 效率维度 ==========
    {
        'name': '极高时间敏感',
        'category': 'super_positioning',
        'sub_category': 'efficiency_dimension',
        'description': '没时间，要最快方案',
        'icon': 'bi-lightning-charge',
        'examples': '职场妈妈、工作太忙',
        'prompt_template': '速成/便捷'
    },
    {
        'name': '高时间敏感',
        'category': 'super_positioning',
        'sub_category': 'efficiency_dimension',
        'description': '时间比较紧张',
        'icon': 'bi-clock',
        'examples': '有点忙但还能抽时间',
        'prompt_template': '效率方案'
    },
    {
        'name': '愿意投入时间',
        'category': 'super_positioning',
        'sub_category': 'efficiency_dimension',
        'description': '愿意花时间研究/学习',
        'icon': 'bi-book',
        'examples': '学习型用户、愿意深入了解',
        'prompt_template': '详细教程/深度内容'
    },

    # ========== 情感维度 ==========
    {
        'name': '焦虑型',
        'category': 'super_positioning',
        'sub_category': 'emotional_dimension',
        'description': '担心、害怕、不确定',
        'icon': 'bi-emoji-frown',
        'examples': '新手妈妈各种担心、怕做错',
        'prompt_template': '安慰/保证'
    },
    {
        'name': '内疚型',
        'category': 'super_positioning',
        'sub_category': 'emotional_dimension',
        'description': '觉得亏欠、想补偿',
        'icon': 'bi-heartbreak',
        'examples': '没陪孩子想补偿、亏欠家人',
        'prompt_template': '情感共鸣/解决方案'
    },
    {
        'name': '成就型',
        'category': 'super_positioning',
        'sub_category': 'emotional_dimension',
        'description': '想要更好、证明自己',
        'icon': 'bi-trophy',
        'examples': '想要做个好妈妈、想要被认可',
        'prompt_template': '鼓励/成就展示'
    },
    {
        'name': '归属型',
        'category': 'super_positioning',
        'sub_category': 'emotional_dimension',
        'description': '想要被认可、被接纳',
        'icon': 'bi-people',
        'examples': '想融入某个圈子、想被认同',
        'prompt_template': '社群/归属感'
    },
    {
        'name': '安全感型',
        'category': 'super_positioning',
        'sub_category': 'emotional_dimension',
        'description': '想要稳定、可靠',
        'icon': 'bi-shield-check',
        'examples': '不敢尝试新东西、喜欢熟悉的感觉',
        'prompt_template': '品牌背书/口碑'
    },

    # ========== 社交维度 ==========
    {
        'name': '需要同类人背书',
        'category': 'super_positioning',
        'sub_category': 'social_dimension',
        'description': '和我一样的人说好才信',
        'icon': 'bi-person-hearts',
        'examples': '看真实用户评价、看妈妈群推荐',
        'prompt_template': '用户案例/UGC'
    },
    {
        'name': '需要专家背书',
        'category': 'super_positioning',
        'sub_category': 'social_dimension',
        'description': '权威人士说好才信',
        'icon': 'bi-award',
        'examples': '医生/专家推荐、权威认证',
        'prompt_template': '专家内容/KOL'
    },
    {
        'name': '需要大众背书',
        'category': 'super_positioning',
        'sub_category': 'social_dimension',
        'description': '大家都用我才放心',
        'icon': 'bi-megaphone',
        'examples': '看销量、看排名',
        'prompt_template': '销量数据/排名'
    },
    {
        'name': '需要熟人背书',
        'category': 'super_positioning',
        'sub_category': 'social_dimension',
        'description': '朋友推荐才信',
        'icon': 'bi-person-check',
        'examples': '朋友推荐、熟人介绍',
        'prompt_template': '口碑推荐/熟人介绍'
    },
    {
        'name': '受圈层影响',
        'category': 'super_positioning',
        'sub_category': 'social_dimension',
        'description': '受特定圈子影响大',
        'icon': 'bi-circle-square',
        'examples': '妈妈群、职场圈、同城圈',
        'prompt_template': '社群营销/圈层渗透'
    },
]


# 子分类中英对照
SUB_CATEGORY_LABELS = {
    'conflict_type': '矛盾类型',
    'transformation_type': '转变类型',
    'transformation_barrier': '转变障碍',
    'change_stage': '转变阶段',
    'buyer_user_relationship': '买用关系',
    'content_type': '内容类型',
    'intent_stage': '意图阶段',
    'risk_dimension': '风险维度',
    'efficiency_dimension': '效率维度',
    'emotional_dimension': '情感维度',
    'social_dimension': '社交维度'
}
