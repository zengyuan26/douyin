import { useCurrentFrame, interpolate, spring } from "remotion";
import { ParticleField } from "../../components/ParticleField";
import { WindTurbine, Bolt, Grid, Certificate, Factory, ArrowExchange } from "../../components/Icons";
import { bgMap, isLightBg } from "./shared";
import type { Cards4Page, Card4Item } from "../types";

const iconMap: Record<string, React.FC<{ size?: number; color?: string }>> = {
  wind: WindTurbine, bolt: Bolt, grid: Grid, certificate: Certificate, factory: Factory, exchange: ArrowExchange,
};

const Card: React.FC<{ index: number; data: Card4Item; light: boolean; textColor: string }> = ({ index, data, light, textColor }) => {
  const frame = useCurrentFrame();
  const d = 8 + index * 12;
  const s = spring({ frame: frame - d, fps: 30, config: { damping: 8, stiffness: 180 } });
  const sc = interpolate(s, [0, 1], [0.8, 1]);
  const o = interpolate(frame, [d, d + 8], [0, 1], { extrapolateRight: "clamp" });
  const Icon = data.icon ? iconMap[data.icon] : null;
  return (
    <div style={{ opacity: o, transform: `scale(${sc})`, flex: "1 1 44%", padding: "28px 24px", borderRadius: 16, background: light ? "rgba(255,255,255,0.5)" : "rgba(255,255,255,0.04)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", border: light ? "1px solid rgba(255,255,255,0.5)" : "1px solid rgba(255,255,255,0.08)", display: "flex", flexDirection: "column", gap: 12, alignItems: "flex-start" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, width: "100%" }}>
        {Icon ? <Icon size={36} color={data.accent} /> : null}
        <div style={{ fontSize: 22, fontWeight: 600, color: "rgba(0,0,0,0.2)", letterSpacing: "0.06em" }}>{data.num}</div>
      </div>
      <div style={{ fontSize: 28, fontWeight: 800, color: textColor }}>{data.title}</div>
      {data.sub ? <div style={{ fontSize: 18, color: light ? "#6B7280" : "rgba(255,255,255,0.5)" }}>{data.sub}</div> : null}
      <div style={{ marginTop: 4, height: 3, width: 40, background: data.accent, borderRadius: 2 }} />
    </div>
  );
};

export const Cards4Scene: React.FC<Cards4Page> = ({ label, title, cards, background }) => {
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
        <h2 style={{ fontSize: 56, fontWeight: 800, color: textColor, margin: 0, lineHeight: 1.12 }}>{title}</h2>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 20, padding: "0 20px" }}>{cards.map((c, i) => <Card key={i} index={i} data={c} light={light} textColor={textColor} />)}</div>
    </div>
  );
};
