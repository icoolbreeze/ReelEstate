// Optional still-frame diagnostics. Records actual rendered foreground bounds;
// no changes to the visible composition or to the background-detail threshold.
import React from "react";
import { fontsReady } from "../fonts";
import { continueRender, delayRender, getInputProps, useCurrentFrame, useVideoConfig } from "remotion";

const AuditFrame: React.FC<{ frame: number }> = ({ frame }) => {
  const { width, height } = useVideoConfig();
  const [handle] = React.useState(() => delayRender("foreground bounds " + frame));
  React.useEffect(() => {
    let live = true, released = false;
    const release = () => {
      if (!released) { released = true; continueRender(handle); }
    };
    const run = async () => {
      await fontsReady;
      await document.fonts.ready;
      await new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
      await Promise.all(Array.from(document.images).map((img) => img.decode().catch(() => undefined)));
      if (!live) return;
      const foreground: { role: string; x: number; y: number; w: number; h: number; text?: string; raster?: string }[] = [];
      for (const el of Array.from(document.querySelectorAll<HTMLElement>("[data-harmony-foreground]"))) {
        let opacity = 1;
        for (let p: HTMLElement | null = el; p; p = p.parentElement) {
          const cs = getComputedStyle(p);
          if (cs.display === "none" || cs.visibility === "hidden") { opacity = 0; break; }
          opacity *= Number(cs.opacity);
        }
        if (opacity <= 0.01) continue;
        const r = el.getBoundingClientRect();
        const x = Math.max(0, r.left), y = Math.max(0, r.top);
        const w = Math.min(width, r.right) - x, h = Math.min(height, r.bottom) - y;
        if (w > 0 && h > 0) foreground.push({ role: el.dataset.harmonyForeground!, x, y, w, h, text: el.dataset.overlayText ?? el.textContent ?? "", raster: el.dataset.overlayRaster });
      }
      const worlds = Array.from(document.querySelectorAll<HTMLElement>("[data-harmony-world]")).map((el) => {
        const r = el.getBoundingClientRect();
        const x = Math.max(0,r.left), y = Math.max(0,r.top), w = Math.min(width,r.right)-x, h = Math.min(height,r.bottom)-y;
        return { kind: el.dataset.harmonyWorld!, source: el.dataset.worldSource ?? "", x,y,w,h };
      }).filter((r) => r.w > 0 && r.h > 0);
      console.warn("HARMONY_LAYERS:" + JSON.stringify({ version: 1, frame, width, height, foreground, worlds }));
      release();
    };
    run().catch((error: unknown) => { console.error(error); release(); });
    return () => { live = false; release(); };
  }, [frame, width, height, handle]);
  return null;
};

export const LayerAudit: React.FC = () => {
  const frame = useCurrentFrame();
  const enabled = typeof window !== "undefined" && (getInputProps() as { layerAudit?: boolean }).layerAudit === true;
  return enabled ? <AuditFrame key={frame} frame={frame} /> : null;
};
