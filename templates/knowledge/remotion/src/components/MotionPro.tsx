// MotionPro — High-end Cinematic & Editorial Motion Kit for Knowledge Koubo.
// Inspired by video-shotcraft (Apache-2.0) and top-tier tech explainers (Mediastorm / Apple Keynote).
// Features:
// 1. Behind-the-Presenter Layering (Depth Parallax behind matted host HG_alpha)
// 2. FUI / HUD Reticle Precision Cards (Inspection HUD with corner brackets)
// 3. 3D Tilt Phone with Radial Ripple Waves
// 4. Illuminated Brand Lightboxes & Laser Blueprint Flow
import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { NUM, SANS, TITLE } from "../fonts";
import { E_OUT, backLite, lerp, seg } from "../lib";

export const W = 1440, H = 1080;

// ---------- Color & Material Tokens (Light Editorial Theme - Video-Shotcraft) ----------
export const C = {
  ink: "#0F172A",          // Deep Slate
  inkSoft: "#334155",      // Slate
  sub: "#64748B",          // Cool Grey
  blue: "#2563EB",         // Beike Royal Blue
  blueGlow: "rgba(37, 99, 235, 0.15)",
  blueDeep: "#1D4ED8",
  blueSoft: "rgba(37, 99, 235, 0.08)",
  gold: "#D97706",         // Warm Amber / Gold Accent
  goldSoft: "rgba(217, 119, 6, 0.08)",
  emerald: "#059669",      // Quality Emerald Green
  emeraldSoft: "rgba(5, 150, 105, 0.08)",
  cardGlass: "rgba(255, 255, 255, 0.92)", // Video-Shotcraft Frosted Glass
  hudBorder: "rgba(15, 23, 42, 0.08)",
  shadowLg: "0 20px 40px -10px rgba(15, 23, 42, 0.08), 0 4px 12px rgba(15, 23, 42, 0.04), 0 0 0 1px rgba(15, 23, 42, 0.05)",
  shadowSm: "0 6px 16px -2px rgba(15, 23, 42, 0.06), 0 0 0 1px rgba(15, 23, 42, 0.04)",
};

// ---------- High-Precision Count-Up Number with Settling Pulse (Rules §7.6 / Taste §6) ----------
export const CountUp: React.FC<{
  target: number;
  decimals?: number;
  local: number;
  start: number;
  duration?: number;
  suffix?: string;
  prefix?: string;
  style?: React.CSSProperties;
}> = ({ target, decimals = 0, local, start, duration = 26, suffix = "", prefix = "", style }) => {
  const p = seg(local, start, start + duration, E_OUT);
  const current = p * target;
  // 落定微脉冲 (Disney原理: 夸张/回稳 <= 1.035, 8帧内归位)
  const settle = seg(local, start + duration, start + duration + 8, E_OUT);
  const settlePop = settle < 1 && settle > 0 ? 1 + 0.035 * Math.sin(settle * Math.PI) : 1;
  const formatted = decimals > 0 ? current.toFixed(decimals) : Math.floor(current).toString();

  return (
    <span style={{
      display: "inline-block",
      fontVariantNumeric: "tabular-nums",
      transform: `scale(${settlePop})`,
      transformOrigin: "bottom right",
      ...style
    }}>
      {prefix}{formatted}{suffix}
    </span>
  );
};

// ---------- High-End Light Tech Editorial Canvas Background ----------
export const StudioCanvas: React.FC<{ variant?: "dark" | "blueprint" | "light" }> = () => {
  return (
    <AbsoluteFill style={{
      background: "linear-gradient(180deg, #F8FAFC 0%, #F1F5F9 55%, #E2E8F0 100%)",
      overflow: "hidden"
    }}>
      {/* Subtle warm center radial glow */}
      <div style={{
        position: "absolute",
        left: W / 2 - 600,
        top: H / 2 - 400,
        width: 1200,
        height: 800,
        borderRadius: "50%",
        background: "radial-gradient(circle, rgba(255, 255, 255, 0.95) 0%, rgba(241, 245, 249, 0.4) 65%, transparent 100%)",
        pointerEvents: "none"
      }} />

      {/* Crisp architectural technical grid */}
      <div style={{
        position: "absolute",
        inset: 0,
        backgroundImage: "linear-gradient(to right, rgba(15, 23, 42, 0.035) 1px, transparent 1px), linear-gradient(to bottom, rgba(15, 23, 42, 0.035) 1px, transparent 1px)",
        backgroundSize: "60px 60px",
        pointerEvents: "none"
      }} />

      {/* Ambient soft glow spots */}
      <div style={{
        position: "absolute",
        left: -150,
        top: -150,
        width: 600,
        height: 600,
        borderRadius: "50%",
        background: "radial-gradient(circle, rgba(37, 99, 235, 0.06) 0%, transparent 70%)",
        pointerEvents: "none"
      }} />
      <div style={{
        position: "absolute",
        right: -150,
        bottom: -150,
        width: 700,
        height: 700,
        borderRadius: "50%",
        background: "radial-gradient(circle, rgba(99, 102, 241, 0.05) 0%, transparent 70%)",
        pointerEvents: "none"
      }} />
    </AbsoluteFill>
  );
};

// =========================================================================
// 1. BEHIND-THE-PRESENTER ASSETS (Layer 2: Between Room & Matted Host)
// =========================================================================

