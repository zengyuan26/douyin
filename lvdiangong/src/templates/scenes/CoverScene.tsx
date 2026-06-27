import { useCurrentFrame, interpolate, spring } from "remotion";
import { FloatingElements } from "../../components/Background";
import { ParticleField } from "../../components/ParticleField";
import type { CoverPage } from "../types";
import { bgMap } from "./shared";

export const CoverScene: React.FC<CoverPage> = ({ label, title, subtitle, tags, background }) => {
  const frame = useCurrentFrame();
  const barW = interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp" });
  const cardS = spring({ frame: frame - 8, fps: 30, config: { damping: 8, stiffness: 180 } });
  const cardY = interpolate(cardS, [0, 1], [60, 0]);
  const cardO = interpolate(frame, [8, 18], [0, 1], { extrapolateRight: "clamp" });
  const isDark = background === "dark";
  const bg = bgMap(background);

  return (
    <div style={{ width: "100%", height: "100%", background: bg, fontFamily: '"Noto Sans SC", -apple-system, sans-serif', display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", padding: "0 100px", position: "relative", overflow: "hidden" }}>
      {isDark && <FloatingElements dark />}
      <ParticleField dark={isDark} />
      <div style={{ position: "absolute", top: 0, left: 0, width: `${barW * 120}px`, height: 3, background: "#C89050" }} />
      <div style={{ opacity: cardO, transform: `translateY(${cardY}px)`, padding: "80px 100px", borderRadius: 24, background: isDark ? "rgba(255,255,255,0.04)" : "rgba(255,255,255,0.5)", backdropFilter: "blur(30px)", WebkitBackdropFilter: "blur(30px)", border: isDark ? "1px solid rgba(255,255,255,0.08)" : "1px solid rgba(255,255,255,0.5)", boxShadow: isDark ? "0 8px 40px rgba(0,0,0,0.3)" : "0 4px 20px rgba(0,0,0,0.06)", display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", gap: 32 }}>
        {label ? <div style={{ fontSize: 18, fontWeight: 600, color: "#C89050", letterSpacing: "0.1em", textTransform: "uppercase" }}>{label}</div> : null}
        <h1 style={{ fontSize: 160, fontWeight: 800, color: isDark ? "#FFFFFF" : "#0D0D0D", margin: 0, lineHeight: 1, letterSpacing: "-0.03em" }}>{title}</h1>
        {subtitle ? <div style={{ fontSize: 28, fontWeight: 400, color: isDark ? "rgba(255,255,255,0.5)" : "rgba(0,0,0,0.4)", marginTop: -8 }}>{subtitle}</div> : null}
        {tags ? <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>{tags.map((t, i) => <div key={i} style={{ padding: "10px 24px", borderRadius: 20, background: isDark ? "rgba(200,144,80,0.1)" : "rgba(200,144,80,0.08)", color: "#C89050", fontSize: 20, fontWeight: 600 }}>{t}</div>)}</div> : null}
      </div>
    </div>
  );
};
