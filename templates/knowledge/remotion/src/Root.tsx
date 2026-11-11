import React from "react";
import { Composition } from "remotion";
import { KnowledgeKoubo, TOTAL } from "./KnowledgeKoubo";
export const Root: React.FC = () => (
  <>
    <Composition id="KnowledgeKoubo" component={KnowledgeKoubo} durationInFrames={TOTAL} fps={30} width={1440} height={1080} />
  </>
);
