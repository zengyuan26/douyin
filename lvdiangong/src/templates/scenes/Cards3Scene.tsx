import { useCurrentFrame, interpolate, spring } from "remotion";
import { ParticleField } from "../../components/ParticleField";
import { bgMap, isLightBg } from "./shared";
import type { Cards3Page, Card3Item } from "../types";

const Card: React.FC<{ index: number; data: Card3Item; light: boolean; textColor: string }> = ({ index, data, light, textColor }) => {
  const frame = useCurrentFrame();
  const d = index * 16;
  const s = spring({ frame: frame - d, fps: 30, config: { damping: 8, stiffness: 180 } });
  const y = interpolate(s, [0, 1], [40, 0]);
  const o = interpolate(frame, [d, d + 8], [0, 1], { extrapolateRight: "clamp" });
  const isHighlighted = data.highlighted;
  return (
    <div style={{ opacity: data.dim ? o * 0.35 : o, transform: `translateY(${y}px)`, flex: 1, padding: "36px 28px", borderRadius: 18, background: isHighlighted ? "rgba(200,144,80,0.08)" : light ? "rgba(255,255,255,0.5)" : "rgba(255,255,255,0.04)", backdropFilter: "blur(20px)", WebkitBackdropFilter: "blur(20px)", border: isHighlighted ? "1px solid rgba(200,144,80,0.25)" : light ? "1px solid rgba(255,255,255,0.5)" : "1px solid rgba(255,255,255,0.08)", boxShadow: isHighlighted ? "0 4px 24px rgba(200,144,80,0.08)" : "0 2px 12px rgba(0,0,0,0.03)", display: "flex", flexDirection: "column", justifyContent: "space-between", gap: 16 }}>
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, color: data.accent, letterSpacing: "0.06em" }}>{data.label}</div>
        <div style={{ fontSize: 32, fontWeight: 800, color: textColor, marginTop: 8 }}>{data.title}</div>
      </div>
      <div>
        <div style={{ fontSize: 52, fontWeight: 800, color: data.accent, lineHeight: 1 }}>{data.stat}</div>
        <div style={{ marginTop: 8, fontSize: 18, color: data.accent }}>{data.tag}</div>
      </div>
    </div>
  );
};

export const Cards3Scene: React.FC<Cards3Page> = ({ label, title, titleAccent, cards, background }) => {
  const frame = useCurrentFrame();
  const bg = bgMap(background);
  const light = isLightBg(background);
  const textColor = light ? "#0D0D0D" : "#FFFFFF";
  const titleO = interpolate(frame, [0, 8], [0, 1], { extrapolateRight: "clamp" });

  return (
    <div style={{ width: "100%", height: "100%", background: bg, fontFamily: '"Noto Sans SC", -apple-system, sans-serif', display: "flex", flexDirection: "column", justifyContent: "center", padding: "0 100px", gap: 36, position: "relative", overflow: "hidden" }}>
      <ParticleField dark={!light} />
      <div style={{ opacity: titleO, padding: "0 20px" }}>
        {label ? <div style={{ fontSize: 15, fontWeight: 600, color: "#C89050", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 12 }}>{label}</div> : null}
        <h2 style={{ fontSize: 56, fontWeight: 800, color: textColor, margin: 0, lineHeight: 1.12 }}>
          {title}{titleAccent ? <><br /><span style={{ color: "#C89050" }}>{titleAccent}</span></> : null}
        </h2>
      </div>
      <div style={{ display: "flex", gap: 24, padding: "0 20px" }}>{cards.map((c, i) => <Card key={i} index={i} data={c} light={light} textColor={textColor} />)}</div>
    </div>
  );
};
