"""
迁移脚本：添加图文内容规则配置表

在 public_models.py 中添加以下表：
1. GraphicContentRule - 图文内容规则主表
2. ImageTemplateRule - 每张图片的定位/情绪规范
3. HeadlineRule - 大字金句规范
4. DesignRule - 设计规格（色彩/字体）
5. SeoRule - SEO标签规则
6. PublishRule - 发布时间策略

运行方式：cd /Volumes/增元/项目/douyin/系统部署 && python3 -c "from migrations.add_graphic_rules import run_migration; run_migration()"
"""

from datetime import datetime
from models.models import db
from models.public_models import PublicUser
from app import app


class GraphicContentRule(db.Model):
    """图文内容规则主表"""
    __tablename__ = 'graphic_content_rules'
    __table_args__ = (
        db.Index('idx_rule_industry', 'industry'),
        db.Index('idx_rule_customer', 'target_customer'),
    )

    id = db.Column(db.Integer, primary_key=True)
    # 规则名称
    rule_name = db.Column(db.String(100), nullable=False)
    # 适用行业（为空表示通用）
    industry = db.Column(db.String(50))
    # 适用客户类型（为空表示通用）
    target_customer = db.Column(db.String(50))

    # 内容结构配置
    image_count = db.Column(db.Integer, default=5)  # 图片数量
    image_ratio = db.Column(db.String(20), default='9:16')  # 图片比例
    structure_type = db.Column(db.String(50))  # 结构类型

    # 规则配置（JSON格式存储详细规则）
    # 包含图片模板、大字金句、设计规格等
    rule_config = db.Column(db.JSON)

    # 状态
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)  # 是否默认规则

    # 版本控制
    version = db.Column(db.String(20), default='v1')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<GraphicContentRule {self.rule_name}>'


class ImageTemplateRule(db.Model):
    """图片模板规范表 - 5张图的详细规则"""
    __tablename__ = 'image_template_rules'
    __table_args__ = (
        db.Index('idx_img_rule_config', 'rule_id', 'image_index'),
    )

    id = db.Column(db.Integer, primary_key=True)
    # 关联规则ID
    rule_id = db.Column(db.Integer, db.ForeignKey('graphic_content_rules.id'), nullable=False)

    # 图片序号（1-5）
    image_index = db.Column(db.Integer, nullable=False)

    # 图片定位：戳痛点/分析原因/揭示误区/解决方案/总结引导
    positioning = db.Column(db.String(50))
    # 情绪基调：震惊/焦虑/共鸣/释然/紧迫
    emotion = db.Column(db.String(50))
    # 功能作用
    function = db.Column(db.String(100))
    # 大字要求描述
    headline_requirement = db.Column(db.Text)

    # 是否必须先戳痛点
    must_pain_first = db.Column(db.Boolean, default=True)

    # 其他配置（JSON）
    extra_config = db.Column(db.JSON)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ImageTemplateRule 图片{self.image_index}>'


