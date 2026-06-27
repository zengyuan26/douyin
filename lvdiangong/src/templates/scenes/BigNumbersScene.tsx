import { useCurrentFrame, interpolate, spring } from "remotion";
import { ParticleField } from "../../components/ParticleField";
import { bgMap, isLightBg } from "./shared";
import type { BigNumbersPage } from "../types";

export const BigNumbersScene: React.FC<BigNumbersPage> = ({ left, right, bottomLine, background }) => {
  const frame = useCurrentFrame();
  const bg = bgMap(background);
  const light = isLightBg(background);
  const textColor = light ? "#0D0D0D" : "#FFFFFF";
  const dimColor = light ? "rgba(0,0,0,0.4)" : "rgba(255,255,255,0.5)";

  const leftS = spring({ frame: frame - 8, fps: 30, config: { damping: 8, stiffness: 180 } });
  const rightS = spring({ frame: frame - 24, fps: 30, config: { damping: 8, stiffness: 180 } });
  const bottomO = interpolate(frame, [50, 66], [0, 1], { extrapolateRight: "clamp" });

  return (
    <div style={{ width: "100%", height: "100%", background: bg, fontFamily: '"Noto Sans SC", -apple-system, sans-serif', display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", padding: "60px 120px", gap: 48, position: "relative", overflow: "hidden" }}>
      <ParticleField dark={!light} />
      <div style={{ display: "flex", gap: 48, width: "100%", justifyContent: "center" }}>
        <div style={{ flex: 1, opacity: interpolate(leftS, [0, 1], [0, 1]), transform: `translateY(${interpolate(leftS, [0, 1], [40, 0])}px)`, padding: "64px 48px", borderRadius: 24, background: light ? "rgba(0,0,0,0.03)" : "rgba(255,255,255,0.04)", backdropFilter: "blur(20px)", WebkitBackdropFilter: "blur(20px)", border: light ? "1px solid rgba(0,0,0,0.06)" : "1px solid rgba(255,255,255,0.06)", textAlign: "center", display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ fontSize: 16, fontWeight: 600, color: dimColor, letterSpacing: "0.08em", textTransform: "uppercase" }}>{left.label}</div>
          <div style={{ fontSize: 88, fontWeight: 800, color: textColor, lineHeight: 1 }}>{left.value}</div>
          <div style={{ fontSize: 22, color: dimColor }}>{left.detail}</div>
        </div>
        <div style={{ flex: 1, opacity: interpolate(rightS, [0, 1], [0, 1]), transform: `translateY(${interpolate(rightS, [0, 1], [40, 0])}px)`, padding: "64px 48px", borderRadius: 24, background: "rgba(200,144,80,0.08)", backdropFilter: "blur(20px)", WebkitBackdropFilter: "blur(20px)", border: "1px solid rgba(200,144,80,0.2)", textAlign: "center", display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ fontSize: 16, fontWeight: 600, color: "#C89050", letterSpacing: "0.08em", textTransform: "uppercase" }}>{right.label}</div>
          <div style={{ fontSize: 88, fontWeight: 800, color: "#C89050", lineHeight: 1 }}>{right.value}</div>
          <div style={{ fontSize: 22, color: dimColor }}>{right.detail}</div>
        </div>
      </div>
      {bottomLine ? <div style={{ opacity: bottomO, fontSize: 28, fontWeight: 600, color: textColor }}>{bottomLine}</div> : null}
    </div>
  );
};
