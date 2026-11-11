import { loadFont } from "@remotion/fonts";
import { staticFile } from "remotion";
const fontLoads: Promise<void>[] = [
  loadFont({ family: "AlimamaShuHeiTi", url: staticFile("fonts/AlimamaShuHeiTi/AlimamaShuHeiTi-Bold.woff2"), weight: "700", format: "woff2" }),
  loadFont({ family: "NotoSansSC4", url: staticFile("fonts/NotoSansSC/NotoSansSC.ttf"), weight: "100 900", format: "truetype" }),
];
for (const [w, n] of [["600", "SemiBold"], ["700", "Bold"], ["800", "ExtraBold"]] as const) {
  fontLoads.push(loadFont({ family: "BarlowCond", url: staticFile(`fonts/BarlowCondensed/BarlowCondensed-${n}Italic.ttf`), weight: w, style: "italic", format: "truetype" }));
}
// @remotion/fonts registers FontFace only after fetching it. document.fonts.ready
// alone can resolve before that registration, so raster drawing awaits these loads.
export const fontsReady = Promise.all(fontLoads).then(() => undefined);
export const TITLE = `AlimamaShuHeiTi, NotoSansSC4, sans-serif`;
export const SANS = `NotoSansSC4, "Noto Sans CJK SC", sans-serif`;
export const NUM = `BarlowCond, NotoSansSC4, sans-serif`;

