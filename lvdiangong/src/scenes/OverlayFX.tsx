import { useCurrentFrame, interpolate, spring, OffthreadVideo, staticFile } from "remotion";

const VIDEO_SRC = staticFile("lvdiangong.mp4");

export const OverlayFX: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <div style={{
      width: 1920, height: 1080,
      position: "relative", overflow: "hidden",
      background: "#000",
    }}>
      {/* 原视频作为底层 */}
      <OffthreadVideo
        src={VIDEO_SRC}
        style={{ width: "100%", height: "100%", objectFit: "contain" }}
      />

      {/* ====== 效果1: 聚光高亮框 (0-4s, dark scene) ====== */}
      <SpotlightBox frame={frame} />

      {/* ====== 效果2: 侧边弹出标注卡片 (5-9s) ====== */}
      <CalloutCard frame={frame} />

      {/* ====== 效果3: 脉冲框 (10-14s) ====== */}
      <PulseBox frame={frame} />
    </div>
  );
};

// ---- 效果1: 聚光框 ----
const SpotlightBox: React.FC<{ frame: number }> = ({ frame }) => {
  if (frame < 5 || frame > 120) return null;

  const s = spring({ frame: frame - 5, fps: 30, config: { damping: 10, stiffness: 180 } });
  const scale = interpolate(s, [0, 1], [0.8, 1]);
  const o = interpolate(frame, [5, 15], [0, 1], { extrapolateRight: "clamp" });
  const pulse = 1 + Math.sin(frame * 0.12) * 0.015;

  return (
    <div style={{
      position: "absolute", inset: 0, zIndex: 10,
      display: "flex", justifyContent: "center", alignItems: "center",
      pointerEvents: "none",
    }}>
      <div style={{
        opacity: o, transform: `scale(${scale * pulse})`,
        width: 700, height: 300, borderRadius: 20,
        border: "3px solid #C89050",
        boxShadow: `
          0 0 60px rgba(200,144,80,0.4),
          0 0 120px rgba(200,144,80,0.15),
          inset 0 0 30px rgba(200,144,80,0.05)
        `,
        background: "rgba(200,144,80,0.03)",
      }}>
        {/* 四角装饰 */}
        <CornerMarkers color="#C89050" />
      </div>
    </div>
  );
};

// ---- 效果2: 侧边弹出标注卡片 ----
const CalloutCard: React.FC<{ frame: number }> = ({ frame }) => {
  if (frame < 110 || frame > 260) return null;

  const s = spring({ frame: frame - 110, fps: 30, config: { damping: 8, stiffness: 200 } });
  const slideX = interpolate(s, [0, 1], [420, 0]);
  const o = interpolate(frame, [110, 118], [0, 1], { extrapolateRight: "clamp" });

  const items = [
    { label: "概念图谱 Vol.4", color: "#C89050" },
    { label: "绿电直供全景", color: "#4D8F8F" },
    { label: "三种绿证·碳交易", color: "#DC2626" },
  ];

  return (
    <div style={{
      position: "absolute", right: 0, top: "50%",
      transform: `translateY(-50%) translateX(${slideX}px)`,
      zIndex: 20, pointerEvents: "none",
      display: "flex", flexDirection: "column", gap: 16,
      padding: "30px 32px",
      background: "rgba(13,13,13,0.85)",
      backdropFilter: "blur(24px)",
      borderRadius: "16px 0 0 16px",
      border: "1px solid rgba(255,255,255,0.08)",
      borderRight: "none",
      boxShadow: "-8px 0 40px rgba(0,0,0,0.3)",
      opacity: o,
    }}>
      {items.map((item, i) => {
        const itemS = spring({
          frame: frame - (110 + i * 8), fps: 30,
          config: { damping: 8, stiffness: 200 },
        });
        const itemY = interpolate(itemS, [0, 1], [20, 0]);
        const itemO = interpolate(frame, [110 + i * 8, 118 + i * 8], [0, 1], { extrapolateRight: "clamp" });
        return (
          <div key={i} style={{
            opacity: itemO, transform: `translateY(${itemY}px)`,
            display: "flex", alignItems: "center", gap: 12,
          }}>
            <div style={{
              width: 10, height: 10, borderRadius: "50%",
              background: item.color,
              boxShadow: `0 0 12px ${item.color}`,
            }} />
            <span style={{
              fontSize: 20, fontWeight: 600, color: "#FFFFFF",
              letterSpacing: "0.02em",
            }}>
              {item.label}
            </span>
          </div>
        );
      })}
    </div>
  );
};

