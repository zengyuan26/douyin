import { useCurrentFrame, interpolate, spring } from "remotion";
import { ParticleField } from "../components/ParticleField";
import { LIGHT_BG_TEAL } from "../components/Background";
import { WindTurbine, Factory, Grid } from "../components/Icons";

export const Scene6_HowSave: React.FC = () => {
  const frame = useCurrentFrame();
  const titleO = interpolate(frame, [0, 8], [0, 1], { extrapolateRight: "clamp" });
  const leftS = spring({ frame: frame - 8, fps: 30, config: { damping: 8, stiffness: 180 } }), leftY = interpolate(leftS, [0, 1], [30, 0]), leftO = interpolate(frame, [8, 14], [0, 1], { extrapolateRight: "clamp" });
  const rightS = spring({ frame: frame - 22, fps: 30, config: { damping: 8, stiffness: 180 } }), rightY = interpolate(rightS, [0, 1], [30, 0]), rightO = interpolate(frame, [22, 28], [0, 1], { extrapolateRight: "clamp" });
  const pulse = Math.sin(frame * 0.12) * 0.5 + 0.5;
  return (
    <div style={{ width: "100%", height: "100%", background: LIGHT_BG_TEAL, fontFamily: '"Noto Sans SC", -apple-system, sans-serif', display: "flex", flexDirection: "column", justifyContent: "center", padding: "0 100px", gap: 36, position: "relative", overflow: "hidden" }}>
      <ParticleField />
      <div style={{ opacity: titleO, padding: "0 20px" }}><div style={{ fontSize: 15, fontWeight: 600, color: "#C89050", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 12 }}>How It Works</div><h2 style={{ fontSize: 64, fontWeight: 800, color: "#0D0D0D", margin: 0, lineHeight: 1.08 }}>不经过电网混池。<br /><span style={{ color: "#4D8F8F" }}>专线直连，电到证到。</span></h2></div>
      <div style={{ display: "flex", gap: 32, padding: "0 20px" }}>
        <div style={{ flex: 1, opacity: leftO, transform: `translateY(${leftY}px)`, padding: "36px", borderRadius: 20, background: "rgba(255,255,255,0.5)", backdropFilter: "blur(20px)", WebkitBackdropFilter: "blur(20px)", border: "1px solid rgba(255,255,255,0.5)", boxShadow: "0 4px 20px rgba(0,0,0,0.04)" }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: "#9CA3AF", letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 20 }}>买证模式</div><div style={{ fontSize: 32, fontWeight: 800, color: "#0D0D0D", marginBottom: 24 }}>证电分离</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 18px", borderRadius: 10, background: "rgba(0,0,0,0.04)" }}><WindTurbine size={28} color="#6B7280" /><span style={{ fontSize: 20, color: "#6B7280" }}>→</span><Grid size={28} color="#6B7280" /><span style={{ fontSize: 20, color: "#6B7280" }}>→</span><Factory size={28} color="#6B7280" /></div>
            <span style={{ padding: "10px 18px", borderRadius: 10, background: "rgba(220,38,38,0.06)", fontSize: 20, color: "#DC2626", fontWeight: 600 }}>绿证 · 交易所买 ↑</span>
          </div>
        </div>
        <div style={{ flex: 1, opacity: rightO, transform: `translateY(${rightY}px)`, padding: "36px", borderRadius: 20, background: "rgba(77,143,143,0.06)", backdropFilter: "blur(20px)", WebkitBackdropFilter: "blur(20px)", border: "1px solid rgba(77,143,143,0.2)", boxShadow: "0 4px 20px rgba(77,143,143,0.06)" }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: "#4D8F8F", letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 20 }}>直供模式</div><div style={{ fontSize: 32, fontWeight: 800, color: "#0D0D0D", marginBottom: 24 }}>证跟电走</div>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4, padding: "10px 14px", borderRadius: 10, background: "rgba(77,143,143,0.1)" }}><WindTurbine size={32} color="#4D8F8F" /><span style={{ fontSize: 14, color: "#4D8F8F", fontWeight: 600 }}>风电场</span></div>
            <div style={{ flex: 1, height: 2, background: `rgba(77,143,143,${0.3 + pulse * 0.3})`, borderRadius: 1 }} />
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4, padding: "10px 14px", borderRadius: 10, background: "rgba(77,143,143,0.1)" }}><Factory size={32} color="#4D8F8F" /><span style={{ fontSize: 14, color: "#4D8F8F", fontWeight: 600 }}>工厂</span></div>
          </div>
          <div style={{ fontSize: 20, color: "#4D8F8F", fontWeight: 600 }}>电到证到 · 零额外成本</div>
        </div>
      </div>
    </div>
  );
};
