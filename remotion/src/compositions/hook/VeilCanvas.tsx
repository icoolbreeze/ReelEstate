import React, { useEffect, useRef } from "react";
import {
  continueRender,
  delayRender,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

// Ghost / double-exposure veil rendered on a canvas.
//
// CSS mix-blend-mode does NOT accept the Porter-Duff operator "destination-in"
// (Chromium drops the declaration; only <blend-mode> keywords are valid), so the
// exact compositing the spec requires is done with 2D canvas, which supports
// globalCompositeOperation = "destination-in":
//   1. plate drawn with filter blur(18px) brightness(0.85)
//   2. alpha clipped (destination-in) by the matte, cover-scaled 1.03 and
//      filtered blur(6px), so the matte alpha dilates ~12px.
// The veil wrapper (in HookMatteV1) applies the BACKGROUND push
// (1.00 -> 1.04, origin 50% 55%), matching the plate it hides behind.

const CANVAS_W = 1440;
const CANVAS_H = 1080;

// dest rects after cover (1440/1088), with extra scales:
const PLATE_DRAW = { x: -54, y: -54, w: 1548, h: 1188 }; // cover * 1.075, keeps blur edges opaque
const MATTE_DRAW = { x: -21.6, y: -16.2, w: 1483.2, h: 1112.4 }; // cover * 1.03

const seekTo = (el: HTMLVideoElement, time: number): Promise<void> =>
  new Promise((resolve) => {
    if (Math.abs(el.currentTime - time) < 0.001) {
      resolve();
      return;
    }
    const onSeeked = () => {
      el.removeEventListener("seeked", onSeeked);
      resolve();
    };
    el.addEventListener("seeked", onSeeked);
    el.currentTime = time;
  });

const drawVeil = (
  canvas: HTMLCanvasElement,
  plate: HTMLVideoElement,
  matte: HTMLVideoElement,
) => {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.globalCompositeOperation = "source-over";
  ctx.clearRect(0, 0, CANVAS_W, CANVAS_H);

  ctx.save();
  ctx.filter = "blur(18px) brightness(0.85)";
  ctx.drawImage(plate, PLATE_DRAW.x, PLATE_DRAW.y, PLATE_DRAW.w, PLATE_DRAW.h);
  ctx.restore();

  ctx.save();
  ctx.globalCompositeOperation = "destination-in";
  ctx.filter = "blur(6px)";
  ctx.drawImage(matte, MATTE_DRAW.x, MATTE_DRAW.y, MATTE_DRAW.w, MATTE_DRAW.h);
  ctx.restore();
};

const hiddenVideo: React.CSSProperties = {
  position: "absolute",
  width: 4,
  height: 4,
  top: -10,
  left: -10,
  opacity: 0.01,
  pointerEvents: "none",
};

export const VeilCanvas: React.FC<{ background: string; matte: string }> = ({
  background,
  matte,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const plateRef = useRef<HTMLVideoElement>(null);
  const matteRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    let cancelled = false;
    const handle = delayRender(`veil canvas seek @frame ${frame}`);
    const time = frame / fps;
    Promise.all([
      seekTo(plateRef.current as HTMLVideoElement, time),
      seekTo(matteRef.current as HTMLVideoElement, time),
    ])
      .then(() => {
        if (cancelled) return;
        drawVeil(
          canvasRef.current as HTMLCanvasElement,
          plateRef.current as HTMLVideoElement,
          matteRef.current as HTMLVideoElement,
        );
        continueRender(handle);
      })
      .catch(() => continueRender(handle));
    return () => {
      cancelled = true;
      continueRender(handle);
    };
  }, [frame, fps]);

  return (
    <>
      <video
        ref={plateRef}
        src={staticFile(background)}
        muted
        playsInline
        preload="auto"
        style={hiddenVideo}
      />
      <video
        ref={matteRef}
        src={staticFile(matte)}
        muted
        playsInline
        preload="auto"
        style={hiddenVideo}
      />
      <canvas
        ref={canvasRef}
        width={CANVAS_W}
        height={CANVAS_H}
        style={{ display: "block", width: "100%", height: "100%" }}
      />
    </>
  );
};
