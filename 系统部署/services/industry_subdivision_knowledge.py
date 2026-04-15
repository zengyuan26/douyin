"""
行业细分赛道知识库

功能：
1. 定义各行业的主流细分赛道
2. 每个细分赛道的问题类型模板
3. 细分赛道识别的关键词匹配规则

使用方式：
from services.industry_subdivision_knowledge import IndustrySubdivisionKnowledge, SubdivisionMatcher

# 获取某个行业的细分赛道
subdivisions = IndustrySubdivisionKnowledge.get_subdivisions("奶粉")

# 匹配细分赛道
matcher = SubdivisionMatcher()
result = matcher.match("卖奶粉，宝宝拉肚子", "奶粉")
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class BusinessType(Enum):
    """经营类型枚举"""
    CONSUMER = "消费品"          # 卖具体产品
    LOCAL_SERVICE = "本地服务"    # 提供上门/到店服务
    ENTERPRISE_SERVICE = "企业服务"  # 面向企业的软件/服务
    PERSONAL_BRAND = "个人品牌"   # 内容创作/知识输出
    MIXED = "混合型"             # 混合型业务


class ClientType(Enum):
    """客户类型枚举"""
    C = "C端个人"
    B = "B端企业"
    MIXED = "混合型"


# ============================================================
# 行业细分赛道知识库
# ============================================================

INDUSTRY_SUBDIVISIONS: Dict[str, Dict[str, Any]] = {

    # --------------- 奶粉行业 ---------------
    "奶粉": {
        "description": "奶粉行业细分",
        "default_problems": {
            "使用者问题": {
                "身体层": ["拉肚子", "便秘", "过敏", "不长肉", "厌奶", "绿便", "奶瓣"],
                "效果层": ["不长肉", "不长高", "效果不明显"],
                "选择层": ["选哪个牌子", "国产还是进口", "普通还是特殊配方"]
            },
            "付费者顾虑": {
                "真假层": ["怕买到假货", "怕货源不正", "怕买到水货"],
                "价格层": ["会不会买贵", "等活动还是现在买"],
                "售后层": ["出了问题找谁", "退换货怎么办"],
                "渠道层": ["从哪买靠谱", "淘宝还是京东", "代购还是官方"]
            }
        },
        "subdivisions": {
            "婴幼儿普通奶粉": {
                "name": "婴幼儿普通奶粉",
                "keywords": ["宝宝", "婴幼儿", "孩子", "1段", "2段", "3段", "配方奶粉", "婴儿奶粉", "奶粉"],
                "business_type": "消费品",
                "problems": {
                    "使用者问题": {
                        "身体层": ["拉肚子", "便秘", "绿便", "奶瓣", "腹胀", "上火"],
                        "效果层": ["不长肉", "不长高", "厌奶", "不爱喝"],
                        "选择层": ["国产还是进口", "哪个牌子好", "选爱他美还是美赞臣"]
                    },
                    "付费者顾虑": {
                        "真假层": ["进口奶粉是不是正品", "怎么验证真假", "保税区发货靠谱吗"],
                        "价格层": ["进口奶粉多少钱", "会不会买贵", "等活动还是现在买"],
                        "售后层": ["退换货怎么办", "宝宝喝完不适怎么办"],
                        "渠道层": ["淘宝还是京东", "代购还是官方旗舰店", "在哪买靠谱"]
                    }
                }
            },
            "特殊配方奶粉_乳糖不耐受": {
                "name": "特殊配方奶粉-乳糖不耐受",
                "keywords": ["乳糖不耐受", "拉肚子", "腹泻", "屁多", "腹胀", "换奶粉"],
                "problems": {
                    "使用者问题": {
                        "身体层": ["喝完就拉", "大便水样", "腹胀", "放屁多", "大便次数多"],
                        "效果层": ["换了奶粉还是拉", "效果不明显", "要喝多久才能好"],
                        "选择层": ["无乳糖还是低乳糖", "哪款好", "要不要换奶粉"],
                        "安全层": ["特殊奶粉长期喝有没有影响", "会不会有营养不够"]
                    },
                    "付费者顾虑": {
                        "真假层": ["特殊奶粉会不会有假货", "怎么判断真假", "保税区发货靠谱吗"],
                        "价格层": ["特殊奶粉太贵了", "长期喝负担不起", "有没有便宜的替代"],
                        "售后层": ["喝了不适怎么办", "效果不好能不能退", "宝宝不喝怎么办"],
                        "渠道层": ["在哪买靠谱", "医院开的太贵网上买一样吗", "跨境购和国内版区别"]
                    }
                }
            },
            "特殊配方奶粉_牛奶蛋白过敏": {
                "name": "特殊配方奶粉-牛奶蛋白过敏",
                "keywords": ["过敏", "湿疹", "荨麻疹", "揉眼睛", "揉鼻子", "红屁股", "嘴巴肿", "不长肉", "发育慢"],
                "problems": {
                    "使用者问题": {
                        "身体层": ["湿疹反复", "红屁股一直不退", "揉眼睛揉鼻子", "嘴巴肿", "大便有血丝"],
                        "效果层": ["换了奶粉还是过敏", "效果不明显", "体重还是不长", "发育落后"],
                        "选择层": ["适度水解还是深度水解", "氨基酸还是深度水解", "哪款适合"],
                        "安全层": ["特殊奶粉长期喝有没有影响", "会不会有副作用"]
                    },
                    "付费者顾虑": {
                        "真假层": ["特殊奶粉货源正不正", "怎么验证真假"],
                        "价格层": ["深度水解太贵了", "氨基酸奶粉多少钱", "长期喝负担得起吗"],
                        "售后层": ["宝宝不喝怎么办", "效果不好能不能退", "什么时候能换普通奶粉"],
                        "渠道层": ["在哪买靠谱", "医院推荐太贵", "跨境购一样吗"]
                    }
                }
            },
            "特殊配方奶粉_早产儿": {
                "name": "特殊配方奶粉-早产儿/低体重",
                "keywords": ["早产", "低体重", "追赶", "追重", "发育迟缓", "体重不达标"],
                "problems": {
                    "使用者问题": {
                        "身体层": ["追赶生长慢", "体重不达标", "发育迟缓"],
                        "效果层": ["追重慢", "吃了很多还是不长肉"],
                        "选择层": ["早产儿奶粉还是普通奶粉", "喝多久能追上", "要不要加母乳强化剂"],
                        "安全层": ["早产儿奶粉长期喝行不行", "会不会有副作用"]
                    },
                    "付费者顾虑": {
                        "真假层": ["早产儿奶粉货源正不正"],
                        "价格层": ["早产儿奶粉贵不贵", "长期喝费用"],
                        "售后层": ["宝宝不喝怎么办", "效果不好怎么办"],
                        "渠道层": ["在哪买靠谱", "医院推荐还是自己买"]
                    }
                }
            },
            "有机奶粉": {
                "name": "有机奶粉",
                "keywords": ["有机", "天然", "无添加", "安全", "绿色"],
                "problems": {
                    "使用者问题": {
                        "安全层": ["有没有激素", "有没有添加剂", "有没有农药残留"],
                        "效果层": ["有机奶粉营养好不好", "和普通奶粉有什么区别"]
                    },
                    "付费者顾虑": {
                        "真假层": ["有机认证是真的吗", "有机奶粉是不是智商税", "怎么验证有机"],
                        "价格层": ["有机奶粉为什么贵", "值不值这个价"],
                        "售后层": ["质量问题怎么处理"],
                        "渠道层": ["在哪买有机奶粉靠谱", "官方旗舰店还是专卖店"]
                    }
                }
            },
            "羊奶粉": {
                "name": "羊奶粉",
                "keywords": ["羊奶", "山羊奶", "羊奶粉"],
                "problems": {
                    "使用者问题": {
                        "身体层": ["消化不好", "便秘", "对牛奶过敏", "不长肉"],
                        "效果层": ["羊奶粉好不好", "和牛奶粉比怎么样", "不长肉宝宝适合吗"],
                        "选择层": ["羊奶粉还是牛奶粉", "哪个牌子好", "纯羊奶粉还是混羊奶粉"]
                    },
                    "付费者顾虑": {
                        "真假层": ["羊奶粉是不是真的", "会不会是牛奶冒充的", "怎么分辨真假"],
                        "价格层": ["羊奶粉为什么贵", "值不值"],
                        "售后层": ["宝宝不喝羊奶粉味道怎么办", "质量问题处理"],
                        "渠道层": ["在哪买靠谱", "哪个牌子正宗"]
                    }
                }
            },
            "成人奶粉": {
                "name": "成人奶粉",
                "keywords": ["中老年", "老人", "爸妈", "女性", "成人", "孕妇", "补钙"],
                "problems": {
                    "使用者问题": {
                        "身体层": ["补钙效果", "睡眠改善", "免疫力", "骨质疏松"],
                        "效果层": ["中老年奶粉有用吗", "喝了有什么效果", "多长时间见效"],
                        "选择层": ["中老年还是女性奶粉", "哪款好", "要不要加钙片"]
                    },
                    "付费者顾虑": {
                        "真假层": ["中老年奶粉质量怎么样", "品牌可信吗"],
                        "价格层": ["中老年奶粉多少钱", "性价比高吗", "长期喝贵不贵"],
                        "售后层": ["质量问题了怎么办"],
                        "渠道层": ["在哪买靠谱", "药店还是超市", "线上买一样吗"]
                    }
                }
            }
        }
    },

    # --------------- 律所行业 ---------------
    "律所": {
        "description": "律师事务所细分",
        "default_problems": {
            "使用者问题": {
                "恐惧层": ["会不会坐牢", "会不会赔钱", "会不会丢工作", "会不会输"],
                "流程层": ["怎么办", "要多久", "要多少钱", "怎么申请"],
                "结果层": ["能不能赢", "能赔多少", "孩子归谁"],
                "费用层": ["律师费多少", "诉讼费多少", "能不能风险代理"]
            },
            "付费者顾虑": {
                "真假层": ["律师靠不靠谱", "胜诉率多少", "有没有经验"],
                "价格层": ["会不会被宰", "收费合不合理", "有没有隐形费用"],
                "选择层": ["选哪个律师", "大所还是小所"],
                "服务层": ["能不能直接联系", "会不会助理在做"]
            }
        },
        "subdivisions": {
            "C端_婚姻家庭": {
                "name": "C端-婚姻家庭法律服务",
                "keywords": ["离婚", "抚养权", "财产分割", "出轨", "家暴", "婚前协议", "婚后财产"],
                "client_type": "C端",
                "problems": {
                    "使用者问题": {
                        "恐惧层": ["会不会判离", "会不会净身出户", "孩子归谁", "要不要第一次判不离"],
                        "流程层": ["起诉要什么材料", "去哪里起诉", "要多久能判", "探视权多久"],
                        "结果层": ["能分到多少财产", "能不能争到抚养权", "抚养费给多少"],
                        "费用层": ["离婚律师费多少", "诉讼费多少钱", "能不能风险代理"],
                        "情感层": ["心理没底", "焦虑害怕", "不知道怎么办", "怕对方抢孩子"]
                    },
                    "付费者顾虑": {
                        "真假层": ["离婚律师靠不靠谱", "有没有经验", "会不会敷衍"],
                        "价格层": ["离婚律师多少钱", "会不会被宰", "收费合不合理"],
                        "选择层": ["选离婚律师还是普通律师", "大所还是小所", "男律师还是女律师"],
                        "服务层": ["能不能直接联系律师", "会不会是助理在做", "回复及时吗"]
                    }
                }
            },
            "C端_劳动纠纷": {
                "name": "C端-劳动纠纷法律服务",
                "keywords": ["劳动仲裁", "被辞退", "赔偿", "加班费", "被裁员", "不发工资", "工伤"],
                "client_type": "C端",
                "problems": {
                    "使用者问题": {
                        "恐惧层": ["会不会被录音", "要不要先离职", "会不会被穿小鞋", "能不能拿到赔偿"],
                        "流程层": ["劳动仲裁怎么申请", "要准备什么材料", "时效多久", "去哪申请"],
                        "结果层": ["能赔多少钱", "2N是怎么算的", "加班费能要到吗", "不签合同怎么办"],
                        "费用层": ["劳动仲裁要不要钱", "请律师多少钱", "能不能风险代理"],
                        "情感层": ["心理压力大", "不知道怎么办", "怕告不赢"]
                    },
                    "付费者顾虑": {
                        "真假层": ["劳动律师靠不靠谱", "有没有胜诉经验"],
                        "价格层": ["劳动仲裁律师费多少", "值不值"],
                        "选择层": ["要不要请律师", "选哪个律师"],
                        "服务层": ["能不能联系到律师", "回复及时吗"]
                    }
                }
            },
            "C端_交通事故": {
                "name": "C端-交通事故法律服务",
                "keywords": ["交通事故", "车祸", "赔偿", "保险理赔", "伤残鉴定"],
                "client_type": "C端",
                "problems": {
                    "使用者问题": {
                        "恐惧层": ["会不会有后遗症", "能不能评上伤残", "赔偿够不够"],
                        "流程层": ["怎么处理事故", "要做哪些鉴定", "要多久才能拿到赔偿"],
                        "结果层": ["能赔多少钱", "伤残等级怎么定", "保险能赔多少"],
                        "费用层": ["律师费多少", "鉴定费多少"],
                        "情感层": ["人受伤了很慌", "不知道怎么办", "对方耍赖怎么办"]
                    },
                    "付费者顾虑": {
                        "真假层": ["交通事故律师靠不靠谱", "专不专业"],
                        "价格层": ["律师费怎么算", "能不能风险代理"],
                        "选择层": ["要不要请律师", "选哪个律师"],
                        "服务层": ["好不好联系", "会不会负责"]
                    }
                }
            },
            "B端_企业法律顾问": {
                "name": "B端-企业法律顾问服务",
                "keywords": ["法律顾问", "常法", "合同审核", "股权", "知识产权", "企业"],
                "client_type": "B端",
                "problems": {
                    "使用者问题": {
                        "功能层": ["合同条款有没有坑", "这样写行不行", "有没有法律风险"],
                        "效率层": ["问个问题要多久回复", "急事能不能当天处理"],
                        "沟通层": ["能不能直接找律师", "要请示几层领导"],
                        "专业层": ["懂不懂我们行业", "有没有做过类似案例"]
                    },
                    "付费者顾虑": {
                        "ROI层": ["一年多少费用", "处理了多少事", "值不值这个价"],
                        "风险层": ["有没有资质", "出了问题谁负责", "会不会泄露商业机密"],
                        "选型层": ["常法还是按项目", "大所还是小所", "本地还是远程"],
                        "售后层": ["换了律师怎么办", "明年涨价怎么办", "服务质量下降怎么办"]
                    }
                }
            },
            "B端_劳动人事": {
                "name": "B端-企业劳动人事法律服务",
                "keywords": ["员工管理", "劳动合同", "劳动纠纷", "规章制度", "企业裁员"],
                "client_type": "B端",
                "problems": {
                    "使用者问题": {
                        "功能层": ["劳动合同怎么写", "规章制度有没有法律效力", "员工违规怎么处理"],
                        "效率层": ["问题回复及时吗", "紧急情况能联系到人吗"],
                        "沟通层": ["联系方便吗", "要通过谁"],
                        "专业层": ["懂不懂劳动法", "有没有处理过类似案例"]
                    },
                    "付费者顾虑": {
                        "ROI层": ["费用多少", "能减少多少风险", "值不值"],
                        "风险层": ["出了问题谁担责", "有没有资质"],
                        "选型层": ["按年还是按项目", "选哪家"],
                        "售后层": ["换了人怎么办", "服务质量能保证吗"]
                    }
                }
            }
        }
    },

    # --------------- 本地服务行业 ---------------
    "上门按摩": {
        "description": "上门按摩服务细分",
        "default_problems": {
            "使用者问题": {
                "体验层": ["按摩后肌肉更疼", "按完第二天更酸", "手法不好", "态度敷衍"],
                "便利层": ["预约要等很久", "技师时间不合适", "沟通成本高"],
                "效果层": ["按的时候舒服", "过两天又疼了", "效果不明显", "没达到预期"],
                "安全层": ["陌生人上门", "女生一个人在家不安全", "财产安全隐患"]
            },
            "付费者顾虑": {
                "专业层": ["技师手法专不专业", "有没有资质", "经验够吗"],
                "靠谱层": ["平台靠不靠谱", "技师会不会敷衍", "会不会中途加价"],
                "价格层": ["收费合不合理", "贵不贵", "有没有隐形费用"],
                "便利层": ["预约方不方便", "时间灵活吗", "能加急吗"]
            }
        },
        "subdivisions": {
            "中式按摩": {
                "name": "中式按摩/推拿",
                "keywords": ["推拿", "按摩", "中式", "经络", "刮痧", "拔罐"],
                "problems": {
                    "使用者问题": {
                        "体验层": ["手法专业吗", "力道够不够", "按完第二天疼"],
                        "便利层": ["预约难不难", "时间方不方便"],
                        "效果层": ["能缓解腰酸背痛吗", "效果能维持多久"],
                        "安全层": ["上门安全吗"]
                    },
                    "付费者顾虑": {
                        "专业层": ["有没有中医资质", "手法正不正宗"],
                        "靠谱层": ["平台正规吗", "会不会乱收费"],
                        "价格层": ["一次多少钱", "套餐划算吗"],
                        "便利层": ["能约到吗", "晚上能约吗"]
                    }
                }
            },
            "SPA服务": {
                "name": "SPA/美容按摩",
                "keywords": ["SPA", "美容", "芳香", "水疗", "养生"],
                "problems": {
                    "使用者问题": {
                        "体验层": ["环境怎么样", "手法好不好", "精油质量"],
                        "便利层": ["服务时间", "流程复不复杂"],
                        "效果层": ["能放松吗", "皮肤有没有变好"],
                        "安全层": ["上门安不安全", "隐私问题"]
                    },
                    "付费者顾虑": {
                        "专业层": ["技师有没有资质", "手法专不专业"],
                        "靠谱层": ["用的产品好不好", "会不会强行推销"],
                        "价格层": ["一次多少钱", "套餐值不值"],
                        "便利层": ["能预约吗", "时间灵活吗"]
                    }
                }
            },
            "运动康复": {
                "name": "运动康复/体态调整",
                "keywords": ["运动康复", "体态", "产后恢复", "理疗", "康复"],
                "problems": {
                    "使用者问题": {
                        "体验层": ["专业吗", "评估准不准", "康复方案合不合理"],
                        "便利层": ["要多久才能见效", "每次要多久"],
                        "效果层": ["真的能改善吗", "要多少次才能好"],
                        "安全层": ["上门做康复训练安全吗"]
                    },
                    "付费者顾虑": {
                        "专业层": ["有没有康复资质", "是不是专业人士"],
                        "靠谱层": ["效果好不好", "会不会骗钱"],
                        "价格层": ["一个疗程多少钱", "要多少个疗程"],
                        "便利层": ["能不能上门", "时间配合"]
                    }
                }
            }
        }
    },

    # --------------- 企业服务行业 ---------------
    "CRM开发": {
        "description": "CRM系统开发服务细分",
        "default_problems": {
            "使用者问题": {
                "功能层": ["功能不匹配需求", "用不上", "太复杂", "操作繁琐"],
                "效率层": ["反而降低效率", "录入多", "审批慢", "报表难用"],
                "集成层": ["和现有系统不兼容", "数据不通", "要重复录入"]
            },
            "付费者顾虑": {
                "实施层": ["实施周期多长", "会不会烂尾", "风险大不大"],
                "ROI层": ["投入这么多能带来多少回报", "值不值"],
                "选型层": ["选SaaS还是定制", "选哪家靠谱"],
                "售后层": ["交付后出问题找谁", "响应及时吗"]
            }
        },
        "subdivisions": {
            "CRM定制开发": {
                "name": "CRM系统定制开发",
                "keywords": ["CRM", "客户管理", "定制开发", "私有部署"],
                "problems": {
                    "使用者问题": {
                        "功能层": ["功能能不能按需定制", "操作复不复杂", "好不好用"],
                        "效率层": ["能提高多少效率", "会不会反而麻烦"],
                        "集成层": ["能不能对接现有ERP", "数据能不能打通"]
                    },
                    "付费者顾虑": {
                        "实施层": ["开发周期多长", "会不会超期", "会不会烂尾"],
                        "ROI层": ["投入多少钱", "多久能回本", "值不值"],
                        "选型层": ["选哪家开发公司", "选SaaS还是私有化部署"],
                        "售后层": ["交付后谁维护", "出问题找谁", "响应快不快"]
                    }
                }
            },
            "CRM实施服务": {
                "name": "CRM实施服务",
                "keywords": ["CRM实施", "Salesforce", "用友", "金蝶", "实施服务"],
                "problems": {
                    "使用者问题": {
                        "功能层": ["系统能不能满足需求", "功能会不会用不上"],
                        "效率层": ["实施完能用吗", "培训够不够"],
                        "集成层": ["能对接现有系统吗", "数据迁移麻不麻烦"]
                    },
                    "付费者顾虑": {
                        "实施层": ["实施周期多久", "能不能按时上线", "成功率"],
                        "ROI层": ["实施费多少", "效果能达到预期吗"],
                        "选型层": ["选哪家实施商", "选什么CRM系统"],
                        "售后层": ["实施完还有支持吗", "谁负责培训"]
                    }
                }
            },
            "CRM培训优化": {
                "name": "CRM培训与优化",
                "keywords": ["CRM培训", "CRM优化", "CRM使用", "CRM效率"],
                "problems": {
                    "使用者问题": {
                        "功能层": ["会不会用", "功能懂不懂", "操作对不对"],
                        "效率层": ["能不能提高效率", "能不能减少录入"],
                        "集成层": ["能不能更好地使用现有功能"]
                    },
                    "付费者顾虑": {
                        "ROI层": ["培训费多少", "能提高多少效率", "值不值"],
                        "选型层": ["要不要做培训", "选什么形式的培训"],
                        "售后层": ["培训完还有支持吗"]
                    }
                }
            }
        }
    },

    # --------------- 个人品牌行业 ---------------
    "知识博主": {
        "description": "知识博主/个人IP细分",
        "default_problems": {
            "内容问题": {
                "方向层": ["不知道做什么内容", "不知道什么内容受欢迎"],
                "素材层": ["素材枯竭", "选题难", "不知道写什么"],
                "风格层": ["风格不稳定", "一会儿严肃一会儿搞笑", "人设不清晰"],
                "质量层": ["内容质量不稳定", "视频制作粗糙"]
            },
            "受众问题": {
                "增长层": ["涨粉慢", "不涨粉", "发视频没人看"],
                "互动层": ["评论少", "没人互动", "私信没人回"],
                "变现层": ["不知道如何变现", "接不到广告"],
                "竞争层": ["同质化严重", "没特色", "竞争不过大V"]
            }
        },
        "subdivisions": {
            "鸟类知识博主": {
                "name": "鸟类知识科普博主",
                "keywords": ["鸟", "鸟类", "观鸟", "养鸟", "宠物鸟", "鸟类知识"],
                "problems": {
                    "内容问题": {
                        "方向层": ["做什么鸟类内容受欢迎", "观鸟还是养鸟内容"],
                        "素材层": ["鸟类素材难找", "拍摄门槛高", "不知道拍什么鸟"],
                        "风格层": ["严肃科普还是轻松有趣", "风格不稳定"],
                        "质量层": ["视频制作粗糙", "画面不清晰"]
                    },
                    "受众问题": {
                        "增长层": ["鸟类博主涨粉难", "受众太小众"],
                        "互动层": ["观鸟爱好者活跃吗", "评论多不多"],
                        "变现层": ["鸟类博主怎么变现", "能不能接广告"],
                        "竞争层": ["头部博主太少了", "有没有机会"]
                    }
                }
            },
            "美食博主": {
                "name": "美食博主",
                "keywords": ["美食", "做饭", "菜谱", "烹饪", "探店"],
                "problems": {
                    "内容问题": {
                        "方向层": ["做什么菜谱内容", "家常菜还是硬菜", "探店还是自己做的"],
                        "素材层": ["做什么菜好", "灵感枯竭"],
                        "风格层": ["接地气还是高大上", "风格统一"],
                        "质量层": ["拍摄好不好看", "画面有没有食欲"]
                    },
                    "受众问题": {
                        "增长层": ["美食博主太多了", "怎么脱颖而出"],
                        "互动层": ["粉丝活跃吗", "评论区都在聊什么"],
                        "变现层": ["美食博主怎么变现", "接广告还是带货"],
                        "竞争层": ["怎么和美食大V竞争", "差异化在哪"]
                    }
                }
            },
            "职场博主": {
                "name": "职场博主",
                "keywords": ["职场", "求职", "简历", "面试", "职业规划", "升职加薪"],
                "problems": {
                    "内容问题": {
                        "方向层": ["做什么职场内容", "求职还是职场成长"],
                        "素材层": ["职场素材哪来", "故事怎么讲"],
                        "风格层": ["鸡汤还是干货", "毒舌还是温和"],
                        "质量层": ["内容深度够不够", "有没有独到见解"]
                    },
                    "受众问题": {
                        "增长层": ["职场博主竞争激烈", "怎么涨粉"],
                        "互动层": ["粉丝职场困惑多吗", "评论多不多"],
                        "变现层": ["职场博主怎么变现", "知识付费还是接广告"],
                        "竞争层": ["怎么差异化", "和大V比优势在哪"]
                    }
                }
            }
        }
    }
}


# ============================================================
# 细分赛道识别器
# ============================================================

@dataclass
class SubdivisionMatch:
    """细分赛道匹配结果"""
    subdivision_id: str           # 细分赛道ID
    subdivision_name: str        # 细分赛道名称
    confidence: float            # 置信度 0-1
    matched_keywords: List[str]  # 匹配的关键词
    problems: Dict[str, Any]     # 问题类型
    needs_clarification: bool    # 是否需要进一步询问
    clarification_question: str  # 询问问题
    clarification_options: List[str]  # 询问选项


class SubdivisionMatcher:
    """细分赛道匹配器"""

    def __init__(self):
        self.industry_cache = {}
        # 核心关键词列表（专有病症/特征词，这些词出现时应该直接提升置信度）
        self.core_keywords = {
            '奶粉': {
                'high_priority': ['乳糖不耐受', '拉肚子', '牛奶蛋白过敏', '过敏', '湿疹', '早产', '低体重',
                                  '有机', '羊奶', '中老年', '老人', '孕妇', '补钙'],
            },
            '律所': {
                'high_priority': ['离婚', '抚养权', '出轨', '家暴', '劳动仲裁', '被辞退', '工伤',
                                 '交通事故', '车祸', '法律顾问', '合同', '股权', '知识产权'],
            },
            '上门按摩': {
                'high_priority': ['推拿', 'SPA', '美容', '运动康复', '体态', '产后', '理疗'],
            },
            'CRM开发': {
                'high_priority': ['CRM', '客户管理', '定制开发', '私有部署', '实施', '培训'],
            },
            '知识博主': {
                'high_priority': ['鸟', '观鸟', '养鸟', '宠物鸟', '美食', '菜谱', '烹饪', '探店',
                                 '职场', '求职', '面试', '职业规划'],
            }
        }

    def _get_keyword_weight(self, keyword: str) -> float:
        """获取关键词权重"""
        # 核心/专业关键词权重更高
        if keyword in ['乳糖不耐受', '牛奶蛋白过敏', '早产', '有机', '羊奶']:
            return 2.0
        elif keyword in ['过敏', '湿疹', '低体重', '追赶']:
            return 1.8
        elif keyword in ['宝宝', '婴幼儿', '孩子', '奶粉', '婴儿']:
            return 0.3  # 大幅降低通用词权重
        elif keyword in ['中老年', '老人', '成人']:
            return 1.5
        return 1.0

    def _check_high_priority_match(self, business_desc_lower: str, industry: str) -> float:
        """检查是否匹配到高优先级关键词，返回额外加分"""
        if industry not in self.core_keywords:
            return 0.0

        high_priority_kws = self.core_keywords[industry].get('high_priority', [])
        for kw in high_priority_kws:
            if kw.lower() in business_desc_lower:
                return 0.3  # 匹配到高优先级关键词，额外加0.3

        return 0.0

    def match(self, business_desc: str, industry: str) -> SubdivisionMatch:
        """
        根据业务描述匹配细分赛道

        Args:
            business_desc: 业务描述
            industry: 行业名称

        Returns:
            SubdivisionMatch: 匹配结果
        """
        if not business_desc or not industry:
            return self._create_uncertain_result(industry)

        business_desc_lower = business_desc.lower()

        # 获取行业的细分赛道
        industry_data = INDUSTRY_SUBDIVISIONS.get(industry, {})
        subdivisions = industry_data.get("subdivisions", {})

        if not subdivisions:
            # 没有细分赛道，返回默认问题
            default_problems = industry_data.get("default_problems", {})
            return SubdivisionMatch(
                subdivision_id="default",
                subdivision_name="通用",
                confidence=0.5,
                matched_keywords=[],
                problems=default_problems,
                needs_clarification=False,
                clarification_question="",
                clarification_options=[]
            )

        # 匹配细分赛道（带权重和高优先级检查）
        matched = []
        has_high_priority = self._check_high_priority_match(business_desc_lower, industry)

        for sub_id, sub_info in subdivisions.items():
            keywords = sub_info.get("keywords", [])
            matched_count = 0
            matched_kws = []
            weighted_score = 0.0

            for kw in keywords:
                if kw.lower() in business_desc_lower:
                    matched_count += 1
                    matched_kws.append(kw)
                    weighted_score += self._get_keyword_weight(kw)

            if matched_count > 0:
                # 计算基础置信度
                base_confidence = min(matched_count / max(len(keywords) * 0.3, 1), 1.0)

                # 如果匹配到了高优先级关键词，且当前赛道也包含该关键词
                core_kw_found = False
                if has_high_priority > 0:
                    for kw in matched_kws:
                        if kw in self.core_keywords.get(industry, {}).get('high_priority', []):
                            core_kw_found = True
                            break

                # 高优先级关键词加分
                priority_bonus = 0.3 if core_kw_found else 0.0

                # 权重分数归一化（最高为1）
                weight_bonus = min(weighted_score / max(matched_count, 1) - 0.5, 1.0) * 0.2

                confidence = min(base_confidence + weight_bonus + priority_bonus, 1.0)
                matched.append({
                    "sub_id": sub_id,
                    "sub_name": sub_info.get("name", sub_id),
                    "confidence": confidence,
                    "matched_keywords": matched_kws,
                    "matched_count": matched_count,
                    "weighted_score": weighted_score,
                    "has_core_kw": core_kw_found,
                    "problems": sub_info.get("problems", {})
                })

        if not matched:
            # 没有匹配到，返回询问
            return SubdivisionMatch(
                subdivision_id="",
                subdivision_name="",
                confidence=0,
                matched_keywords=[],
                problems={},
                needs_clarification=True,
                clarification_question=self._generate_clarification_question(industry, subdivisions),
                clarification_options=list(subdivisions.keys())
            )

        # 返回置信度最高的匹配
        matched.sort(key=lambda x: x["confidence"], reverse=True)
        best = matched[0]

        return SubdivisionMatch(
            subdivision_id=best["sub_id"],
            subdivision_name=best["sub_name"],
            confidence=best["confidence"],
            matched_keywords=best["matched_keywords"],
            problems=best["problems"],
            needs_clarification=False,
            clarification_question="",
            clarification_options=[]
        )

    def match_multiple(self, business_desc: str, industry: str) -> List[SubdivisionMatch]:
        """
        返回所有匹配的细分赛道（用于混合型业务）

        Args:
            business_desc: 业务描述
            industry: 行业名称

        Returns:
            List[SubdivisionMatch]: 匹配结果列表
        """
        if not business_desc or not industry:
            return []

        business_desc_lower = business_desc.lower()
        industry_data = INDUSTRY_SUBDIVISIONS.get(industry, {})
        subdivisions = industry_data.get("subdivisions", {})

        results = []
        for sub_id, sub_info in subdivisions.items():
            keywords = sub_info.get("keywords", [])
            matched_kws = [kw for kw in keywords if kw.lower() in business_desc_lower]

            if matched_kws:
                confidence = len(matched_kws) / max(len(keywords) * 0.3, 1)
                results.append(SubdivisionMatch(
                    subdivision_id=sub_id,
                    subdivision_name=sub_info.get("name", sub_id),
                    confidence=min(confidence, 1.0),
                    matched_keywords=matched_kws,
                    problems=sub_info.get("problems", {}),
                    needs_clarification=False,
                    clarification_question="",
                    clarification_options=[]
                ))

        return sorted(results, key=lambda x: x.confidence, reverse=True)

    def _generate_clarification_question(self, industry: str, subdivisions: Dict) -> str:
        """生成询问问题"""
        sub_names = [sub.get("name", sub_id) for sub_id, sub in subdivisions.items()]
        return f"请问您主要做{industry}的哪个方向？"

    def _create_uncertain_result(self, industry: str) -> SubdivisionMatch:
        """创建不确定的结果"""
        return SubdivisionMatch(
            subdivision_id="",
            subdivision_name="",
            confidence=0,
            matched_keywords=[],
            problems={},
            needs_clarification=True,
            clarification_question=f"请描述您的具体业务，我帮您确定细分方向",
            clarification_options=[]
        )


# ============================================================
# 便捷函数
# ============================================================

def get_subdivisions(industry: str) -> List[Dict]:
    """获取某个行业的所有细分赛道"""
    industry_data = INDUSTRY_SUBDIVISIONS.get(industry, {})
    subdivisions = industry_data.get("subdivisions", {})
    return [
        {"id": sub_id, "name": sub.get("name", sub_id), "keywords": sub.get("keywords", [])}
        for sub_id, sub in subdivisions.items()
    ]


def match_subdivision(business_desc: str, industry: str) -> SubdivisionMatch:
    """便捷函数：匹配细分赛道"""
    matcher = SubdivisionMatcher()
    return matcher.match(business_desc, industry)


def get_problems_for_subdivision(industry: str, subdivision_id: str) -> Dict:
    """获取某个细分赛道的问题类型"""
    industry_data = INDUSTRY_SUBDIVISIONS.get(industry, {})
    subdivisions = industry_data.get("subdivisions", {})
    subdivision = subdivisions.get(subdivision_id, {})
    return subdivision.get("problems", industry_data.get("default_problems", {}))


def get_all_industries() -> List[str]:
    """获取所有已配置的行业"""
    return list(INDUSTRY_SUBDIVISIONS.keys())
