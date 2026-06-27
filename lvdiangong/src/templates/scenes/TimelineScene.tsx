import { useCurrentFrame, interpolate, spring } from "remotion";
import { ParticleField } from "../../components/ParticleField";
import { bgMap, isLightBg } from "./shared";
import type { TimelinePage } from "../types";

export const TimelineScene: React.FC<TimelinePage> = ({ title, acts, bottomLine, background }) => {
  const frame = useCurrentFrame();
  const bg = bgMap(background);
  const light = isLightBg(background);
  const textColor = light ? "#0D0D0D" : "#FFFFFF";
  const dimColor = light ? "rgba(0,0,0,0.5)" : "rgba(255,255,255,0.5)";
  const titleO = interpolate(frame, [0, 8], [0, 1], { extrapolateRight: "clamp" });
  const bottomO = interpolate(frame, [90, 106], [0, 1], { extrapolateRight: "clamp" });

  return (
    <div style={{ width: "100%", height: "100%", background: bg, fontFamily: '"Noto Sans SC", -apple-system, sans-serif', display: "flex", flexDirection: "column", justifyContent: "center", padding: "0 80px", gap: 28, position: "relative", overflow: "hidden" }}>
      <ParticleField dark={!light} />
      <div style={{ opacity: titleO, textAlign: "center" }}>
        <h2 style={{ fontSize: 42, fontWeight: 800, color: textColor, margin: 0, lineHeight: 1.2 }}>{title}</h2>
      </div>
      <div style={{ display: "flex", gap: 16 }}>
        {acts.map((act, i) => {
          const s = spring({ frame: frame - 8 - i * 16, fps: 30, config: { damping: 8, stiffness: 180 } });
          const y = interpolate(s, [0, 1], [30, 0]);
          const o = interpolate(frame, [i * 16, i * 16 + 10], [0, 1], { extrapolateRight: "clamp" });
          return (
            <div key={i} style={{ flex: 1, opacity: o, transform: `translateY(${y}px)`, padding: "20px 14px", borderRadius: 14, background: light ? "rgba(255,255,255,0.5)" : "rgba(255,255,255,0.04)", backdropFilter: "blur(12px)", WebkitBackdropFilter: "blur(12px)", border: `1px solid ${light ? "rgba(0,0,0,0.08)" : "rgba(255,255,255,0.08)"}`, display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: "#C89050", letterSpacing: "0.06em" }}>{act.label}</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: textColor }}>{act.title}</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {act.items.map((item, j) => <div key={j} style={{ fontSize: 14, color: dimColor, lineHeight: 1.4 }}>{item}</div>)}
              </div>
              <div style={{ marginTop: 4, padding: "4px 10px", borderRadius: 6, background: "rgba(200,144,80,0.1)", fontSize: 12, fontWeight: 600, color: "#C89050", alignSelf: "flex-start" }}>{act.tag}</div>
            </div>
          );
        })}
      </div>
      {bottomLine ? <div style={{ opacity: bottomO, textAlign: "center", fontSize: 22, fontWeight: 700, color: textColor }}>{bottomLine}</div> : null}
    </div>
  );
};