// ---- 效果3: 脉冲扫描框 ----
const PulseBox: React.FC<{ frame: number }> = ({ frame }) => {
  if (frame < 260 || frame > 420) return null;

  const positions = [
    { x: "15%", y: "20%", w: 320, h: 200, color: "#C89050", delay: 0 },
    { x: "55%", y: "35%", w: 280, h: 180, color: "#4D8F8F", delay: 20 },
    { x: "35%", y: "60%", w: 360, h: 160, color: "#DC2626", delay: 40 },
  ];

  return (
    <div style={{ position: "absolute", inset: 0, zIndex: 15, pointerEvents: "none" }}>
      {positions.map((pos, i) => {
        const startFrame = 260 + pos.delay;
        if (frame < startFrame) return null;

        const s = spring({
          frame: frame - startFrame, fps: 30,
          config: { damping: 6, stiffness: 160 },
        });
        const scale = interpolate(s, [0, 1], [0.5, 1]);
        const o = interpolate(frame, [startFrame, startFrame + 10], [0, 1], { extrapolateRight: "clamp" });

        // 持续脉冲
        const pulse = 1 + Math.sin((frame - startFrame) * 0.08) * 0.02;
        const dashOffset = (frame - startFrame) * 3;

        return (
          <div key={i} style={{
            position: "absolute",
            left: pos.x, top: pos.y,
            width: pos.w, height: pos.h,
            opacity: o,
            transform: `translate(-50%, -50%) scale(${scale * pulse})`,
          }}>
            {/* 实线边框 */}
            <div style={{
              width: "100%", height: "100%",
              borderRadius: 12,
              border: `2px solid ${pos.color}`,
              background: `${pos.color}0A`,
              boxShadow: `0 0 30px ${pos.color}20, inset 0 0 20px ${pos.color}08`,
            }} />

            {/* 虚线跑动边框 - SVG overlay */}
            <svg style={{
              position: "absolute", inset: -4,
              width: pos.w + 8, height: pos.h + 8,
            }}>
              <rect
                x="1" y="1"
                width={pos.w + 6} height={pos.h + 6}
                rx="13" ry="13"
                fill="none"
                stroke={pos.color}
                strokeWidth="1.5"
                strokeDasharray="12 8"
                strokeDashoffset={-dashOffset}
                opacity={0.5}
              />
            </svg>

            {/* 标签 */}
            <div style={{
              position: "absolute", top: -14, left: 16,
              background: pos.color,
              color: "#FFF",
              fontSize: 13, fontWeight: 700,
              padding: "2px 10px", borderRadius: 4,
              letterSpacing: "0.05em",
            }}>
              {["关键概念", "核心数据", "政策要点"][i]}
            </div>
          </div>
        );
      })}
    </div>
  );
};

// 四角装饰标记
const CornerMarkers: React.FC<{ color: string }> = ({ color }) => {
  const size = 24;
  const corners = [
    { top: -1, left: -1, rot: 0 },
    { top: -1, right: -1, rot: 90 },
    { bottom: -1, left: -1, rot: -90 },
    { bottom: -1, right: -1, rot: 180 },
  ];
  return (
    <>
      {corners.map((c, i) => (
        <div key={i} style={{
          position: "absolute",
          top: c.top ?? undefined,
          left: c.left ?? undefined,
          right: c.right ?? undefined,
          bottom: c.bottom ?? undefined,
          width: size, height: size,
          borderTop: `3px solid ${color}`,
          borderLeft: `3px solid ${color}`,
          transform: `rotate(${c.rot}deg)`,
          transformOrigin: "top left",
        }} />
      ))}
    </>
  );
};
