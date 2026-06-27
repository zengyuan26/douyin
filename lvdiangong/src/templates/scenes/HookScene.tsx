import { useCurrentFrame, interpolate } from "remotion";
import { ParticleField } from "../../components/ParticleField";
import { bgMap, isLightBg } from "./shared";
import type { HookPage } from "../types";

export const HookScene: React.FC<HookPage> = ({ lines, reveal, background }) => {
  const frame = useCurrentFrame();
  const bg = bgMap(background);
  const light = isLightBg(background);
  const textColor = light ? "#0D0D0D" : "#FFFFFF";
  const dimColor = light ? "rgba(0,0,0,0.5)" : "rgba(255,255,255,0.5)";

  return (
    <div style={{ width: "100%", height: "100%", background: bg, fontFamily: '"Noto Sans SC", -apple-system, sans-serif', display: "flex", flexDirection: "column", justifyContent: "center", padding: "0 120px", gap: 16, position: "relative", overflow: "hidden" }}>
      <ParticleField dark={!light} />
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 3, background: "#C89050" }} />
      {lines.map((line, i) => {
        const o = interpolate(frame, [i * 15, i * 15 + 10], [0, 1], { extrapolateRight: "clamp" });
        const isShort = line.length <= 12;
        const isReveal = line === reveal;
        return (
          <div key={i} style={{ opacity: o, fontSize: isReveal ? 72 : isShort ? 32 : 40, fontWeight: isReveal ? 800 : isShort ? 600 : 400, color: isReveal ? "#C89050" : textColor, lineHeight: 1.3, letterSpacing: isShort ? "0.02em" : "0" }}>
            {line}
          </div>
        );
      })}
    </div>
  );
};
