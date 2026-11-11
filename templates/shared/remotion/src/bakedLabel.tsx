// Fixed-resolution label images keep glyphs attached to the chip while the camera moves.
// Every result depends on text/style only; seeking and parallel rendering use identical pixels.
import React from "react";
import { cancelRender, continueRender, delayRender, Img } from "remotion";
import { PAL } from "./palette";
import { fontsReady } from "./fonts";

export const RASTER_SCALE = 3;
const FONT = "NotoSansSC4";
type Baked = { url: string; cssW: number; cssH: number; raster: string };
const cache = new Map<string, Baked>();
const MAX_CACHE = 256;
const FILL = "rgba(251,250,247,0.95)";

const roundRect = (ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) => {
  const rr = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.arcTo(x + w, y, x + w, y + h, rr);
  ctx.arcTo(x + w, y + h, x, y + h, rr);
  ctx.arcTo(x, y + h, x, y, rr);
  ctx.arcTo(x, y, x + w, y, rr);
  ctx.closePath();
};
const font = (ctx: CanvasRenderingContext2D, weight: number, px: number) => {
  ctx.font = `${weight} ${px}px ${FONT}`;
};
const measure = (ctx: CanvasRenderingContext2D, weight: number, px: number, text: string) => {
  font(ctx, weight, px);
  return ctx.measureText(text).width;
};
const makeCanvas = () => {
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("A 2D canvas is required for map labels");
  return { canvas, ctx };
};
const sizeCanvas = (canvas: HTMLCanvasElement, ctx: CanvasRenderingContext2D, w: number, h: number) => {
  canvas.width = Math.ceil(w * RASTER_SCALE);
  canvas.height = Math.ceil(h * RASTER_SCALE);
  ctx.scale(RASTER_SCALE, RASTER_SCALE);
};
const result = (canvas: HTMLCanvasElement): Baked => {
  const url = canvas.toDataURL("image/png");
  let hash = 2166136261;
  for (let i = 0; i < url.length; i++) hash = Math.imul(hash ^ url.charCodeAt(i), 16777619);
  return { url, cssW: canvas.width / RASTER_SCALE, cssH: canvas.height / RASTER_SCALE,
    raster: (hash >>> 0).toString(16) };
};

type ChipOptions = {
  fontPx?: number; weight?: number; color?: string; background?: string;
  padX?: number; padT?: number; padB?: number; radius?: number;
};
export const drawTextChip = (text: string, options: ChipOptions = {}): Baked => {
  const { fontPx = 26, weight = 700, color = PAL.ink, background = FILL,
    padX = 12, padT = 4, padB = 6, radius = 10 } = options;
  const { canvas, ctx } = makeCanvas();
  const w = 2 * padX + measure(ctx, weight, fontPx, text);
  const lineH = fontPx * 1.25;
  sizeCanvas(canvas, ctx, w, padT + lineH + padB);
  roundRect(ctx, 0, 0, canvas.width / RASTER_SCALE, canvas.height / RASTER_SCALE, radius);
  ctx.fillStyle = background;
  ctx.fill();
  font(ctx, weight, fontPx);
  ctx.fillStyle = color;
  ctx.textBaseline = "alphabetic";
  ctx.fillText(text, padX, padT + fontPx);
  return result(canvas);
};
export const drawPinChip = (text: string): Baked => drawTextChip(text);

export const drawRoomChip = (label: string, prefix = ""): Baked => {
  const { canvas, ctx } = makeCanvas();
  const small = 20, big = 24, padX = 12, padT = 3, padB = 4, gap = prefix ? 6 : 0;
  const w1 = measure(ctx, 500, small, prefix);
  const w2 = measure(ctx, 700, big, label);
  sizeCanvas(canvas, ctx, padX * 2 + w1 + gap + w2, padT + big * 1.25 + padB);
  roundRect(ctx, 0, 0, canvas.width / RASTER_SCALE, canvas.height / RASTER_SCALE, 9);
  ctx.fillStyle = FILL;
  ctx.fill();
  ctx.textBaseline = "alphabetic";
  const baseline = padT + big;
  font(ctx, 500, small);
  ctx.fillStyle = PAL.sub;
  ctx.fillText(prefix, padX, baseline);
  font(ctx, 700, big);
  ctx.fillStyle = PAL.ink;
  ctx.fillText(label, padX + w1 + gap, baseline);
  return result(canvas);
};

