# 图文内容模板 (Graphic)

## 概述
基于四维图文设计方法论生成高质量图文内容，适用于小红书、抖音图文、朋友圈等平台。

## 四维设计方法论

### 维度一：情绪动线逻辑
7帧画面严格遵循情绪曲线：
- P1 封面引流帧：期待/好奇，制造悬念
- P2 共情痛点帧：心酸/代入，建立信任
- P3 干货拆解帧（分步）：坚定/专业
- P4 干货拆解帧（对比）：爆发/顿悟
- P5 干货拆解帧（总结）：强化记忆
- P6 升华温暖帧：释然/感动
- P7 收尾转化帧：温暖/行动

### 维度二：视觉资产一致性
三层强制约束：
1. 人物/主体连贯性：同一人物贯穿全部镜头
2. 光影镜头逻辑：柔和自然光 + 低饱和柔焦质感
3. 色彩动态递进：冷色（痛点）→ 暖色（方案）→ 品牌色（闭环）

### 维度三：信息层级架构
- 1核：单帧1个核心焦点
- 3区：场景区 + 符号区 + 点缀区
- 5秒：标题大字 → 图标 → 关键词 → CTA

### 维度四：高转化排版版式
4种版式：
- `billboard`：封面版式（中心人物+大字）
- `problem_solver`：痛点对比版式（❌✅符号）
- `matrix`：干货矩阵版式（等分分镜）
- `trust_builder`：品牌收尾版式（CTA按钮）

## 排版×页码分配
| 页码 | 版式 | 情绪 |
|------|------|------|
| P1 | billboard | 期待 |
| P2 | problem_solver | 共情 |
| P3 | matrix | 获得 |
| P4 | problem_solver | 爆发 |
| P5 | matrix | 强化 |
| P6 | billboard/matrix | 升华 |
| P7 | trust_builder | 转化 |

## 色彩方案
```
冷色（痛点页）：#4A5568 灰蓝 / #E8EEF2 冷灰 / #CBD5E1 银灰
暖色（方案页）：#FFF5EE 米色 / #FFDAB9 淡橘 / #F5F0EB 肤色
品牌色（闭环）：#2563EB 品牌蓝 / #22C55E 品牌绿
```

## 输出字段说明
```json
{
  "slides": [{
    "index": 1,
    "frame_id": "镜头1【封面引流帧】",
    "layout_type": "billboard | problem_solver | matrix | trust_builder",
    "visual_target": "本帧视觉目标",
    "scene_logic": "画面执行方式",
    "color_tone": "cold | warm | brand",
    "character_consistency": "人物形象描述",
    "light_shadow_logic": "光影逻辑",
    "scene_dressing": "场景道具标签",
    "atmosphere_filter": "氛围感滤镜",
    "info_zones": "3区描述"
  }]
}
```
