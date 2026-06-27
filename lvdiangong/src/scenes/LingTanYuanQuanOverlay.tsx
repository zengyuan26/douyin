import { OverlayEngine } from "../components/OverlayEngine";
import config from "../lingtangyuanquan-config.json";

export const LingTanYuanQuanOverlay: React.FC = () => {
  return <OverlayEngine videoSrc={config.videoSrc} effects={config.effects as any} />;
};
