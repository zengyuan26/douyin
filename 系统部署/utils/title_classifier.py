# -*- coding: utf-8 -*-
"""
标题关键词分类器
自动识别标题中的关键词及其类别
支持爆款标题结构分析
"""

import re
from typing import List, Dict, Tuple


class TitleKeywordClassifier:
    """标题关键词分类器"""

    # 关键词类别及对应模式
    KEYWORD_PATTERNS = {
        # 核心关键词 - 产品/服务核心词
        '核心关键词': [
            r'定制水', r'矿泉水', r'纯净水', r'饮用水', r'山泉水',
            r'香肠', r'腊肉', r'肉', r'菜', r'饭', r'汤', r'面',
            r'蛋糕', r'面包', r'饼干', r'零食', r'饮料', r'酒',
            r'手机', r'电脑', r'电视', r'冰箱', r'空调', r'洗衣机',
            r'衣服', r'裤子', r'裙子', r'鞋子', r'包包', r'帽子',
            r'化妆品', r'护肤品', r'口红', r'面膜', r'香水',
            r'汽车', r'电动车', r'自行车', r'家具', r'沙发', r'床',
            r'培训', r'课程', r'咨询', r'服务', r'方案', r'产品'
        ],

        # 长尾关键词 - 具体需求词
        '长尾关键词': [
            r'怎么.*', r'如何.*', r'为什么.*', r'怎么办.*', r'是什么.*',
            r'好不好', r'能不能', r'要不要', r'哪个好', r'哪个更',
            r'多少钱', r'多少岁', r'多久', r'多长时间', r'几天',
            r'怎么做', r'如何做', r'怎么办理', r'怎么选择',
            r'什么牌子', r'什么味道', r'什么意思', r'有什么区别',
            r'要注意', r'需要注意', r'应该注意', r'千万注意',
            r'配方', r'比例', r'做法', r'吃法', r'用法',
            r'教程', r'教学', r'教学', r'秘方', r'秘诀'
        ],

        # 流量关键词 - 吸引点击的词
        '流量关键词': [
            r'泪目', r'哭了', r'感动', r'破防', r'破防了',
            r'没想到', r'竟然', r'居然', r'简直', r'太.*了',
            r'震惊', r'惊讶', r'意外', r'惊喜', r'惊喜了',
            r'火爆', r'爆火', r'走红', r'刷屏', r'封神',
            r'必看', r'必收', r'必学', r'必備', r'收藏',
            r'转发', r'点赞', r'评论', r'关注', r'艾特',
            r'火', r'爆', r'牛', r'强', r'绝', r'神仙',
            r'婆婆', r'妈妈', r'爸爸', r'儿子', r'女儿',
            r'当场', r'瞬间', r'最后', r'结果', r'没想到'
        ],

        # 业务关键词 - 业务相关词
        '业务关键词': [
            r'配方', r'比例', r'做法', r'吃法', r'用法',
            r'教程', r'方法', r'技巧', r'步骤', r'流程',
            r'秘方', r'秘诀', r'诀窍', r'窍门', r'攻略',
            r'指南', r'大全', r'汇总', r'整理', r'推荐',
            r'分享', r'教', r'教你', r'教大家', r'手把手',
            r'批发', r'定制', r'代工', r'加工', r'生产',
            r'招商', r'加盟', r'代理', r'供货', r'源头工厂'
        ],

        # 科普关键词 - 专业/知识词
        '科普关键词': [
            r'原理', r'原因', r'为什么', r'怎么形成的',
            r'技巧', r'窍门', r'诀窍', r'秘诀', r'经验',
            r'知识', r'常识', r'科普', r'讲解', r'说明',
            r'分析', r'解析', r'解读', r'揭秘', r'曝光',
            r'区别', r'差异', r'不同', r'对比', r'比较',
            r'正确', r'错误', r'误区', r'陷阱', r'注意',
            r'禁忌', r'注意事项', r'问题', r'毛病', r'缺点'
        ],

        # 问题关键词 - 疑问句式
        '问题关键词': [
            r'怎么', r'如何', r'为什么', r'怎么办', r'是什么',
            r'好不好', r'能不能', r'要不要', r'哪个', r'哪',
            r'什么', r'多少', r'几', r'是不是', r'有没有',
            r'会不会', r'咋办', r'啥', r'咋', r'么', r'吗', r'呢',
            r'?', r'？', r'吗', r'呢'
        ],

        # 时间关键词 - 时间相关词汇
        '时间关键词': [
            r'今天', r'昨天', r'明天', r'后天', r'前天', r'大前天',
            r'早上', r'上午', r'中午', r'下午', r'晚上', r'凌晨', r'半夜',
            r'几点', r'多久', r'多长时间', r'几小时', r'几分钟',
            r'一年', r'一个月', r'一天', r'一会', r'刚刚', r'刚才',
            r'现在', r'以前', r'从小', r'从小到大',
            r'立春', r'清明', r'端午', r'中秋', r'春节', r'过年',
            r'春天', r'夏天', r'秋天', r'冬天', r'一季度', r'年底',
            r'周日', r'周一', r'周二', r'周三', r'周四', r'周五', r'周六',
            r'周末', r'工作日', r'生日', r'纪念日'
        ],

        # 数字关键词 - 包含数字的词
        '数字关键词': [
            r'\d+岁', r'\d+年', r'\d+月', r'\d+天', r'\d+个',
            r'\d+斤', r'\d+克', r'\d+毫升', r'\d+分钟', r'\d+秒',
            r'\d+次', r'\d+遍', r'\d+步', r'\d+招', r'\d+个技巧',
            r'\d+点', r'\d+分', r'\d+秒', r'一', r'二', r'三', r'四',
            r'五', r'六', r'七', r'八', r'九', r'十', r'百', r'千', r'万',
            r'第一', r'第二', r'第三', r'首先', r'然后', r'最后'
        ],

        # 导航/教程关键词 - 指导性词汇
        '导航/教程关键词': [
            r'教程', r'方法', r'技巧', r'步骤', r'流程', r'顺序',
            r'怎么', r'如何', r'怎样', r'教学', r'分享', r'教',
            r'告诉', r'教你', r'教大家', r'手把手', r'一学就会',
            r'秘方', r'秘诀', r'诀窍', r'窍门', r'攻略',
            r'指南', r'大全', r'汇总', r'整理', r'推荐',
            r'必看', r'必学', r'必收', r'收藏', r'转发'
        ],

        # 情感/情绪关键词 - 表达情感的词
        '情感/情绪关键词': [
            r'感动', r'哭了', r'泪目', r'流泪', r'眼泪', r'伤心',
            r'开心', r'高兴', r'快乐', r'幸福', r'甜蜜', r'温暖',
            r'激动', r'兴奋', r'紧张', r'害怕', r'恐惧', r'担心',
            r'生气', r'愤怒', r'无语', r'崩溃', r'绝望',
            r'惊喜', r'意外', r'震惊', r'惊讶', r'不可思议',
            r'暖心', r'治愈', r'治愈系', r'破防'
        ],

        # 场景/地点关键词 - 场景描述
        '场景关键词': [
            r'在家', r'家里', r'厨房', r'客厅', r'卧室', r'卫生间',
            r'办公室', r'公司', r'学校', r'医院', r'餐厅', r'饭店',
            r'商场', r'超市', r'路上', r'车里', r'车上', r'地铁',
            r'高铁', r'飞机', r'农村', r'城里', r'城市',
            r'户外', r'野外', r'山里', r'海边', r'河边', r'池塘',
            r'小店', r'大排档', r'路边', r'街头', r'直播间'
        ],

        # 评价/对比关键词 - 评价性词汇
        '评价/对比关键词': [
            r'最好', r'最差', r'第一名', r'最牛', r'最强', r'最棒',
            r'不如', r'比.*更', r'比较', r'对比', r'差别', r'区别',
            r'真的', r'假的', r'实测', r'试验', r'亲测', r'尝试',
            r'靠谱', r'不靠谱', r'有用', r'没用', r'有效', r'无效',
            r'值得', r'不值', r'划算', r'亏', r'便宜', r'贵',
            r'好看', r'难看', r'好吃', r'难吃', r'香', r'臭'
        ],

        # 否定关键词
        '否定关键词': [
            r'不要', r'不能', r'别', r'莫', r'不', r'没',
            r'非', r'无', r'未', r'休', r'勿', r'禁止',
            r'不会', r'不准', r'不是', r'没完', r'别再'
        ],

        # 行动/号召关键词
        '行动/号召关键词': [
            r'快来', r'快去', r'赶紧', r'赶快', r'马上', r'立即',
            r'收藏', r'转发', r'点赞', r'评论', r'关注', r'艾特',
            r'分享', r'告诉', r'提醒', r'记得', r'干完',
            r'别错过', r'抓紧', r'错过', r'可惜', r'遗憾'
        ],

        # 修饰/程度关键词
        '修饰/程度关键词': [
            r'超级', r'非常', r'特别', r'极其', r'十分', r'相当',
            r'太', r'真', r'实在', r'简直', r'绝对', r'完全',
            r'彻底', r'万万', r'超', r'巨', r'爆', r'极点', r'极致', r'完美'
        ],

        # 人物/身份关键词
        '人物/身份关键词': [
            r'老公', r'老婆', r'丈夫', r'妻子', r'爸妈', r'父母',
            r'爸爸', r'妈妈', r'爷爷', r'奶奶', r'外公', r'外婆',
            r'儿子', r'女儿', r'孩子', r'宝宝', r'小孩', r'小朋友',
            r'媳妇', r'对象', r'男朋友', r'女朋友',
            r'朋友', r'同学', r'同事', r'老板', r'员工', r'老师',
            r'医生', r'护士', r'警察', r'司机', r'厨师', r'老师傅'
        ],

        # 悬念/好奇心关键词
        '悬念/好奇心关键词': [
            r'猜猜', r'想知道', r'神奇', r'奇怪', r'诡异',
            r'不可思议', r'难以想象', r'真相', r'内幕', r'秘密',
            r'突发', r'曝光'
        ]
    }

    # 关键词类别颜色映射（用于前端展示）
    CATEGORY_COLORS = {
        '核心关键词': 'danger',
        '长尾关键词': 'warning',
        '流量关键词': 'success',
        '业务关键词': 'primary',
        '科普关键词': 'info',
        '问题关键词': 'secondary',
        '时间关键词': 'light',
        '数字关键词': 'dark',
        '导航/教程关键词': 'primary',
        '情感/情绪关键词': 'pink',
        '场景关键词': 'teal',
        '评价/对比关键词': 'orange',
        '否定关键词': 'secondary',
        '行动/号召关键词': 'danger',
        '修饰/程度关键词': 'purple',
        '人物/身份关键词': 'info',
        '悬念/好奇心关键词': 'warning'
    }

    @classmethod
    def classify(cls, title: str) -> Dict[str, List[Dict]]:
        """
        对标题进行关键词分类

        Args:
            title: 标题文本

        Returns:
            分类结果，格式: {类别名: [{'keyword': '关键词', 'position': 位置, 'length': 长度}]}
        """
        if not title:
            return {}

        results = {}

        for category, patterns in cls.KEYWORD_PATTERNS.items():
            matches = []
            for pattern in patterns:
                try:
                    for match in re.finditer(pattern, title):
                        matches.append({
                            'keyword': match.group(),
                            'position': match.start(),
                            'length': len(match.group())
                        })
                except re.error:
                    continue

            if matches:
                results[category] = matches

        return results

    @classmethod
    def get_keywords_summary(cls, title: str) -> Dict:
        """
        获取关键词分类摘要

        Returns:
            {
                'categories': ['问题关键词', '时间关键词', ...],  # 识别到的类别
                'all_keywords': [{'keyword': 'xxx', 'category': '问题关键词'}, ...],  # 所有关键词及类别
                'primary_category': '问题关键词',  # 主要类别（出现最多的）
                'title_type': '疑问句',  # 标题类型
                'title_structure': '核心词+流量词+数字+情绪词',  # 标题结构
                'category_details': {...}  # 详细分类
            }
        """
        classification = cls.classify(title)

        if not classification:
            return {
                'categories': [],
                'all_keywords': [],
                'primary_category': None,
                'title_type': cls._detect_title_type(title),
                'title_structure': '普通标题',
                'category_details': {}
            }

        # 收集所有关键词及其类别
        all_keywords = []
        for category, matches in classification.items():
            for match in matches:
                all_keywords.append({
                    'keyword': match['keyword'],
                    'category': category
                })

        # 找出主要类别（关键词最多的）
        category_counts = {cat: len(matches) for cat, matches in classification.items()}
        primary_category = max(category_counts, key=category_counts.get) if category_counts else None

        # 生成标题结构描述
        title_structure = cls._generate_title_structure(classification)

        return {
            'categories': list(classification.keys()),
            'all_keywords': all_keywords,
            'primary_category': primary_category,
            'title_type': cls._detect_title_type(title),
            'title_structure': title_structure,
            'category_details': classification,
            'category_counts': category_counts
        }

    @classmethod
    def _generate_title_structure(cls, classification: Dict) -> str:
        """生成标题结构描述"""
        structure_parts = []

        # 按优先级顺序检测关键词类别
        priority_categories = [
            ('核心关键词', '核心词'),
            ('流量关键词', '流量词'),
            ('长尾关键词', '长尾词'),
            ('数字关键词', '数字'),
            ('情感/情绪关键词', '情绪词'),
            ('问题关键词', '问题'),
            ('场景关键词', '场景'),
            ('时间关键词', '时间'),
            ('业务关键词', '业务词'),
            ('科普关键词', '科普词'),
            ('修饰/程度关键词', '程度词'),
            ('悬念/好奇心关键词', '悬念'),
            ('导航/教程关键词', '教程'),
            ('人物/身份关键词', '人物')
        ]

        for category, short_name in priority_categories:
            if category in classification:
                structure_parts.append(short_name)

        return '+'.join(structure_parts) if structure_parts else '普通标题'

    @classmethod
    def get_title_structure_display(cls, title: str) -> str:
        """
        获取用于显示的标题结构描述（更直观的格式）

        Returns:
            如：时间关键字+服务关键字+目标人群关键字+地点关键字
        """
        summary = cls.get_keywords_summary(title)
        structure_parts = []

        # 根据识别的类别生成直观的结构描述
        if '时间关键词' in summary.get('categories', []):
            structure_parts.append('时间关键字')
        if '核心关键词' in summary.get('categories', []):
            structure_parts.append('核心业务关键字')
        if '流量关键词' in summary.get('categories', []):
            structure_parts.append('流量关键字')
        if '长尾关键词' in summary.get('categories', []):
            structure_parts.append('长尾需求关键字')
        if '数字关键词' in summary.get('categories', []):
            structure_parts.append('数字')
        if '情感/情绪关键词' in summary.get('categories', []):
            structure_parts.append('情绪关键字')
        if '场景关键词' in summary.get('categories', []):
            structure_parts.append('场景关键字')
        if '人物/身份关键词' in summary.get('categories', []):
            structure_parts.append('人群关键字')
        if '问题关键词' in summary.get('categories', []):
            structure_parts.append('问题关键字')
        if '修饰/程度关键词' in summary.get('categories', []):
            structure_parts.append('程度关键字')

        return '+'.join(structure_parts) if structure_parts else '普通标题'

    @classmethod
    def _detect_title_type(cls, title: str) -> str:
        """检测标题类型"""
        # 疑问句
        question_markers = ['吗', '呢', '？', '怎么', '如何', '为什么', '是不是', '有没有', '?']
        if any(marker in title for marker in question_markers):
            return '疑问句'

        # 感叹句
        exclamation_markers = ['！', '啊', '呀', '哇']
        if any(marker in title for marker in exclamation_markers):
            return '感叹句'

        # 命令/祈使句
        command_markers = ['快来', '赶紧', '赶快', '马上', '立即', '收藏', '转发', '点赞', '别错过']
        if any(marker in title for marker in command_markers):
            return '命令句'

        # 陈述句
        return '陈述句'

    @classmethod
    def format_display(cls, title: str) -> str:
        """
        格式化输出关键词分类结果（用于展示）

        Returns:
            HTML格式的分类结果
        """
        summary = cls.get_keywords_summary(title)

        if not summary['categories']:
            return f'''
            <div class="mb-2">
                <span class="fw-medium">标题类型：</span>
                <span class="badge bg-secondary">{summary['title_type']}</span>
            </div>
            <div class="text-muted small">未能识别出特定关键词类别</div>
            '''

        # 构建HTML
        html = f'''
        <div class="mb-2">
            <span class="fw-medium">标题类型：</span>
            <span class="badge bg-info me-2">{summary['title_type']}</span>
            <span class="badge bg-dark ms-1">{summary['title_structure']}</span>
        </div>
        <div class="mb-2">
            <span class="fw-medium">主要类别：</span>
            <span class="badge bg-primary">{summary['primary_category']}</span>
        </div>
        <div class="mb-2">
            <span class="fw-medium">识别类别：</span>
            {''.join(f'<span class="badge bg-light text-dark me-1 mb-1">{cat}</span>' for cat in summary['categories'])}
        </div>
        '''

        # 添加各类别关键词
        for category, matches in summary['category_details'].items():
            keywords = list({m['keyword'] for m in matches})  # 去重
            color = cls.CATEGORY_COLORS.get(category, 'secondary')
            html += f'''
            <div class="mt-2">
                <small class="text-muted">{category}：</small>
                <span class="small">{' '.join(f'<span class="badge bg-{color} me-1">{k}</span>' for k in keywords[:5])}</span>
            </div>
            '''

        return html

    @classmethod
    def calculate_scores(cls, title: str) -> Dict:
        """
        计算标题各维度评分（满分10分）

        Returns:
            {
                'total_score': 总分,
                'scores': {
                    'keyword_diversity': 关键词多样性,
                    'structure_complexity': 结构复杂度,
                    'emotion_impact': 情绪感染力,
                    'specificity': 具体性,
                    'click_appeal': 吸引力
                },
                'strengths': 优点列表,
                'weaknesses': 缺点列表,
                'suggestions': 改进建议
            }
        """
        summary = cls.get_keywords_summary(title)
        scores = {}
        strengths = []
        weaknesses = []
        suggestions = []

        # 1. 关键词多样性 (满分10)
        # 有核心词+流量词+长尾词+数字+情绪词 = 10分，每少一种扣2分
        categories = summary.get('categories', [])
        keyword_score = min(10, len(categories) * 2)
        if '核心关键词' not in categories:
            weaknesses.append('缺少核心业务关键词')
            suggestions.append('建议添加产品/服务核心词')
        else:
            strengths.append('包含核心业务关键词')
        if '流量关键词' not in categories:
            weaknesses.append('缺少流量吸引词')
            suggestions.append('建议添加"婆婆泪目"、"没想到"等流量词')
        else:
            strengths.append('包含流量关键词')
        if '数字关键词' not in categories:
            weaknesses.append('缺少数字元素')
            suggestions.append('建议添加"48小时"、"3步"等数字增强可信度')
        else:
            strengths.append('包含数字关键词')
        scores['keyword_diversity'] = keyword_score

        # 2. 结构复杂度 (满分10)
        # 根据识别出的类别数量和结构复杂程度评分
        structure = summary.get('title_structure', '')
        structure_parts = structure.split('+') if structure else []
        structure_score = min(10, len(structure_parts) * 2 + 2)
        if len(structure_parts) >= 4:
            strengths.append('标题结构丰富，多元素组合')
        elif len(structure_parts) >= 2:
            strengths.append('标题结构合理')
        else:
            weaknesses.append('标题结构较简单')
            suggestions.append('建议增加更多关键词元素')
        scores['structure_complexity'] = structure_score

        # 3. 情绪感染力 (满分10)
        emotion_score = 5  # 基础分
        if '情感/情绪关键词' in categories:
            emotion_score += 3
            strengths.append('包含情绪感染词')
        if '悬念/好奇心关键词' in categories:
            emotion_score += 2
            strengths.append('包含悬念词引发好奇')
        if '感叹句' in summary.get('title_type', ''):
            emotion_score += 2
        scores['emotion_impact'] = min(10, emotion_score)

        # 4. 具体性 (满分10)
        specificity_score = 5  # 基础分
        if '长尾关键词' in categories:
            specificity_score += 3
            strengths.append('包含长尾关键词精准触达用户')
        if '时间关键词' in categories:
            specificity_score += 2
            strengths.append('包含时间元素增强紧迫感')
        if '场景关键词' in categories:
            specificity_score += 2
            strengths.append('包含场景词增强代入感')
        scores['specificity'] = min(10, specificity_score)

        # 5. 吸引力 (满分10)
        appeal_score = 5  # 基础分
        if '流量关键词' in categories:
            appeal_score += 2
        if '修饰/程度关键词' in categories:
            appeal_score += 2
            strengths.append('使用程度词增强感染力')
        if '否定关键词' in categories:
            appeal_score += 1
        if summary.get('title_type') == '感叹句':
            appeal_score += 2
        elif summary.get('title_type') == '疑问句':
            appeal_score += 3
            strengths.append('疑问句式引发用户思考')
        scores['click_appeal'] = min(10, appeal_score)

        # 计算总分
        total_score = sum(scores.values()) / len(scores) if scores else 0

        return {
            'total_score': round(total_score, 1),
            'scores': {k: round(v, 1) for k, v in scores.items()},
            'strengths': strengths[:5],
            'weaknesses': weaknesses[:5],
            'suggestions': suggestions[:5]
        }

    # 已知的优质标题结构模式（用于匹配规则库）
    KNOWN_TITLE_STRUCTURES = [
        '核心词+流量词+数字',  # 如：香肠灌好48小时竟然
        '核心词+时间+流量词',  # 如：在南漳48小时翻新旧厨柜
        '流量词+核心词+数字+情绪词',  # 如：婆婆泪目定制水竟
        '核心词+长尾词+数字',  # 如：灌香肠最佳时间3个技巧
        '问题+核心词+解决方案',  # 如：香肠破了怎么办
        '时间+地点+服务+目标人群',  # 如：在南漳48小时翻新
    ]


def classify_title_keywords(title: str) -> Dict:
    """
    便捷函数：对标题进行关键词分类

    Args:
        title: 标题文本

    Returns:
        分类结果字典
    """
    return TitleKeywordClassifier.get_keywords_summary(title)


if __name__ == '__main__':
    # 测试
    test_titles = [
        "香肠灌好以后要放几天才能晒",
        "灌香肠最佳时间是什么时候",
        "香肠破了怎么办教你轻松补救",
        "正宗川味香肠配方比例",
        "香肠一蒸就爆原来是这原因",
        "婆婆当场泪目了",
        "满月酒定制水婆婆当场泪目了_龙眼山矿泉水"
    ]

    for title in test_titles:
        print(f"\n{'='*60}")
        print(f"标题: {title}")
        result = classify_title_keywords(title)
        print(f"标题类型: {result['title_type']}")
        print(f"标题结构: {result['title_structure']}")
        print(f"主要类别: {result['primary_category']}")
        print(f"识别类别: {result['categories']}")
        print(f"关键词: {result['all_keywords'][:10]}")
