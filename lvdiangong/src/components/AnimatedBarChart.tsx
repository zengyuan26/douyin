import { useCurrentFrame, interpolate, spring } from "remotion";

export type Bar = { label: string; value: number; color: string; maxValue?: number };

export const AnimatedBarChart: React.FC<{
  data: Bar[];
  width?: number;
  height?: number;
  delay?: number;
}> = ({ data, width = 500, height = 280, delay = 0 }) => {
  const frame = useCurrentFrame();
  const maxVal = Math.max(...data.map((d) => d.maxValue ?? d.value));
  const barH = height / data.length - 16;

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      {data.map((d, i) => {
        // Snappier stagger: 6 frames between bars
        const dly = delay + i * 6;
        // Snappier spring: less damping, more stiffness
        const s = spring({ frame: frame - dly, fps: 30, config: { damping: 10, stiffness: 150 } });
        const barW = interpolate(s, [0, 1], [0, (d.value / maxVal) * (width - 120)]);
        const o = interpolate(frame, [dly, dly + 4], [0, 1], { extrapolateRight: "clamp" });
        const y = i * (barH + 16) + 8;

        // Subtle continuous pulse after initial animation
        const pulse = 1 + (1 - s) * Math.sin(frame * 0.15) * 0.02;

        return (
          <g key={i} opacity={o}>
            <text x="0" y={y + barH / 2 + 6} fill="#6B7280" fontSize="16" fontWeight="600">
              {d.label}
            </text>
            <rect x="100" y={y} width={width - 120} height={barH} rx="6" fill="rgba(0,0,0,0.04)" />
            <rect x="100" y={y} width={barW * pulse} height={barH} rx="6" fill={d.color} />
            <text
              x={100 + barW + 10}
              y={y + barH / 2 + 6}
              fill={d.color}
              fontSize="18"
              fontWeight="700"
              opacity={barW > 30 ? 1 : 0}
            >
              {d.value}
            </text>
          </g>
        );
      })}
    </svg>
  );
};
