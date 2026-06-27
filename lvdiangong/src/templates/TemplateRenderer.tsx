import React from "react";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { Audio } from "remotion";
import type { VideoConfig, PageConfig } from "./types";
import { CoverScene } from "./scenes/CoverScene";
import { Compare2Scene } from "./scenes/Compare2Scene";
import { Cards3Scene } from "./scenes/Cards3Scene";
import { Cards4Scene } from "./scenes/Cards4Scene";
import { ChartBarScene } from "./scenes/ChartBarScene";
import { StepsScene } from "./scenes/StepsScene";
import { PyramidScene } from "./scenes/PyramidScene";
import { BigNumbersScene } from "./scenes/BigNumbersScene";
import { ThreatsScene } from "./scenes/ThreatsScene";
import { CaseStudyScene } from "./scenes/CaseStudyScene";
import { HookScene } from "./scenes/HookScene";
import { NumberGridScene } from "./scenes/NumberGridScene";
import { TimelineScene } from "./scenes/TimelineScene";
import { ClosingScene } from "./scenes/ClosingScene";

function renderPage(page: PageConfig) {
  switch (page.type) {
    case "cover": return <CoverScene {...page} />;
    case "compare-2": return <Compare2Scene {...page} />;
    case "cards-3": return <Cards3Scene {...page} />;
    case "cards-4": return <Cards4Scene {...page} />;
    case "chart-bar": return <ChartBarScene {...page} />;
    case "steps": return <StepsScene {...page} />;
    case "pyramid": return <PyramidScene {...page} />;
    case "big-numbers": return <BigNumbersScene {...page} />;
    case "threats-3": return <ThreatsScene {...page} />;
    case "case-study": return <CaseStudyScene {...page} />;
    case "hook": return <HookScene {...page} />;
    case "number-grid": return <NumberGridScene {...page} />;
    case "timeline": return <TimelineScene {...page} />;
    case "closing": return <ClosingScene {...page} />;
  }
}

export function calcTotalFrames(config: VideoConfig): number {
  const tf = config.transitionFrames ?? 15;
  const sum = config.pages.reduce((acc, p) => acc + p.durationFrames, 0);
  return sum - (config.pages.length - 1) * tf;
}

export const TemplateRenderer: React.FC<{ config: VideoConfig; audioSrc?: string }> = ({ config, audioSrc }) => {
  const tf = config.transitionFrames ?? 15;
  const timing = linearTiming({ durationInFrames: tf });

  return (
    <>
      {audioSrc ? <Audio src={audioSrc} /> : null}
      <TransitionSeries>
        {config.pages.map((page, i) => (
          <React.Fragment key={i}>
            {i > 0 ? <TransitionSeries.Transition presentation={fade()} timing={timing} /> : null}
            <TransitionSeries.Sequence durationInFrames={page.durationFrames}>
              {renderPage(page as PageConfig)}
            </TransitionSeries.Sequence>
          </React.Fragment>
        ))}
      </TransitionSeries>
    </>
  );
};
