import { useCurrentFrame, interpolate } from "remotion";
import { ParticleField } from "../../components/ParticleField";
import { bgMap, isLightBg } from "./shared";
import type { ClosingPage } from "../types";

export const ClosingScene: React.FC<ClosingPage> = ({ title, lines, seriesLine, background }) => {
  const frame = useCurrentFrame();
  const bg = bgMap(background);
  const light = isLightBg(background);
  const textColor = light ? "#0D0D0D" : "#FFFFFF";
  const dimColor = light ? "rgba(0,0,0,0.4)" : "rgba(255,255,255,0.4)";
  const titleO = interpolate(frame, [0, 8], [0, 1], { extrapolateRight: "clamp" });

  return (
    <div style={{ width: "100%", height: "100%", background: bg, fontFamily: '"Noto Sans SC", -apple-system, sans-serif', display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", padding: "0 120px", gap: 12, position: "relative", overflow: "hidden" }}>
      <ParticleField dark={!light} />
      <div style={{ opacity: titleO, marginBottom: 24 }}>
        <h2 style={{ fontSize: 44, fontWeight: 800, color: textColor, margin: 0, textAlign: "center", lineHeight: 1.3 }}>{title}</h2>
      </div>
      {lines.map((line, i) => {
        const o = interpolate(frame, [10 + i * 18, 20 + i * 18], [0, 1], { extrapolateRight: "clamp" });
        return (
          <div key={i} style={{ opacity: o, fontSize: 30, fontWeight: 600, color: "#C89050", textAlign: "center" }}>{line}</div>
        );
      })}
      {seriesLine ? <div style={{ opacity: interpolate(frame, [90, 106], [0, 1], { extrapolateRight: "clamp" }), marginTop: 28, fontSize: 18, color: dimColor, textAlign: "center" }}>{seriesLine}</div> : null}
    </div>
  );
};