// --- S01: Huge Editorial Title Behind Host Head & Shoulders ---
export const HookTitleBehind: React.FC<{ local: number }> = ({ local }) => {
  const enter = seg(local, 4, 22, E_OUT);
  const out = 1 - seg(local, 260, 280, E_OUT);
  if (out <= 0.01) return null;

  return (
    <AbsoluteFill style={{ opacity: out, pointerEvents: "none" }}>
      {/* Subtle host backlight glow with ambient depth diffusion */}
      <div style={{
        position: "absolute",
        left: W / 2 - 360,
        top: 130,
        width: 720,
        height: 720,
        borderRadius: 360,
        background: "radial-gradient(circle, rgba(255,255,255,0.96) 0%, rgba(37,99,235,0.10) 45%, rgba(0,0,0,0) 75%)",
        filter: "blur(32px)",
        opacity: enter
      }} />

      {/* Top micro tag — 次动作滞后 3 帧 */}
      <div style={{
        position: "absolute",
        left: 0,
        width: W,
        top: 110,
        display: "flex",
        justifyContent: "center",
        opacity: seg(local, 7, 24, E_OUT),
        transform: `translateY(${lerp(18, 0, seg(local, 7, 24, E_OUT))}px)`
      }}>
        <div style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 12,
          background: "rgba(255, 255, 255, 0.94)",
          backdropFilter: "blur(14px)",
          border: "1px solid rgba(15, 23, 42, 0.08)",
          color: "#0F172A",
          padding: "6px 20px",
          borderRadius: 999,
          boxShadow: C.shadowSm
        }}>
          <span style={{ width: 8, height: 8, borderRadius: 4, background: "#2563EB" }} />
          <span style={{ fontFamily: NUM, fontStyle: "italic", fontWeight: 800, fontSize: 22, letterSpacing: 4, color: "#2563EB" }}>EP.01</span>
          <span style={{ width: 1, height: 16, background: "rgba(15, 23, 42, 0.12)" }} />
          <span style={{ fontFamily: SANS, fontWeight: 700, fontSize: 20, letterSpacing: 2 }}>房产严选 · 正式开播</span>
        </div>
      </div>

      {/* HUGE CENTERED TITLE ACROSS THE SCREEN BEHIND THE HOST WITH CINEMATIC CONVERGENCE */}
      <div style={{
        position: "absolute",
        left: 0,
        width: W,
        top: 175,
        display: "flex",
        justifyContent: "center",
        opacity: enter,
        transform: `translateY(${lerp(28, 0, enter)}px)`
      }}>
        <div style={{
          fontFamily: TITLE,
          fontWeight: 700,
          fontSize: 128,
          lineHeight: 1.0,
          letterSpacing: lerp(16, 8, enter),
          color: "#0F172A",
          whiteSpace: "nowrap",
          textShadow: "0 10px 36px rgba(15, 23, 42, 0.16), 0 2px 4px rgba(255,255,255,0.9)"
        }}>
          小ONE · 房产严选
        </div>
      </div>

      {/* Baseline Pill Tag behind host */}
      <div style={{
        position: "absolute",
        left: 0,
        width: W,
        top: 315,
        display: "flex",
        justifyContent: "center",
        opacity: seg(local, 18, 30, E_OUT)
      }}>
        <div style={{
          background: "rgba(255, 255, 255, 0.94)",
          backdropFilter: "blur(16px)",
          border: "1px solid rgba(15, 23, 42, 0.08)",
          borderRadius: 14,
          padding: "8px 26px",
          boxShadow: C.shadowLg,
          display: "flex",
          alignItems: "center",
          gap: 14
        }}>
          <span style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 26, color: "#2563EB" }}>贝壳找房平台</span>
          <span style={{ width: 1, height: 18, background: "rgba(15, 23, 42, 0.12)" }} />
          <span style={{ fontFamily: SANS, fontWeight: 700, fontSize: 23, color: "#0F172A" }}>全城真房源筛选系统</span>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// --- S02: Symmetrical Inspection HUD Cards Emerging From Behind Shoulders ---
interface HudCardProps {
  num: string;
  title: string;
  subtitle: string;
  badge?: string;
  warning?: boolean;
  x: number;
  y: number;
  w: number;
  local: number;
  start: number;
  fromRight?: boolean;
}

const HudCard: React.FC<HudCardProps> = ({ num, title, subtitle, badge, warning = false, x, y, w, local, start, fromRight = false }) => {
  // 主卡片入场：平滑阻尼，过冲 <= 3%
  const enter = seg(local, start, start + 13, E_OUT);
  const pop = backLite(seg(local, start, start + 15));
  const offset = fromRight ? 36 : -36;

  // 次动作：四角取景框与角标滞后 4 帧优雅张开
  const sec = seg(local, start + 4, start + 14, E_OUT);

  return (
    <div style={{
      position: "absolute",
      left: x,
      top: y,
      width: w,
      opacity: enter,
      transform: `translateX(${lerp(offset, 0, enter)}px) scale(${lerp(0.96, 1, pop)})`,
      background: warning ? "rgba(255, 255, 255, 0.96)" : "rgba(255, 255, 255, 0.93)",
      backdropFilter: "blur(20px)",
      borderRadius: 18,
      border: warning ? "1.5px solid rgba(225, 29, 72, 0.28)" : "1.5px solid rgba(255, 255, 255, 0.9)",
      boxShadow: warning ? "0 20px 40px -10px rgba(225, 29, 72, 0.14), 0 0 0 1px rgba(225, 29, 72, 0.18)" : C.shadowLg,
      padding: "16px 20px",
      overflow: "hidden"
    }}>
      {/* Precision corner brackets (FUI Reticle) — 次动作平滑展开 */}
      <span style={{ position: "absolute", left: 6, top: 6, width: 10, height: 10, borderLeft: `2.5px solid ${warning ? "#E11D48" : "#2563EB"}`, borderTop: `2.5px solid ${warning ? "#E11D48" : "#2563EB"}`, opacity: sec, transform: `scale(${lerp(0.4, 1, sec)})` }} />
      <span style={{ position: "absolute", right: 6, top: 6, width: 10, height: 10, borderRight: `2.5px solid ${warning ? "#E11D48" : "#2563EB"}`, borderTop: `2.5px solid ${warning ? "#E11D48" : "#2563EB"}`, opacity: sec, transform: `scale(${lerp(0.4, 1, sec)})` }} />
      <span style={{ position: "absolute", left: 6, bottom: 6, width: 10, height: 10, borderLeft: `2.5px solid ${warning ? "#E11D48" : "#2563EB"}`, borderBottom: `2.5px solid ${warning ? "#E11D48" : "#2563EB"}`, opacity: sec, transform: `scale(${lerp(0.4, 1, sec)})` }} />
      <span style={{ position: "absolute", right: 6, bottom: 6, width: 10, height: 10, borderRight: `2.5px solid ${warning ? "#E11D48" : "#2563EB"}`, borderBottom: `2.5px solid ${warning ? "#E11D48" : "#2563EB"}`, opacity: sec, transform: `scale(${lerp(0.4, 1, sec)})` }} />

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{
            fontFamily: NUM,
            fontStyle: "italic",
            fontWeight: 800,
            fontSize: 22,
            color: warning ? "#E11D48" : "#2563EB",
            background: warning ? "rgba(225,29,72,0.08)" : "rgba(37,99,235,0.08)",
            padding: "2px 8px",
            borderRadius: 6
          }}>
            {num}
          </span>
          <span style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 30, color: "#0F172A" }}>{title}</span>
        </div>
        {badge && (
          <span style={{
            fontFamily: SANS,
            fontWeight: 800,
            fontSize: 15,
            color: warning ? "#E11D48" : "#2563EB",
            background: warning ? "rgba(225,29,72,0.08)" : "rgba(37,99,235,0.08)",
            border: warning ? "1px solid rgba(225,29,72,0.22)" : "1px solid rgba(37,99,235,0.22)",
            padding: "3px 8px",
            borderRadius: 6,
            letterSpacing: 0.5,
            opacity: sec,
            transform: `translateY(${lerp(6, 0, sec)}px)`
          }}>
            {badge}
          </span>
        )}
      </div>
      <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 18, color: "#64748B", paddingLeft: 4 }}>
        {subtitle}
      </div>
    </div>
  );
};

