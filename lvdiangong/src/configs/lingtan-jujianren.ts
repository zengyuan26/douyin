import type { VideoConfig } from "../templates/types";

const config: VideoConfig = {
  id: "lingtan-jujianren",
  title: "零碳园区·小陈的故事",
  transitionFrames: 15,
  pages: [
    // P1: 封面 — 24s
    {
      type: "cover", durationFrames: 720,
      label: "一次讲清楚",
      title: "零碳园区",
      tags: ["第一单成交了", "他却亏了五六万"],
      background: "dark",
    },
    // P2: 拒绝 — 28s
    {
      type: "compare-2", durationFrames: 840, background: "light-amber",
      label: "四年前",
      title: "",
      left: {
        label: "基金兄弟", title: "新能源方向",
        items: [
          { icon: "certificate", text: "工厂零碳改造" },
          { icon: "bolt", text: "碳关税要来了" },
        ],
        badge: "一起做？",
      },
      right: {
        label: "小陈", title: "拒绝了",
        items: [
          { icon: "wind", text: "光伏 = 骗补贴" },
          { icon: "factory", text: "跑路、烂尾" },
        ],
        badge: "不碰", badgeColor: "#DC2626",
      },
    },
    // P3: 回头 — 26s
    {
      type: "cards-4", durationFrames: 780, background: "light-amber",
      label: "巴南 · 跑滴滴时听到的",
      title: "",
      cards: [
        { num: "碳关税", title: "一年几十万", accent: "#DC2626", icon: "certificate" },
        { num: "不交？", title: "欧洲客户换供应商", accent: "#C89050", icon: "exchange" },
        { num: "隔壁老王", title: "装了光伏和储能", accent: "#4D8F8F", icon: "bolt" },
        { num: "谁认识", title: "能搞这个的？", accent: "#6B7280", icon: "grid" },
      ],
    },
    // P4: 浅学 — 22s
    {
      type: "big-numbers", durationFrames: 660, background: "light-amber",
      left: { label: "他以为", value: "光伏+储能", detail: "帮工厂省电费\n老板们需要\n这事能干" },
      right: { label: "他不知道", value: "≠ 绿证", detail: "微电网发的电\n没有绿证\n免不了碳关税" },
      bottomLine: "摸清个大概，就开始找客户了。",
    },
    // P5: 栽了 — 40s
    {
      type: "timeline", durationFrames: 1200, background: "light-red",
      title: "",
      acts: [
        {
          label: "① 顺利",
          title: "储能柜装好",
          items: ["xx 机械厂", "安装调试", "电费降了", "双方开心"],
          tag: "熟人",
        },
        {
          label: "② 出事",
          title: "货到欧盟海关",
          items: ["要绿证", "微电网的电 ≠ 绿证", "老板高价去交易所买"],
          tag: "炸了",
        },
        {
          label: "③ 拆了",
          title: "储能柜拆除",
          items: ["责问小陈", "谈不拢", "小陈掏了五六万"],
          tag: "亏了",
        },
      ],
      bottomLine: "他没骗人。他也不知道。",
    },
    // P6: 重学 — 44s
    {
      type: "steps", durationFrames: 1320, background: "light-amber",
      label: "栽了之后，回去重学",
      title: "",
      flowLabels: ["微电网", "绿电交易", "VPP"],
      steps: [
        { num: "01", title: "微电网", body: "屋顶光伏 + 储能。自发自用。降电费。但免不了碳关税。", accent: "#4D8F8F" },
        { num: "02", title: "绿电交易", body: "重庆风场少，做不了绿电直供。走绿电交易买绿证。绿证 = 清洁电力的身份证。", accent: "#C89050" },
        { num: "03", title: "重庆路径", body: "微电网 → 绿电交易 → 虚拟电厂。三步叠上去。这才是重庆工厂最适合走的路。", accent: "#0D0D0D" },
      ],
      bottomLine: "这次，学透了。",
    },
    // P7: 第二单 — 30s
    {
      type: "big-numbers", durationFrames: 900, background: "light-amber",
      left: { label: "第二单 · 老熟人", value: "30 万", detail: "巴南汽配厂\n微电网 + 绿电交易\n总投入 600 万 · 5%" },
      right: { label: "跑了半年", value: "电费 ↓", detail: "电费实打实降了\n绿证按月买\n碳关税解决" },
      bottomLine: "双方都很满意。",
    },
    // P8: 第三单 — 30s
    {
      type: "big-numbers", durationFrames: 900, background: "light-amber",
      left: { label: "第三单 · 转介绍", value: "30 万", detail: "机械厂老板主动介绍\n1000 万改造 · 3%" },
      right: { label: "两笔单子", value: "60 万", detail: "第一单栽了\n第二第三单成了\n路走对了" },
      bottomLine: "不是钱。是客户认可。",
    },
    // P9: 收尾 — 26s
    {
      type: "closing", durationFrames: 780, background: "light-amber",
      title: "大方向对，就不怕走得慢。",
      lines: [
        "熟人生意。要有资源。",
        "正儿八经要有耐心。",
        "简单的事大家卷。门槛高的竞争少。",
        "多点耐心，多点诚心。",
      ],
      seriesLine: "源网荷储 → 虚拟电厂 → 微电网 → 绿电直供 → 零碳园区",
    },
  ],
};

export default config;
