import { useCurrentFrame, interpolate, spring, OffthreadVideo, staticFile } from "remotion";

// ============================================================
//  动效配置文件 — 下次做视频只改这个 JSON
// ============================================================

export type BoxEffect = SpotlightBox | CalloutBox | PulseBox;

type SpotlightBox = {
  type: "spotlight";    // 聚光高亮框 — 画面中心发光框
  start: number;        // 开始帧
  end: number;           // 结束帧
  width: number;         // 框宽度
  height: number;        // 框高度
  x?: string;            // 水平位置，默认 "center"
  y?: string;            // 垂直位置，默认 "center"
  color?: string;        // 发光颜色，默认金色
  label?: string;        // 顶部标签文字
};

type CalloutBox = {
  type: "callout";       // 弹出标注卡片 — 侧边滑入
  start: number;
  end: number;
  side: "left" | "right"; // 从哪边滑入
  title?: string;         // 卡片标题
  items: { label: string; color?: string }[];  // 逐行弹出列表
};

type PulseBox = {
  type: "pulse";          // 脉冲扫描框 — 持续脉冲+跑马灯
  start: number;
  end: number;
  x: string;              // "15%"  "55%"  "center"
  y: string;              // "20%"  "40%"  "60%"
  width: number;
  height: number;
  color?: string;
  label?: string;
  delay?: number;          // 相对 start 的延迟帧数
};

// ============================================================
//  OverlayEngine — 一个组件搞定所有叠加效果
// ============================================================

export const OverlayEngine: React.FC<{
  videoSrc: string;       // public/ 下的视频文件名
  effects: BoxEffect[];
}> = ({ videoSrc, effects }) => {
  const frame = useCurrentFrame();

  return (
    <div style={{ width: 1920, height: 1080, position: "relative", overflow: "hidden", background: "#000" }}>
      <OffthreadVideo src={staticFile(videoSrc)} style={{ width: "100%", height: "100%", objectFit: "contain" }} />

      {effects.map((fx, i) => {
        if (frame < fx.start || frame > fx.end) return null;
        switch (fx.type) {
          case "spotlight": return <Spotlight key={i} {...fx} frame={frame} />;
          case "callout":   return <Callout key={i} {...fx} frame={frame} />;
          case "pulse":     return <PulseBox key={i} {...fx} frame={frame} />;
          default:          return null;
        }
      })}
    </div>
  );
};

// ---- 聚光框实现 ----
const Spotlight: React.FC<SpotlightBox & { frame: number }> = (p) => {
  const { frame, start, width, height, x = "center", y = "center", color = "#C89050", label } = p;
  const s = spring({ frame: frame - start, fps: 30, config: { damping: 10, stiffness: 180 } });
  const o = interpolate(frame, [start, start + 10], [0, 1], { extrapolateRight: "clamp" });
  const pulse = 1 + Math.sin(frame * 0.12) * 0.015;

  return (
    <div style={{
      position: "absolute", inset: 0, zIndex: 10,
      display: "flex", justifyContent: x === "center" ? "center" : "flex-start",
      alignItems: y === "center" ? "center" : "flex-start",
      pointerEvents: "none",
      paddingLeft: x === "center" ? 0 : x,
      paddingTop: y === "center" ? 0 : y,
    }}>
      <div style={{
        opacity: o, transform: `scale(${interpolate(s, [0, 1], [0.8, 1]) * pulse})`,
        width, height, borderRadius: 20, position: "relative",
        border: `3px solid ${color}`,
        boxShadow: `0 0 60px ${color}66, 0 0 120px ${color}26, inset 0 0 30px ${color}0D`,
        background: `${color}08`,
      }}>
        <CornerMarks color={color} />
        {label && (
          <div style={{
            position: "absolute", top: -16, left: 20,
            background: color, color: "#FFF",
            fontSize: 14, fontWeight: 700, padding: "3px 12px",
            borderRadius: 4, letterSpacing: "0.05em",
          }}>{label}</div>
        )}
      </div>
    </div>
  );
};

