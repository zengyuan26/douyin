import { useCurrentFrame, interpolate, spring } from "remotion";
import { ParticleField } from "../components/ParticleField";
import { LIGHT_BG_AMBER } from "../components/Background";
import { AnimatedBarChart } from "../components/AnimatedBarChart";

const forces = [
  { icon: "01", title: "CBAM 全面执行", sub: "出口欧盟必须说明电力来源。加碳税。所有出口企业抢绿证。", accent: "#DC2626" },
  { icon: "02", title: "国内考核扩围", sub: "绿电消费考核行业范围扩大。买证的人越来越多。", accent: "#C89050" },
];

const Card: React.FC<{ index: number; data: (typeof forces)[number] }> = ({ index, data }) => {
  const frame = useCurrentFrame();
  const d = index * 16;
  const s = spring({ frame: frame - d, fps: 30, config: { damping: 8, stiffness: 180 } });
  const y = interpolate(s, [0, 1], [40, 0]);
  const o = interpolate(frame, [d, d + 8], [0, 1], { extrapolateRight: "clamp" });
  const barW = interpolate(frame, [d + 10, d + 28], [0, 1], { extrapolateRight: "clamp", extrapolateLeft: "clamp" });
  return (
    <div style={{ opacity: o, transform: `translateY(${y}px)`, padding: "32px 28px", borderRadius: 18, background: "rgba(255,255,255,0.5)", backdropFilter: "blur(20px)", WebkitBackdropFilter: "blur(20px)", border: "1px solid rgba(255,255,255,0.5)", boxShadow: "0 4px 20px rgba(0,0,0,0.04)", display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ width: 48, height: 48, borderRadius: 14, background: data.accent, color: "#FFF", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20, fontWeight: 800 }}>{data.icon}</div>
      <div style={{ fontSize: 26, fontWeight: 700, color: "#0D0D0D" }}>{data.title}</div>
      <div style={{ fontSize: 20, fontWeight: 400, color: "#6B7280", lineHeight: 1.4, flex: 1 }}>{data.sub}</div>
      <div style={{ height: 3, borderRadius: 2, background: "rgba(0,0,0,0.06)", overflow: "hidden" }}><div style={{ height: "100%", width: `${barW * 100}%`, background: data.accent, borderRadius: 2 }} /></div>
    </div>
  );
};

export const Scene3_WhyRise: React.FC = () => {
  const frame = useCurrentFrame();
  const titleO = interpolate(frame, [0, 6], [0, 1], { extrapolateRight: "clamp" });
  const chartO = interpolate(frame, [10, 18], [0, 1], { extrapolateRight: "clamp" });
  return (
    <div style={{ width: "100%", height: "100%", background: LIGHT_BG_AMBER, fontFamily: '"Noto Sans SC", -apple-system, sans-serif', display: "flex", flexDirection: "column", justifyContent: "center", padding: "0 80px", gap: 28, position: "relative", overflow: "hidden" }}>
      <ParticleField />
      <div style={{ opacity: titleO, padding: "0 20px" }}>
        <div style={{ fontSize: 15, fontWeight: 600, color: "#C89050", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 12 }}>Why Rising</div>
        <h2 style={{ fontSize: 60, fontWeight: 800, color: "#0D0D0D", margin: 0, lineHeight: 1.08, letterSpacing: "-0.03em" }}>三个推手 — 同时施压</h2>
      </div>
      <div style={{ display: "flex", gap: 24, padding: "0 20px" }}>
        {forces.map((f, i) => <Card key={i} index={i} data={f} />)}
        <div style={{ opacity: chartO, flex: 1, padding: "28px", borderRadius: 18, background: "rgba(255,255,255,0.5)", backdropFilter: "blur(20px)", WebkitBackdropFilter: "blur(20px)", border: "1px solid rgba(255,255,255,0.5)", boxShadow: "0 4px 20px rgba(0,0,0,0.04)", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
          <div style={{ fontSize: 16, fontWeight: 600, color: "#6B7280", marginBottom: 16, alignSelf: "flex-start" }}>绿电交易绿证价格</div>
          <AnimatedBarChart delay={16} width={320} height={240} data={[
            { label: "2023", value: 0.8, color: "#C89050" }, { label: "2024", value: 3.2, color: "#C89050" },
            { label: "2025", value: 5.5, color: "#DC2626" }, { label: "2026", value: 7.8, color: "#DC2626" },
          ]} />
          <div style={{ fontSize: 14, color: "#DC2626", fontWeight: 600, marginTop: 8 }}>元 / 个</div>
        </div>
      </div>
    </div>
  );
};
