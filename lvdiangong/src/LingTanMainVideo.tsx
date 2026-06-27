import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { Page1_Cover } from "./lingtan/Page1_Cover";
import { Page2_Comparison } from "./lingtan/Page2_Comparison";
import { Page3_Threats } from "./lingtan/Page3_Threats";

const T = linearTiming({ durationInFrames: 15 });

export const LingTanMainVideo: React.FC = () => {
  return (
    <TransitionSeries>
      <TransitionSeries.Sequence durationInFrames={180}>
        <Page1_Cover />
      </TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={fade()} timing={T} />

      <TransitionSeries.Sequence durationInFrames={300}>
        <Page2_Comparison />
      </TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={fade()} timing={T} />

      <TransitionSeries.Sequence durationInFrames={270}>
        <Page3_Threats />
      </TransitionSeries.Sequence>
    </TransitionSeries>
  );
};
