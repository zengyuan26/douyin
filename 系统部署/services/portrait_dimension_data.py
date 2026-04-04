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
- weight: LLM权重（满分10分），用于画像分析时各维度的权重配置
"""

# 子分类默认权重（LLM画像分析时使用）
SUB_CATEGORY_WEIGHTS = {
    'conflict_type': 8.0,        # 矛盾类型：8分
    'transformation_type': 7.0, # 转变类型：7分
    'transformation_barrier': 9.0,  # 转变障碍：9分
    'change_stage': 6.0,        # 转变阶段：6分
    'buyer_user_relationship': 7.0,  # 买用关系：7分
    'content_type': 7.0,        # 内容类型：7分
    'intent_stage': 6.0,        # 意图阶段：6分
    'risk_dimension': 9.0,      # 风险维度：9分
    'cost_dimension': 7.0,       # 成本维度：7分
    'efficiency_dimension': 8.0, # 效率维度：8分
    'emotional_dimension': 10.0,  # 情感维度：10分
    'social_dimension': 8.0,    # 社交维度：8分
}

# 画像维度数据
PORTRAIT_DIMENSIONS_DATA = [
    # ========== 矛盾类型（核心元维度）==========
    # 权重说明：矛盾类型整体8分
    {
        'name': '缺失型',
        'category': 'super_positioning',
        'sub_category': 'conflict_type',
        'description': '用户没有/不足某种资源、能力或条件，需要获得',
        'icon': 'bi-dash-circle',
        'examples': '没粉丝、没预算、没知识、没渠道',
        'usage_tips': '描述用户缺少什么 → 获得后能怎样',
        'prompt_template': '解决方案/获取路径',
        'weight': 8.0
    },
    {
        'name': '拥有型',
        'category': 'super_positioning',
        'sub_category': 'conflict_type',
        'description': '用户有资源/能力/条件，但不知道怎么有效利用',
        'icon': 'bi-lightning-charge',
        'examples': '1000万粉丝不知道怎么变现、有钱不知道怎么投资、有产品不知道怎么卖',
        'usage_tips': '描述用户拥有什么资源 → 激活/变现方法',
        'prompt_template': '激活路径/变现方法',
        'weight': 8.0
    },
    {
        'name': '冲突型',
        'category': 'super_positioning',
        'sub_category': 'conflict_type',
        'description': '用户想要但有顾虑/障碍，意愿和行动之间存在矛盾',
        'icon': 'bi-arrow-left-right',
        'examples': '想要健康但管不住嘴、想要省钱但忍不住花、想要学习但拖延',
        'usage_tips': '描述用户想要什么 + 障碍是什么',
        'prompt_template': '消除障碍/降低门槛',
        'weight': 8.0
    },
    {
        'name': '替代型',
        'category': 'super_positioning',
        'sub_category': 'conflict_type',
        'description': '用户有现有方案但效果不好，想要更好的替代',
        'icon': 'bi-arrow-repeat',
        'examples': '用旧奶粉但宝宝不长肉、用旧手机但太卡、换护肤品但没效果',
        'usage_tips': '描述现有方案的问题 + 更好的选择',
        'prompt_template': '升级替代/效果对比',
        'weight': 8.0
    },
    {
        'name': '减少型',
        'category': 'super_positioning',
        'sub_category': 'conflict_type',
        'description': '用户想要简化、降低、减少某些东西',
        'icon': 'bi-dash-lg',
        'examples': '太复杂想简化、太多想精简、太贵想降低、太高想减少',
        'usage_tips': '描述用户想减少什么 + 简化方案',
        'prompt_template': '简化方案/精简路径',
        'weight': 8.0
    },

    # ========== 转变类型（整体权重7分）==========
    {
        'name': '坏→好',
        'category': 'super_positioning',
        'sub_category': 'transformation_type',
        'description': '从问题状态到正常状态',
        'icon': 'bi-arrow-up-circle',
        'examples': '宝宝腹泻→肠胃健康、生病→康复',
        'prompt_template': '问题解决',
        'weight': 7.0
    },
    {
        'name': '无→有',
        'category': 'super_positioning',
        'sub_category': 'transformation_type',
        'description': '从缺失到拥有',
        'icon': 'bi-plus-circle',
        'examples': '不会说话→开口说话、没粉丝→有粉丝',
        'prompt_template': '获取路径',
        'weight': 7.0
    },
    {
        'name': '差→好',
        'category': 'super_positioning',
        'sub_category': 'transformation_type',
        'description': '从较差到较好',
        'icon': 'bi-graph-up-arrow',
        'examples': '普通奶粉→优质奶粉、低配→高配',
        'prompt_template': '升级方案',
        'weight': 7.0
    },
    {
        'name': '旧→新',
        'category': 'super_positioning',
        'sub_category': 'transformation_type',
        'description': '从旧状态到新状态',
        'icon': 'bi-arrow-right-circle',
        'examples': '旧奶粉→新奶粉、旧手机→新手机',
        'prompt_template': '切换引导',
        'weight': 7.0
    },
    {
        'name': '少→多',
        'category': 'super_positioning',
        'sub_category': 'transformation_type',
        'description': '从少到多',
        'icon': 'bi-plus-lg',
        'examples': '奶量不足→奶量充足、粉丝少→粉丝多',
        'prompt_template': '增量方案',
        'weight': 7.0
    },
    {
        'name': '高→低',
        'category': 'super_positioning',
        'sub_category': 'transformation_type',
        'description': '从高到低（减少）',
        'icon': 'bi-arrow-down-circle',
        'examples': '过敏严重→脱敏成功、血压高→降低',
        'prompt_template': '降低方案',
        'weight': 7.0
    },
    {
        'name': '闲置→激活',
        'category': 'super_positioning',
        'sub_category': 'transformation_type',
        'description': '有资源但不会用 → 有资源且会用',
        'icon': 'bi-lightning',
        'examples': '1000万粉丝不知道怎么变现、有钱不知道怎么投资',
        'prompt_template': '激活路径',
        'weight': 7.0
    },
    {
        'name': '模糊→清晰',
        'category': 'super_positioning',
        'sub_category': 'transformation_type',
        'description': '有但不知道怎么用 → 知道怎么用',
        'icon': 'bi-question-circle',
        'examples': '有资源但迷茫、有能力但不会展示',
        'prompt_template': '方法指导',
        'weight': 7.0
    },

    # ========== 转变障碍 - 内在（认知权重最高9分）==========
    {
        'name': '认知',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '不知道正确的方法/知识',
        'icon': 'bi-brain',
        'examples': '不知道怎么转奶、不知道选哪个',
        'applicable_audience': '内在',
        'prompt_template': '科普/教程',
        'weight': 9.0
    },
    {
        'name': '资源',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '金钱/时间/精力不足',
        'icon': 'bi-wallet2',
        'examples': '预算不够、太忙没时间',
        'applicable_audience': '内在',
        'prompt_template': '性价比/便捷方案',
        'weight': 8.0
    },
    {
        'name': '决策',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '信息太多不知道怎么选',
        'icon': 'bi-list-check',
        'examples': '牌子太多、不知道哪个好',
        'applicable_audience': '内在',
        'prompt_template': '对比/推荐',
        'weight': 8.0
    },
    {
        'name': '心理',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '害怕改变后更糟',
        'icon': 'bi-emoji-frown',
        'examples': '担心失败、怕换错了',
        'applicable_audience': '内在',
        'prompt_template': '案例/安慰',
        'weight': 9.0
    },
    {
        'name': '代理焦虑',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '买用分离，担心决策伤害使用人',
        'icon': 'bi-shield-exclamation',
        'examples': '不知道我的选择对不对、担心伤害宝宝',
        'applicable_audience': '内在',
        'prompt_template': '专家背书/安全性',
        'weight': 9.0
    },
    {
        'name': '拥有型',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '有资源但不知道怎么用',
        'icon': 'bi-lightning-charge',
        'examples': '粉丝多不知道怎么变现、有钱不知道怎么投资',
        'applicable_audience': '内在',
        'prompt_template': '变现方法/激活路径',
        'weight': 8.0
    },

    # ========== 转变障碍 - 他人（整体权重8分）==========
    {
        'name': '反对',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '家人觉得没必要/浪费',
        'icon': 'bi-person-x',
        'examples': '老公说不用、婆婆说浪费',
        'applicable_audience': '他人',
        'prompt_template': '权威背书/共识建立',
        'weight': 8.0
    },
    {
        'name': '口碑',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '周围人有负面经历',
        'icon': 'bi-megaphone',
        'examples': '朋友说不好用、网上有差评',
        'applicable_audience': '他人',
        'prompt_template': '真实案例/数据',
        'weight': 8.0
    },
    {
        'name': '分歧',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '家人之间意见不一致',
        'icon': 'bi-people',
        'examples': '老婆要买老公不让、父母意见不合',
        'applicable_audience': '他人',
        'prompt_template': '共识建立/沟通技巧',
        'weight': 8.0
    },
    {
        'name': '社交压力',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '怕被人说/跟别人不一样',
        'icon': 'bi-chat-left-dots',
        'examples': '不好意思、怕被邻居说',
        'applicable_audience': '他人',
        'prompt_template': '社群归属/正面引导',
        'weight': 7.0
    },
    {
        'name': '权威影响',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '专业人士/医生说不用',
        'icon': 'bi-bandaid',
        'examples': '医生说不用补、专家说没效果',
        'applicable_audience': '他人',
        'prompt_template': '专业内容/认证',
        'weight': 9.0
    },

    # ========== 转变障碍 - 环境（整体权重7分）==========
    {
        'name': '渠道',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '买不到/不方便买',
        'icon': 'bi-shop',
        'examples': '当地没有、不知道哪里买',
        'applicable_audience': '环境',
        'prompt_template': '购买指南/正品渠道',
        'weight': 7.0
    },
    {
        'name': '时间',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '没时间了解/行动',
        'icon': 'bi-clock',
        'examples': '工作太忙、没时间研究',
        'applicable_audience': '环境',
        'prompt_template': '便捷方案/省时',
        'weight': 8.0
    },
    {
        'name': '条件',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '产品/服务本身有限制',
        'icon': 'bi-slash-circle',
        'examples': '选择少、有门槛限制',
        'applicable_audience': '环境',
        'prompt_template': '替代方案说明',
        'weight': 7.0
    },
    {
        'name': '沉没成本',
        'category': 'super_positioning',
        'sub_category': 'transformation_barrier',
        'description': '舍不得换旧方案',
        'icon': 'bi-hourglass-split',
        'examples': '旧的还剩很多、不想浪费',
        'applicable_audience': '环境',
        'prompt_template': '切换引导/优惠',
        'weight': 7.0
    },

    # ========== 转变阶段（整体权重6分）==========
    {
        'name': '转变前',
        'category': 'super_positioning',
        'sub_category': 'change_stage',
        'description': '还没开始，考虑要不要做',
        'icon': 'bi-compass',
        'examples': '时机焦虑、选择焦虑',
        'prompt_template': '时机选择/方案对比',
        'weight': 6.0
    },
    {
        'name': '转变中',
        'category': 'super_positioning',
        'sub_category': 'change_stage',
        'description': '正在执行，需要指导',
        'icon': 'bi-arrow-right',
        'examples': '操作焦虑、效果焦虑',
        'prompt_template': '操作指导/效果跟踪',
        'weight': 6.0
    },
    {
        'name': '转变后',
        'category': 'super_positioning',
        'sub_category': 'change_stage',
        'description': '已经完成，需要确认/持续',
        'icon': 'bi-check-circle',
        'examples': '效果焦虑、调整焦虑',
        'prompt_template': '效果确认/持续方案',
        'weight': 6.0
    },

    # ========== 买用关系（整体权重7分）==========
    {
        'name': '买用一体',
        'category': 'super_positioning',
        'sub_category': 'buyer_user_relationship',
        'description': '付费人和使用人是同一人',
        'icon': 'bi-person',
        'examples': '我给自己买、我自己用',
        'prompt_template': '个人利益导向',
        'weight': 7.0
    },
    {
        'name': '保护型',
        'category': 'super_positioning',
        'sub_category': 'buyer_user_relationship',
        'description': '付费人想保护使用人（买用分离）',
        'icon': 'bi-heart',
        'examples': '宝妈买给宝宝、家长买给孩子',
        'prompt_template': '安全性/关爱',
        'weight': 9.0
    },
    {
        'name': '孝心型',
        'category': 'super_positioning',
        'sub_category': 'buyer_user_relationship',
        'description': '晚辈给长辈买',
        'icon': 'bi-people-fill',
        'examples': '子女给父母买、孙子给爷爷奶奶买',
        'prompt_template': '孝心表达/健康',
        'weight': 8.0
    },
    {
        'name': '责任型',
        'category': 'super_positioning',
        'sub_category': 'buyer_user_relationship',
        'description': '因责任而购买',
        'icon': 'bi-briefcase',
        'examples': '公司给员工买福利、老板给客户买礼品',
        'prompt_template': '责任/便利',
        'weight': 7.0
    },

    # ========== 内容类型（整体权重7分）==========
    {
        'name': '科普',
        'category': 'super_positioning',
        'sub_category': 'content_type',
        'description': '告诉你为什么/是什么',
        'icon': 'bi-book',
        'examples': '为什么会这样、是什么原理',
        'prompt_template': '原因/原理',
        'weight': 7.0
    },
    {
        'name': '教程',
        'category': 'super_positioning',
        'sub_category': 'content_type',
        'description': '告诉你怎么做',
        'icon': 'bi-list-ol',
        'examples': '步骤1、步骤2、步骤3',
        'prompt_template': '方法/步骤',
        'weight': 7.0
    },
    {
        'name': '对比',
        'category': 'super_positioning',
        'sub_category': 'content_type',
        'description': '告诉你选哪个',
        'icon': 'bi-bar-chart',
        'examples': 'A和B哪个好、有什么区别',
        'prompt_template': '对比分析',
        'weight': 8.0
    },
    {
        'name': '推荐',
        'category': 'super_positioning',
        'sub_category': 'content_type',
        'description': '帮你做决定',
        'icon': 'bi-hand-thumbs-up',
        'examples': '推荐这个、直接选这个',
        'prompt_template': '决策支持',
        'weight': 8.0
    },
    {
        'name': '背书',
        'category': 'super_positioning',
        'sub_category': 'content_type',
        'description': '告诉你信谁',
        'icon': 'bi-award',
        'examples': '专家说好、明星都在用',
        'prompt_template': '权威认证',
        'weight': 9.0
    },
    {
        'name': '案例',
        'category': 'super_positioning',
        'sub_category': 'content_type',
        'description': '告诉你别人也这么做',
        'icon': 'bi-chat-quote',
        'examples': '某某也是这么做的、真实案例分享',
        'prompt_template': '真实故事',
        'weight': 8.0
    },
    {
        'name': '安慰',
        'category': 'super_positioning',
        'sub_category': 'content_type',
        'description': '消除你的顾虑',
        'icon': 'bi-emoji-smile',
        'examples': '别担心、这是正常的',
        'prompt_template': '情感支持',
        'weight': 7.0
    },
    {
        'name': '促销',
        'category': 'super_positioning',
        'sub_category': 'content_type',
        'description': '告诉你现在买划算',
        'icon': 'bi-tag',
        'examples': '限时优惠、先买有赠品',
        'prompt_template': '优惠信息',
        'weight': 6.0
    },

    # ========== 意图阶段（整体权重6分）==========
    {
        'name': '问题感知',
        'category': 'super_positioning',
        'sub_category': 'intent_stage',
        'description': '发现问题，但不明确',
        'icon': 'bi-exclamation-circle',
        'examples': '宝宝转奶、腹泻怎么办',
        'prompt_template': '问题识别',
        'weight': 6.0
    },
    {
        'name': '信息搜索',
        'category': 'super_positioning',
        'sub_category': 'intent_stage',
        'description': '寻找解决方案',
        'icon': 'bi-search',
        'examples': '转奶方法、奶粉推荐',
        'prompt_template': '方案寻找',
        'weight': 7.0
    },
    {
        'name': '方案评估',
        'category': 'super_positioning',
        'sub_category': 'intent_stage',
        'description': '对比多个方案',
        'icon': 'bi-scale',
        'examples': '哪款好、对比',
        'prompt_template': '方案对比',
        'weight': 8.0
    },
    {
        'name': '购买决策',
        'category': 'super_positioning',
        'sub_category': 'intent_stage',
        'description': '决定购买',
        'icon': 'bi-cart-check',
        'examples': '哪里买、正品',
        'prompt_template': '购买引导',
        'weight': 8.0
    },
    {
        'name': '购买后',
        'category': 'super_positioning',
        'sub_category': 'intent_stage',
        'description': '使用后的问题',
        'icon': 'bi-bag-check',
        'examples': '转奶成功、效果',
        'prompt_template': '使用指导',
        'weight': 6.0
    },

    # ========== 风险维度（整体权重9分）==========
    {
        'name': '风险厌恶',
        'category': 'super_positioning',
        'sub_category': 'risk_dimension',
        'description': '对风险的厌恶程度',
        'icon': 'bi-shield',
        'examples': '高风险厌恶=一定要保障、低风险厌恶=愿意尝试',
        'prompt_template': '保障/退路',
        'weight': 9.0
    },
    {
        'name': '财务风险',
        'category': 'super_positioning',
        'sub_category': 'risk_dimension',
        'description': '担心钱打水漂',
        'icon': 'bi-currency-dollar',
        'examples': '太贵了不敢买、怕买了没效果',
        'prompt_template': '性价比/省钱',
        'weight': 9.0
    },
    {
        'name': '健康风险',
        'category': 'super_positioning',
        'sub_category': 'risk_dimension',
        'description': '担心身体受伤害',
        'icon': 'bi-heart-pulse',
        'examples': '怕有副作用、怕不安全',
        'prompt_template': '安全性/成分',
        'weight': 10.0
    },
    {
        'name': '机会风险',
        'category': 'super_positioning',
        'sub_category': 'risk_dimension',
        'description': '担心错过更好的',
        'icon': 'bi-clock-history',
        'examples': '买了这个错过那个、选错了怎么办',
        'prompt_template': '对比/最优推荐',
        'weight': 8.0
    },

    # ========== 效率维度（整体权重8分）==========
    {
        'name': '极高时间敏感',
        'category': 'super_positioning',
        'sub_category': 'efficiency_dimension',
        'description': '没时间，要最快方案',
        'icon': 'bi-lightning-charge',
        'examples': '职场妈妈、工作太忙',
        'prompt_template': '速成/便捷',
        'weight': 8.0
    },
    {
        'name': '高时间敏感',
        'category': 'super_positioning',
        'sub_category': 'efficiency_dimension',
        'description': '时间比较紧张',
        'icon': 'bi-clock',
        'examples': '有点忙但还能抽时间',
        'prompt_template': '效率方案',
        'weight': 8.0
    },
    {
        'name': '愿意投入时间',
        'category': 'super_positioning',
        'sub_category': 'efficiency_dimension',
        'description': '愿意花时间研究/学习',
        'icon': 'bi-book',
        'examples': '学习型用户、愿意深入了解',
        'prompt_template': '详细教程/深度内容',
        'weight': 7.0
    },

    # ========== 成本维度（整体权重7分）==========
    {
        'name': '极度价格敏感',
        'category': 'super_positioning',
        'sub_category': 'cost_dimension',
        'description': '预算非常有限，只买最便宜的',
        'icon': 'bi-currency-dollar',
        'examples': '学生党、低收入群体、只买特价',
        'prompt_template': '极致性价比/最低价推荐',
        'weight': 7.0
    },
    {
        'name': '性价比导向',
        'category': 'super_positioning',
        'sub_category': 'cost_dimension',
        'description': '不求最便宜，但要值',
        'icon': 'bi-graph-up',
        'examples': '精打细算、货比三家、买对不买贵',
        'prompt_template': '性价比分析/值不值',
        'weight': 7.0
    },
    {
        'name': '首次购买谨慎',
        'category': 'super_positioning',
        'sub_category': 'cost_dimension',
        'description': '第一次买怕吃亏、怕被坑',
        'icon': 'bi-shield-check',
        'examples': '新客怕被宰、怕买亏了',
        'prompt_template': '首购保障/不满意退/真实评测',
        'weight': 8.0
    },
    {
        'name': '促销驱动型',
        'category': 'super_positioning',
        'sub_category': 'cost_dimension',
        'description': '看到优惠才买，没有优惠不买',
        'icon': 'bi-tag',
        'examples': '等双11、蹲直播间、领券购买',
        'prompt_template': '限时优惠/专属折扣/活动预告',
        'weight': 6.0
    },
    {
        'name': '沉没成本敏感',
        'category': 'super_positioning',
        'sub_category': 'cost_dimension',
        'description': '舍不得放弃已投入的，怕浪费',
        'icon': 'bi-hourglass-split',
        'examples': '用了一半不舍得换、积分不能浪费',
        'prompt_template': '损失规避/划算切换/不浪费',
        'weight': 7.0
    },

    # ========== 情感维度（整体权重10分）==========
    {
        'name': '焦虑型',
        'category': 'super_positioning',
        'sub_category': 'emotional_dimension',
        'description': '担心、害怕、不确定',
        'icon': 'bi-emoji-frown',
        'examples': '新手妈妈各种担心、怕做错',
        'prompt_template': '安慰/保证',
        'weight': 10.0
    },
    {
        'name': '内疚型',
        'category': 'super_positioning',
        'sub_category': 'emotional_dimension',
        'description': '觉得亏欠、想补偿',
        'icon': 'bi-heartbreak',
        'examples': '没陪孩子想补偿、亏欠家人',
        'prompt_template': '情感共鸣/解决方案',
        'weight': 9.0
    },
    {
        'name': '成就型',
        'category': 'super_positioning',
        'sub_category': 'emotional_dimension',
        'description': '想要更好、证明自己',
        'icon': 'bi-trophy',
        'examples': '想要做个好妈妈、想要被认可',
        'prompt_template': '鼓励/成就展示',
        'weight': 8.0
    },
    {
        'name': '归属型',
        'category': 'super_positioning',
        'sub_category': 'emotional_dimension',
        'description': '想要被认可、被接纳',
        'icon': 'bi-people',
        'examples': '想融入某个圈子、想被认同',
        'prompt_template': '社群/归属感',
        'weight': 8.0
    },
    {
        'name': '安全感型',
        'category': 'super_positioning',
        'sub_category': 'emotional_dimension',
        'description': '想要稳定、可靠',
        'icon': 'bi-shield-check',
        'examples': '不敢尝试新东西、喜欢熟悉的感觉',
        'prompt_template': '品牌背书/口碑',
        'weight': 9.0
    },

    # ========== 社交维度（整体权重8分）==========
    {
        'name': '需要同类人背书',
        'category': 'super_positioning',
        'sub_category': 'social_dimension',
        'description': '和我一样的人说好才信',
        'icon': 'bi-person-hearts',
        'examples': '看真实用户评价、看妈妈群推荐',
        'prompt_template': '用户案例/UGC',
        'weight': 8.0
    },
    {
        'name': '需要专家背书',
        'category': 'super_positioning',
        'sub_category': 'social_dimension',
        'description': '权威人士说好才信',
        'icon': 'bi-award',
        'examples': '医生/专家推荐、权威认证',
        'prompt_template': '专家内容/KOL',
        'weight': 9.0
    },
    {
        'name': '需要大众背书',
        'category': 'super_positioning',
        'sub_category': 'social_dimension',
        'description': '大家都用我才放心',
        'icon': 'bi-megaphone',
        'examples': '看销量、看排名',
        'prompt_template': '销量数据/排名',
        'weight': 7.0
    },
    {
        'name': '需要熟人背书',
        'category': 'super_positioning',
        'sub_category': 'social_dimension',
        'description': '朋友推荐才信',
        'icon': 'bi-person-check',
        'examples': '朋友推荐、熟人介绍',
        'prompt_template': '口碑推荐/熟人介绍',
        'weight': 8.0
    },
    {
        'name': '受圈层影响',
        'category': 'super_positioning',
        'sub_category': 'social_dimension',
        'description': '受特定圈子影响大',
        'icon': 'bi-circle-square',
        'examples': '妈妈群、职场圈、同城圈',
        'prompt_template': '社群营销/圈层渗透',
        'weight': 8.0
    },

    # ========== 定制礼赠仪式场景识别层（整体权重10分）==========
    # 新增：只要业务含 定制/刻字/LOGO/专属/纪念/伴手礼/礼赠，自动触发此层
    {
        'name': '婚宴仪式',
        'category': 'custom_gift',
        'sub_category': 'ritual_event',
        'description': '婚礼宴请场景，送礼和定制需求强烈',
        'icon': 'bi-heart',
        'examples': '婚礼伴手礼、婚宴定制酒、婚纱摄影伴手礼',
        'prompt_template': '婚礼定制推荐/婚礼礼品避坑',
        'weight': 10.0,
        'trigger_keywords': ['婚礼', '婚宴', '结婚', '伴郎', '伴娘', '订婚'],
        'ritual_keywords': ['婚宴伴手礼', '婚礼定制', '结婚礼品', '婚礼伴手礼定制']
    },
    {
        'name': '寿宴仪式',
        'category': 'custom_gift',
        'sub_category': 'ritual_event',
        'description': '祝寿宴请场景，注重吉祥寓意',
        'icon': 'bi-gift',
        'examples': '寿宴定制酒、祝寿礼品、老人祝寿伴手礼',
        'prompt_template': '寿宴定制推荐/祝寿礼品避坑',
        'weight': 10.0,
        'trigger_keywords': ['寿宴', '祝寿', '生日宴', '老人', '长辈'],
        'ritual_keywords': ['寿宴礼品', '祝寿定制', '生日定制礼品']
    },
    {
        'name': '满月/百日宴',
        'category': 'custom_gift',
        'sub_category': 'ritual_event',
        'description': '新生儿宴请场景，送礼讲究寓意和安全性',
        'icon': 'bi-balloon',
        'examples': '满月伴手礼、百日宴定制、宝宝宴礼品',
        'prompt_template': '满月定制推荐/宝宝礼品避坑',
        'weight': 10.0,
        'trigger_keywords': ['满月', '百日', '周岁', '宝宝宴', '新生儿', '满月酒'],
        'ritual_keywords': ['满月伴手礼', '百日宴定制', '宝宝满月礼品', '周岁定制']
    },
    {
        'name': '乔迁之喜',
        'category': 'custom_gift',
        'sub_category': 'ritual_event',
        'description': '搬家宴请场景，注重实用和寓意',
        'icon': 'bi-house',
        'examples': '乔迁定制礼品、新居入伙伴手礼、搬家宴请礼品',
        'prompt_template': '乔迁定制推荐/搬家礼品避坑',
        'weight': 9.0,
        'trigger_keywords': ['乔迁', '搬家', '新居', '入伙', '新房'],
        'ritual_keywords': ['乔迁礼品', '搬家伴手礼', '新居入伙定制', '搬家礼品定制']
    },
    {
        'name': '升学宴/谢师宴',
        'category': 'custom_gift',
        'sub_category': 'ritual_event',
        'description': '升学或感谢老师场景，注重纪念意义',
        'icon': 'bi-mortarboard',
        'examples': '升学宴礼品、谢师宴定制、毕业伴手礼',
        'prompt_template': '升学定制推荐/谢师礼品避坑',
        'weight': 9.0,
        'trigger_keywords': ['升学', '谢师', '高考', '中考', '毕业', '金榜题名'],
        'ritual_keywords': ['升学宴礼品', '谢师宴定制', '毕业伴手礼', '状元宴礼品']
    },
    {
        'name': '开业典礼',
        'category': 'custom_gift',
        'sub_category': 'ritual_event',
        'description': '店铺/公司开业场景，注重宣传和喜庆',
        'icon': 'bi-shop-window',
        'examples': '开业定制礼品、开业伴手礼、开张庆典礼品',
        'prompt_template': '开业定制推荐/开店礼品避坑',
        'weight': 9.0,
        'trigger_keywords': ['开业', '开张', '新店', '新公司', '开业的'],
        'ritual_keywords': ['开业礼品', '开业伴手礼', '开张定制', '新店开业礼品']
    },
    {
        'name': '年会/团建',
        'category': 'custom_gift',
        'sub_category': 'ritual_event',
        'description': '公司年会/团建场景，注重纪念和团队感',
        'icon': 'bi-people',
        'examples': '年会定制礼品、团建伴手礼、公司纪念品',
        'prompt_template': '年会定制推荐/团建礼品避坑',
        'weight': 8.0,
        'trigger_keywords': ['年会', '团建', '公司活动', '企业团建', '员工福利'],
        'ritual_keywords': ['年会礼品', '团建伴手礼', '企业定制礼品', '公司纪念品定制']
    },
    {
        'name': '发布会/启动仪式',
        'category': 'custom_gift',
        'sub_category': 'ritual_event',
        'description': '产品/项目发布会场景，注重品牌展示',
        'icon': 'bi-megaphone',
        'examples': '发布会伴手礼、启动仪式定制、媒体礼品',
        'prompt_template': '发布会定制推荐/启动仪式礼品避坑',
        'weight': 8.0,
        'trigger_keywords': ['发布会', '启动仪式', '新品发布', '媒体', '启动会'],
        'ritual_keywords': ['发布会礼品', '启动仪式定制', '媒体伴手礼', '新品发布礼品']
    },
    {
        'name': '纪念日/节日',
        'category': 'custom_gift',
        'sub_category': 'ritual_event',
        'description': '各类纪念日和传统节日场景',
        'icon': 'bi-calendar-event',
        'examples': '节日定制礼品、纪念日伴手礼、中秋/端午/春节礼品',
        'prompt_template': '节日定制推荐/节日礼品避坑',
        'weight': 9.0,
        'trigger_keywords': ['纪念日', '中秋', '端午', '春节', '元宵', '重阳', '七夕', '节日'],
        'ritual_keywords': ['节日礼品', '节日定制', '中秋伴手礼', '端午礼品', '春节礼品定制']
    },
    {
        'name': '商务答谢',
        'category': 'custom_gift',
        'sub_category': 'ritual_event',
        'description': '商务往来答谢场景，注重档次和定制感',
        'icon': 'bi-briefcase',
        'examples': '商务定制礼品、答谢伴手礼、客户礼品',
        'prompt_template': '商务定制推荐/客户礼品避坑',
        'weight': 9.0,
        'trigger_keywords': ['商务', '答谢', '客户', '合作伙伴', '礼品定制', '企业礼品'],
        'ritual_keywords': ['商务礼品', '客户定制', '答谢礼品', '企业伴手礼定制']
    },

    # ========== 定制礼赠心理顾虑识别层（整体权重10分）==========
    {
        'name': '办宴体面顾虑',
        'category': 'custom_gift',
        'sub_category': 'ritual_psychology',
        'description': '担心宴请不够体面，怕丢面子',
        'icon': 'bi-emoji-smile',
        'examples': '婚宴礼品不够档次、寿宴礼品太普通、宾客不满意',
        'prompt_template': '体面定制方案/高端礼品推荐',
        'weight': 10.0,
        'psychology_type': 'face_concern'
    },
    {
        'name': '送礼走心顾虑',
        'category': 'custom_gift',
        'sub_category': 'ritual_psychology',
        'description': '担心礼品不够用心，显得敷衍',
        'icon': 'bi-heart-pulse',
        'examples': '礼品太大众没心意、定制的东西好不好、能不能体现心意',
        'prompt_template': '走心定制方案/个性化礼品推荐',
        'weight': 10.0,
        'psychology_type': 'sincerity_concern'
    },
    {
        'name': '定制踩坑顾虑',
        'category': 'custom_gift',
        'sub_category': 'ritual_psychology',
        'description': '担心定制过程出问题，交付延误或质量差丢面子',
        'icon': 'bi-exclamation-triangle',
        'examples': '定制工期赶不上、送来发现质量问题、定制效果和想象不符',
        'prompt_template': '避坑指南/定制保障方案',
        'weight': 10.0,
        'psychology_type': 'quality_concern'
    },
    {
        'name': '性价比顾虑',
        'category': 'custom_gift',
        'sub_category': 'ritual_psychology',
        'description': '担心定制价格虚高，花冤枉钱',
        'icon': 'bi-wallet',
        'examples': '定制品是不是都很贵、批量定制有没有优惠',
        'prompt_template': '性价比分析/定制报价指南',
        'weight': 8.0,
        'psychology_type': 'price_concern'
    },

    # ========== 定制礼赠内容类型识别层（整体权重9分）==========
    {
        'name': '宴席选款种草',
        'category': 'custom_gift',
        'sub_category': 'ritual_content_type',
        'description': '帮助用户选择适合宴席的定制礼品',
        'icon': 'bi-list-check',
        'examples': '婚宴伴手礼选哪款、寿宴选什么礼品有面子',
        'prompt_template': '宴席礼品推荐/选款指南',
        'weight': 9.0,
        'content_base': '前置观望种草盘',
        'content_direction': '种草型'
    },
    {
        'name': '吉利款式种草',
        'category': 'custom_gift',
        'sub_category': 'ritual_content_type',
        'description': '推荐寓意好、受欢迎的定制款式',
        'icon': 'bi-star',
        'examples': '婚宴送什么寓意好、寿宴礼品哪些款式最吉利',
        'prompt_template': '吉利款式推荐/寓意解读',
        'weight': 9.0,
        'content_base': '前置观望种草盘',
        'content_direction': '种草型'
    },
    {
        'name': '案例对比种草',
        'category': 'custom_gift',
        'sub_category': 'ritual_content_type',
        'description': '通过真实案例对比，帮助用户做决策',
        'icon': 'bi-bar-chart',
        'examples': '某客户的婚宴伴手礼选择对比、真实定制案例分享',
        'prompt_template': '案例分析/对比推荐',
        'weight': 8.0,
        'content_base': '前置观望种草盘',
        'content_direction': '种草型'
    },
    {
        'name': '定制避坑指南',
        'category': 'custom_gift',
        'sub_category': 'ritual_content_type',
        'description': '帮助用户避免定制过程中的常见坑',
        'icon': 'bi-shield-check',
        'examples': '定制伴手礼常见的坑、定制工期延误怎么处理',
        'prompt_template': '避坑指南/防骗指南',
        'weight': 9.0,
        'content_base': '前置观望种草盘',
        'content_direction': '种草型'
    },
    {
        'name': '定制报价刚需',
        'category': 'custom_gift',
        'sub_category': 'ritual_content_type',
        'description': '定制价格和报价相关问题，解决临门一脚',
        'icon': 'bi-currency-dollar',
        'examples': '定制伴手礼多少钱、最低价多少、怎么报价',
        'prompt_template': '报价透明/价格攻略',
        'weight': 9.0,
        'content_base': '刚需痛点盘',
        'content_direction': '转化型'
    },
    {
        'name': '定稿排版刚需',
        'category': 'custom_gift',
        'sub_category': 'ritual_content_type',
        'description': '定制设计稿件确认相关问题',
        'icon': 'bi-pencil',
        'examples': '定稿需要多久、稿件修改次数、设计不满意怎么办',
        'prompt_template': '定稿流程/修改政策',
        'weight': 8.0,
        'content_base': '刚需痛点盘',
        'content_direction': '转化型'
    },
    {
        'name': '加急制作刚需',
        'category': 'custom_gift',
        'sub_category': 'ritual_content_type',
        'description': '加急定制相关问题，时间紧迫用户需求',
        'icon': 'bi-clock',
        'examples': '能不能加急、加急要多少钱、时间来不及怎么办',
        'prompt_template': '加急方案/时间管理',
        'weight': 8.0,
        'content_base': '刚需痛点盘',
        'content_direction': '转化型'
    },
    {
        'name': '现场搭配配套',
        'category': 'custom_gift',
        'sub_category': 'ritual_content_type',
        'description': '宴席现场礼品搭配和使用指导',
        'icon': 'bi-people-fill',
        'examples': '伴手礼怎么摆放、宴席现场怎么分发',
        'prompt_template': '现场搭配指南/分发技巧',
        'weight': 7.0,
        'content_base': '使用配套搜后种草盘',
        'content_direction': '种草型'
    },
    {
        'name': '发放储存配套',
        'category': 'custom_gift',
        'sub_category': 'ritual_content_type',
        'description': '礼品保存和发放相关问题',
        'icon': 'bi-box-seam',
        'examples': '伴手礼怎么保存、未发放的怎么处理、保质期多久',
        'prompt_template': '储存指南/发放建议',
        'weight': 6.0,
        'content_base': '使用配套搜后种草盘',
        'content_direction': '种草型'
    },
    {
        'name': '礼盒配套推荐',
        'category': 'custom_gift',
        'sub_category': 'ritual_content_type',
        'description': '礼盒包装搭配和升级推荐',
        'icon': 'bi-box',
        'examples': '伴手礼盒怎么搭配更体面、礼盒升级方案',
        'prompt_template': '礼盒搭配/升级推荐',
        'weight': 7.0,
        'content_base': '使用配套搜后种草盘',
        'content_direction': '种草型'
    },
]


# ========== 定制礼赠识别配置 ==========

# 触发关键词列表：业务描述中包含这些词，自动触发定制礼赠识别层
CUSTOM_GIFT_TRIGGER_KEYWORDS = [
    '定制', '刻字', 'LOGO', '专属', '纪念', '伴手礼', '礼赠',
    '礼品', '礼物', '赠品', '定制水', '定制酒', '定制茶叶',
    '企业定制', '公司定制', '批量定制', '活动定制', '婚礼定制',
    '生日定制', '节日定制', '会议定制', '培训定制', '团建定制'
]

# 定制产品关键词映射：用于识别具体定制品类
CUSTOM_PRODUCT_KEYWORDS = {
    '定制水': ['定制水', '定制饮用水', '定制矿泉水', '定制瓶装水'],
    '定制酒': ['定制酒', '定制白酒', '定制红酒', '定制啤酒', '定制酒水'],
    '定制茶叶': ['定制茶叶', '定制茶', '定制礼盒茶', '定制茶礼'],
    '定制伴手礼': ['伴手礼', '伴手礼品', '婚礼伴手礼', '商务伴手礼', '活动伴手礼'],
    '企业定制物料': ['企业定制', '公司定制', '定制物料', '企业物料', '公司物料'],
}

# 三大底盘内容分类映射
CUSTOM_GIFT_CONTENT_BASE_MAP = {
    # 前置观望种草盘（种草型）
    '前置观望种草盘': [
        '宴席选款种草', '吉利款式种草', '案例对比种草', '定制避坑指南'
    ],
    # 刚需痛点盘（转化型）
    '刚需痛点盘': [
        '定制报价刚需', '定稿排版刚需', '加急制作刚需'
    ],
    # 使用配套搜后种草盘（种草型）
    '使用配套搜后种草盘': [
        '现场搭配配套', '发放储存配套', '礼盒配套推荐'
    ]
}


def is_custom_gift_business(business_description: str) -> bool:
    """
    判断业务是否为定制礼赠类业务

    Args:
        business_description: 业务描述文本

    Returns:
        True 如果业务包含定制礼赠相关关键词
    """
    if not business_description:
        return False

    desc_lower = business_description.lower()
    for keyword in CUSTOM_GIFT_TRIGGER_KEYWORDS:
        if keyword.lower() in desc_lower:
            return True
    return False


def get_ritual_event_from_business(business_description: str) -> list:
    """
    从业务描述中提取仪式场景类型

    Args:
        business_description: 业务描述文本

    Returns:
        匹配的仪式场景列表
    """
    matched_rituals = []
    for dimension in PORTRAIT_DIMENSIONS_DATA:
        if dimension.get('sub_category') == 'ritual_event':
            trigger_kws = dimension.get('trigger_keywords', [])
            for kw in trigger_kws:
                if kw in business_description:
                    matched_rituals.append(dimension['name'])
                    break
    return matched_rituals


def get_custom_gift_portrait_psychology() -> list:
    """
    获取定制礼赠画像应包含的心理顾虑

    Returns:
        心理顾虑维度列表
    """
    psychologies = []
    for dimension in PORTRAIT_DIMENSIONS_DATA:
        if dimension.get('sub_category') == 'ritual_psychology':
            psychologies.append({
                'name': dimension['name'],
                'description': dimension['description'],
                'psychology_type': dimension.get('psychology_type', ''),
                'prompt_template': dimension.get('prompt_template', '')
            })
    return psychologies


def get_content_type_by_base(base_name: str) -> list:
    """
    根据底盘名称获取对应的内容类型

    Args:
        base_name: 底盘名称

    Returns:
        内容类型列表
    """
    return CUSTOM_GIFT_CONTENT_BASE_MAP.get(base_name, [])


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
    'cost_dimension': '成本维度',
    'efficiency_dimension': '效率维度',
    'emotional_dimension': '情感维度',
    'social_dimension': '社交维度',
    'ritual_event': '仪式场景',
    'ritual_psychology': '定制心理',
    'ritual_content_type': '定制内容类型'
}
