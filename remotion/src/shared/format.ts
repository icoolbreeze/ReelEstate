import type { Project } from "../types";

export const locationText = (p: Project): string => {
  const l = p.property.location;
  return [l.district, l.street, l.community].filter(Boolean).join(" ");
};

export const areaText = (p: Project): string => `${p.property.area.type} ${p.property.area.value}㎡`;

export const priceText = (p: Project): string =>
  `${p.price.type} ${p.price.value}${p.price.unit}（截至 ${p.price.valid_until}）`;
