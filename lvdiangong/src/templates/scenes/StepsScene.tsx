import { useCurrentFrame, interpolate, spring } from "remotion";
import { ParticleField } from "../../components/ParticleField";
import { bgMap, isLightBg } from "./shared";
import type { StepsPage } from "../types";

export const StepsScene: React.FC<StepsPage> = ({ label, title, steps, bottomLine, background, flowLabels }) => {
  const frame = useCurrentFrame();
  const bg = bgMap(background);
  const light = isLightBg(background);
  const textColor = light ? "#0D0D0D" : "#FFFFFF";
  const dimColor = light ? "rgba(0,0,0,0.4)" : "rgba(255,255,255,0.5)";
  const titleO = interpolate(frame, [0, 8], [0, 1], { extrapolateRight: "clamp" });
  const bottomO = interpolate(frame, [80, 96], [0, 1], { extrapolateRight: "clamp" });

  return (
    <div style={{ width: "100%", height: "100%", background: bg, fontFamily: '"Noto Sans SC", -apple-system, sans-serif', display: "flex", flexDirection: "column", justifyContent: "center", padding: "0 100px", gap: 28, position: "relative", overflow: "hidden" }}>
      <ParticleField dark={!light} />
      <div style={{ opacity: titleO, padding: "0 20px" }}>
        {label ? <div style={{ fontSize: 15, fontWeight: 600, color: "#C89050", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 12 }}>{label}</div> : null}
        <h2 style={{ fontSize: 52, fontWeight: 800, color: textColor, margin: 0, lineHeight: 1.12 }}>{title}</h2>
      </div>
      {flowLabels ? (
        <div style={{ display: "flex", alignItems: "center", gap: 0, padding: "0 20px", opacity: interpolate(frame, [8, 16], [0, 1], { extrapolateRight: "clamp" }) }}>
          {flowLabels.map((fl, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center" }}>
              <div style={{ padding: "8px 18px", borderRadius: 10, background: light ? "rgba(0,0,0,0.04)" : "rgba(255,255,255,0.06)", fontSize: 16, fontWeight: 600, color: textColor }}>{fl}</div>
              {i < flowLabels.length - 1 ? <div style={{ margin: "0 8px", fontSize: 18, color: dimColor }}>→</div> : null}
            </div>
          ))}
        </div>
      ) : null}
      <div style={{ display: "flex", flexDirection: "column", gap: 14, padding: "0 20px" }}>
        {steps.map((step, i) => {
          const s = spring({ frame: frame - 10 - i * 12, fps: 30, config: { damping: 8, stiffness: 180 } });
          const y = interpolate(s, [0, 1], [20, 0]);
          const o = interpolate(frame, [i * 12, i * 12 + 8], [0, 1], { extrapolateRight: "clamp" });
          return (
            <div key={i} style={{ opacity: o, transform: `translateY(${y}px)`, padding: "20px 24px", borderRadius: 14, background: light ? "rgba(255,255,255,0.5)" : "rgba(255,255,255,0.04)", backdropFilter: "blur(12px)", WebkitBackdropFilter: "blur(12px)", border: light ? "1px solid rgba(0,0,0,0.06)" : "1px solid rgba(255,255,255,0.08)", display: "flex", alignItems: "center", gap: 20 }}>
              <div style={{ fontSize: 22, fontWeight: 700, color: step.accent || "#C89050", minWidth: 36 }}>{step.num}</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 24, fontWeight: 700, color: textColor }}>{step.title}</div>
                <div style={{ fontSize: 18, color: dimColor, marginTop: 2 }}>{step.body}</div>
                {step.substeps ? (
                  <div style={{ display: "flex", gap: 16, marginTop: 8 }}>
                    {step.substeps.map((ss, j) => (
                      <div key={j} style={{ flex: 1, padding: "10px 14px", borderRadius: 8, background: light ? "rgba(0,0,0,0.03)" : "rgba(255,255,255,0.04)", fontSize: 15, color: dimColor }}>
                        <strong style={{ color: textColor }}>{ss.left}</strong> — {ss.right}
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
              {step.tag ? <div style={{ fontSize: 14, fontWeight: 600, color: step.accent || "#C89050", whiteSpace: "nowrap" }}>{step.tag}</div> : null}
            </div>
          );
        })}
      </div>
      {bottomLine ? <div style={{ opacity: bottomO, padding: "0 20px", fontSize: 22, fontWeight: 600, color: textColor, textAlign: "center" }}>{bottomLine}</div> : null}
    </div>
  );
};
