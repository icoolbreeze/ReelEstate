# 房源讲解系列

本目录用于租赁、二手房和新房；知识类在 projects/knowledge，会客厅在 projects/interview。三者共用正式发布编号：ep01-intro（知识）、ep02-zidong（租赁）、ep03-bangtai-cangjin（新房），下一正式编号为 4（以 `npm run episodes` 为准）。

新建从 templates/listing/episode.json 读取空白模板，不复制已有一期。xihu 测试工程已按用户要求删除。房源编号只放 episode.yaml 的 listing.ref 和 data/listing_ref.json，不进画面与目录名。

生产交接见 docs/PRODUCTION.md，先运行 npm run doctor。渲染只使用 episode.yaml + episode.json 工程；正式发布资料为 compliance.json，实际旁白从 data/timeline.json 校验。

共享素材在 templates/shared/public，公共组件在 templates/shared/remotion/src，Node 依赖在 tools/remotion。期内目录见 docs/FOOTAGE-SPEC.md：footage/raw（只读）+ footage/raw_manifest.json、footage/restored/{master,proxy}、footage/shots、footage/assets、sources/{amap,docs}，其余目录按需创建。`_sources/` 放还没建期的原始资料（如 `_sources/wuhou-xipai-yufu/`），不是一期。旧 projects/map-hub 联接已移除。
