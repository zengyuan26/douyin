import { OverlayEngine } from "../components/OverlayEngine";
import config from "../effects-config.json";

export const ConfigDrivenOverlay: React.FC = () => {
  return <OverlayEngine videoSrc={config.videoSrc} effects={config.effects as any} />;
};
