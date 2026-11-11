import React from "react";
import EP from "../episode/episode.json";
import BRANDS from "../episode/brands.json";
import { KnowledgeBrandStrip } from "../shared/BrandStrip";
export const BrandStrip: React.FC<{ dark?: number }> = ({ dark }) => <KnowledgeBrandStrip dark={dark} brands={BRANDS} episode={EP} />;