// ---- 侧边卡片实现 ----
const Callout: React.FC<CalloutBox & { frame: number }> = (p) => {
  const { frame, start, side, title, items } = p;
  const s = spring({ frame: frame - start, fps: 30, config: { damping: 8, stiffness: 200 } });
  const slideX = interpolate(s, [0, 1], [side === "right" ? 420 : -420, 0]);
  const o = interpolate(frame, [start, start + 8], [0, 1], { extrapolateRight: "clamp" });

  return (
    <div style={{
      position: "absolute", top: "50%",
      [side]: 0,
      transform: `translateY(-50%) translateX(${slideX}px)`,
      zIndex: 20, pointerEvents: "none",
      padding: "30px 32px",
      background: "rgba(13,13,13,0.85)",
      backdropFilter: "blur(24px)",
      borderRadius: side === "right" ? "16px 0 0 16px" : "0 16px 16px 0",
      border: "1px solid rgba(255,255,255,0.08)",
      [`border${side === "right" ? "Right" : "Left"}`]: "none",
      boxShadow: `${side === "right" ? "-" : ""}8px 0 40px rgba(0,0,0,0.3)`,
      opacity: o,
    }}>
      {title && (
        <div style={{ fontSize: 14, color: "#C89050", fontWeight: 600, letterSpacing: "0.08em", marginBottom: 16 }}>
          {title}
        </div>
      )}
      {items.map((item, i) => {
        const itemS = spring({ frame: frame - (start + i * 8), fps: 30, config: { damping: 8, stiffness: 200 } });
        return (
          <div key={i} style={{
            opacity: interpolate(frame, [start + i * 8, start + i * 8 + 8], [0, 1], { extrapolateRight: "clamp" }),
            transform: `translateY(${interpolate(itemS, [0, 1], [20, 0])}px)`,
            display: "flex", alignItems: "center", gap: 12, marginBottom: 12,
          }}>
            <div style={{
              width: 10, height: 10, borderRadius: "50%",
              background: item.color || "#C89050",
              boxShadow: `0 0 12px ${item.color || "#C89050"}`,
            }} />
            <span style={{ fontSize: 20, fontWeight: 600, color: "#FFF", letterSpacing: "0.02em" }}>
              {item.label}
            </span>
          </div>
        );
      })}
    </div>
  );
};

// ---- 脉冲框实现 ----
const PulseBox: React.FC<PulseBox & { frame: number }> = (p) => {
  const { frame, start, x, y, width, height, color = "#C89050", label, delay = 0 } = p;
  const actualStart = start + delay;
  if (frame < actualStart) return null;

  const s = spring({ frame: frame - actualStart, fps: 30, config: { damping: 6, stiffness: 160 } });
  const o = interpolate(frame, [actualStart, actualStart + 10], [0, 1], { extrapolateRight: "clamp" });
  const pulse = 1 + Math.sin((frame - actualStart) * 0.08) * 0.02;
  const dashOffset = (frame - actualStart) * 3;

  return (
    <div style={{
      position: "absolute", left: x, top: y, width, height,
      opacity: o, zIndex: 15, pointerEvents: "none",
      transform: `translate(-50%, -50%) scale(${interpolate(s, [0, 1], [0.5, 1]) * pulse})`,
    }}>
      <div style={{
        width: "100%", height: "100%", borderRadius: 12,
        border: `2px solid ${color}`,
        background: `${color}0A`,
        boxShadow: `0 0 30px ${color}20, inset 0 0 20px ${color}08`,
      }} />
      <svg style={{ position: "absolute", inset: -4, width: width + 8, height: height + 8 }}>
        <rect x="1" y="1" width={width + 6} height={height + 6} rx="13" ry="13"
          fill="none" stroke={color} strokeWidth="1.5"
          strokeDasharray="12 8" strokeDashoffset={-dashOffset} opacity={0.5} />
      </svg>
      {label && (
        <div style={{
          position: "absolute", top: -14, left: 16,
          background: color, color: "#FFF",
          fontSize: 13, fontWeight: 700, padding: "2px 10px",
          borderRadius: 4, letterSpacing: "0.05em",
        }}>{label}</div>
      )}
    </div>
  );
};

const CornerMarks: React.FC<{ color: string }> = ({ color }) => {
  const size = 24;
  const marks = [
    { top: -1, left: -1, rot: 0 },
    { top: -1, right: -1, rot: 90 },
    { bottom: -1, left: -1, rot: -90 },
    { bottom: -1, right: -1, rot: 180 },
  ];
  return (
    <>
      {marks.map((m, i) => (
        <div key={i} style={{
          position: "absolute",
          top: m.top ?? undefined, left: m.left ?? undefined,
          right: m.right ?? undefined, bottom: m.bottom ?? undefined,
          width: size, height: size,
          borderTop: `3px solid ${color}`, borderLeft: `3px solid ${color}`,
          transform: `rotate(${m.rot}deg)`, transformOrigin: "top left",
        }} />
      ))}
    </>
  );
};
