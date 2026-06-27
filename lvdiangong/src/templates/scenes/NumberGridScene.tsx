import { useCurrentFrame, interpolate, spring } from "remotion";
import { ParticleField } from "../../components/ParticleField";
import { bgMap, isLightBg } from "./shared";
import type { NumberGridPage } from "../types";

export const NumberGridScene: React.FC<NumberGridPage> = ({ title, cards, bottomLine, background }) => {
  const frame = useCurrentFrame();
  const bg = bgMap(background);
  const light = isLightBg(background);
  const textColor = light ? "#0D0D0D" : "#FFFFFF";
  const dimColor = light ? "rgba(0,0,0,0.5)" : "rgba(255,255,255,0.5)";
  const titleO = interpolate(frame, [0, 8], [0, 1], { extrapolateRight: "clamp" });
  const bottomO = interpolate(frame, [70, 86], [0, 1], { extrapolateRight: "clamp" });

  return (
    <div style={{ width: "100%", height: "100%", background: bg, fontFamily: '"Noto Sans SC", -apple-system, sans-serif', display: "flex", flexDirection: "column", justifyContent: "center", padding: "0 120px", gap: 32, position: "relative", overflow: "hidden" }}>
      <ParticleField dark={!light} />
      <div style={{ opacity: titleO, textAlign: "center" }}>
        <h2 style={{ fontSize: 48, fontWeight: 800, color: textColor, margin: 0 }}>{title}</h2>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 24, justifyContent: "center" }}>
        {cards.map((c, i) => {
          const s = spring({ frame: frame - 8 - i * 10, fps: 30, config: { damping: 8, stiffness: 180 } });
          const y = interpolate(s, [0, 1], [20, 0]);
          const o = interpolate(frame, [i * 10, i * 10 + 8], [0, 1], { extrapolateRight: "clamp" });
          return (
            <div key={i} style={{ flex: "1 1 40%", maxWidth: "48%", opacity: o, transform: `translateY(${y}px)`, padding: "32px 24px", borderRadius: 16, background: light ? "rgba(255,255,255,0.5)" : "rgba(255,255,255,0.04)", backdropFilter: "blur(12px)", WebkitBackdropFilter: "blur(12px)", border: `1px solid ${c.accent}30`, textAlign: "center" }}>
              <div style={{ fontSize: 16, fontWeight: 600, color: dimColor, marginBottom: 8 }}>{c.label}</div>
              <div style={{ fontSize: 44, fontWeight: 800, color: c.accent, lineHeight: 1.1 }}>{c.value}</div>
            </div>
          );
        })}
      </div>
      {bottomLine ? <div style={{ opacity: bottomO, textAlign: "center", fontSize: 22, fontWeight: 600, color: textColor }}>{bottomLine}</div> : null}
    </div>
  );
};
