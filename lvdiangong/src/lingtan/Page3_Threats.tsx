import { useCurrentFrame, interpolate, spring } from "remotion";
import { LIGHT_BG_RED } from "../components/Background";
import { ParticleField } from "../components/ParticleField";

const threats = [
  {
    title: "CBAM 碳关税",
    subtitle: "2026年全面执行",
    accent: "#DC2626",
    points: [
      "出口欧盟，每件产品必须证明碳足迹",
      "不证明？加征碳税",
    ],
    stat: "碳税可能吃掉 15-30% 利润",
  },
  {
    title: "国内双碳考核",
    subtitle: "从选做题变必做题",
    accent: "#DC2626",
    points: [
      "重点用能单位碳达峰时间表压缩",
      "绿电消费比例要求逐年提高",
    ],
    stat: "园区循环化改造写入十四五",
  },
  {
    title: "供应链传导",
    subtitle: "客户在替你着急",
    accent: "#6B7280",
    points: [
      "苹果、特斯拉、宝马发布供应链碳中和目标",
      "大客户 green supply chain 条款往下压",
    ],
    stat: "不达标 → 丢订单",
  },
];

export const Page3_Threats: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <div style={{
      width: "100%", height: "100%", background: LIGHT_BG_RED,
      fontFamily: '"Noto Sans SC", -apple-system, sans-serif',
      display: "flex", flexDirection: "column", justifyContent: "center",
      padding: "60px 100px", position: "relative", overflow: "hidden", gap: 36,
    }}>
      <ParticleField />

      {/* Header */}
      <div style={{ opacity: interpolate(frame, [0, 8], [0, 1], { extrapolateRight: "clamp" }) }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: "#DC2626", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 8 }}>
          Why Now
        </div>
        <h2 style={{ fontSize: 56, fontWeight: 800, color: "#0D0D0D", margin: 0, lineHeight: 1.1 }}>
          三把刀架在脖子上。<br/>不搞，成本只会越来越高。
        </h2>
      </div>

      {/* Three threat cards */}
      <div style={{ display: "flex", gap: 24, flex: 1, alignItems: "stretch" }}>
        {threats.map((t, i) => (
          <ThreatCard key={i} data={t} index={i} frame={frame} />
        ))}
      </div>

      {/* Bottom conclusion */}
      <div style={{
        opacity: interpolate(frame, [70, 80], [0, 1], { extrapolateRight: "clamp" }),
        textAlign: "center", padding: "16px 40px",
        background: "rgba(220,38,38,0.06)", borderRadius: 12,
        border: "1px solid rgba(220,38,38,0.12)",
      }}>
        <span style={{ fontSize: 20, fontWeight: 700, color: "#0D0D0D" }}>
          三股力量，同一个方向——
        </span>
        <span style={{ fontSize: 20, fontWeight: 800, color: "#DC2626" }}>
          你的工厂必须零碳。
        </span>
      </div>
    </div>
  );
};

const ThreatCard: React.FC<{ data: typeof threats[0]; index: number; frame: number }> = ({ data, index, frame }) => {
  const d = 15 + index * 14;
  const s = spring({ frame: frame - d, fps: 30, config: { damping: 8, stiffness: 180 } });
  const o = interpolate(frame, [d, d + 8], [0, 1], { extrapolateRight: "clamp" });
  const y = interpolate(s, [0, 1], [50, 0]);

  return (
    <div style={{
      flex: 1, opacity: o, transform: `translateY(${y}px)`,
      padding: "32px 28px", borderRadius: 18,
      background: "rgba(255,255,255,0.55)",
      backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)",
      border: `1px solid rgba(255,255,255,0.5)`,
      borderLeft: `4px solid ${data.accent}`,
      boxShadow: "0 2px 16px rgba(0,0,0,0.03)",
      display: "flex", flexDirection: "column", gap: 16,
    }}>
      <div>
        <div style={{ fontSize: 24, fontWeight: 800, color: "#0D0D0D" }}>{data.title}</div>
        <div style={{ fontSize: 14, color: data.accent, fontWeight: 600, marginTop: 4 }}>{data.subtitle}</div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {data.points.map((p, j) => {
          const pS = spring({ frame: frame - (d + 10 + j * 5), fps: 30, config: { damping: 8, stiffness: 200 } });
          return (
            <div key={j} style={{
              opacity: interpolate(pS, [0, 1], [0.3, 1]),
              fontSize: 15, color: "#4B5563", lineHeight: 1.5,
            }}>
              · {p}
            </div>
          );
        })}
      </div>
      <div style={{
        marginTop: "auto", padding: "10px 16px", borderRadius: 10,
        background: `${data.accent}0D`,
        fontSize: 15, fontWeight: 700, color: data.accent,
        border: `1px solid ${data.accent}1A`,
      }}>
        {data.stat}
      </div>
    </div>
  );
};
