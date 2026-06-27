import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { Scene1_Cover } from "./scenes/Scene1_Cover";
import { Scene2_ThreeTypes } from "./scenes/Scene2_ThreeTypes";
import { Scene3_WhyRise } from "./scenes/Scene3_WhyRise";
import { Scene4_Bottleneck } from "./scenes/Scene4_Bottleneck";
import { Scene5_ThreePaths } from "./scenes/Scene5_ThreePaths";
import { Scene6_HowSave } from "./scenes/Scene6_HowSave";
import { Scene7_HowToChoose } from "./scenes/Scene7_HowToChoose";
import { Scene8_Puzzle } from "./scenes/Scene8_Puzzle";

const T = linearTiming({ durationInFrames: 15 });

export const MainVideo: React.FC = () => {
  return (
    <TransitionSeries>
      <TransitionSeries.Sequence durationInFrames={180}>
        <Scene1_Cover />
      </TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={fade()} timing={T} />

      <TransitionSeries.Sequence durationInFrames={300}>
        <Scene2_ThreeTypes />
      </TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={fade()} timing={T} />

      <TransitionSeries.Sequence durationInFrames={240}>
        <Scene3_WhyRise />
      </TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={fade()} timing={T} />

      <TransitionSeries.Sequence durationInFrames={300}>
        <Scene4_Bottleneck />
      </TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={fade()} timing={T} />

      <TransitionSeries.Sequence durationInFrames={270}>
        <Scene5_ThreePaths />
      </TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={fade()} timing={T} />

      <TransitionSeries.Sequence durationInFrames={210}>
        <Scene6_HowSave />
      </TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={fade()} timing={T} />

      <TransitionSeries.Sequence durationInFrames={240}>
        <Scene7_HowToChoose />
      </TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={fade()} timing={T} />

      <TransitionSeries.Sequence durationInFrames={240}>
        <Scene8_Puzzle />
      </TransitionSeries.Sequence>
    </TransitionSeries>
  );
};
