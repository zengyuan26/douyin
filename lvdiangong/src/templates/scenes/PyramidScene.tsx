import { useCurrentFrame, interpolate, spring } from "remotion";
import { DARK_BG } from "../../components/Background";
import { ParticleField } from "../../components/ParticleField";
import type { PyramidPage, PyramidBlock } from "../types";

const Block: React.FC<{ index: number; data: PyramidBlock; width: string; isLast: boolean }> = ({ index, data, width, isLast }) => {
  const frame = useCurrentFrame();
  const d = index * 14;
  const s = spring({ frame: frame - d, fps: 30, config: { damping: 8, stiffness: 180 } });
  const sc = interpolate(s, [0, 1], [0.7, 1]);
  const o = interpolate(frame, [d, d + 6], [0, 1], { extrapolateRight: "clamp" });
  return (
    <div style={{ width, alignSelf: "center", opacity: o, transform: `scale(${sc})`, padding: "16px 24px", borderRadius: 14, background: data.bg, color: data.color, textAlign: "center", fontSize: 24, fontWeight: 800, display: "flex", flexDirection: "column", gap: 4, letterSpacing: "0.02em", boxShadow: isLast ? "0 4px 24px rgba(77,143,143,0.3)" : "none" }}>
      <div>{data.label}</div>
      {data.sub ? <div style={{ fontSize: 15, opacity: 0.65, fontWeight: 500 }}>{data.sub}</div> : null}
    </div>
  );
};

export const PyramidScene: React.FC<PyramidPage> = ({ label, title, blocks, cta, question }) => {
  const frame = useCurrentFrame();
  const titleO = interpolate(frame, [0, 8], [0, 1], { extrapolateRight: "clamp" });
  const ctaO = interpolate(frame, [100, 116], [0, 1], { extrapolateRight: "clamp" });

  return (
    <div style={{ width: "100%", height: "100%", background: DARK_BG, fontFamily: '"Noto Sans SC", -apple-system, sans-serif', display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "50px 180px", gap: 16, position: "relative", overflow: "hidden" }}>
      <ParticleField dark />
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 3, background: "#C89050" }} />
      <div style={{ opacity: titleO, marginBottom: 32 }}>
        {label ? <div style={{ fontSize: 15, fontWeight: 600, color: "#C89050", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 12, textAlign: "center" }}>{label}</div> : null}
        <h2 style={{ fontSize: 52, fontWeight: 800, color: "#FFFFFF", margin: 0, textAlign: "center", letterSpacing: "-0.03em" }}>{title}</h2>
      </div>
      {blocks.length >= 1 ? <Block index={0} data={blocks[0]} width="82%" isLast={false} /> : null}
      {blocks.length >= 3 ? <div style={{ display: "flex", gap: 16, width: "82%", justifyContent: "center" }}><Block index={1} data={blocks[1]} width="40%" isLast={false} /><Block index={2} data={blocks[2]} width="40%" isLast={false} /></div> : null}
      {blocks.slice(3, -1).map((b, i) => <Block key={i + 3} index={i + 3} data={b} width="54%" isLast={false} />)}
      {blocks.length >= 1 ? <Block index={blocks.length - 1} data={blocks[blocks.length - 1]} width="36%" isLast={true} /> : null}
      {cta ? <div style={{ opacity: ctaO, marginTop: 36, fontSize: 30, fontWeight: 800, color: "#C89050" }}>{cta}</div> : null}
      {question ? <div style={{ opacity: interpolate(frame, [116, 130], [0, 1], { extrapolateRight: "clamp" }), marginTop: 8, padding: "12px 28px", borderRadius: 20, background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.08)", fontSize: 22, fontWeight: 600, color: "rgba(255,255,255,0.5)" }}>{question}</div> : null}
    </div>
  );
};
