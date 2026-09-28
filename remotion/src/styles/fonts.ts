// Bundled fonts (free for commercial use; licenses next to the files in src/assets/fonts/<family>/):
//   Noto Sans SC (SIL OFL 1.1), Montserrat (SIL OFL 1.1), Barlow Condensed (SIL OFL 1.1),
//   阿里妈妈数黑体 AlimamaShuHeiTi (Alimama free commercial licence, LICENSE.txt; official woff2, unmodified).
// Imported through webpack so they work regardless of --public-dir (= project dir).
import { cancelRender, continueRender, delayRender } from "remotion";
import shuhei from "../assets/fonts/AlimamaShuHeiTi/AlimamaShuHeiTi-Bold.woff2";
import barlowBoldIt from "../assets/fonts/BarlowCondensed/BarlowCondensed-BoldItalic.woff2";
import barlowSemiIt from "../assets/fonts/BarlowCondensed/BarlowCondensed-SemiBoldItalic.woff2";
import montItalic from "../assets/fonts/Montserrat/Montserrat-Italic-VF.woff2";
import mont from "../assets/fonts/Montserrat/Montserrat-VF.woff2";
import noto from "../assets/fonts/NotoSansSC/NotoSansSC-VF.woff2";

type Face = { family: string; url: string; weight: string; style?: string };
const FACES: Face[] = [
  { family: "RE Noto Sans SC", url: noto, weight: "100 900" },
  { family: "RE Montserrat", url: mont, weight: "100 900" },
  { family: "RE Montserrat", url: montItalic, weight: "100 900", style: "italic" },
  { family: "RE ShuHeiTi", url: shuhei, weight: "700" },
  { family: "RE Barlow Condensed", url: barlowSemiIt, weight: "600", style: "italic" },
  { family: "RE Barlow Condensed", url: barlowBoldIt, weight: "700", style: "italic" },
];

let started = false;
export const ensureFonts = (): void => {
  if (started || typeof document === "undefined") return;
  started = true;
  const handle = delayRender("Loading bundled fonts");
  Promise.all(
    FACES.map((f) => {
      const face = new FontFace(f.family, `url(${f.url}) format("woff2")`, { weight: f.weight, style: f.style ?? "normal" });
      return face.load().then((loaded) => {
        (document.fonts as unknown as { add: (f: FontFace) => void }).add(loaded);
      });
    }),
  )
    .then(() => continueRender(handle))
    .catch((err) => cancelRender(err));
};

export const F = {
  sans: '"RE Noto Sans SC", "Noto Sans SC", "Microsoft YaHei", sans-serif',
  latin: '"RE Montserrat", "RE Noto Sans SC", sans-serif',
  shuhei: '"RE ShuHeiTi", "RE Noto Sans SC", sans-serif',
  barlow: '"RE Barlow Condensed", "RE Noto Sans SC", sans-serif',
};
