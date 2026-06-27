import { useCurrentFrame, interpolate, spring } from "remotion";
import { DARK_BG, FloatingElements, LIGHT_BG_AMBER } from "../components/Background";
import { ParticleField } from "../components/ParticleField";
import { AnimatedBarChart } from "../components/AnimatedBarChart";
import { CountUp } from "../components/CountUp";

export const DemoFX: React.FC = () => {
  const frame = useCurrentFrame();

  // Phase timing
  const phase1End = 60;   // 0-2s: text reveal
  const phase2End = 150;  // 2-5s: bar chart
  const phase3End = 240;  // 5-8s: count-up + particle
  const phase4End = 300;  // 8-10s: outro

  // Phase 1: title swoop
  const titleS = spring({ frame, fps: 30, config: { damping: 8, stiffness: 200 } });
  const titleY = interpolate(titleS, [0, 1], [40, 0]);
  const titleO = interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp" });
  const subtitleO = interpolate(frame, [8, 18], [0, 1], { extrapolateRight: "clamp" });
  const barO = interpolate(frame, [8, 18], [0, 1], { extrapolateRight: "clamp" });

  // Phase 2: amber accent color for dark theme
  const amberAccent = "#C89050";
  const chartData = [
    { label: "AI生成", value: 78, color: amberAccent },
    { label: "人工剪辑", value: 45, color: "#4D8F8F" },
    { label: "模板套用", value: 32, color: "#6B7280" },
  ];

  // Phase 3: count-up values
  const avgScore = 87;

  // Section visibility
  const section1 = frame < phase2End;
  const section2 = frame >= 40 && frame < phase4End;
  const section3 = frame >= phase2End;

  return (
    <div style={{
      width: "100%", height: "100%",
      fontFamily: '"Noto Sans SC", -apple-system, sans-serif',
      position: "relative", overflow: "hidden",
    }}>
      {/* Background layers */}
      {frame < phase2End ? (
        <div style={{ position: "absolute", inset: 0, background: DARK_BG }}>
          <FloatingElements dark />
          <ParticleField dark count={50} />
        </div>
      ) : (
        <div style={{ position: "absolute", inset: 0, background: LIGHT_BG_AMBER }}>
          <ParticleField dark={false} count={40} />
        </div>
      )}

      {/* Content */}
      <div style={{
        position: "relative", zIndex: 30,
        width: "100%", height: "100%",
        display: "flex", flexDirection: "column",
        justifyContent: "center", alignItems: "center",
        padding: "60px 100px", gap: 40,
      }}>
        {/* Phase 1: Hero title */}
        {section1 && (
          <>
            <div style={{ opacity: titleO, transform: `translateY(${titleY}px)` }}>
              <div style={{
                fontSize: 18, fontWeight: 600, color: amberAccent,
                letterSpacing: "0.1em", textTransform: "uppercase",
                textAlign: "center", marginBottom: 16,
              }}>
                Motion Effects Demo
              </div>
              <h1 style={{
                fontSize: 96, fontWeight: 800, color: "#FFFFFF",
                margin: 0, lineHeight: 1.05, textAlign: "center",
                background: "linear-gradient(180deg, #FFFFFF 0%, rgba(255,255,255,0.65) 100%)",
                WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
              }}>
                AI动效生成
              </h1>
            </div>
            <div style={{ opacity: subtitleO, textAlign: "center" }}>
              <div style={{
                fontSize: 22, color: "rgba(255,255,255,0.6)", fontWeight: 400,
              }}>
                Remotion · 程序化视频动画 · 零手工关键帧
              </div>
            </div>
          </>
        )}

        {/* Phase 2: Bar chart */}
        {section2 && (
          <div style={{ opacity: barO, width: "100%", maxWidth: 700 }}>
            <h2 style={{
              fontSize: 32, fontWeight: 800, color: frame >= phase2End ? "#0D0D0D" : "#FFFFFF",
              marginBottom: 24, textAlign: "center",
            }}>
              三种动效生成方式对比
            </h2>
            <div style={{
              padding: "40px 60px", borderRadius: 20,
              background: frame >= phase2End
                ? "rgba(255,255,255,0.6)"
                : "rgba(255,255,255,0.06)",
              backdropFilter: "blur(20px)",
              border: frame >= phase2End
                ? "1px solid rgba(255,255,255,0.5)"
                : "1px solid rgba(255,255,255,0.08)",
            }}>
              <AnimatedBarChart data={chartData} width={560} height={200} delay={6} />
            </div>
          </div>
        )}

        {/* Phase 3: Count-up stats */}
        {section3 && (
          <div style={{
            opacity: interpolate(frame, [phase2End + 5, phase2End + 20], [0, 1], { extrapolateRight: "clamp" }),
            display: "flex", gap: 50, justifyContent: "center",
          }}>
            <StatCard
              label="综合评分"
              value={avgScore}
              unit="分"
              delay={phase2End + 10}
              color="#C89050"
            />
            <StatCard
              label="渲染速度"
              value={30}
              unit="fps"
              delay={phase2End + 20}
              color="#4D8F8F"
            />
            <StatCard
              label="效果类型"
              value={12}
              unit="+"
              delay={phase2End + 30}
              color="#DC2626"
            />
          </div>
        )}
      </div>

      {/* Top amber bar (persistent) */}
      <div style={{
        position: "absolute", top: 0, left: 0,
        width: `${interpolate(frame, [0, 15], [0, 120], { extrapolateRight: "clamp" })}px`,
        height: 3, background: amberAccent, zIndex: 50,
      }} />
    </div>
  );
};

const StatCard: React.FC<{
  label: string; value: number; unit: string;
  delay: number; color: string;
}> = ({ label, value, unit, delay, color }) => {
  const frame = useCurrentFrame();
  const s = spring({ frame: frame - delay, fps: 30, config: { damping: 8, stiffness: 180 } });
  const scale = interpolate(s, [0, 1], [0.6, 1]);
  return (
    <div style={{
      transform: `scale(${scale})`,
      padding: "36px 44px", borderRadius: 20,
      background: "rgba(255,255,255,0.6)",
      backdropFilter: "blur(16px)",
      border: "1px solid rgba(255,255,255,0.5)",
      boxShadow: "0 4px 24px rgba(0,0,0,0.04)",
      display: "flex", flexDirection: "column",
      alignItems: "center", gap: 8,
    }}>
      <div style={{ fontSize: 48, fontWeight: 800, color, lineHeight: 1 }}>
        <CountUp value={value} delay={delay} duration={18} />
        <span style={{ fontSize: 24, fontWeight: 400, color: "#9CA3AF" }}>{unit}</span>
      </div>
      <div style={{ fontSize: 16, color: "#6B7280", fontWeight: 500 }}>{label}</div>
    </div>
  );
};