const drawFocusCard = (title: string, detail: string, distance: string, reserveDistance: string): Baked => {
  const { canvas, ctx } = makeCanvas();
  const titleW = measure(ctx, 700, 22, title);
  const detailW = measure(ctx, 500, 15, detail);
  const distanceW = Math.max(measure(ctx, 700, 18, distance), measure(ctx, 700, 18, reserveDistance));
  const width = Math.max(titleW, detailW + 8 + distanceW) + 28;
  const height = 6 + 22 * 1.2 + 18 * 1.3 + 8;
  sizeCanvas(canvas, ctx, width, height);
  roundRect(ctx, 0, 0, canvas.width / RASTER_SCALE, canvas.height / RASTER_SCALE, 10);
  ctx.fillStyle = PAL.card;
  ctx.fill();
  ctx.textBaseline = "alphabetic";
  font(ctx, 700, 22);
  ctx.fillStyle = PAL.ink;
  ctx.fillText(title, 14, 6 + 22);
  const baseline = 6 + 22 * 1.2 + 18;
  font(ctx, 500, 15);
  ctx.fillStyle = PAL.sub;
  ctx.fillText(detail, 14, baseline);
  font(ctx, 700, 18);
  ctx.fillStyle = PAL.accent;
  ctx.fillText(distance, 14 + detailW + 8, baseline);
  return result(canvas);
};

let fontReady: Promise<void> | null = null;
const waitFace = () => {
  if (!fontReady) fontReady = (async () => {
    await fontsReady;
    const specs = [
      ...[500, 600, 700, 800].map((w) => ({ font: `${w} 26px ${FONT}`, text: "客厅卧室双桥路站" })),
      { font: "italic 700 20px BarlowCond", text: "0123456789" },
      { font: "italic 600 14px BarlowCond", text: "ABCDEFGHIJKLMNOPQRSTUVWXYZ /" },
      { font: "700 38px AlimamaShuHeiTi", text: "客厅卧室" },
    ];
    const loaded = await Promise.all(specs.map((s) => document.fonts.load(s.font, s.text)));
    await document.fonts.ready;
    if (loaded.some((faces) => faces.length === 0) || !specs.every((s) => document.fonts.check(s.font, s.text)))
      throw new Error("A label font was not registered before raster drawing");
  })();
  return fontReady;
};

const BakedGraphic: React.FC<{ cacheKey: string; draw: () => Baked; shadow?: boolean; text?: string }> = ({ cacheKey, draw, shadow = true, text = "" }) => {
  const hit = cache.get(cacheKey) ?? null;
  const [baked, setBaked] = React.useState<Baked | null>(hit);
  const [handle] = React.useState<number | null>(() => hit ? null : delayRender("map label: " + cacheKey));
  const released = React.useRef(false);
  React.useEffect(() => {
    let live = true;
    const release = () => {
      if (handle !== null && !released.current) {
        released.current = true;
        continueRender(handle);
      }
    };
    const prepare = async () => {
      let value = cache.get(cacheKey);
      if (!value) {
        await waitFace();
        if (!live) return;
        value = draw();
        if (cache.size >= MAX_CACHE) cache.delete(cache.keys().next().value!);
        cache.set(cacheKey, value);
      }
      if (live) setBaked(value);
      release();
    };
    prepare().catch((err: unknown) => {
      if (live) cancelRender(err instanceof Error ? err : new Error(String(err)));
      else release();
    });
    return () => { live = false; release(); };
  }, [cacheKey, draw, handle]);
  if (!baked) return null;
  // Remotion Img also waits for data-URL decoding before the frame is captured.
  return <Img alt="" data-harmony-foreground="label" data-overlay-text={text} data-overlay-raster={baked.raster} src={baked.url} style={{
    width: baked.cssW, height: baked.cssH, display: "block", flex: "none",
    boxShadow: shadow ? PAL.shadow : undefined,
  }} />;
};