class HeadlineRule(db.Model):
    """大字金句规范表"""
    __tablename__ = 'headline_rules'
    __table_args__ = (
        db.Index('idx_headline_rule', 'rule_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey('graphic_content_rules.id'), nullable=False)

    # 金句类型：main_title/ pain_point / revelation / solution
    headline_type = db.Column(db.String(50), nullable=False)
    # 类型名称
    type_name = db.Column(db.String(50))

    # 规则配置
    char_min = db.Column(db.Integer, default=5)  # 最少字数
    char_max = db.Column(db.Integer, default=10)  # 最多字数
    # 位置要求
    position_requirement = db.Column(db.String(100))
    # 作用描述
    function_desc = db.Column(db.Text)

    # 示例
    examples = db.Column(db.JSON)

    # 强制要求
    is_required = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<HeadlineRule {self.headline_type}>'


class DesignRule(db.Model):
    """设计规格表"""
    __tablename__ = 'design_rules'
    __table_args__ = (
        db.Index('idx_design_rule', 'rule_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey('graphic_content_rules.id'), nullable=False)

    # 规格类型：color_scheme/font/layout/forbidden
    design_type = db.Column(db.String(50), nullable=False)

    # 配置数据（JSON格式）
    # 色彩方案：{"主色调": "#xxx", "辅助色": "#xxx", ...}
    # 字体规范：{"允许": [...], "禁止": [...]}
    # 排版要求：{"对齐": "...", "间距": "...", "简洁度": "..."}
    # 禁止项：[...]
    config_data = db.Column(db.JSON)

    # 描述
    description = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<DesignRule {self.design_type}>'


class SeoRule(db.Model):
    """SEO标签规则表"""
    __tablename__ = 'seo_rules'
    __table_args__ = (
        db.Index('idx_seo_rule', 'rule_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey('graphic_content_rules.id'), nullable=False)

    # 标签数量
    tag_count = db.Column(db.Integer, default=6)
    # 标签类型配置（JSON）
    # {"区域词": true, "品牌词": true, "长尾词": true, "热点词": false}
    tag_types = db.Column(db.JSON)

    # 关键词类型配置（JSON）
    # {"核心词": true, "痛点词": true, "场景词": false, "长尾词": true}
    keyword_types = db.Column(db.JSON)

    # 生成规则描述
    rule_description = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<SeoRule rule_id={self.rule_id}>'


class PublishRule(db.Model):
    """发布时间策略表"""
    __tablename__ = 'publish_rules'
    __table_args__ = (
        db.Index('idx_publish_rule', 'rule_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey('graphic_content_rules.id'), nullable=False)

    # 发布时间配置（JSON）
    # [{"day": "周一", "time": "07:30", "reason": "通勤时间"}, ...]
    schedule_config = db.Column(db.JSON)

    # 合规检查项（JSON）
    # ["禁止绝对化用语", "禁止虚假宣传", ...]
    compliance_checklist = db.Column(db.JSON)

    # 规则描述
    rule_description = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<PublishRule rule_id={self.rule_id}>'


# 默认规则数据
DEFAULT_GRAPHIC_RULE = {
    'rule_name': '默认图文规则',
    'image_count': 5,
    'image_ratio': '9:16',
    'structure_type': '痛点递进',
    'rule_config': {},
}

DEFAULT_IMAGE_TEMPLATES = [
    {'image_index': 1, 'positioning': '戳痛点', 'emotion': '震惊/焦虑', 'function': '直接呈现用户痛苦', 'headline_requirement': '痛点词3-5字，醒目位置'},
    {'image_index': 2, 'positioning': '分析原因', 'emotion': '好奇/追问', 'function': '为什么会这样？', 'headline_requirement': '揭秘语5-8字'},
    {'image_index': 3, 'positioning': '揭示误区', 'emotion': '共鸣/对比', 'function': '你以为...其实...', 'headline_requirement': '误区揭示5-8字'},
    {'image_index': 4, 'positioning': '解决方案', 'emotion': '期待/释然', 'function': '终于等到...', 'headline_requirement': '方案名5字内'},
    {'image_index': 5, 'positioning': '总结引导', 'emotion': '紧迫/行动', 'function': '快试试/评论区见', 'headline_requirement': '行动号召3-5字'},
]

DEFAULT_HEADLINE_RULES = [
    {'headline_type': 'main_title', 'type_name': '主标题', 'char_min': 5, 'char_max': 7, 'position_requirement': '图片1/3处', 'function_desc': '吸引点击'},
    {'headline_type': 'pain_point', 'type_name': '痛点词', 'char_min': 3, 'char_max': 5, 'position_requirement': '醒目突出', 'function_desc': '戳中痛点'},
    {'headline_type': 'revelation', 'type_name': '揭秘语', 'char_min': 5, 'char_max': 8, 'position_requirement': 'C位', 'function_desc': '揭示真相'},
    {'headline_type': 'solution', 'type_name': '方案名', 'char_min': 3, 'char_max': 5, 'position_requirement': '显眼', 'function_desc': '给出答案'},
]

DEFAULT_DESIGN_RULES = [
    {'design_type': 'color_scheme', 'config_data': {'主色调': '#007AFF', '辅助色': '#5856D6', '警示色': '#FF3B30', '信任色': '#34C759'}},
    {'design_type': 'font', 'config_data': {'允许': ['苹方', '思源黑体', 'Helvetica'], '禁止': ['华文彩云', '幼圆', '楷体']}},
    {'design_type': 'layout', 'config_data': {'对齐': '左对齐或居中', '间距': '留白充足', '简洁度': '核心内容突出'}},
    {'design_type': 'forbidden', 'config_data': ['纯色背景', 'emoji', '特殊符号', '花哨字体']},
]

DEFAULT_SEO_RULE = {
    'tag_count': 6,
    'tag_types': {'区域词': True, '品牌词': True, '长尾词': True, '热点词': False},
    'keyword_types': {'核心词': True, '痛点词': True, '场景词': True, '长尾词': True},
}

DEFAULT_PUBLISH_RULE = {
    'schedule_config': [
        {'day': '周一', 'time': '07:30', 'reason': '通勤时间'},
        {'day': '周二', 'time': '12:00', 'reason': '午休时间'},
        {'day': '周三', 'time': '20:30', 'reason': '晚间放松'},
        {'day': '周四', 'time': '12:00', 'reason': '午休时间'},
        {'day': '周五', 'time': '18:00', 'reason': '下班路上'},
        {'day': '周六', 'time': '10:00', 'reason': '周末休闲'},
        {'day': '周日', 'time': '20:00', 'reason': '周末晚间'},
    ],
    'compliance_checklist': ['禁止绝对化用语', '禁止虚假宣传', '禁止侵权内容', '禁止低俗内容'],
}


def init_default_rules(created_by=None):
    """初始化默认规则"""
    # 检查是否已有默认规则
    existing = GraphicContentRule.query.filter_by(is_default=True).first()
    if existing:
        print('默认规则已存在，跳过初始化')
        return existing

    # 创建主规则
    rule = GraphicContentRule(
        rule_name=DEFAULT_GRAPHIC_RULE['rule_name'],
        image_count=DEFAULT_GRAPHIC_RULE['image_count'],
        image_ratio=DEFAULT_GRAPHIC_RULE['image_ratio'],
        structure_type=DEFAULT_GRAPHIC_RULE['structure_type'],
        rule_config=DEFAULT_GRAPHIC_RULE['rule_config'],
        is_active=True,
        is_default=True,
        created_by=created_by,
    )
    db.session.add(rule)
    db.session.flush()

    # 创建图片模板
    for template in DEFAULT_IMAGE_TEMPLATES:
        img_rule = ImageTemplateRule(
            rule_id=rule.id,
            **template
        )
        db.session.add(img_rule)

    # 创建大字金句规则
    for headline in DEFAULT_HEADLINE_RULES:
        hl_rule = HeadlineRule(
            rule_id=rule.id,
            **headline,
            is_required=True
        )
        db.session.add(hl_rule)

    # 创建设计规则
    for design in DEFAULT_DESIGN_RULES:
        ds_rule = DesignRule(
            rule_id=rule.id,
            **design
        )
        db.session.add(ds_rule)

    # 创建SEO规则
    seo_rule = SeoRule(
        rule_id=rule.id,
        **DEFAULT_SEO_RULE
    )
    db.session.add(seo_rule)

    # 创建发布规则
    publish_rule = PublishRule(
        rule_id=rule.id,
        **DEFAULT_PUBLISH_RULE
    )
    db.session.add(publish_rule)

    db.session.commit()
    print(f'默认图文规则创建成功，ID: {rule.id}')
    return rule


def run_migration():
    """运行迁移"""
    with app.app_context():
        db.create_all()
        print('数据库表创建完成')
        init_default_rules()
        print('迁移完成')


if __name__ == '__main__':
    run_migration()
