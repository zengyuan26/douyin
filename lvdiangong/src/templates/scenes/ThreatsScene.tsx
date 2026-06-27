import { useCurrentFrame, interpolate, spring } from "remotion";
import { ParticleField } from "../../components/ParticleField";
import { bgMap, isLightBg } from "./shared";
import type { ThreatsPage } from "../types";

const accentMap: Record<string, string> = {
  red: "#DC2626", amber: "#C89050", gray: "#6B7280", teal: "#4D8F8F",
};

export const ThreatsScene: React.FC<ThreatsPage> = ({ title, cards, bottomLine, background }) => {
  const frame = useCurrentFrame();
  const bg = bgMap(background);
  const light = isLightBg(background);
  const textColor = light ? "#0D0D0D" : "#FFFFFF";
  const titleO = interpolate(frame, [0, 8], [0, 1], { extrapolateRight: "clamp" });
  const bottomO = interpolate(frame, [60, 76], [0, 1], { extrapolateRight: "clamp" });

  return (
    <div style={{ width: "100%", height: "100%", background: bg, fontFamily: '"Noto Sans SC", -apple-system, sans-serif', display: "flex", flexDirection: "column", justifyContent: "center", padding: "0 100px", gap: 32, position: "relative", overflow: "hidden" }}>
      <ParticleField dark={!light} />
      <div style={{ opacity: titleO, padding: "0 20px" }}>
        <h2 style={{ fontSize: 56, fontWeight: 800, color: textColor, margin: 0, lineHeight: 1.12 }}>{title}</h2>
      </div>
      <div style={{ display: "flex", gap: 24, padding: "0 20px" }}>
        {cards.map((c, i) => {
          const s = spring({ frame: frame - 8 - i * 14, fps: 30, config: { damping: 8, stiffness: 180 } });
          const y = interpolate(s, [0, 1], [30, 0]);
          const o = interpolate(frame, [i * 14, i * 14 + 8], [0, 1], { extrapolateRight: "clamp" });
          const ac = accentMap[c.accent] || c.accent;
          return (
            <div key={i} style={{ flex: 1, opacity: o, transform: `translateY(${y}px)`, padding: "32px 28px", borderRadius: 18, background: light ? "rgba(255,255,255,0.5)" : "rgba(255,255,255,0.04)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", border: "1px solid rgba(255,255,255,0.1)", borderLeft: `4px solid ${ac}`, display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ fontSize: 28, fontWeight: 800, color: textColor }}>{c.title}</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {c.bullets.map((b, j) => <div key={j} style={{ fontSize: 18, color: light ? "#6B7280" : "rgba(255,255,255,0.6)", lineHeight: 1.5 }}>{b}</div>)}
              </div>
              {c.stat ? <div style={{ fontSize: 36, fontWeight: 800, color: ac, marginTop: 4 }}>{c.stat}</div> : null}
              {c.tag ? <div style={{ marginTop: 8, fontSize: 16, fontWeight: 600, color: ac }}>{c.tag}</div> : null}
            </div>
          );
        })}
      </div>
      {bottomLine ? <div style={{ opacity: bottomO, padding: "0 20px", fontSize: 24, fontWeight: 600, color: textColor, textAlign: "center" }}>{bottomLine}</div> : null}
    </div>
  );
};
