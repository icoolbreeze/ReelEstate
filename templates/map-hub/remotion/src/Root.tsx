import React from "react";
import { Composition } from "remotion";
import { LABEL_PROBE, LabelJitterProbe, MapHubKoubo, TOTAL } from "./MapHubKoubo";
import { MapHubHeygen, HEYGEN_TOTAL } from "./HeygenCut";
import { Opener, DURATION } from "./components/opener/Opener";
export const Root: React.FC = () => (
  <>
    <Composition id="MapHubKoubo" component={MapHubKoubo} durationInFrames={TOTAL} fps={30} width={1440} height={1080} />
    <Composition id="MapHubHeygen" component={MapHubHeygen} durationInFrames={HEYGEN_TOTAL} fps={30} width={1440} height={1080} />
    <Composition id="Opener" component={Opener} durationInFrames={DURATION} fps={30} width={1440} height={1080} defaultProps={{ theme: "light" as const, map: "flovaSat3Db" as const, strip: true, chrome: true }} />
    <Composition id="LabelJitterProbe" component={LabelJitterProbe} durationInFrames={Math.max(1, LABEL_PROBE.n)} fps={30} width={1440} height={1080} defaultProps={{ mode: "baked" as const }} />
  </>
);
