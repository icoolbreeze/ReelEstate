import type { StyleName } from "../types";
import { MEDIASTORM } from "./mediastorm";
import type { StyleTokens } from "./types";

export const STYLES: Record<StyleName, StyleTokens> = { mediastorm: MEDIASTORM };
export const getStyle = (name?: string): StyleTokens => STYLES[(name as StyleName)] ?? MEDIASTORM;
export type { StyleTokens };
