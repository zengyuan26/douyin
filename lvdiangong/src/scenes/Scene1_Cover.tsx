import { useCurrentFrame, interpolate, spring } from "remotion";
import { DARK_BG, FloatingElements } from "../components/Background";
import { ParticleField } from "../components/ParticleField";

export const Scene1_Cover: React.FC = () => {
  const frame = useCurrentFrame();
  const barW = interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp" });
  const cardS = spring({ frame: frame - 8, fps: 30, config: { damping: 8, stiffness: 180 } });
  const cardY = interpolate(cardS, [0, 1], [60, 0]);
  const cardO = interpolate(frame, [8, 18], [0, 1], { extrapolateRight: "clamp" });

  return (
    <div style={{
      width: "100%", height: "100%", background: DARK_BG,
      fontFamily: '"Noto Sans SC", -apple-system, sans-serif',
      display: "flex", flexDirection: "column", justifyContent: "center",
      alignItems: "center", padding: "0 100px",
      position: "relative", overflow: "hidden",
    }}>
      <FloatingElements dark />
      <ParticleField dark />
      {/* Top amber bar */}
      <div style={{
        position: "absolute", top: 0, left: 0, width: `${barW * 120}px`, height: 3, background: "#C89050",
      }} />

      {/* Glass card */}
      <div style={{
        opacity: cardO, transform: `translateY(${cardY}px)`,
        padding: "80px 100px", borderRadius: 24,
        background: "rgba(255,255,255,0.04)",
        backdropFilter: "blur(30px)", WebkitBackdropFilter: "blur(30px)",
        border: "1px solid rgba(255,255,255,0.08)",
        boxShadow: "0 8px 40px rgba(0,0,0,0.3)",
        display: "flex", flexDirection: "column",
        alignItems: "center", textAlign: "center", gap: 32,
      }}>
        <div style={{ fontSize: 18, fontWeight: 600, color: "#C89050", letterSpacing: "0.1em", textTransform: "uppercase" }}>
          Concept Map · Vol. 4
        </div>
        <h1 style={{
          fontSize: 160, fontWeight: 800, color: "#FFFFFF",
          margin: 0, lineHeight: 1, letterSpacing: "-0.03em",
          background: "linear-gradient(180deg, #FFFFFF 0%, rgba(255,255,255,0.7) 100%)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
        }}>
          绿电直供
        </h1>
        <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
          {["三种绿证", "碳交易", "碳足迹"].map((t, i) => (
            <div key={i} style={{
              padding: "10px 24px", borderRadius: 20,
              background: "rgba(200,144,80,0.1)", color: "#C89050",
              fontSize: 20, fontWeight: 600,
            }}>
              {t}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
