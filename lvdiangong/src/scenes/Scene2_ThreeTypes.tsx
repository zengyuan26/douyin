import { useCurrentFrame, interpolate, spring } from "remotion";
import { LIGHT_BG_AMBER } from "../components/Background";
import { ParticleField } from "../components/ParticleField";

const certs = [
  { label: "MUST BUY", title: "普通绿证", stat: "几毛钱", tag: "国内考核用", accent: "rgba(156,163,175,0.6)" },
  { label: "MUST BUY · RISING", title: "绿电交易绿证", stat: "3→7 块", tag: "越买越贵", accent: "#C89050" },
  { label: "NO COST", title: "直供绿证", stat: "免费", tag: "电到证到", accent: "#4D8F8F" },
];

const Card: React.FC<{ index: number; data: (typeof certs)[number] }> = ({ index, data }) => {
  const frame = useCurrentFrame();
  const d = index * 16;
  const s = spring({ frame: frame - d, fps: 30, config: { damping: 8, stiffness: 180 } });
  const y = interpolate(s, [0, 1], [60, 0]);
  const o = interpolate(frame, [d, d + 10], [0, 1], { extrapolateRight: "clamp" });
  const barFill = interpolate(frame, [d + 12, d + 32], [0, 1], { extrapolateRight: "clamp", extrapolateLeft: "clamp" });
  return (
    <div style={{ opacity: o, transform: `translateY(${y}px)`, flex: 1, padding: "40px 32px", borderRadius: 20, background: "rgba(255,255,255,0.5)", backdropFilter: "blur(20px)", WebkitBackdropFilter: "blur(20px)", border: "1px solid rgba(255,255,255,0.5)", boxShadow: "0 4px 20px rgba(0,0,0,0.04)", display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ fontSize: 13, fontWeight: 600, letterSpacing: "0.08em", color: data.accent }}>{data.label}</div>
      <div style={{ fontSize: 36, fontWeight: 800, color: "#0D0D0D" }}>{data.title}</div>
      <div><div style={{ fontSize: 64, fontWeight: 800, color: data.accent, lineHeight: 1 }}>{data.stat}</div>
        <div style={{ marginTop: 12, fontSize: 18, color: "#6B7280" }}>{data.tag}</div></div>
      <div style={{ height: 3, borderRadius: 2, background: "rgba(0,0,0,0.06)", overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${barFill * 100}%`, background: data.accent, borderRadius: 2 }} /></div>
    </div>
  );
};

export const Scene2_ThreeTypes: React.FC = () => {
  const frame = useCurrentFrame();
  const titleO = interpolate(frame, [0, 8], [0, 1], { extrapolateRight: "clamp" });
  return (
    <div style={{ width: "100%", height: "100%", background: LIGHT_BG_AMBER, fontFamily: '"Noto Sans SC", -apple-system, sans-serif', display: "flex", flexDirection: "column", justifyContent: "center", padding: "0 100px", gap: 36, position: "relative", overflow: "hidden" }}>
      <ParticleField />
      <div style={{ opacity: titleO, padding: "0 20px" }}>
        <div style={{ fontSize: 15, fontWeight: 600, color: "#C89050", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 12 }}>Three Types</div>
        <h2 style={{ fontSize: 64, fontWeight: 800, color: "#0D0D0D", margin: 0, lineHeight: 1.08, letterSpacing: "-0.03em" }}>三种绿证。<br/><span style={{ color: "#4D8F8F" }}>第三种，不用花钱。</span></h2>
      </div>
      <div style={{ display: "flex", gap: 24, padding: "0 20px" }}>{certs.map((c, i) => <Card key={i} index={i} data={c} />)}</div>
    </div>
  );
};
