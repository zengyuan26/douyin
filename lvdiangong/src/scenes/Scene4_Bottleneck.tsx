import { useCurrentFrame, interpolate, spring } from "remotion";
import { ParticleField } from "../components/ParticleField";
import { LIGHT_BG_RED } from "../components/Background";
import { WindTurbine, Bolt, Grid } from "../components/Icons";

const layers = [
  { num: "01", title: "资源卡", accent: "#C89050", Icon: WindTurbine },
  { num: "02", title: "通道卡", accent: "#DC2626", Icon: Bolt },
  { num: "03", title: "精度卡", accent: "#6B7280", Icon: Grid },
  { num: "04", title: "地域卡", accent: "#DC2626", Icon: null },
];

const Card: React.FC<{ index: number; data: (typeof layers)[number] }> = ({ index, data }) => {
  const frame = useCurrentFrame();
  const d = index * 14;
  const s = spring({ frame: frame - d, fps: 30, config: { damping: 8, stiffness: 180 } });
  const sc = interpolate(s, [0, 1], [0.7, 1]);
  const o = interpolate(frame, [d, d + 6], [0, 1], { extrapolateRight: "clamp" });
  return (
    <div style={{ opacity: o, transform: `scale(${sc})`, width: "48%", padding: "32px 28px", borderRadius: 16, background: "rgba(255,255,255,0.5)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", border: "1px solid rgba(255,255,255,0.5)", boxShadow: "0 2px 16px rgba(0,0,0,0.03)", display: "flex", alignItems: "center", gap: 20 }}>
      <div style={{ width: 56, height: 56, borderRadius: 14, background: data.accent, color: "#FFF", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22, fontWeight: 800, overflow: "hidden" }}>
        {data.Icon ? <data.Icon size={36} color="#FFF" /> : data.num}
      </div>
      <div style={{ fontSize: 34, fontWeight: 800, color: "#0D0D0D" }}>{data.title}</div>
    </div>
  );
};

export const Scene4_Bottleneck: React.FC = () => {
  const frame = useCurrentFrame();
  const titleO = interpolate(frame, [0, 8], [0, 1], { extrapolateRight: "clamp" });
  const mapO = interpolate(frame, [100, 118], [0, 1], { extrapolateRight: "clamp" });
  return (
    <div style={{ width: "100%", height: "100%", background: LIGHT_BG_RED, fontFamily: '"Noto Sans SC", -apple-system, sans-serif', display: "flex", gap: 60, padding: "70px 100px", position: "relative", overflow: "hidden" }}>
      <ParticleField />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center" }}>
        <div style={{ opacity: titleO, marginBottom: 32 }}>
          <div style={{ fontSize: 15, fontWeight: 600, color: "#C89050", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 12 }}>Bottleneck</div>
          <h2 style={{ fontSize: 64, fontWeight: 800, color: "#0D0D0D", margin: 0, lineHeight: 1.08 }}>四层卡脖子</h2>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 16 }}>{layers.map((l, i) => <Card key={i} index={i} data={l} />)}</div>
      </div>
      <div style={{ flex: 1, opacity: mapO, display: "flex", alignItems: "center", justifyContent: "center", padding: 40, borderRadius: 24, background: "rgba(255,255,255,0.5)", backdropFilter: "blur(20px)", WebkitBackdropFilter: "blur(20px)", border: "1px solid rgba(255,255,255,0.5)", boxShadow: "0 8px 32px rgba(0,0,0,0.04)" }}>
        <svg viewBox="0 0 360 280" style={{ width: 340 }}>
          <path d="M 80 60 Q 160 35, 240 50 Q 300 60, 320 105 Q 335 155, 310 220 Q 280 285, 240 320 Q 200 340, 160 335 Q 120 330, 95 300 Q 60 265, 42 220 Q 22 160, 50 110 Q 60 80, 80 60 Z" fill="rgba(200,144,80,0.04)" stroke="rgba(0,0,0,0.06)" strokeWidth="1" />
          <circle cx="105" cy="105" r="5" fill="#C89050" /><circle cx="105" cy="105" r={15 + Math.sin(frame * 0.15) * 5} fill="none" stroke="rgba(200,144,80,0.2)" strokeWidth="1" />
          <text x="145" y="110" fill="#C89050" fontSize="14" fontWeight="700">风电场</text>
          <circle cx="280" cy="200" r="5" fill="#DC2626" /><circle cx="280" cy="200" r={18 + Math.sin(frame * 0.15 + 1) * 5} fill="none" stroke="rgba(220,38,38,0.2)" strokeWidth="1" />
          <text x="210" y="195" fill="#DC2626" fontSize="14" fontWeight="700">用电大户</text>
          <line x1="110" y1="105" x2="275" y2="198" stroke="rgba(0,0,0,0.08)" strokeWidth="1" strokeDasharray="6,4" />
          <text x="160" y="148" fill="#9CA3AF" fontSize="12">2000—3000 KM</text>
        </svg>
      </div>
    </div>
  );
};
