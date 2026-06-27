import { useCurrentFrame, interpolate, spring } from "remotion";
import { ParticleField } from "../../components/ParticleField";
import { AnimatedBarChart } from "../../components/AnimatedBarChart";
import { bgMap, isLightBg } from "./shared";
import type { ChartBarPage } from "../types";

export const ChartBarScene: React.FC<ChartBarPage> = ({ label, title, items, chartData, background }) => {
  const frame = useCurrentFrame();
  const bg = bgMap(background);
  const light = isLightBg(background);
  const textColor = light ? "#0D0D0D" : "#FFFFFF";
  const titleO = interpolate(frame, [0, 8], [0, 1], { extrapolateRight: "clamp" });

  return (
    <div style={{ width: "100%", height: "100%", background: bg, fontFamily: '"Noto Sans SC", -apple-system, sans-serif', display: "flex", flexDirection: "column", justifyContent: "center", padding: "0 100px", gap: 32, position: "relative", overflow: "hidden" }}>
      <ParticleField dark={!light} />
      <div style={{ opacity: titleO, padding: "0 20px" }}>
        {label ? <div style={{ fontSize: 15, fontWeight: 600, color: "#C89050", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 12 }}>{label}</div> : null}
        <h2 style={{ fontSize: 56, fontWeight: 800, color: textColor, margin: 0, lineHeight: 1.12 }}>{title}</h2>
      </div>
      <div style={{ display: "flex", gap: 40, padding: "0 20px" }}>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 16 }}>
          {items.map((item, i) => {
            const s = spring({ frame: frame - 8 - i * 12, fps: 30, config: { damping: 8, stiffness: 180 } });
            const y = interpolate(s, [0, 1], [20, 0]);
            const o = interpolate(frame, [i * 12, i * 12 + 8], [0, 1], { extrapolateRight: "clamp" });
            return (
              <div key={i} style={{ opacity: o, transform: `translateY(${y}px)`, padding: "24px 28px", borderRadius: 14, background: light ? "rgba(255,255,255,0.5)" : "rgba(255,255,255,0.04)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", border: light ? "1px solid rgba(255,255,255,0.5)" : "1px solid rgba(255,255,255,0.08)", borderLeft: `4px solid ${item.accent}` }}>
                <div style={{ fontSize: 16, fontWeight: 600, color: "rgba(0,0,0,0.2)", letterSpacing: "0.06em", marginBottom: 6 }}>{item.num}</div>
                <div style={{ fontSize: 24, fontWeight: 700, color: textColor }}>{item.title}</div>
                <div style={{ fontSize: 18, color: light ? "#6B7280" : "rgba(255,255,255,0.5)", marginTop: 4 }}>{item.sub}</div>
              </div>
            );
          })}
        </div>
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <AnimatedBarChart data={chartData} width={400} height={300} delay={16} />
        </div>
      </div>
    </div>
  );
};
