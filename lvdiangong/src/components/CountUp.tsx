import { useCurrentFrame, interpolate } from "remotion";

// Animated number counter — counts up from 0 to target
export const CountUp: React.FC<{
  value: number;
  delay?: number;
  duration?: number;
  prefix?: string;
  suffix?: string;
  style?: React.CSSProperties;
}> = ({ value, delay = 0, duration = 20, prefix = "", suffix = "", style }) => {
  const frame = useCurrentFrame();
  const progress = interpolate(frame, [delay, delay + duration], [0, 1], {
    extrapolateRight: "clamp",
    extrapolateLeft: "clamp",
  });
  // Ease out cubic for natural deceleration
  const eased = 1 - Math.pow(1 - progress, 3);
  const display = Math.round(value * eased);

  return <span style={style}>{prefix}{display.toLocaleString()}{suffix}</span>;
};

// Animated percentage ring — fills from 0 to pct
export const CountUpPct: React.FC<{
  value: number;
  delay?: number;
  duration?: number;
  style?: React.CSSProperties;
}> = ({ value, delay = 0, duration = 20, style }) => {
  const frame = useCurrentFrame();
  const progress = interpolate(frame, [delay, delay + duration], [0, 1], {
    extrapolateRight: "clamp",
    extrapolateLeft: "clamp",
  });
  const eased = 1 - Math.pow(1 - progress, 3);
  const display = Math.round(value * eased);

  return <span style={style}>{display}%</span>;
};
