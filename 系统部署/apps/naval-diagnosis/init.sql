-- 纳瓦尔商业诊断系统 数据库初始化

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    openid VARCHAR(64) UNIQUE,
    nickname VARCHAR(100),
    phone VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 诊断会话表
CREATE TABLE IF NOT EXISTS diagnosis_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    status VARCHAR(20) DEFAULT 'in_progress',
    current_question INT DEFAULT 0,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    session_data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 问卷问题表
CREATE TABLE IF NOT EXISTS questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_key VARCHAR(50) NOT NULL,
    question_type VARCHAR(20) NOT NULL,
    category VARCHAR(50),
    content JSONB NOT NULL,
    options JSONB,
    is_required BOOLEAN DEFAULT true,
    is_active BOOLEAN DEFAULT true,
    display_order INT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 问卷答案表
CREATE TABLE IF NOT EXISTS answers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES diagnosis_sessions(id) ON DELETE CASCADE,
    question_key VARCHAR(50) NOT NULL,
    answer_value JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 诊断结果表
CREATE TABLE IF NOT EXISTS diagnosis_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES diagnosis_sessions(id) ON DELETE CASCADE UNIQUE,
    user_id UUID REFERENCES users(id),
    -- 分数
    total_score INT DEFAULT 0,
    -- LLM推断结果
    inferred_value_type VARCHAR(50),
    inferred_asset_type VARCHAR(50),
    inferred_leverage JSONB DEFAULT '[]',
    -- 阶段
    current_stage VARCHAR(50),
    stage_label VARCHAR(100),
    -- 结论
    strengths JSONB DEFAULT '[]',
    weaknesses JSONB DEFAULT '[]',
    insights JSONB DEFAULT '[]',
    recommendations JSONB DEFAULT '[]',
    -- 原始数据
    raw_data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 分享表