export const InspectionHudBehind: React.FC<{ local: number }> = ({ local }) => {
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {/* Behind-Presenter Central Radar Grid */}
      <div style={{
        position: "absolute",
        left: W / 2 - 380,
        top: 140,
        width: 760,
        height: 760,
        borderRadius: 380,
        border: "1px dashed rgba(37,99,235,0.15)",
        background: "radial-gradient(circle, rgba(37,99,235,0.05) 0%, rgba(255,255,255,0) 70%)",
        opacity: seg(local, 4, 18, E_OUT)
      }} />

      {/* LEFT WING (Emerging from behind Left Shoulder) — 安全避让边界 x=90, w=390 */}
      <HudCard
        num="01"
        title="空间与得房"
        subtitle="实测套内面积 · 规避公摊水分"
        badge="真实实测"
        x={90}
        y={210}
        w={390}
        local={local}
        start={12}
        fromRight={false}
      />
      <HudCard
        num="02"
        title="采光与噪音"
        subtitle="早晚日照测算 · 街道分贝实录"
        badge="现场量测"
        x={90}
        y={390}
        w={390}
        local={local}
        start={24}
        fromRight={false}
      />

      {/* RIGHT WING (Emerging from behind Right Shoulder) — 右侧避开 96px 碰撞区 x=950, w=390 (max 1340) */}
      <HudCard
        num="03"
        title="硬伤瑕疵披露"
        subtitle="采光遮挡 · 异味噪音如实讲清"
        badge="不避缺点"
        warning={true}
        x={950}
        y={210}
        w={390}
        local={local}
        start={36}
        fromRight={true}
      />
      <HudCard
        num="04"
        title="真实费用拆解"
        subtitle="租金单价 · 物业水电 · 隐形成本"
        badge="费用全清"
        x={950}
        y={390}
        w={390}
        local={local}
        start={48}
        fromRight={true}
      />
    </AbsoluteFill>
  );
};

