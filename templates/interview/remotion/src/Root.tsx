import React from "react";
import { Composition } from "remotion";
import { FPS, HEIGHT, InterviewLounge, TOTAL, WIDTH } from "./InterviewLounge";

export const Root: React.FC = () => (
  <Composition id="InterviewLounge" component={InterviewLounge} durationInFrames={TOTAL} fps={FPS} width={WIDTH} height={HEIGHT} />
);
