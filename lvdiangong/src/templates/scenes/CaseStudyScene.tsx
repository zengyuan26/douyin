import { useCurrentFrame, interpolate, spring } from "remotion";
import { ParticleField } from "../../components/ParticleField";
import { bgMap, isLightBg } from "./shared";
import type { CaseStudyPage } from "../types";

export const CaseStudyScene: React.FC<CaseStudyPage> = ({ title, before, after, investment, annualSavings, payback, bottomLine, background }) => {
  const frame = useCurrentFrame();
  const bg = bgMap(background);
  const light = isLightBg(background);
  const textColor = light ? "#0D0D0D" : "#FFFFFF";
  const dimColor = light ? "rgba(0,0,0,0.5)" : "rgba(255,255,255,0.5)";
  const titleO = interpolate(frame, [0, 8], [0, 1], { extrapolateRight: "clamp" });
  const leftS = spring({ frame: frame - 8, fps: 30, config: { damping: 8, stiffness: 180 } });
  const rightS = spring({ frame: frame - 24, fps: 30, config: { damping: 8, stiffness: 180 } });
  const bottomO = interpolate(frame, [70, 86], [0, 1], { extrapolateRight: "clamp" });

  return (
    <div style={{ width: "100%", height: "100%", background: bg, fontFamily: '"Noto Sans SC", -apple-system, sans-serif', display: "flex", flexDirection: "column", justifyContent: "center", padding: "0 100px", gap: 28, position: "relative", overflow: "hidden" }}>
      <ParticleField dark={!light} />
      <div style={{ opacity: titleO, padding: "0 20px" }}>
        <h2 style={{ fontSize: 46, fontWeight: 800, color: textColor, margin: 0, lineHeight: 1.15 }}>{title}</h2>
      </div>
      <div style={{ display: "flex", gap: 32, padding: "0 20px" }}>
        <div style={{ flex: 1, opacity: interpolate(leftS, [0, 1], [0, 1]), transform: `translateY(${interpolate(leftS, [0, 1], [30, 0])}px)`, padding: "32px 28px", borderRadius: 18, background: light ? "rgba(0,0,0,0.03)" : "rgba(255,255,255,0.03)", border: `1px solid ${light ? "rgba(0,0,0,0.08)" : "rgba(255,255,255,0.06)"}`, borderLeft: "4px solid #6B7280" }}>
          <div style={{ fontSize: 16, fontWeight: 600, color: "#9CA3AF", letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 16 }}>{before.label}</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {before.items.map((item, i) => <div key={i} style={{ fontSize: 18, color: dimColor, lineHeight: 1.5 }}>{item}</div>)}
          </div>
        </div>
        <div style={{ flex: 1, opacity: interpolate(rightS, [0, 1], [0, 1]), transform: `translateY(${interpolate(rightS, [0, 1], [30, 0])}px)`, padding: "32px 28px", borderRadius: 18, background: "rgba(200,144,80,0.06)", border: "1px solid rgba(200,144,80,0.15)", borderLeft: "4px solid #C89050" }}>
          <div style={{ fontSize: 16, fontWeight: 600, color: "#C89050", letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 16 }}>{after.label}</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {after.items.map((item, i) => <div key={i} style={{ fontSize: 18, color: dimColor, lineHeight: 1.5 }}>{item}</div>)}
          </div>
          <div style={{ marginTop: 20, display: "flex", gap: 20 }}>
            <div><div style={{ fontSize: 13, color: dimColor }}>投入</div><div style={{ fontSize: 26, fontWeight: 800, color: textColor }}>{investment}</div></div>
            <div><div style={{ fontSize: 13, color: dimColor }}>年省</div><div style={{ fontSize: 26, fontWeight: 800, color: "#C89050" }}>{annualSavings}</div></div>
            <div><div style={{ fontSize: 13, color: dimColor }}>回本</div><div style={{ fontSize: 26, fontWeight: 800, color: textColor }}>{payback}</div></div>
          </div>
        </div>
      </div>
      {bottomLine ? <div style={{ opacity: bottomO, padding: "0 20px", fontSize: 24, fontWeight: 700, color: textColor, textAlign: "center" }}>{bottomLine}</div> : null}
    </div>
  );
};
