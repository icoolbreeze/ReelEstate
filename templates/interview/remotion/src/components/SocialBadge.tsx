import React from "react";
import SOCIAL from "../episode/social.json";
import { KnowledgeSocialBadge } from "../shared/SocialBadge";

export const SocialBadge: React.FC<{ start?: number }> = ({ start }) => (
  <KnowledgeSocialBadge start={start} rows={SOCIAL.rows} />
);
