# 📊 Social Media Trend Monitor API

## 接口概述

```
┌─────────────────────────────────────────────────────────────────┐
│                    社交媒体趋势监控接口                          │
│                    Social Media Trend Monitor                    │
├─────────────────────────────────────────────────────────────────┤
│  监控平台：抖音、短视频、小红书、大众点评                          │
│  核心功能：行业动态监控、用户评论分析、竞品追踪、舆情预警         │
│  监控对象：#话题标签 下的用户评论、探店视频、DIY教程             │
│  输出维度：用户需求、舆情风险、竞品动态、内容热点                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 接口配置

### 基本信息

```json
{
  "interface_name": "social_media_trend_monitor",
  "version": "2.0.0",
  "description": "多平台社交媒体趋势监控接口，支持抖音、快手、小红书、大众点评的话题标签监控、视频分析、评论挖掘、竞品追踪",
  "category": "market_intelligence",
  "skill": "insights-analyst",
  "endpoint": "/api/trend-monitor",
  "method": "POST",
  "auth_type": "api_key"
}
```

### 依赖配置

```json
{
  "dependencies": {
    "douyin_api": {
      "version": "v2",
      "required": true,
      "permissions": ["video:search", "comment:list", "user:info", "shop:analysis"]
    },
    "kuaishou_api": {
      "version": "v1",
      "required": true,
      "permissions": ["video:search", "comment:list", "user:info"]
    },
    "xiaohongshu_api": {
      "version": "v1",
      "required": true,
      "permissions": ["note:search", "comment:list", "user:info", "topic:analysis"]
    },
    "dianping_api": {
      "version": "v1",
      "required": true,
      "permissions": ["review:search", "shop:info", "comment:list"]
    },
    "data_storage": {
      "type": "database",
      "required": true,
      "retention_days": 90
    }
  },
  "rate_limit": {
    "requests_per_minute": 60,
    "burst_limit": 100
  }
}
```

---

## 请求参数

### 请求头

```json
{
  "headers": {
    "Authorization": "Bearer {API_KEY}",
    "Content-Type": "application/json",
    "X-Tenant-ID": "{TENANT_ID}",
    "X-Request-ID": "{UUID}"
  }
}
```

### 请求体

```json
{
  "request": {
    "config": {
      "monitor_mode": "realtime|scheduled|both",
      "time_range": "24h|7d|30d|custom",
      "platforms": ["douyin", "kuaishou", "xiaohongshu", "dianping"],
      "custom_range": {
        "start": "YYYY-MM-DD HH:mm:ss",
        "end": "YYYY-MM-DD HH:mm:ss"
      }
    },
    "monitor_targets": {
      "douyin": {
        "hashtags": ["#核心话题1", "#核心话题2"],
        "keywords": ["关键词1", "关键词2"],
        "accounts": { "include": [], "exclude": [] },
        "video_types": ["探店视频", "DIY教程", "测评视频"]
      },
      "kuaishou": {
        "hashtags": ["#核心话题1", "#核心话题2"],
        "keywords": ["关键词1", "关键词2"],
        "accounts": { "include": [], "exclude": [] },
        "video_types": ["段子", "教程", "测评"]
      },
      "xiaohongshu": {
        "hashtags": ["#核心话题1", "#核心话题2"],
        "keywords": ["关键词1", "关键词2"],
        "accounts": { "include": [], "exclude": [] },
        "note_types": ["笔记", "测评", "教程"]
      },
      "dianping": {
        "hashtags": [],
        "keywords": ["关键词1", "关键词2"],
        "shop_categories": ["美食", "服务", "零售"],
        "review_types": ["好评", "中评", "差评"]
      }
    },
    "monitor_dimensions": {
      "user_needs": {
        "enabled": true,
        "categories": ["问题咨询", "使用场景", "需求表达", "痛点抱怨"]
      },
      "public_sentiment": {
        "enabled": true,
        "alert_levels": ["low", "medium", "high", "critical"],
        "categories": ["负面投诉", "虚假宣传", "质量投诉", "服务投诉"]
      },
      "competitor_dynamics": {
        "enabled": true,
        "track_fields": ["新视频", "互动数据", "转化策略", "内容创新"]
      },
      "content_trends": {
        "enabled": true,
        "track_metrics": ["播放量", "点赞量", "评论量", "转发量", "完播率"]
      }
    },
    "analysis_config": {
      "sentiment_analysis": true,
      "keyword_extraction": true,
      "trend_prediction": true,
      "competitor_comparison": true
    },
    "output_config": {
      "format": "json|markdown|excel",
      "include_raw_data": true,
      "include_analysis": true,
      "include_recommendations": true
    }
  }
}
```

### 请求示例

```json
{
  "request": {
    "config": {
      "monitor_mode": "scheduled",
      "time_range": "7d"
    },
    "monitor_targets": {
      "hashtags": ["#奶粉", "#婴儿奶粉", "#敏宝宝奶粉", "#送礼奶粉"],
      "keywords": ["奶粉怎么选", "奶粉推荐", "奶粉避坑"],
      "accounts": {
        "include": ["头部竞品1", "头部竞品2", "头部竞品3"],
        "exclude": []
      },
      "video_types": ["探店视频", "DIY教程", "测评视频"]
    },
    "monitor_dimensions": {
      "user_needs": {
        "enabled": true,
        "categories": ["问题咨询", "使用场景", "需求表达", "痛点抱怨"]
      },
      "public_sentiment": {
        "enabled": true,
        "alert_levels": ["high", "critical"],
        "categories": ["负面投诉", "虚假宣传"]
      },
      "competitor_dynamics": {
        "enabled": true,
        "track_fields": ["新视频", "互动数据", "转化策略"]
      },
      "content_trends": {
        "enabled": true,
        "track_metrics": ["播放量", "点赞量", "评论量"]
      }
    },
    "analysis_config": {
      "sentiment_analysis": true,
      "keyword_extraction": true,
      "trend_prediction": true,
      "competitor_comparison": true
    },
    "output_config": {
      "format": "markdown",
      "include_raw_data": true,
      "include_analysis": true,
      "include_recommendations": true
    }
  }
}
```

---

## 响应结构

### 响应体

```json
{
  "response": {
    "status": "success|partial|failed",
    "request_id": "{UUID}",
    "timestamp": "YYYY-MM-DD HH:mm:ss",
    "data_scope": {
      "monitor_period": "2024-01-01 至 2024-01-07",
      "hashtags_monitored": 5,
      "videos_analyzed": 1500,
      "comments_analyzed": 25000,
      "accounts_tracked": 20
    },
    "analysis_results": {
      "user_needs": {
        "summary": "用户需求分析摘要",
        "total_mentions": 5000,
        "sentiment_distribution": {
          "positive": 0.45,
          "neutral": 0.35,
          "negative": 0.20
        },
        "needs_breakdown": [
          {
            "category": "问题咨询",
            "count": 2000,
            "percentage": 0.40,
            "top_keywords": ["怎么选", "哪个好", "推荐"],
            "trend": "up|stable|down",
            "trend_change": "+15%",
            "example_comments": [
              {
                "content": "宝宝过敏体质喝什么奶粉好？",
                "sentiment": "neutral",
                "likes": 52
              },
              {
                "content": "奶粉冲泡用什么水？",
                "sentiment": "neutral",
                "likes": 38
              }
            ],
            "content_recommendations": [
              "制作「敏宝宝奶粉选购指南」内容",
              "制作「奶粉冲泡正确方法」教程"
            ]
          },
          {
            "category": "使用场景",
            "count": 1500,
            "percentage": 0.30,
            "top_keywords": ["送礼", "换奶", "囤货"],
            "trend": "stable",
            "trend_change": "+5%",
            "example_comments": [
              {
                "content": "过年回家想给侄子买奶粉，求推荐",
                "sentiment": "positive",
                "likes": 120
              }
            ],
            "content_recommendations": [
              "制作「送礼奶粉推荐」内容",
              "制作「换奶粉正确流程」教程"
            ]
          }
        ],
        "key_insights": [
          "敏宝宝相关咨询增长15%，建议加强蓝海内容布局",
          "送礼场景需求稳定，可持续产出节日内容",
          "换奶期问题集中，建议制作换奶攻略"
        ]
      },
      "public_sentiment": {
        "summary": "舆情分析摘要",
        "total_mentions": 2500,
        "sentiment_distribution": {
          "positive": 0.65,
          "neutral": 0.25,
          "negative": 0.10,
          "critical": 0.02
        },
        "alert_summary": {
          "total_alerts": 15,
          "by_level": {
            "low": 8,
            "medium": 4,
            "high": 2,
            "critical": 1
          }
        },
        "alerts": [
          {
            "alert_id": "ALERT-001",
            "level": "critical",
            "category": "负面投诉",
            "title": "某品牌奶粉出现质量问题投诉",
            "description": "检测到3条关于某品牌奶粉结块、有虫的投诉",
            "first_detected": "2024-01-05 14:30",
            "last_detected": "2024-01-05 16:45",
            "mentions_count": 3,
            "sentiment": "negative",
            "related_hashtags": ["#奶粉", "#婴儿食品安全"],
            "trend": "escalating",
            "recommended_action": "立即核实并准备危机公关预案",
            "affected_brand": "竞品A",
            "severity_score": 95
          },
          {
            "alert_id": "ALERT-002",
            "level": "high",
            "category": "虚假宣传",
            "title": "某竞品夸大宣传被用户质疑",
            "description": "用户质疑某竞品宣称的「100%有机」真实性",
            "first_detected": "2024-01-04 10:00",
            "mentions_count": 15,
            "sentiment": "negative",
            "trend": "stable",
            "recommended_action": "可作为内容素材，适当借势",
            "affected_brand": "竞品B",
            "severity_score": 75
          }
        ],
        "risk_indicators": [
          {
            "indicator": "质量投诉",
            "current_value": 12,
            "threshold": 20,
            "status": "warning",
            "trend": "+25%"
          },
          {
            "indicator": "服务投诉",
            "current_value": 5,
            "threshold": 15,
            "status": "normal",
            "trend": "+10%"
          }
        ],
        "positive_highlights": [
          {
            "type": "用户好评",
            "content": "XX品牌奶粉宝宝爱喝，消化也很好",
            "mentions_count": 50,
            "sentiment": "positive"
          }
        ]
      },
      "competitor_dynamics": {
        "summary": "竞品动态分析摘要",
        "tracked_accounts": 10,
        "total_videos_analyzed": 500,
        "competitors": [
          {
            "name": "竞品A",
            "account_type": "品牌官方",
            "videos_count": 50,
            "total_views": 5000000,
            "avg_engagement_rate": 0.045,
            "content_focus": ["产品测评", "育儿科普", "品牌故事"],
            "recent_strategies": [
              {
                "strategy": "直播带货",
                "description": "开始加大直播带货频次",
                "impact": "转化率提升20%",
                "trend": "up"
              },
              {
                "strategy": "KOC种草",
                "description": "大量投放中小博主",
                "曝光量": "单月曝光1000万+",
                "trend": "stable"
              }
            ],
            "top_performing_videos": [
              {
                "title": "XX奶粉深度测评",
                "views": 500000,
                "likes": 25000,
                "comments": 1500,
                "engagement_rate": 0.05,
                "content_type": "测评视频",
                "success_factors": ["专业背书", "对比实验", "真实体验"]
              }
            ],
            "content_gaps": [
              "缺少送礼场景内容",
              "敏宝宝专题内容较少",
              "DIY教程类内容缺失"
            ],
            "weaknesses": [
              "评论区互动不及时",
              "用户问题响应慢",
              "内容更新频率下降"
            ],
            "opportunities": [
              "可针对性布局送礼场景",
              "加强敏宝宝内容",
              "制作DIY教程差异化竞争"
            ]
          },
          {
            "name": "竞品B",
            "account_type": "个人IP",
            "videos_count": 30,
            "total_views": 3000000,
            "avg_engagement_rate": 0.068,
            "content_focus": ["育儿经验", "产品推荐", "避坑指南"],
            "recent_strategies": [
              {
                "strategy": "人设打造",
                "description": "强化专业营养师人设",
                "impact": "粉丝增长30%",
                "trend": "up"
              }
            ],
            "top_performing_videos": [
              {
                "title": "奶粉怎么选？营养师教你",
                "views": 800000,
                "likes": 45000,
                "comments": 3000,
                "engagement_rate": 0.06,
                "content_type": "教程视频",
                "success_factors": ["专业身份", "干货输出", "互动性强"]
              }
            ],
            "content_gaps": [
              "缺乏产品深度测评",
              "本地化内容较少",
              "转化链路不清晰"
            ],
            "opportunities": [
              "加强产品对比内容",
              "增加地域化内容",
              "优化私域转化路径"
            ]
          }
        ],
        "industry_benchmarks": {
          "avg_engagement_rate": 0.04,
          "avg_video_views": 100000,
          "avg_comments_per_video": 500,
          "top_content_types": ["教程视频", "测评视频", "避坑指南"]
        },
        "key_findings": [
          "竞品A开始加大直播带货，可关注其转化策略",
          "竞品B人设打造成功，粉丝增长30%，可借鉴",
          "行业平均互动率4%，头部可达6-7%",
          "教程类和测评类内容表现最佳"
        ]
      },
      "content_trends": {
        "summary": "内容热点分析摘要",
        "monitored_hashtags": ["#奶粉", "#婴儿奶粉", "#敏宝宝奶粉"],
        "trending_topics": [
          {
            "topic": "送礼奶粉",
            "hashtag": "#送礼奶粉",
            "related_keywords": ["过年", "送人", "高端"],
            "trend_status": "rising",
            "trend_score": 85,
            "avg_views": 50000,
            "engagement_rate": 0.05,
            "content_types": ["推荐类", "清单类", "对比类"],
            "peak_time": "节假日",
            "recommendation": "建议提前1周布局节日送礼内容",
            "example_videos": [
              {
                "title": "送礼奶粉红黑榜",
                "views": 200000,
                "likes": 12000,
                "comments": 800,
                "engagement_rate": 0.064,
                "content_type": "对比类",
                "success_factors": ["实用清单", "价格对比", "品牌背书"]
              }
            ]
          },
          {
            "topic": "敏宝宝奶粉",
            "hashtag": "#敏宝宝奶粉",
            "related_keywords": ["过敏", "乳糖不耐受", "深度水解"],
            "trend_status": "stable",
            "trend_score": 78,
            "avg_views": 35000,
            "engagement_rate": 0.058,
            "content_types": ["科普类", "问题解答", "产品推荐"],
            "peak_time": "全季节",
            "recommendation": "持续产出，保持内容质量",
            "example_videos": [
              {
                "title": "敏宝宝奶粉怎么选？",
                "views": 150000,
                "likes": 9000,
                "comments": 600,
                "engagement_rate": 0.064,
                "content_type": "科普类",
                "success_factors": ["专业解答", "详细对比", "实用建议"]
              }
            ]
          }
        ],
        "declining_topics": [
          {
            "topic": "海淘奶粉",
            "trend_status": "declining",
            "trend_score": 35,
            "reason": "用户对海淘信任度下降"
          }
        ],
        "emerging_topics": [
          {
            "topic": "成分党",
            "hashtag": "#成分党奶粉",
            "related_keywords": ["配方", "成分表", "OPO", "乳铁蛋白"],
            "trend_status": "emerging",
            "trend_score": 65,
            "recommendation": "建议布局成分解析类内容",
            "content_direction": [
              "OPO成分深度解析",
              "乳铁蛋白含量对比",
              "配方表怎么看"
            ]
          }
        ],
        "content_performance_analysis": {
          "best_performing_types": [
            {
              "type": "教程视频",
              "avg_engagement_rate": 0.052,
              "avg_views": 80000,
              "key_success_factors": ["实用性强", "步骤清晰", "易于操作"]
            },
            {
              "type": "测评视频",
              "avg_engagement_rate": 0.048,
              "avg_views": 120000,
              "key_success_factors": ["对比全面", "数据详实", "观点鲜明"]
            }
          ],
          "content_gaps_opportunities": [
            {
              "gap": "DIY教程类内容",
              "current_supply": "低",
              "user_demand": "高",
              "recommendation": "制作冲泡技巧、辅食搭配等DIY内容",
              "priority": "high"
            },
            {
              "gap": "本地化内容",
              "current_supply": "中",
              "user_demand": "中",
              "recommendation": "制作本地门店探店、本地优惠等内容",
              "priority": "medium"
            }
          ]
        },
        "seasonal_predictions": [
          {
            "event": "春节",
            "recommendation": "提前2周布局送礼内容",
            "content_directions": ["送礼清单", "高端推荐", "礼盒评测"],
            "expected_trend": "送礼奶粉搜索量+200%"
          },
          {
            "event": "618大促",
            "recommendation": "提前1周布局促销内容",
            "content_directions": ["促销攻略", "性价比推荐", "省钱技巧"],
            "expected_trend": "奶粉购买攻略搜索量+150%"
          }
        ]
      }
    },
    "action_recommendations": {
      "immediate": [
        {
          "priority": "P0",
          "action": "制作敏宝宝奶粉专题内容",
          "reason": "用户需求增长15%，竞品布局较少",
          "content_type": "科普+产品推荐",
          "hashtags": ["#敏宝宝奶粉", "#奶粉推荐"],
          "deadline": "3天内"
        }
      ],
      "short_term": [
        {
          "priority": "P1",
          "action": "布局送礼场景内容",
          "reason": "春节将至，送礼需求上升",
          "content_type": "清单推荐",
          "hashtags": ["#送礼奶粉", "#年货"],
          "deadline": "1周内"
        },
        {
          "priority": "P1",
          "action": "制作成分解析类内容",
          "reason": 「成分党」成为新兴话题",
          "content_type": "深度科普",
          "hashtags": ["#成分党", "#奶粉配方"],
          "deadline": "2周内"
        }
      ],
      "medium_term": [
        {
          "priority": "P2",
          "action": "开发DIY教程内容线",
          "reason": "竞品内容缺口，用户需求存在",
          "content_type": "教程视频",
          "examples": ["冲泡技巧", "辅食搭配", "花样吃法"],
          "deadline": "1个月内"
        },
        {
          "priority": "P2",
          "action": "优化竞品A的转化策略",
          "reason": "竞品直播带货效果良好",
          "action_detail": "学习其直播间话术和促销节奏",
          "deadline": "1个月内"
        }
      ]
    },
    "raw_data_export": {
      "format": "excel",
      "download_url": "/api/trend-monitor/export/{REQUEST_ID}.xlsx",
      "available_until": "2024-01-14 10:00:00",
      "data_included": {
        "videos": true,
        "comments": true,
        "alerts": true,
        "competitor_data": true
      }
    }
  }
}
```

---

## 核心监控维度详解

### 1. 用户需求类监控

```json
{
  "user_needs": {
    "description": "监控用户真实需求，直接反哺内容创作",
    "categories": {
      "question_inquiry": {
        "description": "用户问题咨询",
        "keywords": ["怎么选", "哪个好", "推荐", "求问"],
        "analysis_points": ["问题类型分布", "痛点识别", "需求强度"]
      },
      "usage_scenario": {
        "description": "使用场景表达",
        "keywords": ["送礼", "换奶", "囤货", "日常"],
        "analysis_points": ["场景频率", "场景特点", "场景需求"]
      },
      "need_expression": {
        "description": "需求直接表达",
        "keywords": ["想要", "需要", "求推荐", "求分享"],
        "analysis_points": ["需求类型", "需求强度", "转化潜力"]
      },
      "pain_point_complaint": {
        "description": "痛点抱怨",
        "keywords": ["不好", "不行", "太差", "后悔"],
        "analysis_points": ["痛点类型", "痛点频率", "改进方向"]
      }
    },
    "output_metrics": {
      "mentions_count": "总提及次数",
      "trend": "趋势变化",
      "sentiment": "情感倾向",
      "top_keywords": "高频关键词",
      "content_recommendations": "内容建议"
    }
  }
}
```

### 2. 舆情风险类监控

```json
{
  "public_sentiment": {
    "description": "监控负面舆情，及时预警响应",
    "alert_levels": {
      "low": {
        "description": "轻度关注",
        "threshold": "5条以下同类投诉",
        "response": "记录跟踪"
      },
      "medium": {
        "description": "中度关注",
        "threshold": "5-10条同类投诉",
        "response": "分析原因"
      },
      "high": {
        "description": "高度关注",
        "threshold": "10-20条同类投诉",
        "response": "准备预案"
      },
      "critical": {
        "description": "严重警告",
        "threshold": "20条以上同类投诉",
        "response": "立即响应"
      }
    },
    "risk_categories": {
      "quality_complaint": {
        "description": "产品质量投诉",
        "keywords": ["质量", "假货", "变质", "异物", "过期"]
      },
      "service_complaint": {
        "description": "服务投诉",
        "keywords": ["客服", "售后", "态度", "不回复"]
      },
      "false_advertising": {
        "description": "虚假宣传质疑",
        "keywords": ["虚假", "夸大", "骗人", "不是真的"]
      },
      "safety_issue": {
        "description": "安全问题",
        "keywords": ["危险", "有害", "中毒", "住院"]
      }
    },
    "output_metrics": {
      "alert_count": "预警数量",
      "severity_score": "严重程度评分",
      "affected_brand": "涉及品牌",
      "trend": "发展趋势",
      "recommended_action": "建议措施"
    }
  }
}
```

### 3. 竞品动态类监控

```json
{
  "competitor_dynamics": {
    "description": "追踪竞品内容策略，找差异化",
    "track_items": {
      "new_videos": {
        "description": "新发布视频",
        "analysis_points": ["发布频率", "内容类型", "发布时间"]
      },
      "engagement_data": {
        "description": "互动数据",
        "metrics": ["播放量", "点赞量", "评论量", "转发量", "完播率"]
      },
      "conversion_strategy": {
        "description": "转化策略",
        "analysis_points": ["带货频率", "促销方式", "转化话术"]
      },
      "content_innovation": {
        "description": "内容创新",
        "analysis_points": ["新形式", "新角度", "新话题"]
      }
    },
    "analysis_output": {
      "competitor_ranking": "竞品排名",
      "strategy_insights": "策略洞察",
      "content_gaps": "内容缺口",
      "weaknesses": "竞品弱点",
      "opportunities": "差异化机会"
    }
  }
}
```

### 4. 内容热点类监控

```json
{
  "content_trends": {
    "description": "借势热点流量，提升内容曝光",
    "track_metrics": {
      "views": "播放量",
      "likes": "点赞量",
      "comments": "评论量",
      "shares": "转发量",
      "completion_rate": "完播率"
    },
    "trend_types": {
      "rising": {
        "description": "上升趋势",
        "action": "快速跟进布局"
      },
      "stable": {
        "description": "稳定趋势",
        "action": "保持内容产出"
      },
      "declining": {
        "description": "下降趋势",
        "action": "减少投入或转换方向"
      },
      "emerging": {
        "description": "新兴趋势",
        "action": "优先布局抢占先机"
      }
    },
    "analysis_output": {
      "trending_topics": "热门话题",
      "declining_topics": "衰退话题",
      "emerging_topics": "新兴话题",
      "seasonal_predictions": "季节性预测",
      "content_opportunities": "内容机会"
    }
  }
}
```

---

## 定时任务配置

### 定时任务类型

```json
{
  "scheduled_tasks": {
    "daily_monitoring": {
      "cron": "0 9 * * *",
      "description": "每日监控报告",
      "output": "markdown",
      "monitor_scope": "前24小时数据"
    },
    "weekly_analysis": {
      "cron": "0 10 * * 1",
      "description": "每周综合分析报告",
      "output": "markdown",
      "monitor_scope": "前7天数据",
      "include_competitor_comparison": true
    },
    "monthly_trend_report": {
      "cron": "0 9 1 * *",
      "description": "月度趋势报告",
      "output": "markdown+excel",
      "monitor_scope": "前30天数据",
      "include_predictions": true
    },
    "realtime_alert": {
      "cron": "*/5 * * * *",
      "description": "实时舆情监控",
      "trigger": "当检测到高风险舆情时立即推送"
    }
  }
}
```

---

## 使用场景示例

### 场景1：竞品分析

```json
{
  "request": {
    "config": {
      "monitor_mode": "scheduled",
      "time_range": "7d"
    },
    "monitor_targets": {
      "hashtags": ["#奶粉"],
      "accounts": {
        "include": ["竞品A", "竞品B", "竞品C"]
      }
    },
    "monitor_dimensions": {
      "competitor_dynamics": {
        "enabled": true
      }
    }
  }
}
```

### 场景2：舆情监控

```json
{
  "request": {
    "config": {
      "monitor_mode": "realtime"
    },
    "monitor_targets": {
      "hashtags": ["#奶粉", "#婴儿食品安全"]
    },
    "monitor_dimensions": {
      "public_sentiment": {
        "enabled": true,
        "alert_levels": ["high", "critical"]
      }
    }
  }
}
```

### 场景3：热点借势

```json
{
  "request": {
    "config": {
      "monitor_mode": "scheduled",
      "time_range": "24h"
    },
    "monitor_targets": {
      "hashtags": ["#奶粉", "#育儿"]
    },
    "monitor_dimensions": {
      "content_trends": {
        "enabled": true
      }
    }
  }
}
```

---

## 与其他模块的联动

```
                    ┌─────────────────────────┐
                    │  Social Trend Monitor    │
                    │  社交媒体趋势监控接口     │
                    └───────────┬─────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
          ▼                     ▼                     ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  User Needs     │   │  Content Team  │   │  PR Team        │
│  用户需求分析     │   │  内容团队       │   │  公关团队        │
│                 │   │                 │   │                 │
│ • 问题挖掘       │   │ • 热点借势      │   │ • 舆情预警      │
│ • 痛点分析       │   │ • 选题建议      │   │ • 危机响应      │
│ • 内容方向       │   │ • 竞品学习      │   │ • 品牌形象      │
└─────────────────┘   └─────────────────┘   └─────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │  Insights Analyst       │
                    │  市场洞察专家           │
                    └─────────────────────────┘
```

---

## 配置

```json
{
  "name": "social-media-trend-monitor",
  "version": "1.0.0",
  "description": "抖音社交媒体趋势监控接口，支持用户需求、舆情风险、竞品动态、内容热点四大维度监控",
  "skill": "insights-analyst",
  "api_endpoint": "/api/trend-monitor",
  "monitor_platforms": ["douyin"],
  "monitor_types": ["短视频", "小店"],
  "monitor_dimensions": [
    "user_needs",
    "public_sentiment",
    "competitor_dynamics",
    "content_trends"
  ],
  "dependencies": ["douyin_api", "data_storage"]
}
```

---

## 维护日志

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| 1.0.0 | 2024-01-12 | 初始版本，支持四大监控维度 |