export const BakedPinChip: React.FC<{ text: string }> = ({ text }) => {
  const draw = React.useCallback(() => drawPinChip(text), [text]);
  const key = "pin:" + text;
  return <BakedGraphic key={key} cacheKey={key} draw={draw} text={text} />;
};
export const BakedRoomChip: React.FC<{ label: string; prefix?: string }> = ({ label, prefix = "" }) => {
  const draw = React.useCallback(() => drawRoomChip(label, prefix), [label, prefix]);
  const key = "room:" + JSON.stringify([prefix, label]);
  return <BakedGraphic key={key} cacheKey={key} draw={draw} text={[prefix, label].filter(Boolean).join(" ")} />;
};
export const BakedBadge: React.FC<{ text: string; options?: ChipOptions; shadow?: boolean }> = ({ text, options = {}, shadow = true }) => {
  const key = "badge:" + JSON.stringify([text, options]);
  const draw = React.useCallback(() => drawTextChip(text, JSON.parse(key.slice(6))[1] as ChipOptions), [text, key]);
  return <BakedGraphic key={key} cacheKey={key} draw={draw} shadow={shadow} text={text} />;
};
export const BakedFocusCard: React.FC<{ title: string; detail: string; distance: string; reserveDistance: string }> = ({ title, detail, distance, reserveDistance }) => {
  const key = "focus:" + JSON.stringify([title, detail, distance, reserveDistance]);
  const draw = React.useCallback(() => drawFocusCard(title, detail, distance, reserveDistance), [title, detail, distance, reserveDistance]);
  return <BakedGraphic key={key} cacheKey={key} draw={draw} text={[title, detail, distance].join(" ")} />;
};


export const annotationChipSize = (label: string, sub = "", variant: "scan" | "station" = "scan") => {
  const major = variant === "scan" ? 22 : 38;
  const pad = variant === "scan" ? 12 : 18;
  const index = variant === "scan" ? 24 : 32;
  const secondary = variant === "scan" ? 10 : 13;
  return {
    w: 2 * pad + index + 12 + Array.from(label).length * (major + 1) + (sub ? 12 + Array.from(sub).length * secondary : 0),
    h: variant === "scan" ? 44 : 64,
  };
};
const drawAnnotationChip = (index: number, label: string, sub: string, variant: "scan" | "station"): Baked => {
  const size = annotationChipSize(label, sub, variant);
  const { canvas, ctx } = makeCanvas();
  sizeCanvas(canvas, ctx, size.w, size.h);
  roundRect(ctx, 0, 0, size.w, size.h, variant === "scan" ? 8 : 12);
  ctx.fillStyle = variant === "scan" ? "rgba(20,18,16,0.84)" : "#7B2FF7";
  ctx.fill();
  if (variant === "station") {
    ctx.strokeStyle = "#2A0F4F"; ctx.lineWidth = 3; ctx.stroke();
  }
  const pad = variant === "scan" ? 12 : 18;
  const baseline = variant === "scan" ? 29 : 43;
  const numSize = variant === "scan" ? 20 : 26;
  const major = variant === "scan" ? 22 : 38;
  const minor = variant === "scan" ? 14 : 17;
  ctx.textBaseline = "alphabetic";
  ctx.font = "italic 700 " + numSize + "px BarlowCond";
  ctx.fillStyle = PAL.gold;
  const number = String(index).padStart(2, "0");
  ctx.fillText(number, pad, baseline);
  let x = pad + (variant === "scan" ? 24 : 32) + 12;
  ctx.font = "700 " + major + "px " + (variant === "scan" ? FONT : "AlimamaShuHeiTi");
  ctx.fillStyle = "#FBFBF8";
  ctx.fillText(label, x, baseline);
  x += ctx.measureText(label).width + 12;
  if (sub) {
    ctx.font = "italic 600 " + minor + "px BarlowCond";
    ctx.fillStyle = "#D6D9DF";
    for (const ch of Array.from(sub)) {
      ctx.fillText(ch, x, baseline);
      x += ctx.measureText(ch).width + 1.5;
    }
  }
  return result(canvas);
};
export const BakedAnnotationChip: React.FC<{ index: number; label: string; sub?: string; variant?: "scan" | "station" }> = ({ index, label, sub = "", variant = "scan" }) => {
  const key = "annotation:" + JSON.stringify([index, label, sub, variant]);
  const draw = React.useCallback(() => drawAnnotationChip(index, label, sub, variant), [index, label, sub, variant]);
  return <BakedGraphic key={key} cacheKey={key} draw={draw} text={[label, sub].filter(Boolean).join(" ")} />;
};

