import React from "react";
import { Composition, type CalculateMetadataFunction } from "remotion";
import { HookMatteV1 } from "./compositions/hook/HookMatteV1";
import { NewHomeVideo } from "./compositions/new-home/NewHomeVideo";
import { RentalVideo } from "./compositions/rental/RentalVideo";
import { ResaleVideo } from "./compositions/resale/ResaleVideo";
import { SAMPLE } from "./sampleProjects";
import { totalFrames } from "./shared/timeline";
import type { Category, Project, Ratio } from "./types";

// Default 4:3 1440x1080; vertical variants 3:4 and 9:16.
export const RATIOS: Record<Ratio, { width: number; height: number }> = {
  "4x3": { width: 1440, height: 1080 },
  "3x4": { width: 1080, height: 1440 },
  "9x16": { width: 1080, height: 1920 },
};
const FPS = 30;

const CATEGORIES: { name: string; category: Category; component: React.FC<Project> }[] = [
  { name: "Rental", category: "rental", component: RentalVideo },
  { name: "Resale", category: "resale", component: ResaleVideo },
  { name: "NewHome", category: "new-home", component: NewHomeVideo },
];

// Duration follows narration (TTS durations from audio/segments.json if present).
const calculateMetadata: CalculateMetadataFunction<Project> = ({ props }) => {
  const fps = props.export?.fps ?? FPS;
  return { fps, durationInFrames: totalFrames(props, fps) };
};

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="HookMatteV1"
      component={HookMatteV1}
      width={1440}
      height={1080}
      fps={FPS}
      durationInFrames={150}
      defaultProps={{
        background: "hook_matte/clip1.mp4",
        matte: "hook_matte/clip1_alpha.webm",
        rooms: [
          "hook_matte/rooms/living.jpg",
          "hook_matte/rooms/bedroom.jpg",
          "hook_matte/rooms/kitchen.jpg",
        ],
        brandLogos: [],
      }}
    />
    {CATEGORIES.flatMap((c) =>
      (Object.keys(RATIOS) as Ratio[]).map((ratio) => (
        <Composition
          key={`${c.name}-${ratio}`}
          id={`${c.name}-${ratio}`}
          component={c.component}
          width={RATIOS[ratio].width}
          height={RATIOS[ratio].height}
          fps={FPS}
          durationInFrames={FPS * 10}
          defaultProps={SAMPLE[c.category]}
          calculateMetadata={calculateMetadata}
        />
      )),
    )}
  </>
);
