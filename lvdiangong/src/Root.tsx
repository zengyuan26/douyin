import { Composition } from "remotion";
import { loadFont } from "@remotion/google-fonts/NotoSansSC";
import { MainVideo } from "./MainVideo";
import { DemoFX } from "./scenes/DemoFX";
import { OverlayFX } from "./scenes/OverlayFX";
import { ConfigDrivenOverlay } from "./scenes/ConfigDrivenOverlay";
import { LingTanYuanQuanOverlay } from "./scenes/LingTanYuanQuanOverlay";
import { LingTanMainVideo } from "./LingTanMainVideo";
import { TemplateRenderer, calcTotalFrames } from "./templates/TemplateRenderer";
import * as configs from "./configs";
import { staticFile } from "remotion";

loadFont("normal", {
  weights: ["400", "700"],
  ignoreTooManyRequestsWarning: true,
});

export const RemotionRoot: React.FC = () => {
  return (
    <>
      {/* === Template compositions (auto from configs/index.ts) === */}
      {Object.values(configs).map((config) => {
        const hasAudio = config.id === "lingtan-jujianren";
        return (
          <Composition
            key={config.id}
            id={config.id}
            component={() => (
              <TemplateRenderer
                config={config}
                audioSrc={hasAudio ? staticFile("audio.mp3") : undefined}
              />
            )}
            durationInFrames={hasAudio ? 7895 : calcTotalFrames(config)}
            fps={config.fps ?? 30}
            width={config.width ?? 1920}
            height={config.height ?? 1080}
          />
        );
      })}

      {/* === Legacy hardcoded === */}
      <Composition
        id="LvDianZhiGong-Legacy"
        component={MainVideo}
        durationInFrames={1875}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="LingTanZeroPark-Legacy"
        component={LingTanMainVideo}
        durationInFrames={780}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="DemoFX"
        component={DemoFX}
        durationInFrames={300}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="OverlayFX"
        component={OverlayFX}
        durationInFrames={450}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="ConfigDrivenOverlay"
        component={ConfigDrivenOverlay}
        durationInFrames={450}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="LingTanYuanQuanOverlay"
        component={LingTanYuanQuanOverlay}
        durationInFrames={450}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
