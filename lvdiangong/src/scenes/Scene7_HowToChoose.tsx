import { useCurrentFrame, interpolate, spring } from "remotion";
import { ParticleField } from "../components/ParticleField";
import { LIGHT_BG_AMBER } from "../components/Background";

const routes = [
  { num: "01", text: "离风场 ≤ 30km、在试点省", action: "做直供", accent: "#C89050" },
  { num: "02", text: "离得远、有屋顶", action: "做微电网", accent: "#4D8F8F" },
  { num: "03", text: "两个条件都有", action: "奔零碳园区", accent: "#0D0D0D" },
];
const ops = [
  { num: "01", title: "搭伙", body: "你 + 风电场业主 = 项目公司" },
  { num: "02", title: "四个规矩", body: "自发自用 ≥ 60% · 绿电 ≥ 30%" },
  { num: "03", title: "多久落地", body: "几个月到一年 · 99 个已获批" },
];

export const Scene7_HowToChoose: React.FC = () => {
  const frame = useCurrentFrame();
  const titleO = interpolate(frame, [0, 8], [0, 1], { extrapolateRight: "clamp" });
  const routesO = interpolate(frame, [8, 16], [0, 1], { extrapolateRight: "clamp" });
  return (
    <div style={{ width: "100%", height: "100%", background: LIGHT_BG_AMBER, fontFamily: '"Noto Sans SC", -apple-system, sans-serif', display: "flex", gap: 60, padding: "60px 100px", position: "relative", overflow: "hidden" }}>
      <ParticleField />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", gap: 16 }}>
        <div style={{ opacity: titleO }}><div style={{ fontSize: 15, fontWeight: 600, color: "#C89050", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 12 }}>Find Your Path</div><h2 style={{ fontSize: 64, fontWeight: 800, color: "#0D0D0D", margin: 0, lineHeight: 1.08 }}>对号入座</h2></div>
        <div style={{ opacity: routesO, display: "flex", flexDirection: "column", gap: 14, marginTop: 8 }}>
          {routes.map((r, i) => {
            const s = spring({ frame: frame - 12 - i * 10, fps: 30, config: { damping: 8, stiffness: 180 } });
            const y = interpolate(s, [0, 1], [20, 0]);
            return (<div key={i} style={{ transform: `translateY(${y}px)`, padding: "24px 28px", borderRadius: 16, background: "rgba(255,255,255,0.5)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", border: "1px solid rgba(255,255,255,0.5)", boxShadow: "0 2px 12px rgba(0,0,0,0.03)" }}><div style={{ fontSize: 16, fontWeight: 600, color: "rgba(0,0,0,0.2)", letterSpacing: "0.06em", marginBottom: 4 }}>{r.num}</div><div style={{ fontSize: 26, fontWeight: 700, color: "#0D0D0D" }}>{r.text}</div><div style={{ fontSize: 22, fontWeight: 700, color: r.accent }}>{r.action}</div></div>);
          })}
        </div>
      </div>
      <div style={{ flex: 1, opacity: routesO, padding: "44px 40px", borderRadius: 24, background: "rgba(255,255,255,0.5)", backdropFilter: "blur(24px)", WebkitBackdropFilter: "blur(24px)", border: "1px solid rgba(255,255,255,0.5)", boxShadow: "0 8px 32px rgba(0,0,0,0.04)", display: "flex", flexDirection: "column", justifyContent: "center", gap: 28 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: "#9CA3AF", letterSpacing: "0.06em", textTransform: "uppercase" }}>操作流程</div>
        {ops.map((o, i) => (<div key={i} style={{ opacity: interpolate(frame, [20 + i * 16, 26 + i * 16], [0, 1], { extrapolateRight: "clamp" }), paddingBottom: i < 2 ? 24 : 0, borderBottom: i < 2 ? "1px solid rgba(0,0,0,0.06)" : "none" }}><div style={{ fontSize: 18, fontWeight: 600, color: "rgba(0,0,0,0.2)", marginBottom: 4 }}>{o.num}</div><div style={{ fontSize: 28, fontWeight: 800, color: "#0D0D0D" }}>{o.title}</div><div style={{ fontSize: 20, fontWeight: 400, color: "#6B7280", marginTop: 2 }}>{o.body}</div></div>))}
      </div>
    </div>
  );
};
