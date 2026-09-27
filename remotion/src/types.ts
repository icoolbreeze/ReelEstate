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

export type Project = {
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
