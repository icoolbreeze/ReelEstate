// Mirrors pipeline/schema/*.json. Keep in sync with templates/ and check.py.
export type Category = "rental" | "resale" | "new-home";
export type Ratio = "4x3" | "3x4" | "9x16";
export type PresenterMode = "fullscreen" | "pip-left" | "pip-right";

export type Card = { title: string; lines?: string[] };

export type Segment = {
  id: string;
  text: string;
  presenter: PresenterMode;
  presenter_clip?: string; // relative to project dir (= Remotion public dir)
  clip_start?: number; // seconds
  broll?: string; // image or video, relative to project dir
  visual_label?: string; // e.g. 效果图 / 非实景
  card?: Card;
};

export type AudioSegment = { id: string; text: string; file: string; duration: number | null };

export type Project = RenderExtras & {
  schema_version?: number;
  id: string;
  category: Category;
  title: string;
  is_example?: boolean;
  ai_voice?: boolean;
  ad_disclosure?: boolean;
  export?: { default_ratio?: Ratio; ratios?: Ratio[]; fps?: number };
  property: {
    property_type: string;
    layout?: string;
    area: { type: "建筑面积" | "套内建筑面积"; value: number };
    location: { city: string; district: string; street?: string; community?: string };
    floor?: string;
    orientation?: string;
    decoration?: string;
    build_year?: number | null;
  };
  price: { type: string; value: number; unit: string; valid_until: string };
  agency: { full_name: string; record_no?: string };
  agent: { name: string; certified_on_camera: boolean };
  highlights?: string[];
  drawbacks: string[];
  nearby?: { name: string; distance_m?: number; basis?: string; status?: string }[];
  tts?: { voice?: string; mode?: string };
  narration: { segments: Segment[] };
  audio?: AudioSegment[]; // injected by pipeline/render.py from audio/segments.json
  rental?: { rent_type?: string; room_desc?: string; payment_terms?: string; service_fee?: string; utilities?: string };
  resale?: { verification_code?: string; owner_consent?: boolean; property_right?: string };
  new_home?: {
    project_name?: string;
    developer_full_name?: string;
    presale_permit_no?: string;
    renderings?: { file: string; label: string }[];
    planned_facilities?: { name: string; status: string }[];
  };
};

// ---- v5: one-sentence workflow (shots.json-driven rendering) ----
// Mirrors pipeline/schema/shots.json + fields injected by pipeline/render.py.
export type StyleName = "qiuzhi" | "mediastorm";
export type ShotPresenter = PresenterMode | "none";
export type ShotType = "presenter" | "wall" | "map" | "room" | "broll" | "spec" | "number" | "outro";

export type RoomInfo = { zh: string; en?: string; pill?: string; index?: number; total?: number };
export type SpecInfo = { title: string; lines: string[]; variant?: "default" | "warning" };
export type LocationInfo = { main: string; sub?: string };
export type NumberInfo = { value: string; unit?: string; caption?: string; over?: boolean };

export type Shot = {
  id: string;
  segment: string; // narration segment id; segment duration is split across its shots by weight
  weight?: number;
  type: ShotType;
  presenter?: ShotPresenter;
  media?: string; // image/video relative to project dir
  locator?: string; // floorplan room key to highlight
  push?: boolean; // slow push-in on media
  room?: RoomInfo;
  spec?: SpecInfo;
  location?: LocationInfo;
  number?: NumberInfo;
  cta?: string;
};

export type FloorplanRoom = { key: string; zh: string; x: number; y: number; w: number; h: number };
export type ShotsDoc = {
  style?: StyleName;
  generated_by?: string;
  shots: Shot[];
  floorplan?: { schematic?: boolean; rooms: FloorplanRoom[] };
};

export type WallCard = {
  id: string;
  cover?: string;
  community: string;
  layout?: string;
  area?: string;
  rent?: string;
  orientation?: string;
  floor?: string;
};
export type WallDoc = { cards: WallCard[]; picked: string | null; blur_others?: boolean };

export type MediaInfo = { file: string; ai?: boolean; source_tag?: string; attribution?: string };

export type RenderExtras = {
  style?: StyleName;
  shots?: ShotsDoc;
  wall?: WallDoc;
  media?: Record<string, MediaInfo>; // keyed by relative file path (from assets/manifest.json)
  presenter_clip?: string; // default talking-head clip for presenter shots
  bgm?: string;
  sfx?: Record<string, string>;
  map?: { image: string; attribution: string };
};
