import { useCurrentFrame } from "remotion";

// Continuous floating geometric shapes — renders above everything
export const FloatingElements: React.FC<{ dark?: boolean }> = ({ dark }) => {
  const frame = useCurrentFrame();
  const c = dark ? "rgba(200,144,80,0.12)" : "rgba(200,144,80,0.15)";
  const c2 = dark ? "rgba(77,143,143,0.1)" : "rgba(77,143,143,0.12)";

  return (
    <div style={{ position: "absolute", inset: 0, pointerEvents: "none", zIndex: 10 }}>
      {/* Floating circle 1 */}
      <div style={{
        position: "absolute",
        top: `${20 + Math.sin(frame * 0.03) * 8}%`,
        left: `${10 + Math.cos(frame * 0.025) * 6}%`,
        width: 90, height: 90, borderRadius: "50%",
        border: `2px solid ${c}`,
      }} />
      {/* Floating circle 2 */}
      <div style={{
        position: "absolute",
        top: `${55 + Math.cos(frame * 0.035) * 10}%`,
        right: `${8 + Math.sin(frame * 0.028) * 8}%`,
        width: 60, height: 60, borderRadius: "50%",
        border: `2px solid ${c2}`,
      }} />
      {/* Floating diamond */}
      <div style={{
        position: "absolute",
        bottom: `${15 + Math.sin(frame * 0.032) * 7}%`,
        left: `${40 + Math.cos(frame * 0.027) * 5}%`,
        width: 50, height: 50, borderRadius: 8,
        border: `2px solid ${c}`,
        transform: `rotate(${45 + Math.sin(frame * 0.02) * 10}deg)`,
      }} />
    </div>
  );
};

// CSS background strings — gradient orbs + subtle dot grid

// Light theme: bigger, darker dots + cross lines (engineering grid feel)
const gridLight = `url("data:image/svg+xml,%3Csvg width='60' height='60' xmlns='http://www.w3.org/2000/svg'%3E%3Ccircle cx='30' cy='30' r='1.5' fill='rgba(0,0,0,0.12)'/%3E%3Cline x1='30' y1='0' x2='30' y2='60' stroke='rgba(0,0,0,0.04)' stroke-width='0.5'/%3E%3Cline x1='0' y1='30' x2='60' y2='30' stroke='rgba(0,0,0,0.04)' stroke-width='0.5'/%3E%3C/svg%3E")`;

// Dark theme: subtle dots + lines
const gridDark = `url("data:image/svg+xml,%3Csvg width='60' height='60' xmlns='http://www.w3.org/2000/svg'%3E%3Ccircle cx='30' cy='30' r='1.5' fill='rgba(255,255,255,0.08)'/%3E%3Cline x1='30' y1='0' x2='30' y2='60' stroke='rgba(255,255,255,0.04)' stroke-width='0.5'/%3E%3Cline x1='0' y1='30' x2='60' y2='30' stroke='rgba(255,255,255,0.04)' stroke-width='0.5'/%3E%3C/svg%3E")`;

export const DARK_BG = `
  radial-gradient(ellipse 800px 600px at 75% 20%, rgba(200,144,80,0.2) 0%, transparent 55%),
  radial-gradient(ellipse 600px 500px at 20% 75%, rgba(77,143,143,0.15) 0%, transparent 55%),
  ${gridDark},
  #0D0D0D
`;

export const LIGHT_BG_AMBER = `
  radial-gradient(ellipse 800px 500px at 80% 15%, rgba(200,144,80,0.22) 0%, transparent 50%),
  radial-gradient(ellipse 600px 400px at 15% 85%, rgba(200,144,80,0.14) 0%, transparent 50%),
  radial-gradient(ellipse 400px 300px at 50% 45%, rgba(77,143,143,0.1) 0%, transparent 45%),
  ${gridLight},
  linear-gradient(160deg, #F5F5F0 0%, #FAFAF8 50%, #F5F5F0 100%)
`;

export const LIGHT_BG_RED = `
  radial-gradient(ellipse 800px 500px at 80% 20%, rgba(220,38,38,0.14) 0%, transparent 50%),
  radial-gradient(ellipse 600px 400px at 15% 85%, rgba(220,38,38,0.08) 0%, transparent 50%),
  radial-gradient(ellipse 400px 300px at 50% 40%, rgba(200,144,80,0.1) 0%, transparent 45%),
  ${gridLight},
  linear-gradient(160deg, #F5F5F0 0%, #FAFAF8 50%, #F5F5F0 100%)
`;

export const LIGHT_BG_TEAL = `
  radial-gradient(ellipse 800px 500px at 80% 20%, rgba(77,143,143,0.2) 0%, transparent 50%),
  radial-gradient(ellipse 600px 400px at 15% 85%, rgba(77,143,143,0.12) 0%, transparent 50%),
  radial-gradient(ellipse 400px 300px at 50% 50%, rgba(200,144,80,0.08) 0%, transparent 45%),
  ${gridLight},
  linear-gradient(160deg, #F5F5F0 0%, #FAFAF8 50%, #F5F5F0 100%)
`;