// --- S06: Trust & Guarantee Shield Behind Host ---
export const TrustShieldBehind: React.FC<{ local: number }> = ({ local }) => {
  const enter = seg(local, 8, 22, E_OUT);

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {/* Central Official Guarantee Watermark Seal */}
      <div style={{
        position: "absolute",
        left: W / 2 - 300,
        top: 130,
        width: 600,
        height: 600,
        borderRadius: 300,
        border: "2px solid rgba(217,119,6,0.22)",
        background: "radial-gradient(circle, rgba(254,243,199,0.45) 0%, rgba(255,255,255,0) 70%)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "flex-start",
        paddingTop: 40,
        opacity: enter
      }}>
        <div style={{
          fontFamily: SANS,
          fontWeight: 800,
          fontSize: 22,
          letterSpacing: 6,
          color: C.gold,
          textTransform: "uppercase"
        }}>
          BEIKE QUALITY GUARANTEE
        </div>
        <div style={{
          marginTop: 8,
          fontFamily: TITLE,
          fontWeight: 700,
          fontSize: 48,
          color: C.gold,
          letterSpacing: 4
        }}>
          先C后B · 先行垫付
        </div>
      </div>

      {/* Left Shoulder: Senior Agent Role Card */}
      <div style={{
        position: "absolute",
        left: 90,
        top: 250,
        width: 410,
        opacity: seg(local, 14, 26, E_OUT),
        transform: `translateX(${lerp(-40, 0, seg(local, 14, 26, E_OUT))}px)`,
        background: "rgba(255, 255, 255, 0.93)",
        backdropFilter: "blur(20px)",
        borderRadius: 20,
        border: "1.5px solid rgba(37, 99, 235, 0.2)",
        boxShadow: C.shadowLg,
        padding: "20px 24px"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{ width: 56, height: 56, borderRadius: 16, overflow: "hidden", border: "2px solid rgba(37, 99, 235, 0.3)", position: "relative", flexShrink: 0, boxShadow: C.shadowSm }}>
            <Img src={staticFile("broll/flova/04_acn_3.png")} style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "28% 22%" }} />
          </div>
          <div>
            <div style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 32, color: C.ink }}>一线资深经纪人</div>
            <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 18, color: C.blue }}>全程带看 · 真实房况挑刺</div>
          </div>
        </div>
        <div style={{ marginTop: 12, fontFamily: SANS, fontWeight: 500, fontSize: 19, color: C.sub, lineHeight: 1.4 }}>
          扎根社区摸透楼盘底细，每套房如实指出缺陷，陪你看清每一个细节。
        </div>
      </div>

      {/* Right Shoulder: Store Manager Safety Role Card */}
      <div style={{
        position: "absolute",
        right: 90,
        top: 250,
        width: 410,
        opacity: seg(local, 26, 38, E_OUT),
        transform: `translateX(${lerp(40, 0, seg(local, 26, 38, E_OUT))}px)`,
        background: "rgba(255, 255, 255, 0.93)",
        backdropFilter: "blur(20px)",
        borderRadius: 20,
        border: "1.5px solid rgba(5, 150, 105, 0.2)",
        boxShadow: C.shadowLg,
        padding: "20px 24px"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{ width: 56, height: 56, borderRadius: 16, overflow: "hidden", border: "2px solid rgba(5, 150, 105, 0.3)", position: "relative", flexShrink: 0, boxShadow: C.shadowSm }}>
            <Img src={staticFile("broll/flova/04_acn_4.png")} style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "80% 28%" }} />
          </div>
          <div>
            <div style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 32, color: C.ink }}>合规风控店经理</div>
            <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 18, color: C.emerald }}>严审产权 · 资金安全监管</div>
          </div>
        </div>
        <div style={{ marginTop: 12, fontFamily: SANS, fontWeight: 500, fontSize: 19, color: C.sub, lineHeight: 1.4 }}>
          把控签约合同与交易规则，依托平台保障机制，守住交易安全底线。
        </div>
      </div>
    </AbsoluteFill>
  );
};

// --- S07: Outro Mission Cards Behind Host Shoulders ---
export const OutroMissionBehind: React.FC<{ local: number }> = ({ local }) => {
  const enter = seg(local, 6, 20, E_OUT);

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {/* Central Host Glow */}
      <div style={{
        position: "absolute",
        left: W / 2 - 300,
        top: 140,
        width: 600,
        height: 600,
        borderRadius: 300,
        background: "radial-gradient(circle, rgba(37,99,235,0.08) 0%, rgba(255,255,255,0.8) 50%, transparent 75%)",
        filter: "blur(20px)",
        opacity: enter
      }} />

      {/* Top Banner Behind Head */}
      <div style={{
        position: "absolute",
        left: 0,
        width: W,
        top: 120,
        display: "flex",
        justifyContent: "center",
        opacity: enter,
        transform: `translateY(${lerp(24, 0, enter)}px)`
      }}>
        <div style={{
          background: "rgba(255, 255, 255, 0.94)",
          backdropFilter: "blur(14px)",
          border: "1px solid rgba(15, 23, 42, 0.08)",
          color: C.ink,
          padding: "8px 24px",
          borderRadius: 999,
          boxShadow: C.shadowSm,
          display: "flex",
          alignItems: "center",
          gap: 12
        }}>
          <span style={{ width: 8, height: 8, borderRadius: 4, background: C.blue }} />
          <span style={{ fontFamily: SANS, fontWeight: 700, fontSize: 20, letterSpacing: 2 }}>
            官方政策解读 · 实地真房源筛选
          </span>
        </div>
      </div>

      {/* Left Shoulder: Channel Mission Card */}
      <div style={{
        position: "absolute",
        left: 90,
        top: 260,
        width: 400,
        opacity: seg(local, 12, 24, E_OUT),
        transform: `translateX(${lerp(-40, 0, seg(local, 12, 24, E_OUT))}px)`,
        background: "rgba(255, 255, 255, 0.93)",
        backdropFilter: "blur(20px)",
        borderRadius: 20,
        border: "1.5px solid rgba(37, 99, 235, 0.2)",
        boxShadow: C.shadowLg,
        padding: "20px 24px"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 44, height: 44, borderRadius: 12, background: "rgba(37, 99, 235, 0.08)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <span style={{ fontSize: 22 }}>📑</span>
          </div>
          <div>
            <div style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 30, color: C.ink }}>政策从官方文件出发</div>
            <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 17, color: C.blue }}>不盲从中介话术 · 客观解读</div>
          </div>
        </div>
        <div style={{ marginTop: 10, fontFamily: SANS, fontWeight: 500, fontSize: 18, color: C.sub, lineHeight: 1.4 }}>
          税费政策、购房资格、租房规范，每一条都有官方依据可循。
        </div>
      </div>

      {/* Right Shoulder: Interaction & Follow Card */}
      <div style={{
        position: "absolute",
        right: 90,
        top: 260,
        width: 400,
        opacity: seg(local, 24, 36, E_OUT),
        transform: `translateX(${lerp(40, 0, seg(local, 24, 36, E_OUT))}px)`,
        background: "rgba(255, 255, 255, 0.93)",
        backdropFilter: "blur(20px)",
        borderRadius: 20,
        border: "1.5px solid rgba(217, 119, 6, 0.2)",
        boxShadow: C.shadowLg,
        padding: "20px 24px"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 44, height: 44, borderRadius: 12, background: "rgba(217, 119, 6, 0.08)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <span style={{ fontSize: 22 }}>💬</span>
          </div>
          <div>
            <div style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 30, color: C.ink }}>成都租房买房找小ONE</div>
            <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 17, color: C.gold }}>欢迎关注 · 留言你的找房需求</div>
          </div>
        </div>
        <div style={{ marginTop: 10, fontFamily: SANS, fontWeight: 500, fontSize: 18, color: C.sub, lineHeight: 1.4 }}>
          关注这个账号，带你避开每一个租售踩坑点，挑到心仪好房。
        </div>
      </div>
    </AbsoluteFill>
  );
};


