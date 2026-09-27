# project.json 字段说明

`npm run new` 会把 `templates/<category>/project.json` 复制到新项目并填好 `id`、`category`。
以 `_` 开头的键（如 `_comment`）是注释，程序忽略。所有 `待填` 必须替换，否则 check 不通过。

## 通用字段

| 字段 | 说明 | 合规要求 |
|---|---|---|
| `id` | 文件夹名，如 `2026-10-03-lvcheng-2b1l` | 英文/拼音 |
| `category` | `rental` / `resale` / `new-home` | |
| `title` | 视频标题（中文） | 与内容一致，无违禁词 |
| `is_example` | 示例数据标记 | 示例不得发布 |
| `ai_voice` | 是否使用 AI 配音（TTS 自动设为 true） | 发布时勾 AI 标注 |
| `ad_disclosure` | 是否商业推广（需标“广告”） | |
| `export.default_ratio` / `ratios` | `4x3` / `3x4` / `9x16` | |
| `property.property_type` | 房产类型 | 公约必填 |
| `property.layout` | 户型，如 3室2厅1卫 | |
| `property.area.type` / `value` | `建筑面积` 或 `套内建筑面积` + 数值（㎡） | 公约/房广第4条必填 |
| `property.location.*` | 城市、区、街道、小区 | 至少精确到街道或小区 |
| `price.type` / `value` / `unit` / `valid_until` | 价格类型、数值、单位、有效期 YYYY-MM-DD | 真实价格 + 有效期 |
| `agency.full_name` | 中介/销售机构全称（营业执照） | 公约必填 |
| `agency.record_no` | 经纪机构备案号 | 部分城市要求公示 |
| `agent.name` / `certified_on_camera` | 出镜经纪人；是否为视频号认证本人 | 必须 true |
| `highlights[]` | 亮点（客观描述） | 无绝对化用语 |
| `drawbacks[]` | 缺点 | 公约要求，至少 1 条 |
| `nearby[]` | `name`、`distance_m`、`basis`、`status` | 用距离不用时间；在建/规划中要标 |
| `tts.voice` / `tts.mode` | 音色预设（`voices/presets.json`）/ `voicedesign`\|`customvoice`\|`clone` | |
| `narration.segments[]` | `id`、`text`、`presenter`（`fullscreen`/`pip-left`/`pip-right`），可选 `card{title,lines[]}`、`presenter_clip`、`clip_start`、`broll`、`visual_label` | |

## 分类字段

- **rental**：`rental.rent_type`（整租/合租）、`room_desc`、`payment_terms`（押付方式，必填）、`service_fee`、`utilities`、`available_from`、`min_lease_months`；`price.type` = `月租金`，`unit` = `元/月`。
- **resale**：`resale.verification_code`（房源核验编码，必填）、`owner_consent`（必须 true 且 `consent/` 有文件）、`property_right`、`ownership_note`；`price.type` 通常为 `挂牌价`。
- **new-home**：`new_home.project_name`、`developer_full_name`（必填）、`presale_permit_no`（必填）、`delivery_date`、`delivery_standard`、`renderings[]{file,label}`（label 含“效果图/非实景”）、`planned_facilities[]{name,status}`。
