import { useCurrentFrame } from "remotion";

type Particle = { x: number; y: number; r: number; speed: number; phase: number; opacity: number };

// Generate a stable set of particles
const generateParticles = (count: number, seed: number): Particle[] => {
  const particles: Particle[] = [];
  for (let i = 0; i < count; i++) {
    const pseudoRandom = ((seed * 9301 + i * 49297 + 233280) % 233280) / 233280;
    particles.push({
      x: ((i * 137 + seed * 73) % 100) / 100,
      y: ((i * 251 + seed * 47) % 100) / 100,
      r: 1 + pseudoRandom * 3,
      speed: 0.3 + pseudoRandom * 0.7,
      phase: pseudoRandom * Math.PI * 2,
      opacity: 0.15 + pseudoRandom * 0.5,
    });
  }
  return particles;
};

export const ParticleField: React.FC<{ dark?: boolean; count?: number }> = ({
  dark = false,
  count = 45,
}) => {
  const frame = useCurrentFrame();
  // Use a fixed seed for consistent particles across renders
  const particles = generateParticles(count, dark ? 42 : 84);
  const baseA = dark ? "0.6" : "0.5";
  const baseA2 = dark ? "0.5" : "0.4";
  const color = dark ? `rgba(200,144,80,${baseA})` : `rgba(200,144,80,${baseA})`;
  const color2 = dark ? `rgba(77,143,143,${baseA2})` : `rgba(77,143,143,${baseA2})`;

  return (
    <div style={{ position: "absolute", inset: 0, pointerEvents: "none", zIndex: 20 }}>
      <svg width="100%" height="100%" style={{ position: "absolute", inset: 0 }}>
        {particles.map((p, i) => {
          const driftX = Math.sin(frame * 0.015 * p.speed + p.phase) * 20;
          const driftY = Math.cos(frame * 0.012 * p.speed + p.phase) * 20;
          const cx = p.x * 100 + driftX / 10;
          const cy = p.y * 100 + driftY / 10;
          // Alternate colors
          const isAlternate = i % 3 === 0;
          // Subtle twinkle
          const twinkle = 0.7 + 0.3 * Math.sin(frame * 0.05 + p.phase);

          return (
            <circle
              key={i}
              cx={`${cx}%`}
              cy={`${cy}%`}
              r={p.r}
              fill={isAlternate ? color2 : color}
              opacity={p.opacity * twinkle}
            />
          );
        })}
        {/* Larger glow particles */}
        {particles.slice(0, 8).map((p, i) => {
          const driftX = Math.sin(frame * 0.01 * p.speed + p.phase) * 30;
          const driftY = Math.cos(frame * 0.008 * p.speed + p.phase) * 30;
          const cx = p.x * 100 + driftX / 10;
          const cy = p.y * 100 + driftY / 10;
          const twinkle = 0.6 + 0.4 * Math.sin(frame * 0.04 + p.phase + 1);
          return (
            <circle
              key={`glow-${i}`}
              cx={`${cx}%`}
              cy={`${cy}%`}
              r={p.r * 3}
              fill={i % 2 === 0 ? color2 : color}
              opacity={p.opacity * 0.3 * twinkle}
              filter="blur(4px)"
            />
          );
        })}
      </svg>
    </div>
  );
};
