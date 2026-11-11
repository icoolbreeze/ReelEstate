import React from "react";
import EP from "../episode/episode.json";
import BRANDS from "../episode/brands.json";
import { ListingBrandStrip } from "../shared/BrandStrip";
export const BrandStrip: React.FC<{ dark?: number }> = ({ dark }) => <ListingBrandStrip dark={dark} brands={BRANDS} episode={EP} />;