// =========================================================================
// 2. B-ROLL SCENES (S03 Platform, S04 Brands, S05 ACN Flow)
// =========================================================================

// --- S03: 3D Tilt Phone with Radial Ripple Waves & Giant Stat Cards ---
export const PlatformShowcase: React.FC<{ local: number }> = ({ local }) => {
  const enter = seg(local, 2, 16, E_OUT);

  return (
    <AbsoluteFill>
      <StudioCanvas />

      {/* Title */}
      <div style={{ position: "absolute", left: 100, top: 70, opacity: enter }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: 10, background: "rgba(37, 99, 235, 0.08)", padding: "6px 18px", borderRadius: 999, border: "1px solid rgba(37, 99, 235, 0.2)" }}>
          <span style={{ width: 8, height: 8, borderRadius: 4, background: C.blue }} />
          <span style={{ fontFamily: SANS, fontWeight: 800, fontSize: 20, color: C.blue }}>ABOUT 贝壳生态</span>
        </div>
        <div style={{ marginTop: 12, fontFamily: TITLE, fontWeight: 700, fontSize: 68, color: C.ink }}>
          连接线上线下 · 庞大房源底座
        </div>
      </div>

      {/* Left: 3D Tilt Phone with Animated Ripple Rings */}
      <div style={{
        position: "absolute",
        left: 120,
        top: 210,
        width: 380,
        height: 640,
        perspective: 1000,
        opacity: enter
      }}>
        {/* Radial Ripple Waves behind the phone */}
        {[0, 1, 2].map((ring) => {
          const t = (local * 0.02 + ring * 0.33) % 1;
          return (
            <div key={ring} style={{
              position: "absolute",
              left: 190 - 240 * t,
              top: 320 - 240 * t,
              width: 480 * t,
              height: 480 * t,
              borderRadius: 240 * t,
              border: "2px solid rgba(37, 99, 235, 0.15)",
              opacity: (1 - t) * 0.6
            }} />
          );
        })}

        {/* 3D Phone Shell - Ceramic Pearl White */}
        <div style={{
          width: 320,
          height: 620,
          borderRadius: 44,
          background: "#FFFFFF",
          boxShadow: "0 30px 60px -15px rgba(15, 23, 42, 0.15), 0 0 0 1px rgba(15, 23, 42, 0.08), 0 10px 20px -5px rgba(0,0,0,0.04)",
          transform: `rotateY(10deg) rotateX(4deg) translateY(${lerp(30, 0, enter)}px)`,
          padding: 10,
          overflow: "hidden"
        }}>
          <div style={{ width: "100%", height: "100%", borderRadius: 36, overflow: "hidden", background: "#FFF", border: "1px solid rgba(15, 23, 42, 0.06)" }}>
            <Img src={staticFile("broll/v2/beike_home_feed.jpg")} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
          </div>
        </div>
      </div>

      {/* Right Rail: Stat Cards (2026 Latest Interim Data) */}
      <div style={{ position: "absolute", left: 560, top: 220, width: 780, display: "flex", flexDirection: "column", gap: 20 }}>
        {/* Stat 1: 54万+ 经纪人 */}
        <div style={{
          background: "rgba(255, 255, 255, 0.94)",
          backdropFilter: "blur(20px)",
          borderRadius: 22,
          padding: "20px 32px",
          boxShadow: C.shadowLg,
          border: "1.5px solid rgba(37, 99, 235, 0.2)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          opacity: seg(local, 12, 24, E_OUT),
          transform: `translateX(${lerp(40, 0, seg(local, 12, 24, E_OUT))}px)`
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
            <div style={{ width: 56, height: 56, borderRadius: 16, background: "rgba(37, 99, 235, 0.08)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <span style={{ fontSize: 28 }}>👥</span>
            </div>
            <div>
              <div style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 34, color: C.ink }}>全平台专业经纪人</div>
              <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 18, color: C.sub }}>深耕社区 · 实地看房服务</div>
            </div>
          </div>
          <div style={{ textAlign: "right" }}>
            <CountUp
              target={54}
              decimals={0}
              local={local}
              start={14}
              duration={26}
              style={{ fontFamily: NUM, fontStyle: "italic", fontWeight: 800, fontSize: 68, color: C.blue }}
            />
            <span style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 34, color: C.blueDeep, marginLeft: 4 }}>万+</span>
          </div>
        </div>

        {/* Stat 2: 5.7万+ 活跃门店 */}
        <div style={{
          background: "rgba(255, 255, 255, 0.94)",
          backdropFilter: "blur(20px)",
          borderRadius: 22,
          padding: "20px 32px",
          boxShadow: C.shadowLg,
          border: "1.5px solid rgba(5, 150, 105, 0.2)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          opacity: seg(local, 24, 36, E_OUT),
          transform: `translateX(${lerp(40, 0, seg(local, 24, 36, E_OUT))}px)`
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
            <div style={{ width: 56, height: 56, borderRadius: 16, background: "rgba(5, 150, 105, 0.08)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <span style={{ fontSize: 28 }}>🏪</span>
            </div>
            <div>
              <div style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 34, color: C.ink }}>全国活跃线下门店</div>
              <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 18, color: C.sub }}>覆盖全域 · 邻里就近接待</div>
            </div>
          </div>
          <div style={{ textAlign: "right" }}>
            <CountUp
              target={5.7}
              decimals={1}
              local={local}
              start={26}
              duration={26}
              style={{ fontFamily: NUM, fontStyle: "italic", fontWeight: 800, fontSize: 68, color: C.emerald }}
            />
            <span style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 34, color: "#047857", marginLeft: 4 }}>万+</span>
          </div>
        </div>

        {/* VR Highlight Banner */}
        <div style={{
          background: "linear-gradient(135deg, rgba(255, 255, 255, 0.96) 0%, rgba(248, 250, 252, 0.96) 100%)",
          backdropFilter: "blur(20px)",
          borderRadius: 20,
          border: "1.5px solid rgba(37, 99, 235, 0.25)",
          padding: "16px 28px",
          boxShadow: C.shadowLg,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          color: C.ink,
          opacity: seg(local, 36, 48, E_OUT),
          transform: `translateX(${lerp(40, 0, seg(local, 36, 48, E_OUT))}px)`
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
            <div style={{ width: 72, height: 50, borderRadius: 10, overflow: "hidden", border: "1.5px solid rgba(37, 99, 235, 0.2)", flexShrink: 0, boxShadow: C.shadowSm }}>
              <Img src={staticFile("broll/flova/04_acn_2.png")} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            </div>
            <div>
              <div style={{ fontFamily: SANS, fontWeight: 700, fontSize: 24, color: C.ink }}>大部分主力房源支持 VR 全景看房</div>
              <div style={{ fontFamily: SANS, fontWeight: 500, fontSize: 16, color: C.sub, marginTop: 2 }}>
                三维全景实勘 · 户型朝向真实还原
              </div>
            </div>
          </div>
          <span style={{
            background: "rgba(37, 99, 235, 0.08)",
            border: "1px solid rgba(37, 99, 235, 0.2)",
            padding: "8px 20px",
            borderRadius: 999,
            fontFamily: SANS,
            fontWeight: 800,
            fontSize: 18,
            color: C.blue
          }}>
            线上实境还原
          </span>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// --- S04: Chengdu Brands Showcase (Illuminated Brand Cards & 1000+ Hero) ---
export const ChengduBrandsShowcase: React.FC<{ local: number }> = ({ local }) => {
  const enter = seg(local, 2, 16, E_OUT);

  const BRANDS = [
    { name: "链家", desc: "直营品质标杆", col: "#00AE66", file: "broll/v2/lianjia_mono.png", isMono: true },
    { name: "德佑", desc: "成都千店深耕", col: "#C8283C", file: "broll/v2/deyou_color.png" },
    { name: "21世纪不动产", desc: "全国特许加盟", col: "#B8860B", file: "broll/v2/c21.png" },
    { name: "中环地产", desc: "社区深耕品牌", col: "#C8283C", file: "broll/v2/zhonghuan_color.png" },
    { name: "富房不动产", desc: "成都本土20年", col: "#C8283C", file: "broll/v2/fufang_mono.png", isMono: true },
  ];

  return (
    <AbsoluteFill>
      <StudioCanvas />

      {/* Ambient Chengdu Skyline Backdrop */}
      <div style={{ position: "absolute", inset: 0, opacity: 0.16, pointerEvents: "none" }}>
        <Img src={staticFile("broll/flova/02_skyline.png")} style={{ width: "100%", height: "100%", objectFit: "cover", filter: "contrast(110%)" }} />
      </div>

      {/* Header */}
      <div style={{ position: "absolute", left: 0, width: W, top: 70, textAlign: "center", opacity: enter }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: 10, background: "rgba(37, 99, 235, 0.08)", padding: "6px 20px", borderRadius: 999, border: "1px solid rgba(37, 99, 235, 0.2)" }}>
          <span style={{ width: 8, height: 8, borderRadius: 4, background: C.blue }} />
          <span style={{ fontFamily: SANS, fontWeight: 800, fontSize: 20, color: C.blue }}>成都市房产经纪品牌生态</span>
        </div>
        <div style={{ marginTop: 12, fontFamily: TITLE, fontWeight: 700, fontSize: 64, color: C.ink }}>
          在成都，这些知名品牌全部打通接入
        </div>
      </div>

      {/* 5 Brand Cards in Grid */}
      <div style={{
        position: "absolute",
        left: 0,
        width: W,
        top: 220,
        display: "flex",
        justifyContent: "center",
        gap: 24,
        padding: "0 80px"
      }}>
        {BRANDS.map((b, i) => {
          const st = 10 + i * 5; // stagger 5 帧，符合 taste §7.6
          const q = seg(local, st, st + 12, E_OUT);
          const pop = backLite(seg(local, st, st + 14));

          return (
            <div key={b.name} style={{
              flex: 1,
              maxWidth: 240,
              height: 250,
              background: "rgba(255, 255, 255, 0.94)",
              backdropFilter: "blur(20px)",
              borderRadius: 22,
              border: "1.5px solid rgba(255, 255, 255, 0.9)",
              boxShadow: C.shadowLg,
              padding: "20px 16px",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "space-between",
              opacity: q,
              transform: `translateY(${lerp(50, 0, q)}px) scale(${lerp(0.9, 1, pop)})`
            }}>
              <div style={{
                width: 190,
                height: 84,
                background: "#F8FAFC",
                border: "1px solid rgba(15, 23, 42, 0.06)",
                borderRadius: 14,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: "6px 14px",
                boxShadow: "inset 0 1px 3px rgba(0,0,0,0.02)"
              }}>
                {b.isMono ? (
                  <div style={{
                    height: 60,
                    width: 160,
                    background: b.col,
                    WebkitMaskImage: `url(${staticFile(b.file)})`,
                    maskImage: `url(${staticFile(b.file)})`,
                    WebkitMaskSize: "contain",
                    maskSize: "contain",
                    WebkitMaskRepeat: "no-repeat",
                    maskRepeat: "no-repeat",
                    WebkitMaskPosition: "center",
                    maskPosition: "center"
                  }} />
                ) : (
                  <Img src={staticFile(b.file)} style={{ maxWidth: 160, maxHeight: 68, objectFit: "contain" }} />
                )}
              </div>
              <div style={{ textAlign: "center" }}>
                <div style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 26, color: C.ink }}>{b.name}</div>
                <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 16, color: C.sub, marginTop: 4 }}>{b.desc}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Hero Banner: 德佑在成都 1000+ 家门店 with Real Chengdu Storefront Photo */}
      <div style={{
        position: "absolute",
        left: 100,
        top: 505,
        width: 1240,
        background: "linear-gradient(135deg, rgba(255, 255, 255, 0.96) 0%, rgba(255, 245, 245, 0.96) 100%)",
        backdropFilter: "blur(20px)",
        borderRadius: 24,
        border: "2px solid rgba(225, 29, 72, 0.25)",
        boxShadow: C.shadowLg,
        padding: "20px 32px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        opacity: seg(local, 45, 60, E_OUT),
        transform: `translateY(${lerp(30, 0, seg(local, 45, 60, E_OUT))}px)`
      }}>
        {/* Left: Real Documentary Photo of Chengdu Street Storefront */}
        <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
          <div style={{ width: 240, height: 160, borderRadius: 16, overflow: "hidden", position: "relative", boxShadow: C.shadowSm, flexShrink: 0, border: "1.5px solid rgba(225, 29, 72, 0.2)" }}>
            <Img src={staticFile("broll/flova/03_store.png")} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            <div style={{
              position: "absolute",
              bottom: 6,
              left: 6,
              right: 6,
              background: "rgba(15,23,42,0.82)",
              backdropFilter: "blur(6px)",
              color: "#FFFFFF",
              borderRadius: 6,
              padding: "2px 8px",
              fontSize: 12,
              fontFamily: SANS,
              fontWeight: 700,
              textAlign: "center"
            }}>
              📍 成都社区门店实景
            </div>
          </div>
          <div>
            <div style={{ display: "inline-flex", alignItems: "center", gap: 8, background: "rgba(225, 29, 72, 0.08)", border: "1px solid rgba(225, 29, 72, 0.25)", padding: "4px 14px", borderRadius: 999, marginBottom: 8 }}>
              <span style={{ width: 6, height: 6, borderRadius: 3, background: "#E11D48" }} />
              <span style={{ fontFamily: SANS, fontWeight: 800, fontSize: 16, color: "#E11D48" }}>高密度社区覆盖</span>
            </div>
            <div style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 34, color: C.ink }}>德佑 · 成都品质加盟标杆</div>
            <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 19, color: C.sub, marginTop: 4 }}>
              扎根蓉城大街小巷 · 任意门店均可调取全城真实房源
            </div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexShrink: 0 }}>
          <span style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 30, color: C.inkSoft }}>成都已超</span>
          <CountUp
            target={1000}
            decimals={0}
            local={local}
            start={48}
            duration={28}
            suffix="+"
            style={{ fontFamily: NUM, fontStyle: "italic", fontWeight: 800, fontSize: 80, color: "#E11D48", lineHeight: 1 }}
          />
          <span style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 30, color: "#E11D48" }}>家门店</span>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// --- S05: ACN Blueprint Matrix with Flova Documentary Photos & Flowing Laser Stream ---
