import { useCurrentFrame, interpolate, spring } from "remotion";
import { DARK_BG } from "../components/Background";
import { ParticleField } from "../components/ParticleField";

const blocks = [
  { label: "源网荷储", sub: "战略地基", bg: "#0D0D0D", color: "#FFFFFF" },
  { label: "微电网", sub: "园内自循环", bg: "#C89050", color: "#FFFFFF" },
  { label: "绿电直供", sub: "园外拉专线", bg: "#C89050", color: "#FFFFFF" },
  { label: "虚拟电厂", sub: "统一调度 · 四份收入", bg: "#C89050", color: "#FFFFFF" },
  { label: "零碳园区", sub: "", bg: "#4D8F8F", color: "#FFFFFF" },
];

const Block: React.FC<{ index: number; data: (typeof blocks)[number] }> = ({ index, data }) => {
  const frame = useCurrentFrame();
  const d = index * 14;
  const s = spring({ frame: frame - d, fps: 30, config: { damping: 8, stiffness: 180 } });
  const sc = interpolate(s, [0, 1], [0.7, 1]);
  const o = interpolate(frame, [d, d + 6], [0, 1], { extrapolateRight: "clamp" });
  const isLayer2 = index === 1 || index === 2;
  const width = index === 0 ? "82%" : isLayer2 ? "40%" : index === 3 ? "54%" : "36%";
  const isLast = index === blocks.length - 1;
  return (
    <div style={{ width, alignSelf: "center", opacity: o, transform: `scale(${sc})`, padding: "16px 24px", borderRadius: 14, background: data.bg, color: data.color, textAlign: "center", fontSize: 24, fontWeight: 800, display: "flex", flexDirection: "column", gap: 4, letterSpacing: "0.02em", boxShadow: isLast ? "0 4px 24px rgba(77,143,143,0.3)" : "none" }}>
      <div>{data.label}</div>
      {data.sub ? <div style={{ fontSize: 15, opacity: 0.65, fontWeight: 500 }}>{data.sub}</div> : null}
    </div>
  );
};

export const Scene8_Puzzle: React.FC = () => {
  const frame = useCurrentFrame();
  const titleO = interpolate(frame, [0, 8], [0, 1], { extrapolateRight: "clamp" });
  const ctaO = interpolate(frame, [100, 116], [0, 1], { extrapolateRight: "clamp" });
  const qO = interpolate(frame, [116, 130], [0, 1], { extrapolateRight: "clamp" });
  return (
    <div style={{ width: "100%", height: "100%", background: DARK_BG, fontFamily: '"Noto Sans SC", -apple-system, sans-serif', display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "50px 180px", gap: 16, position: "relative", overflow: "hidden" }}>
      <ParticleField dark />
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 3, background: "#C89050" }} />
      <div style={{ opacity: titleO, marginBottom: 40 }}><div style={{ fontSize: 15, fontWeight: 600, color: "#C89050", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 12, textAlign: "center" }}>The Big Picture</div><h2 style={{ fontSize: 56, fontWeight: 800, color: "#FFFFFF", margin: 0, textAlign: "center", letterSpacing: "-0.03em" }}>四块拼图 → 零碳园区</h2></div>
      <Block index={0} data={blocks[0]} />
      <div style={{ display: "flex", gap: 16, width: "82%", justifyContent: "center" }}><Block index={1} data={blocks[1]} /><Block index={2} data={blocks[2]} /></div>
      <Block index={3} data={blocks[3]} /><Block index={4} data={blocks[4]} />
      <div style={{ opacity: ctaO, marginTop: 40, fontSize: 32, fontWeight: 800, color: "#C89050" }}>下期拆解：零碳园区</div>
      <div style={{ opacity: qO, marginTop: 4, padding: "12px 28px", borderRadius: 20, background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.08)", fontSize: 22, fontWeight: 600, color: "rgba(255,255,255,0.5)" }}>你现在在哪个阶段？评论区聊聊</div>
    </div>
  );
};
