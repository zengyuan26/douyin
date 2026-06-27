import { useCurrentFrame, interpolate, spring } from "remotion";
import { ParticleField } from "../components/ParticleField";
import { LIGHT_BG_AMBER } from "../components/Background";

const paths = [
  { label: "PATH A", title: "绿电交易", stat: "140 万/年", tag: "越买越贵", accent: "#6B7280", dim: false },
  { label: "PATH B", title: "普通绿证", stat: "几毛钱", tag: "海关不认", accent: "#9CA3AF", dim: true },
  { label: "PATH C", title: "绿电直供", stat: "免费", tag: "第三条路 →", accent: "#C89050", accent2: true },
];

const Card: React.FC<{ index: number; data: (typeof paths)[number] }> = ({ index, data }) => {
  const frame = useCurrentFrame();
  const d = index * 16;
  const s = spring({ frame: frame - d, fps: 30, config: { damping: 8, stiffness: 180 } });
  const y = interpolate(s, [0, 1], [40, 0]);
  const o = interpolate(frame, [d, d + 8], [0, 1], { extrapolateRight: "clamp" });
  return (
    <div style={{ opacity: data.dim ? o * 0.35 : o, transform: `translateY(${y}px)`, flex: 1, padding: "36px 28px", borderRadius: 18, background: data.accent2 ? "rgba(200,144,80,0.08)" : "rgba(255,255,255,0.5)", backdropFilter: "blur(20px)", WebkitBackdropFilter: "blur(20px)", border: data.accent2 ? "1px solid rgba(200,144,80,0.25)" : "1px solid rgba(255,255,255,0.5)", boxShadow: data.accent2 ? "0 4px 24px rgba(200,144,80,0.08)" : "0 2px 12px rgba(0,0,0,0.03)", display: "flex", flexDirection: "column", justifyContent: "space-between", gap: 16 }}>
      <div><div style={{ fontSize: 13, fontWeight: 600, color: data.accent, letterSpacing: "0.06em" }}>{data.label}</div>
        <div style={{ fontSize: 32, fontWeight: 800, color: "#0D0D0D", marginTop: 8 }}>{data.title}</div></div>
      <div><div style={{ fontSize: 52, fontWeight: 800, color: data.accent, lineHeight: 1 }}>{data.stat}</div>
        <div style={{ marginTop: 8, fontSize: 18, color: data.accent }}>{data.tag}</div></div>
    </div>
  );
};

export const Scene5_ThreePaths: React.FC = () => {
  const frame = useCurrentFrame();
  const titleO = interpolate(frame, [0, 8], [0, 1], { extrapolateRight: "clamp" });
  return (
    <div style={{ width: "100%", height: "100%", background: LIGHT_BG_AMBER, fontFamily: '"Noto Sans SC", -apple-system, sans-serif', display: "flex", flexDirection: "column", justifyContent: "center", padding: "0 100px", gap: 36, position: "relative", overflow: "hidden" }}>
      <ParticleField />
      <div style={{ opacity: titleO, padding: "0 20px" }}>
        <div style={{ fontSize: 15, fontWeight: 600, color: "#C89050", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 12 }}>The Decision</div>
        <h2 style={{ fontSize: 64, fontWeight: 800, color: "#0D0D0D", margin: 0, lineHeight: 1.08, letterSpacing: "-0.03em" }}>继续买，每年多花几十万。<br /><span style={{ color: "#C89050" }}>第三条路：建直供，一次投入。</span></h2>
      </div>
      <div style={{ display: "flex", gap: 24, padding: "0 20px" }}>{paths.map((p, i) => <Card key={i} index={i} data={p} />)}</div>
    </div>
  );
};
