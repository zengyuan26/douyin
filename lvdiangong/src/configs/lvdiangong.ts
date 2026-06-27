import type { VideoConfig } from "../templates/types";

const config: VideoConfig = {
  id: "lvdiangong",
  title: "绿电直供·5分钟讲透",
  transitionFrames: 15,
  pages: [
    {
      type: "cover", durationFrames: 180,
      label: "Concept Map · Vol. 4",
      title: "绿电直供",
      tags: ["三种绿证", "碳交易", "碳足迹"],
      background: "dark",
    },
    {
      type: "cards-3", durationFrames: 300,
      label: "Three Types",
      title: "三种绿证。第三种，不用花钱。",
      background: "light-amber",
      cards: [
        { label: "MUST BUY", title: "普通绿证", stat: "几毛钱", tag: "国内考核用", accent: "rgba(156,163,175,0.6)" },
        { label: "MUST BUY · RISING", title: "绿电交易绿证", stat: "3→7 块", tag: "越买越贵", accent: "#C89050" },
        { label: "NO COST", title: "直供绿证", stat: "免费", tag: "电到证到", accent: "#4D8F8F" },
      ],
    },
    {
      type: "chart-bar", durationFrames: 240,
      label: "Why Rising",
      title: "三个推手 — 同时施压",
      background: "light-amber",
      items: [
        { num: "01", title: "CBAM 全面执行", sub: "出口欧盟必须说明电力来源。加碳税。所有出口企业抢绿证。", accent: "#DC2626" },
        { num: "02", title: "国内考核扩围", sub: "绿电消费考核行业范围扩大。买证的人越来越多。", accent: "#C89050" },
      ],
      chartData: [
        { label: "2023", value: 0.8, color: "#C89050" },
        { label: "2024", value: 3.2, color: "#C89050" },
        { label: "2025", value: 5.5, color: "#DC2626" },
        { label: "2026", value: 7.8, color: "#DC2626" },
      ],
    },
    {
      type: "cards-4", durationFrames: 300,
      label: "Bottleneck",
      title: "四层卡脖子",
      background: "light-red",
      cards: [
        { num: "01", title: "资源卡", sub: "绿电资源与用电负荷地理错配", accent: "#C89050", icon: "wind" },
        { num: "02", title: "通道卡", sub: "特高压通道有限，省间壁垒", accent: "#DC2626", icon: "bolt" },
        { num: "03", title: "精度卡", sub: "年度匹配无法满足小时级溯源", accent: "#6B7280", icon: "grid" },
        { num: "04", title: "地域卡", sub: "试点省份有限，全国尚未铺开", accent: "#DC2626" },
      ],
    },
    {
      type: "cards-3", durationFrames: 270,
      label: "The Decision",
      title: "继续买，每年多花几十万。",
      titleAccent: "第三条路：建直供，一次投入。",
      background: "light-amber",
      cards: [
        { label: "PATH A", title: "绿电交易", stat: "140 万/年", tag: "越买越贵", accent: "#6B7280" },
        { label: "PATH B", title: "普通绿证", stat: "几毛钱", tag: "海关不认", accent: "#9CA3AF", dim: true },
        { label: "PATH C", title: "绿电直供", stat: "免费", tag: "第三条路 →", accent: "#C89050", highlighted: true },
      ],
    },
    {
      type: "compare-2", durationFrames: 210,
      label: "How It Works",
      title: "不经过电网混池。",
      titleAccent: "专线直连，电到证到。",
      background: "light-teal",
      left: {
        label: "买证模式", title: "证电分离",
        items: [{ text: "风电 → 电网混池 → 工厂" }, { text: "绿证 · 交易所单独购买 ↑" }],
        badge: "年年花钱 · 价格在涨", badgeColor: "#DC2626",
      },
      right: {
        label: "直供模式", title: "证跟电走",
        items: [{ text: "风电场 → 专线直连 → 工厂" }, { text: "绿证 · 自动核发，跟电走" }],
        badge: "电到证到 · 零额外成本", badgeColor: "#4D8F8F",
      },
    },
    {
      type: "steps", durationFrames: 240,
      label: "Find Your Path",
      title: "对号入座",
      background: "light-amber",
      steps: [
        { num: "01", title: "离风场 ≤ 30km、在试点省", body: "做直供", accent: "#C89050" },
        { num: "02", title: "离得远、有屋顶", body: "做微电网", accent: "#4D8F8F" },
        { num: "03", title: "两个条件都有", body: "奔零碳园区", accent: "#0D0D0D" },
      ],
    },
    {
      type: "pyramid", durationFrames: 240,
      label: "The Big Picture",
      title: "四块拼图 → 零碳园区",
      blocks: [
        { label: "源网荷储", sub: "战略地基", bg: "#0D0D0D", color: "#FFFFFF" },
        { label: "微电网", sub: "园内自循环", bg: "#C89050", color: "#FFFFFF" },
        { label: "绿电直供", sub: "园外拉专线", bg: "#C89050", color: "#FFFFFF" },
        { label: "虚拟电厂", sub: "统一调度 · 四份收入", bg: "#C89050", color: "#FFFFFF" },
        { label: "零碳园区", sub: "", bg: "#4D8F8F", color: "#FFFFFF" },
      ],
      cta: "下期拆解：零碳园区",
      question: "你现在在哪个阶段？评论区聊聊",
    },
  ],
};

export default config;
