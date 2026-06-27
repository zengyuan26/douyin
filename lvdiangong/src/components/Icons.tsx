import React from "react";

// Wind turbine icon
export const WindTurbine: React.FC<{ size?: number; color?: string }> = ({ size = 80, color = "#C89050" }) => (
  <svg width={size} height={size} viewBox="0 0 80 80" fill="none">
    <rect x="38" y="40" width="4" height="35" rx="2" fill={color} opacity="0.5" />
    <ellipse cx="40" cy="25" rx="6" ry="2" fill={color} opacity="0.3" />
    <line x1="40" y1="25" x2="40" y2="8" stroke={color} strokeWidth="3" strokeLinecap="round" />
    <path d="M 28 14 L 40 8 L 52 14" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M 32 20 L 40 8 L 48 20" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" opacity="0.6" />
    <path d="M 35 26 L 40 8 L 45 26" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" opacity="0.4" />
  </svg>
);

// Factory icon
export const Factory: React.FC<{ size?: number; color?: string }> = ({ size = 80, color = "#6B7280" }) => (
  <svg width={size} height={size} viewBox="0 0 80 80" fill="none">
    <rect x="10" y="25" width="18" height="40" rx="2" fill={color} opacity="0.15" stroke={color} strokeWidth="2" />
    <rect x="15" y="30" width="8" height="8" rx="1" fill={color} opacity="0.3" />
    <polygon points="24,14 33,14 37,25 19,25" fill={color} opacity="0.12" stroke={color} strokeWidth="1.5" />
    <rect x="32" y="20" width="18" height="45" rx="2" fill={color} opacity="0.15" stroke={color} strokeWidth="2" />
    <rect x="37" y="28" width="8" height="10" rx="1" fill={color} opacity="0.3" />
    <rect x="37" y="42" width="8" height="10" rx="1" fill={color} opacity="0.3" />
    <rect x="50" y="12" width="4" height="53" rx="2" fill={color} opacity="0.2" />
    <rect x="54" y="30" width="14" height="35" rx="2" fill={color} opacity="0.1" stroke={color} strokeWidth="1.5" />
    <rect x="58" y="36" width="6" height="8" rx="1" fill={color} opacity="0.25" />
  </svg>
);

// Power line / transmission icon
export const PowerLine: React.FC<{ size?: number; color?: string }> = ({ size = 80, color = "#C89050" }) => (
  <svg width={size} height={size} viewBox="0 0 80 80" fill="none">
    <rect x="18" y="10" width="6" height="60" rx="3" fill={color} opacity="0.5" />
    <rect x="56" y="10" width="6" height="60" rx="3" fill={color} opacity="0.5" />
    <path d="M 21 20 Q 40 30, 59 25" stroke={color} strokeWidth="1.5" fill="none" opacity="0.6" />
    <path d="M 21 35 Q 40 45, 59 40" stroke={color} strokeWidth="2" fill="none" />
    <path d="M 21 50 Q 40 60, 59 55" stroke={color} strokeWidth="1.5" fill="none" opacity="0.6" />
    {/* Lightning bolt on line */}
    <polygon points="37,30 33,42 38,42 34,55 43,38 38,38 42,30" fill={color} />
  </svg>
);

// Bolt / energy icon
export const Bolt: React.FC<{ size?: number; color?: string }> = ({ size = 48, color = "#C89050" }) => (
  <svg width={size} height={size} viewBox="0 0 48 48" fill="none">
    <polygon points="26,4 14,26 22,26 18,44 34,20 26,20 30,4" fill={color} />
  </svg>
);

// Grid / network icon
export const Grid: React.FC<{ size?: number; color?: string }> = ({ size = 80, color = "#4D8F8F" }) => (
  <svg width={size} height={size} viewBox="0 0 80 80" fill="none">
    <rect x="10" y="10" width="60" height="60" rx="4" stroke={color} strokeWidth="2" />
    <line x1="40" y1="10" x2="40" y2="70" stroke={color} strokeWidth="1" opacity="0.4" />
    <line x1="10" y1="40" x2="70" y2="40" stroke={color} strokeWidth="1" opacity="0.4" />
    <circle cx="25" cy="25" r="4" fill={color} opacity="0.6" />
    <circle cx="55" cy="25" r="4" fill={color} opacity="0.3" />
    <circle cx="25" cy="55" r="4" fill={color} opacity="0.3" />
    <circle cx="55" cy="55" r="4" fill={color} opacity="0.6" />
  </svg>
);

// Green certificate / document icon
export const Certificate: React.FC<{ size?: number; color?: string }> = ({ size = 80, color = "#4D8F8F" }) => (
  <svg width={size} height={size} viewBox="0 0 80 80" fill="none">
    <rect x="15" y="8" width="50" height="64" rx="6" fill={color} opacity="0.1" stroke={color} strokeWidth="2" />
    <line x1="25" y1="24" x2="55" y2="24" stroke={color} strokeWidth="2" opacity="0.4" />
    <line x1="25" y1="34" x2="50" y2="34" stroke={color} strokeWidth="2" opacity="0.3" />
    <line x1="25" y1="44" x2="52" y2="44" stroke={color} strokeWidth="2" opacity="0.25" />
    <circle cx="60" cy="60" r="12" fill={color} />
    <path d="M 55 60 L 58 63 L 65 56" stroke="#FFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

// Arrow / exchange icon
export const ArrowExchange: React.FC<{ size?: number; color?: string }> = ({ size = 60, color = "#C89050" }) => (
  <svg width={size} height={size} viewBox="0 0 60 40" fill="none">
    <line x1="5" y1="20" x2="50" y2="20" stroke={color} strokeWidth="3" strokeLinecap="round" />
    <polygon points="42,12 55,20 42,28" fill={color} />
  </svg>
);
