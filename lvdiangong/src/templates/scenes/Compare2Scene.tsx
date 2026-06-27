import { useCurrentFrame, interpolate, spring } from "remotion";
import { ParticleField } from "../../components/ParticleField";
import { bgMap, isLightBg } from "./shared";
import type { Compare2Page } from "../types";

export const Compare2Scene: React.FC<Compare2Page> = ({ label, title, titleAccent, left, right, bottomLine, background }) => {
  const frame = useCurrentFrame();
  const bg = bgMap(background);
  const light = isLightBg(background);
  const textColor = light ? "#0D0D0D" : "#FFFFFF";
  const titleO = interpolate(frame, [0, 8], [0, 1], { extrapolateRight: "clamp" });
  const leftS = spring({ frame: frame - 8, fps: 30, config: { damping: 8, stiffness: 180 } });
  const rightS = spring({ frame: frame - 22, fps: 30, config: { damping: 8, stiffness: 180 } });
  const leftO = interpolate(frame, [8, 14], [0, 1], { extrapolateRight: "clamp" });
  const rightO = interpolate(frame, [22, 28], [0, 1], { extrapolateRight: "clamp" });

  const panelStyle = (accent: string, o: number, y: number) => ({
    flex: 1, opacity: o, transform: `translateY(${y}px)`, padding: "36px", borderRadius: 20,
    background: light ? "rgba(255,255,255,0.5)" : "rgba(255,255,255,0.04)",
    backdropFilter: "blur(20px)", WebkitBackdropFilter: "blur(20px)",
    border: `1px solid ${accent}20`, boxShadow: light ? "0 4px 20px rgba(0,0,0,0.04)" : "0 4px 20px rgba(0,0,0,0.2)",
  });

  const itemStyle = (accent: string) => ({
    padding: "12px 16px", borderRadius: 10,
    background: light ? "rgba(0,0,0,0.04)" : "rgba(255,255,255,0.04)",
    fontSize: 20, color: light ? "#4B5563" : "rgba(255,255,255,0.7)",
  });

  return (
    <div style={{ width: "100%", height: "100%", background: bg, fontFamily: '"Noto Sans SC", -apple-system, sans-serif', display: "flex", flexDirection: "column", justifyContent: "center", padding: "0 100px", gap: 32, position: "relative", overflow: "hidden" }}>
      <ParticleField dark={!light} />
      <div style={{ opacity: titleO, padding: "0 20px" }}>
        {label ? <div style={{ fontSize: 15, fontWeight: 600, color: "#C89050", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 12 }}>{label}</div> : null}
        <h2 style={{ fontSize: 56, fontWeight: 800, color: textColor, margin: 0, lineHeight: 1.12 }}>
          {title}{titleAccent ? <><br /><span style={{ color: "#C89050" }}>{titleAccent}</span></> : null}
        </h2>
      </div>
      <div style={{ display: "flex", gap: 32, padding: "0 20px" }}>
        <div style={panelStyle(left.badgeColor || "#6B7280", leftO, interpolate(leftS, [0, 1], [30, 0]))}>
          <div style={{ fontSize: 14, fontWeight: 600, color: "#9CA3AF", letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 16 }}>{left.label}</div>
          <div style={{ fontSize: 32, fontWeight: 800, color: textColor, marginBottom: 24 }}>{left.title}</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {left.items.map((item, i) => <div key={i} style={itemStyle(item.accent || "#6B7280")}>{item.text}</div>)}
          </div>
          {left.badge ? <div style={{ marginTop: 16, padding: "10px 18px", borderRadius: 10, background: "rgba(220,38,38,0.06)", fontSize: 20, color: "#DC2626", fontWeight: 600 }}>{left.badge}</div> : null}
        </div>
        <div style={panelStyle(right.badgeColor || "#4D8F8F", rightO, interpolate(rightS, [0, 1], [30, 0]))}>
          <div style={{ fontSize: 14, fontWeight: 600, color: "#4D8F8F", letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 16 }}>{right.label}</div>
          <div style={{ fontSize: 32, fontWeight: 800, color: textColor, marginBottom: 24 }}>{right.title}</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {right.items.map((item, i) => <div key={i} style={itemStyle(item.accent || "#4D8F8F")}>{item.text}</div>)}
          </div>
          {right.badge ? <div style={{ marginTop: 16, padding: "10px 18px", borderRadius: 10, background: "rgba(77,143,143,0.08)", fontSize: 20, color: "#4D8F8F", fontWeight: 600 }}>{right.badge}</div> : null}
        </div>
      </div>
      {bottomLine ? <div style={{ opacity: interpolate(frame, [50, 66], [0, 1], { extrapolateRight: "clamp" }), padding: "0 20px", fontSize: 24, fontWeight: 600, color: textColor, textAlign: "center" }}>{bottomLine}</div> : null}
    </div>
  );
};
