import type { VideoConfig } from "../templates/types";

const config: VideoConfig = {
  id: "lingtan-zero-park",
  title: "零碳园区·一次讲透",
  transitionFrames: 15,
  pages: [
    {
      type: "cover", durationFrames: 180,
      label: "Concept Map · Vol. 5",
      title: "零碳园区",
      subtitle: "微电网 · 绿电直供 · 虚拟电厂 · 碳足迹趋零",
      background: "dark",
    },
    {
      type: "compare-2", durationFrames: 270,
      label: "What Is It",
      title: "不是买一张证。是建一套系统。",
      background: "light-amber",
      left: {
        label: "买证模式", title: "证电两张皮",
        items: [
          { text: "电走电网，绿证去交易所买" },
          { text: "每年买。价格一直在涨" },
        ],
        badge: "年年花钱 · 越花越多", badgeColor: "#DC2626",
      },
      right: {
        label: "建系统模式", title: "证跟着电走",
        items: [
          { text: "微电网自发自用 + 绿电直供拉专线 + VPP 调度剩余" },
          { text: "三路汇聚，证跟着电自动产生" },
        ],
        badge: "一次投入 · 证是副产品", badgeColor: "#4D8F8F",
      },
      bottomLine: "零碳园区 = 让你的工厂用电，每一度都说得清、不花钱买证、还有收益。",
    },
    {
      type: "threats-3", durationFrames: 240,
      title: "三把刀架在脖子上。不搞，成本只会越来越高。",
      background: "light-red",
      cards: [
        {
          title: "CBAM 碳关税",
          bullets: ["2026年全面执行", "出口欧盟必须证明碳足迹", "不证明？加征碳税"],
          stat: "碳税可能吃掉 15-30% 利润",
          accent: "red",
        },
        {
          title: "国内双碳考核",
          bullets: ["重点用能单位碳达峰考核在压缩", "绿电消费比例要求逐年提高", "园区循环化改造写入十四五"],
          tag: "从选做题变必做题",
          accent: "red",
        },
        {
          title: "供应链传导",
          bullets: ["苹果、特斯拉、宝马已发布供应链碳中和目标", "大客户 green supply chain 条款往下压", "不达标→丢订单"],
          tag: "客户在替你着急",
          accent: "gray",
        },
      ],
      bottomLine: "三股力量，同一个方向——你的工厂必须零碳。",
    },
    {
      type: "steps", durationFrames: 300,
      label: "How To",
      title: "一步一步来。不是一口气全建完。",
      background: "light-amber",
      steps: [
        { num: "01", title: "底座——源网荷储规划", body: "搞清楚用多少电、什么时候用、屋顶多大、离风场多远 → 一张能源路线图", tag: "第1-2个月", accent: "#0D0D0D" },
        { num: "02", title: "两条腿走路", body: "左：微电网（屋顶光伏+储能，自发自用 ≥60%）| 右：绿电直供（建专线，绿证免费）", tag: "第3-8个月", accent: "#C89050", substeps: [{ left: "微电网", right: "屋顶光伏+储能+负荷管理" }, { left: "绿电直供", right: "离风场≤30km+试点省" }] },
        { num: "03", title: "挂 VPP 调度", body: "分散资源交给VPP统一调度，利用率从30%拉到80%+，多出三份收入", tag: "第6-12个月", accent: "#C89050" },
        { num: "04", title: "认证闭环", body: "每小时碳足迹数据可追溯，第三方认证+绿证自动核发，出口免碳税", tag: "第6-12个月（可并行）", accent: "#4D8F8F" },
      ],
      bottomLine: "四步可以重叠推进。关键是第一步先动起来。",
    },
    {
      type: "big-numbers", durationFrames: 210,
      background: "light-amber",
      left: { label: "投入", value: "约 1000 万", detail: "微电网 + 绿电直供专线" },
      right: { label: "年省", value: "约 300 万+", detail: "绿证+电费+VPP+碳税" },
      bottomLine: "3-4 年回本。你已经在为绿证付钱了，为什么不拿这笔钱建一套自己能用的系统。",
    },
    {
      type: "threats-3", durationFrames: 240,
      title: "四类人。对号入座。",
      background: "light-amber",
      cards: [
        {
          title: "出口欧盟企业",
          bullets: ["产品出口欧洲、被CBAM覆盖", "碳关税直接吃利润", "不上零碳园区，价格没竞争力"],
          tag: "最急 · 马上搞",
          accent: "red",
        },
        {
          title: "新建工业园区",
          bullets: ["还在规划阶段，可以从零设计", "一步到位比后期改造便宜 40%+"],
          tag: "最佳时机 · 现在就规划",
          accent: "amber",
        },
        {
          title: "上市公司 / ESG 报告企业",
          bullets: ["年报要披露碳排放数据", "零碳园区=最好的ESG故事", "绿色融资还能拿利率优惠"],
          tag: "降融资成本",
          accent: "gray",
        },
      ],
    },
    {
      type: "steps", durationFrames: 240,
      label: "Start Here",
      title: "三步走。先审计，再建系统，最后挂网。",
      background: "light-amber",
      flowLabels: ["能源审计", "微电网", "绿电直供 + VPP", "零碳认证"],
      steps: [
        { num: "01", title: "能源审计", body: "花5-10万，做一个月用电数据采集。拿到：负荷曲线 + 屋顶评估 + 直供可行性。花得最值的一笔钱。", accent: "#C89050" },
        { num: "02", title: "上微电网", body: "光伏+储能+EMS。先解决自发自用。优先上储能（最灵活、收益最确定）。投入约 500-800 万。", accent: "#4D8F8F" },
        { num: "03", title: "直供 + VPP", body: "符合条件→建直供专线。不符合→先挂VPP调度。接入费100-200万。算账见第5页，3-4年回本。", accent: "#C89050" },
      ],
      bottomLine: "先上先锁定。政策窗口期不等人。",
    },
    {
      type: "case-study", durationFrames: 270,
      title: "江苏某电子元器件厂。出口欧洲。3 年回本。",
      background: "light-amber",
      before: {
        label: "改前",
        items: [
          "年用电 1200 万度，出口额 6000 万",
          "绿电合规成本从 18 万涨到 120 万（还在涨）",
          "碳关税一旦落地：≈900 万/年",
          "三笔支出：近 2000 万/年",
        ],
      },
      after: {
        label: "改后",
        items: [
          "屋顶光伏 + 储能 + 直供专线 + 接 VPP，四件套上齐",
          "绿证免费，电费降 240 万，VPP 增收 35 万，碳税归零",
          "年省近 400 万（不含碳税消除）",
        ],
      },
      investment: "约 1200 万",
      annualSavings: "近 400 万",
      payback: "3 年",
      bottomLine: "一年差出一套系统钱。投资回收后每年多出近 400 万。",
    },
    {
      type: "pyramid", durationFrames: 240,
      label: "The Big Picture",
      title: "五期概念图谱。一条线串起来。",
      blocks: [
        { label: "源网荷储", sub: "战略地基", bg: "#0D0D0D", color: "#FFFFFF" },
        { label: "虚拟电厂", sub: "调度增收", bg: "#C89050", color: "#FFFFFF" },
        { label: "微电网", sub: "园内自发", bg: "#C89050", color: "#FFFFFF" },
        { label: "绿电直供", sub: "园外专线", bg: "#C89050", color: "#FFFFFF" },
        { label: "零碳园区", sub: "四层叠满", bg: "#4D8F8F", color: "#FFFFFF" },
      ],
      cta: "概念图谱系列完结。下期开新系列。",
      question: "你想听什么方向？评论区告诉我",
    },
  ],
};

export default config;
