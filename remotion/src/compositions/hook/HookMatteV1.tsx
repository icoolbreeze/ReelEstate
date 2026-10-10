import React from "react";
import { AbsoluteFill, OffthreadVideo, staticFile, useCurrentFrame } from "remotion";
import { ensureFonts } from "../../styles/fonts";
import { BrandBar } from "./BrandBar";
import { RoomCards } from "./RoomCards";
import { Title } from "./Title";
import { VeilCanvas } from "./VeilCanvas";
import { cameraProgress } from "./shared";

ensureFonts();

export type HookMatteProps = {
  background: string;
  matte: string;
  rooms: string[];
  brandLogos: string[];
  /** Dev helper: true = settled title on black (ink-box measurement); "plate" = plate only. */
  probe?: boolean | "plate";
};

const videoCover: React.CSSProperties = {
  width: "100%",
  height: "100%",
  objectFit: "cover",
};

/**
 * HookMatteV1 — 5-second talking-head price hook 「月租 4800」.
 * Source clip and matte are 1088x816 (4:3); cover onto 1440x1080 via
 * objectFit:"cover" (cover scale 1440/1088 ≈ 1.323529). Every layer shares
 * that base; the camera push is a CSS scale on top, origin at the chest.
 */
export const HookMatteV1: React.FC<HookMatteProps> = ({
  background,
  matte,
  rooms,
  brandLogos,
  probe = false,
}) => {
  const frame = useCurrentFrame();
  const p = cameraProgress(frame);
  const bgScale = 1 + 0.04 * p;
  const personScale = 1 + 0.07 * p;

  const bgSrc = staticFile(background);
  const matteSrc = staticFile(matte);

  const plate = (
    <AbsoluteFill
      style={{ transform: `scale(${bgScale})`, transformOrigin: "50% 55%" }}
    >
      <OffthreadVideo
        src={bgSrc}
        style={{ ...videoCover, filter: "brightness(0.92)" }}
      />
    </AbsoluteFill>
  );

  if (probe === true) {
    return (
      <AbsoluteFill style={{ backgroundColor: "#000" }}>
        <Title forceSettled />
      </AbsoluteFill>
    );
  }
  if (probe === "plate") {
    return <AbsoluteFill style={{ backgroundColor: "#000" }}>{plate}</AbsoluteFill>;
  }

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {/* Layer 1a: sharp background plate, original audio kept, dimmed 0.92 */}
      {plate}

      {/* Layer 1b: ghost veil (destination-in dilated matte), background push */}
      <AbsoluteFill
        style={{ transform: `scale(${bgScale})`, transformOrigin: "50% 55%" }}
      >
        <VeilCanvas background={background} matte={matte} />
      </AbsoluteFill>

      {/* Layer 2: room-photo cards */}
      <RoomCards rooms={rooms} />

      {/* Layer 3: title 「月租 4800」 */}
      <Title />

      {/* Layer 4: sharp matted person, faster push */}
      <AbsoluteFill
        style={{ transform: `scale(${personScale})`, transformOrigin: "50% 55%" }}
      >
        <OffthreadVideo transparent muted src={matteSrc} style={videoCover} />
      </AbsoluteFill>

      {/* Layer 5: brand bar (only when real logo files are provided) */}
      <BrandBar brandLogos={brandLogos} />
    </AbsoluteFill>
  );
};