CREATE TABLE IF NOT EXISTS report_shares (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    result_id UUID REFERENCES diagnosis_results(id) ON DELETE CASCADE,
    share_code VARCHAR(20) UNIQUE,
    view_count INT DEFAULT 0,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_users_openid ON users(openid);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON diagnosis_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON diagnosis_sessions(status);
CREATE INDEX IF NOT EXISTS idx_answers_session ON answers(session_id);
CREATE INDEX IF NOT EXISTS idx_results_session ON diagnosis_results(session_id);
CREATE INDEX IF NOT EXISTS idx_shares_code ON report_shares(share_code);

-- 插入默认问题
INSERT INTO questions (question_key, question_type, category, content, options, display_order) VALUES
-- 问题1：你靠什么赚钱
('q1_earn_type', 'single_choice', 'value_type', 
 '{"title": "你主要靠什么赚钱？", "subtitle": "选择最接近的方式", "image": "earn"}',
 '[{"value": "product", "label": "卖产品", "icon": "📦", "description": "实物或数字产品"}, {"value": "skill", "label": "卖手艺", "icon": "🛠️", "description": "设计、编程等服务"}, {"value": "knowledge", "label": "卖知识", "icon": "📚", "description": "咨询、培训等服务"}, {"value": "labor", "label": "卖体力", "icon": "💪", "description": "服务、跑腿等"}]',
 1),

-- 问题2：能不能复制
('q2_replicable', 'single_choice', 'asset_type',
 '{"title": "这件事，除了你别人能做吗？", "subtitle": "想想你的不可替代性", "image": "unique"}',
 '[{"value": "only_me", "label": "只有我能做", "icon": "🦸", "description": "独特能力，很难复制"}, {"value": "need_train", "label": "需要培训一段时间", "icon": "📖", "description": "需要学习才能做"}, {"value": "anyone", "label": "随便谁都能做", "icon": "🤷", "description": "门槛较低"}]',
 2),

-- 问题3：休息一周会怎样
('q3_pause_week', 'single_choice', 'asset_type',
 '{"title": "如果你休息一周，业务会怎样？", "subtitle": "测试你的依赖程度", "image": "pause"}',
 '[{"value": "stop", "label": "完全停止", "icon": "🛑", "description": "没有你就转不了"}, {"value": "some_impact", "label": "有点影响", "icon": "⚠️", "description": "勉强能维持"}, {"value": "no_impact", "label": "完全不受影响", "icon": "🚀", "description": "自动化运转"}]',
 3),

-- 问题4：有没有团队
('q4_team', 'single_choice', 'leverage',
 '{"title": "你是单打独斗还是有团队？", "subtitle": "看看你的杠杆情况", "image": "team"}',
 '[{"value": "alone", "label": "一个人", "icon": "🧑", "description": "全靠自己"}, {"value": "small_team", "label": "2-5人小团队", "icon": "👥", "description": "有人帮忙分担"}, {"value": "big_team", "label": "5人以上团队", "icon": "🏢", "description": "规模化运营"}]',
 4),

-- 问题5：有没有做内容
('q5_content', 'single_choice', 'leverage',
 '{"title": "你有没有在抖音、小红书等平台发内容？", "subtitle": "看看你的获客方式", "image": "content"}',
 '[{"value": "yes_active", "label": "有在做", "icon": "✅", "description": "定期发布内容"}, {"value": "yes_sometimes", "label": "偶尔发发", "icon": "📝", "description": "不太规律"}, {"value": "no", "label": "没在做", "icon": "❌", "description": "没时间/不会"}]',
 5),

-- 问题6：客户从哪来
('q6_client_source', 'single_choice', 'leverage',
 '{"title": "你的新客户一般从哪里来？", "subtitle": "看看你的获客效率", "image": "clients"}',
 '[{"value": "referral", "label": "朋友/老客户介绍", "icon": "🤝", "description": "口碑转介绍"}, {"value": "active", "label": "自己主动推广", "icon": "📢", "description": "发广告、群发等"}, {"value": "passive", "label": "客户主动找上门", "icon": "📞", "description": "自然流量"}]',
 6),

-- 问题7：有没有睡后收入
('q7_passive_income', 'single_choice', 'leverage',
 '{"title": "你有没有"睡着也能赚钱"的收入？", "subtitle": "比如课程、版权、租金等", "image": "passive"}',
 '[{"value": "yes", "label": "有", "icon": "💰", "description": "有被动收入来源"}, {"value": "some", "label": "有一点", "icon": "🪙", "description": "占比不高"}, {"value": "no", "label": "没有", "icon": "⏰", "description": "完全靠劳动"}]',
 7),

-- 问题8：收入天花板
('q8_income_limit', 'single_choice', 'value_type',
 '{"title": "你觉得自己的收入有天花板吗？", "subtitle": "想想你的上升空间", "image": "ceiling"}',
 '[{"value": "very_high", "label": "几乎没上限", "icon": "♾️", "description": "可以无限增长"}, {"value": "some_limit", "label": "有一定上限", "icon": "📊", "description": "增长会放缓"}, {"value": "very_limited", "label": "上限很明显", "icon": "🚧", "description": "很难突破"}]',
 8),

-- 问题9：有没有可复制的模式
('q9_model', 'single_choice', 'asset_type',
 '{"title": "你的业务有没有可复制的模式？", "subtitle": "比如标准流程、产品化", "image": "model"}',
 '[{"value": "yes_standard", "label": "有标准流程", "icon": "📋", "description": "可以复制放大"}, {"value": "some_formal", "label": "有点规范", "icon": "📄", "description": "还不够标准化"}, {"value": "chaos", "label": "比较随意", "icon": "🌀", "description": "全靠经验"}]',
 9),

-- 问题10：想不想做大
('q10_ambition', 'single_choice', 'value_type',
 '{"title": "你未来想把这件事做大吗？", "subtitle": "决定你的天花板", "image": "ambition"}',
 '[{"value": "very_much", "label": "当然想", "icon": "🚀", "description": "想做大事业"}, {"value": "somewhat", "label": "还好", "icon": "🤔", "description": "随缘发展"}, {"value": "no_need", "label": "不想太累", "icon": "☀️", "description": "够用就行"}]',
 10)

ON CONFLICT (question_key) DO NOTHING;
