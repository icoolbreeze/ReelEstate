import type { StyleName } from "../types";
import { MEDIASTORM } from "./mediastorm";
import { QIUZHI } from "./qiuzhi";
import type { StyleTokens } from "./types";

export const STYLES: Record<StyleName, StyleTokens> = { qiuzhi: QIUZHI, mediastorm: MEDIASTORM };
export const getStyle = (name?: string): StyleTokens => STYLES[(name as StyleName) ?? "qiuzhi"] ?? QIUZHI;
export type { StyleTokens };