export const AcnBlueprintShowcase: React.FC<{ local: number }> = ({ local }) => {
  const enter = seg(local, 2, 16, E_OUT);

  const STEPS = [
    {
      num: "01",
      title: "房源录入",
      sub: "房屋信息建档核验",
      photo: "broll/flova/04_acn_1.png",
      tag: "实名建档",
      role: "录入人",
      highlight: "一房一码专属ID",
    },
    {
      num: "02",
      title: "VR 实勘",
      sub: "全景摄影激光测距",
      photo: "broll/flova/04_acn_2.png",
      tag: "实境还原",
      role: "摄影师",
      highlight: "三维全景空间实录",
    },
    {
      num: "03",
      title: "专职带看",
      sub: "精细带看客观分析",
      photo: "broll/flova/04_acn_3.png",
      tag: "实地挑刺",
      role: "经纪人",
      highlight: "直言瑕疵不避缺点",
    },
    {
      num: "04",
      title: "合规签约",
      sub: "合同风控安全监管",
      photo: "broll/flova/04_acn_4.png",
      tag: "先C后B",
      role: "店经理",
      highlight: "官方监管资金安全",
    },
  ];

  return (
    <AbsoluteFill>
      <StudioCanvas />

      {/* Header */}
      <div style={{ position: "absolute", left: 0, width: W, top: 55, textAlign: "center", opacity: enter }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: 10, background: "rgba(37, 99, 235, 0.08)", padding: "6px 20px", borderRadius: 999, border: "1px solid rgba(37, 99, 235, 0.2)" }}>
          <span style={{ width: 8, height: 8, borderRadius: 4, background: C.blue }} />
          <span style={{ fontFamily: SANS, fontWeight: 800, fontSize: 20, color: C.blue }}>ACN 经纪人合作网络</span>
        </div>
        <div style={{ marginTop: 10, fontFamily: TITLE, fontWeight: 700, fontSize: 62, color: C.ink }}>
          多品牌房源互通 · 专业分工协作
        </div>
      </div>

      {/* 4 Process Documentary Cards Connected by High-Tech Laser Stream */}
      <div style={{
        position: "absolute",
        left: 0,
        width: W,
        top: 205,
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        gap: 20,
        padding: "0 40px"
      }}>
        {STEPS.map((s, i) => {
          const st = 10 + i * 12;
          const q = seg(local, st, st + 12, E_OUT);
          const pop = backLite(seg(local, st, st + 14));

          // 焦点跟随机制：依据语音流转高亮当前步骤
          const activeIndex = local < 45 ? 0 : local < 88 ? 1 : local < 132 ? 2 : local < 178 ? 3 : 4;
          const isActive = activeIndex === i || activeIndex === 4;

          return (
            <React.Fragment key={s.num}>
              {/* Documentary Step Card with Interactive Focus Flow */}
              <div style={{
                width: 280,
                height: 440,
                background: "rgba(255, 255, 255, 0.95)",
                backdropFilter: "blur(20px)",
                borderRadius: 22,
                border: isActive ? "2px solid #2563EB" : "1.5px solid rgba(15, 23, 42, 0.08)",
                boxShadow: isActive ? "0 24px 48px -10px rgba(37,99,235,0.22), 0 0 0 1px #2563EB" : C.shadowLg,
                display: "flex",
                flexDirection: "column",
                overflow: "hidden",
                opacity: q * (isActive ? 1 : 0.88),
                transform: `translateY(${lerp(36, 0, q) - (isActive && activeIndex !== 4 ? 6 : 0)}px) scale(${lerp(0.94, 1, pop) * (isActive && activeIndex !== 4 ? 1.025 : 1)})`,
                transition: "border 0.3s, box-shadow 0.3s"
              }}>
                {/* Photo Header */}
                <div style={{ width: "100%", height: 215, position: "relative", overflow: "hidden" }}>
                  <Img src={staticFile(s.photo)} style={{ width: "100%", height: "100%", objectFit: "cover", transform: isActive ? "scale(1.03)" : "scale(1)" }} />
                  {/* Bottom Vignette & Gradient */}
                  <div style={{
                    position: "absolute",
                    inset: 0,
                    background: "linear-gradient(to bottom, rgba(15,23,42,0.06) 0%, transparent 40%, rgba(255,255,255,0.92) 100%)"
                  }} />

                  {/* Top-Left Step Badge */}
                  <div style={{
                    position: "absolute",
                    left: 12,
                    top: 12,
                    background: isActive ? "#2563EB" : "rgba(255, 255, 255, 0.92)",
                    backdropFilter: "blur(8px)",
                    border: isActive ? "1px solid #1D4ED8" : "1px solid rgba(37, 99, 235, 0.3)",
                    borderRadius: 8,
                    padding: "3px 10px",
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    boxShadow: C.shadowSm
                  }}>
                    <span style={{ width: 6, height: 6, borderRadius: 3, background: isActive ? "#FFFFFF" : C.blue }} />
                    <span style={{ fontFamily: NUM, fontStyle: "italic", fontWeight: 800, fontSize: 18, color: isActive ? "#FFFFFF" : C.blue }}>
                      {s.num}
                    </span>
                  </div>

                  {/* Top-Right Role Tag */}
                  <div style={{
                    position: "absolute",
                    right: 12,
                    top: 12,
                    background: isActive ? "rgba(37, 99, 235, 0.9)" : "rgba(37, 99, 235, 0.1)",
                    backdropFilter: "blur(8px)",
                    border: "1px solid rgba(37, 99, 235, 0.25)",
                    borderRadius: 999,
                    padding: "3px 12px",
                    color: isActive ? "#FFFFFF" : C.blue,
                    fontSize: 13,
                    fontFamily: SANS,
                    fontWeight: 700,
                    boxShadow: isActive ? "0 4px 12px rgba(37,99,235,0.3)" : "none"
                  }}>
                    {s.role}
                  </div>
                </div>

                {/* Info Body */}
                <div style={{ padding: "16px 20px 20px", display: "flex", flexDirection: "column", justifyContent: "space-between", flex: 1 }}>
                  <div>
                    <div style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 32, color: C.ink }}>{s.title}</div>
                    <div style={{ fontFamily: SANS, fontWeight: 500, fontSize: 17, color: C.sub, marginTop: 6 }}>{s.sub}</div>
                  </div>

                  {/* Benefit Pill */}
                  <div style={{
                    background: isActive ? "rgba(37, 99, 235, 0.08)" : "rgba(15, 23, 42, 0.04)",
                    border: isActive ? "1px solid rgba(37, 99, 235, 0.2)" : "1px solid rgba(15, 23, 42, 0.08)",
                    borderRadius: 10,
                    padding: "8px 12px",
                    display: "flex",
                    alignItems: "center",
                    gap: 8
                  }}>
                    <span style={{ width: 6, height: 6, borderRadius: 3, background: C.blue }} />
                    <span style={{ fontFamily: SANS, fontWeight: 600, fontSize: 15, color: isActive ? C.blue : C.inkSoft }}>{s.highlight}</span>
                  </div>
                </div>
              </div>

              {/* Connecting Laser Energy Tube */}
              {i < STEPS.length - 1 && (
                <div style={{
                  width: 28,
                  height: 6,
                  background: i < activeIndex ? "rgba(37, 99, 235, 0.35)" : "rgba(37, 99, 235, 0.12)",
                  position: "relative",
                  borderRadius: 3,
                  boxShadow: "inset 0 1px 2px rgba(0,0,0,0.06)",
                  opacity: q
                }}>
                  <div style={{
                    position: "absolute",
                    left: 0,
                    top: -2,
                    width: 14,
                    height: 10,
                    borderRadius: 5,
                    background: C.blue,
                    boxShadow: "0 0 12px #2563EB, 0 0 4px #FFFFFF",
                    transform: `translateX(${((local * 2.5 + i * 14) % 24)}px)`
                  }} />
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Bottom Takeaway Tag */}
      <div style={{
        position: "absolute",
        left: 0,
        width: W,
        top: 690,
        display: "flex",
        justifyContent: "center",
        opacity: seg(local, 60, 75, E_OUT)
      }}>
        <div style={{
          background: "rgba(255, 255, 255, 0.94)",
          backdropFilter: "blur(16px)",
          border: "1.5px solid rgba(15, 23, 42, 0.08)",
          borderRadius: 999,
          padding: "12px 36px",
          color: C.ink,
          fontFamily: SANS,
          fontWeight: 700,
          fontSize: 24,
          boxShadow: C.shadowSm
        }}>
          💡 各司其职，不藏房源 · 在一家店就能看全成都好房
        </div>
      </div>
    </AbsoluteFill>
  );
};
