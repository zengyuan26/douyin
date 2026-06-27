import { useCurrentFrame, interpolate, spring } from "remotion";
import { LIGHT_BG_AMBER } from "../components/Background";
import { ParticleField } from "../components/ParticleField";

export const Page2_Comparison: React.FC = () => {
  const frame = useCurrentFrame();
  const titleO = interpolate(frame, [0, 8], [0, 1], { extrapolateRight: "clamp" });

  return (
    <div style={{
      width: "100%", height: "100%", background: LIGHT_BG_AMBER,
      fontFamily: '"Noto Sans SC", -apple-system, sans-serif',
      display: "flex", flexDirection: "column", justifyContent: "center",
      padding: "60px 100px", position: "relative", overflow: "hidden", gap: 40,
    }}>
      <ParticleField />

      {/* Section header */}
      <div style={{ opacity: titleO }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: "#C89050", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 8 }}>
          What Is It
        </div>
        <h2 style={{ fontSize: 56, fontWeight: 800, color: "#0D0D0D", margin: 0, lineHeight: 1.1 }}>
          不是买一张证。<br/>是建一套不发愁的系统。
        </h2>
      </div>

      {/* Two comparison cards */}
      <div style={{ display: "flex", gap: 32 }}>
        <CompareCard
          frame={frame}
          index={0}
          side="left"
          title="买证模式"
          accent="#DC2626"
          items={["电→电网→工厂", "绿证→交易所→花钱买", "每年买 · 价格一直涨"]}
          badge="年年花钱 · 越花越多"
        />
        <CompareCard
          frame={frame}
          index={1}
          side="right"
          title="建系统模式"
          accent="#4D8F8F"
          items={["微电网自发自用", "绿电直供专线", "VPP调度增收"]}
          badge="一次投入 · 证是副产品"
        />
      </div>

      {/* Bottom line */}
      <BottomLine frame={frame} />
    </div>
  );
};

const CompareCard: React.FC<{
  frame: number; index: number;
  side: "left" | "right";
  title: string; accent: string;
  items: string[];
  badge: string;
}> = ({ frame, index, side, title, accent, items, badge }) => {
  const d = index * 12;
  const s = spring({ frame: frame - d - 10, fps: 30, config: { damping: 8, stiffness: 180 } });
  const o = interpolate(frame, [d + 10, d + 18], [0, 1], { extrapolateRight: "clamp" });
  const y = interpolate(s, [0, 1], [40, 0]);

  const bg = side === "left"
    ? "rgba(0,0,0,0.03)"
    : "rgba(77,143,143,0.06)";
  const border = side === "left"
    ? "1px solid rgba(0,0,0,0.06)"
    : "1px solid rgba(77,143,143,0.15)";

  return (
    <div style={{
      flex: 1, opacity: o, transform: `translateY(${y}px)`,
      padding: "40px 36px", borderRadius: 20, background: bg,
      backdropFilter: "blur(16px)", border,
      display: "flex", flexDirection: "column", gap: 24,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ width: 8, height: 32, borderRadius: 4, background: accent }} />
        <div style={{ fontSize: 28, fontWeight: 800, color: "#0D0D0D" }}>{title}</div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {items.map((item, i) => {
          const itemS = spring({ frame: frame - (d + 18 + i * 6), fps: 30, config: { damping: 8, stiffness: 200 } });
          return (
            <div key={i} style={{
              opacity: interpolate(itemS, [0, 1], [0.3, 1]),
              transform: `translateX(${interpolate(itemS, [0, 1], [15, 0])}px)`,
              fontSize: 20, color: "#374151", fontWeight: 500,
              display: "flex", alignItems: "center", gap: 10,
            }}>
              <div style={{ width: 6, height: 6, borderRadius: "50%", background: accent, flexShrink: 0 }} />
              {item}
            </div>
          );
        })}
      </div>
      <div style={{
        alignSelf: "flex-start", padding: "6px 16px", borderRadius: 8,
        background: accent, color: "#FFF", fontSize: 14, fontWeight: 700,
        letterSpacing: "0.02em",
        opacity: interpolate(frame, [d + 50, d + 60], [0, 1], { extrapolateRight: "clamp" }),
      }}>
        {badge}
      </div>
    </div>
  );
};

const BottomLine: React.FC<{ frame: number }> = ({ frame }) => {
  const o = interpolate(frame, [70, 80], [0, 1], { extrapolateRight: "clamp" });
  return (
    <div style={{
      opacity: o, textAlign: "center",
      padding: "20px 40px", borderRadius: 14,
      background: "rgba(200,144,80,0.08)", border: "1px solid rgba(200,144,80,0.15)",
    }}>
      <span style={{ fontSize: 22, fontWeight: 700, color: "#0D0D0D" }}>
        零碳园区 = 让你的工厂用电，
      </span>
      <span style={{ fontSize: 22, fontWeight: 700, color: "#C89050" }}>
        每一度都说得清、不花钱买证、还有收益。
      </span>
    </div>
  );
};
