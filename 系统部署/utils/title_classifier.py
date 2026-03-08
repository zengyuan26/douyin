# -*- coding: utf-8 -*-
"""
标题关键词分类器
自动识别标题中的关键词及其类别
"""

import re
from typing import List, Dict, Tuple


class TitleKeywordClassifier:
    """标题关键词分类器"""
    
    # 关键词类别及对应模式
    KEYWORD_PATTERNS = {
        # 问题关键词 - 疑问句式
        '问题关键词': [
            r'怎么', r'如何', r'为什么', r'怎么办', r'是什么', r'好不好', 
            r'能不能', r'要不要', r'哪个', r'哪', r'什么', r'多少',
            r'几', r'是不是', r'有没有', r'会不会', r'为什么', r'咋办',
            r'啥', r'咋', r'么', r'吗', r'呢'
        ],
        
        # 时间关键词 - 时间相关词汇
        '时间关键词': [
            r'今天', r'昨天', r'明天', r'后天', r'前天', r'大前天',
            r'早上', r'上午', r'中午', r'下午', r'晚上', r'凌晨', r'半夜',
            r'几点', r'多久', r'多长时间', r'几小时', r'几分钟',
            r'一年', r'一个月', r'一天', r'一会', r'刚刚', r'刚才',
            r'现在', r'以前', r'以前', r'以前', r'从小', r'从小到大',
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
            r'教学', r'秘方', r'秘诀', r'诀窍', r'窍门', r'攻略',
            r'指南', r'大全', r'汇总', r'整理', r'汇总', r'推荐',
            r'必看', r'必学', r'必收', r'收藏', r'转发'
        ],
        
        # 情感/情绪关键词 - 表达情感的词
        '情感/情绪关键词': [
            r'感动', r'哭了', r'泪目', r'流泪', r'眼泪', r'伤心',
            r'开心', r'高兴', r'快乐', r'幸福', r'甜蜜', r'温暖',
            r'激动', r'兴奋', r'紧张', r'害怕', r'恐惧', r'担心',
            r'生气', r'愤怒', r'生气', r'无语', r'崩溃', r'绝望',
            r'惊喜', r'意外', r'震惊', r'惊讶', r'不可思议',
            r'感动', r'暖心', r'治愈', r'治愈系', r'破防'
        ],
        
        # 场景/地点关键词 - 场景描述
        '场景关键词': [
            r'在家', r'家里', r'厨房', r'客厅', r'卧室', r'卫生间',
            r'办公室', r'公司', r'学校', r'医院', r'餐厅', r'饭店',
            r'商场', r'超市', r'路上', r'车里', r'车上', r'地铁',
            r'高铁', r'飞机', r'农村', r'城里', r'城市', r'农村',
            r'户外', r'野外', r'山里', r'海边', r'河边', r'池塘',
            r'饭店', r'餐馆', r'小店', r'大排档', r'路边', r'街头'
        ],
        
        # 评价/对比关键词 - 评价性词汇
        '评价/对比关键词': [
            r'最好', r'最差', r'第一名', r'最牛', r'最强', r'最棒',
            r'不如', r'比', r'比较', r'对比', r'差别', r'区别',
            r'真的', r'假的', r'实测', r'试验', r'亲测', r'尝试',
            r'靠谱', r'不靠谱', r'有用', r'没用', r'有效', r'无效',
            r'值得', r'不值', r'划算', r'亏', r'便宜', r'贵',
            r'好看', r'难看', r'好吃', r'难吃', r'香', r'臭'
        ],
        
        # 否定关键词
        '否定关键词': [
            r'不要', r'不能', r'不要', r'别', r'莫', r'不', r'没',
            r'非', r'无', r'未', r'别', r'休', r'勿', r'禁止',
            r'不能', r'不会', r'不要', r'不准', r'不是', r'没完'
        ],
        
        # 行动/号召关键词
        '行动/号召关键词': [
            r'快来', r'快去', r'赶紧', r'赶快', r'马上', r'立即',
            r'收藏', r'转发', r'点赞', r'评论', r'关注', r'艾特',
            r'分享', r'告诉', r'提醒', r'记得', r'千完', r'不要错过',
            r'别错过', r'抓紧', r'错过', r'可惜', r'遗憾'
        ],
        
        # 原因/结果关键词
        '原因/结果关键词': [
            r'因为', r'所以', r'由于', r'因此', r'导致', r'造成',
            r'结果', r'所以', r'因此', r'于是', r'然后', r'接着',
            r'于是', r'因此', r'原来', r'难怪', r'难怪', r'居然',
            r'竟然', r'原来', r'原因', r'理由', r'为了', r'目的'
        ],
        
        # 产品/品牌关键词
        '产品关键词': [
            r'定制', r'定制水', r'矿泉水', r'饮用水', r'纯净水',
            r'冰箱', r'空调', r'洗衣机', r'电视', r'手机', r'电脑',
            r'汽车', r'电动车', r'自行车', r'飞机', r'高铁',
            r'化妆品', r'护肤品', r'口红', r'面膜', r'香水',
            r'衣服', r'裤子', r'裙子', r'鞋子', r'帽子', r'包包',
            r'家具', r'沙发', r'床', r'桌子', r'椅子', r'柜子',
            r'食材', r'蔬菜', r'水果', r'肉类', r'海鲜', r'调料'
        ],
        
        # 修饰/程度关键词
        '修饰/程度关键词': [
            r'超级', r'非常', r'特别', r'极其', r'十分', r'相当',
            r'太', r'真', r'实在', r'简直', r'绝对', r'完全',
            r'彻底', r'居然', r'竟然', r'没想到', r'万万',
            r'超', r'巨', r'爆', r'极点', r'极致', r'完美'
        ],
        
        # 人物/身份关键词
        '人物/身份关键词': [
            r'老公', r'老婆', r'丈夫', r'妻子', r'爸妈', r'父母',
            r'爸爸', r'妈妈', r'爷爷', r'奶奶', r'外公', r'外婆',
            r'儿子', r'女儿', r'孩子', r'宝宝', r'小孩', r'小朋友',
            r'老公', r'媳妇', r'对象', r'男朋友', r'女朋友',
            r'朋友', r'同学', r'同事', r'老板', r'员工', r'老师',
            r'医生', r'护士', r'警察', r'司机', r'厨师', r'老师傅'
        ],
        
        # 悬念/好奇心关键词
        '悬念/好奇心关键词': [
            r'竟然', r'居然', r'没想到', r'猜猜', r'想知道',
            r'神奇', r'奇怪', r'诡异', r'不可思议', r'难以想象',
            r'真相', r'内幕', r'秘密', r'秘密', r'曝光',
            r'突发', r'意外', r'惊喜', r'意外', r'没想到'
        ]
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
                for match in re.finditer(pattern, title):
                    matches.append({
                        'keyword': match.group(),
                        'position': match.start(),
                        'length': len(match.group())
                    })
            
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
                'title_type': '疑问句'  # 标题类型判断
            }
        """
        classification = cls.classify(title)
        
        if not classification:
            return {
                'categories': [],
                'all_keywords': [],
                'primary_category': None,
                'title_type': cls._detect_title_type(title)
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
        
        return {
            'categories': list(classification.keys()),
            'all_keywords': all_keywords,
            'primary_category': primary_category,
            'title_type': cls._detect_title_type(title),
            'category_details': classification
        }
    
    @classmethod
    def _detect_title_type(cls, title: str) -> str:
        """检测标题类型"""
        # 疑问句
        question_markers = ['吗', '呢', '？', '怎么', '如何', '为什么', '是不是', '有没有']
        if any(marker in title for marker in question_markers) or title.endswith('?'):
            return '疑问句'
        
        # 感叹句
        exclamation_markers = ['！', '啊', '呀', '哇', '太', '真']
        if any(marker in title for marker in exclamation_markers):
            return '感叹句'
        
        # 命令/祈使句
        command_markers = ['快来', '赶紧', '赶快', '马上', '立即', '收藏', '转发', '点赞']
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
            html += f'''
            <div class="mt-2">
                <small class="text-muted">{category}：</small>
                <span class="small">{' '.join(keywords[:5])}</span>
            </div>
            '''
        
        return html


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
        "婆婆当场泪目了"
    ]
    
    for title in test_titles:
        print(f"\n{'='*60}")
        print(f"标题: {title}")
        result = classify_title_keywords(title)
        print(f"标题类型: {result['title_type']}")
        print(f"主要类别: {result['primary_category']}")
        print(f"识别类别: {result['categories']}")
        print(f"关键词: {result['all_keywords'][:10]}")
