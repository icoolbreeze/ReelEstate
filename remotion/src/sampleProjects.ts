// Default props for Remotion Studio when no --props is given. 示例数据（虚构）。
// Real renders always pass the project's project.json via pipeline/render.py.
import type { Category, Project } from "./types";

const base = (category: Category): Project => ({
  id: "2026-01-01-sample",
  category,
  title: "示例数据",
  is_example: true,
  property: {
    property_type: "普通住宅",
    layout: "2室1厅1卫",
    area: { type: "建筑面积", value: 89 },
    location: { city: "示例市", district: "示例区", street: "示例街道", community: "示例小区" },
  },
  price: { type: "挂牌价", value: 300, unit: "万元", valid_until: "2099-12-31" },
  agency: { full_name: "示例房地产经纪有限公司" },
  agent: { name: "示例", certified_on_camera: true },
  drawbacks: ["示例缺点"],
  narration: {
    segments: [
      { id: "s01", text: "这是示例开场，全屏口播。", presenter: "fullscreen" },
      { id: "s02", text: "这里切到右下小窗，展示信息卡。", presenter: "pip-right", card: { title: "房源信息", lines: ["2室1厅1卫", "建筑面积 89㎡"] } },
      { id: "s03", text: "左下小窗讲解细节。", presenter: "pip-left" },
    ],
  },
});

export const SAMPLE: Record<Category, Project> = {
  rental: {
    ...base("rental"),
    price: { type: "月租金", value: 3200, unit: "元/月", valid_until: "2099-12-31" },
    rental: { rent_type: "整租", payment_terms: "押一付三" },
  },
  resale: { ...base("resale"), resale: { verification_code: "示例核验编码", owner_consent: true } },
  "new-home": {
    ...base("new-home"),
    price: { type: "备案均价", value: 32000, unit: "元/㎡", valid_until: "2099-12-31" },
    new_home: { project_name: "示例府", developer_full_name: "示例置业有限公司", presale_permit_no: "示例预售证0000" },
  },
};
