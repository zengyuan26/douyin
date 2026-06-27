import type { Bar } from "../components/AnimatedBarChart";

// ── Shared ──
export type BgTheme = "dark" | "light-amber" | "light-teal" | "light-red";
export type AccentColor = "#C89050" | "#4D8F8F" | "#DC2626" | "#6B7280" | "#0D0D0D";

// ── Page types ──

export interface CoverPage {
  type: "cover";
  label?: string;
  title: string;
  subtitle?: string;
  tags?: string[];
  background?: BgTheme;
}

export interface Compare2Page {
  type: "compare-2";
  label?: string;
  title: string;
  titleAccent?: string;
  left: {
    label: string;
    title: string;
    items: { icon?: string; text: string; accent?: string }[];
    badge?: string;
    badgeColor?: string;
  };
  right: {
    label: string;
    title: string;
    items: { icon?: string; text: string; accent?: string }[];
    badge?: string;
    badgeColor?: string;
  };
  bottomLine?: string;
  background?: BgTheme;
}

export interface Card3Item {
  label: string;
  title: string;
  stat: string;
  tag: string;
  accent: string;
  dim?: boolean;
  highlighted?: boolean;
}

export interface Cards3Page {
  type: "cards-3";
  label?: string;
  title: string;
  titleAccent?: string;
  cards: Card3Item[];
  background?: BgTheme;
}

export interface Card4Item {
  num: string;
  title: string;
  sub?: string;
  accent: string;
  icon?: "wind" | "bolt" | "grid" | "certificate" | "factory" | "exchange";
}

export interface Cards4Page {
  type: "cards-4";
  label?: string;
  title: string;
  cards: Card4Item[];
  background?: BgTheme;
}

export interface ChartBarPage {
  type: "chart-bar";
  label?: string;
  title: string;
  items: { num: string; title: string; sub: string; accent: string }[];
  chartData: Bar[];
  background?: BgTheme;
}

export interface StepItem {
  num: string;
  title: string;
  body: string;
  tag?: string;
  accent?: string;
  substeps?: { left: string; right: string }[];
}

export interface StepsPage {
  type: "steps";
  label?: string;
  title: string;
  steps: StepItem[];
  bottomLine?: string;
  background?: BgTheme;
  flowLabels?: string[];
}

export interface PyramidBlock {
  label: string;
  sub: string;
  bg: string;
  color: string;
}

export interface PyramidPage {
  type: "pyramid";
  label?: string;
  title: string;
  blocks: PyramidBlock[];
  cta?: string;
  question?: string;
  background?: BgTheme;
}

export interface BigNumbersPage {
  type: "big-numbers";
  left: { label: string; value: string; detail: string };
  right: { label: string; value: string; detail: string };
  bottomLine: string;
  background?: BgTheme;
}

export interface ThreatCard {
  title: string;
  bullets: string[];
  stat?: string;
  tag?: string;
  accent: string;
}

export interface ThreatsPage {
  type: "threats-3";
  title: string;
  cards: ThreatCard[];
  bottomLine?: string;
  background?: BgTheme;
}

export interface CaseStudyPage {
  type: "case-study";
  title: string;
  before: { label: string; items: string[] };
  after: { label: string; items: string[] };
  investment: string;
  annualSavings: string;
  payback: string;
  bottomLine: string;
  background?: BgTheme;
}

export interface HookPage {
  type: "hook";
  lines: string[];
  reveal: string;
  background?: BgTheme;
}

export interface NumberGridPage {
  type: "number-grid";
  title: string;
  cards: { label: string; value: string; accent: string }[];
  bottomLine?: string;
  background?: BgTheme;
}

export interface TimelineAct {
  label: string;
  title: string;
  items: string[];
  tag: string;
}

export interface TimelinePage {
  type: "timeline";
  title: string;
  acts: TimelineAct[];
  bottomLine?: string;
  background?: BgTheme;
}

export interface ClosingPage {
  type: "closing";
  title: string;
  lines: string[];
  seriesLine?: string;
  background?: BgTheme;
}

// ── Union ──

export type PageConfig =
  | CoverPage
  | Compare2Page
  | Cards3Page
  | Cards4Page
  | ChartBarPage
  | StepsPage
  | PyramidPage
  | BigNumbersPage
  | ThreatsPage
  | CaseStudyPage
  | HookPage
  | NumberGridPage
  | TimelinePage
  | ClosingPage;

export interface VideoConfig {
  id: string;
  title: string;
  fps?: number;
  width?: number;
  height?: number;
  transitionFrames?: number;
  pages: (PageConfig & { durationFrames: number })[];
}
