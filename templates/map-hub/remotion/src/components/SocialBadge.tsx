import React from "react";
import SOCIAL from "../episode/social.json";
import { ListingSocialBadge } from "../shared/SocialBadge";
export const SocialBadge: React.FC<{ start?: number }> = ({ start }) => <ListingSocialBadge start={start} rows={SOCIAL.rows} />;
