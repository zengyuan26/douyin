import { DARK_BG, LIGHT_BG_AMBER, LIGHT_BG_TEAL, LIGHT_BG_RED } from "../../components/Background";
import type { BgTheme } from "../types";

export function bgMap(theme?: BgTheme): string {
  switch (theme) {
    case "light-amber": return LIGHT_BG_AMBER;
    case "light-teal": return LIGHT_BG_TEAL;
    case "light-red": return LIGHT_BG_RED;
    default: return DARK_BG;
  }
}

export function isLightBg(theme?: BgTheme): boolean {
  return theme?.startsWith("light-") ?? false;
}
