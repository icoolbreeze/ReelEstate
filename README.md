# ReelEstate

房产视频生产工程：Python 流程编排 + Remotion 渲染。正式内容分为房源讲解、知识口播和小ONE会客厅，发布期号统一分配。只支持 episode.yaml 工程；[跨 agent 生产交接](docs/PRODUCTION.md) 是现行操作入口。

**项目用途：仅限非商业用途（用户于 2026-10-31 明确）。** 素材与服务接入按非商业使用条件选择，可采用允许非商业使用的音效、音乐、字体、图片和第三方代码，不要求额外商用授权。署名、再分发及服务条款仍按原许可执行；统一规则见[共用制作规范 §0](docs/CONVENTIONS-shared.md#0-项目用途与素材许可)。

| 路径 | 用途 |
|---|---|
| `projects/listing/` | 房源期；`category` 区分 rental / resale / new-home；`_sources/` 放未建期的原始资料；期内目录见 docs/FOOTAGE-SPEC.md |
| `projects/knowledge/` | 知识、政策、市场分析期 |
| `projects/interview/` | 小ONE会客厅；`series: interview` |
| `pipeline/common/` | 工作区、配音设置、字幕对齐、HeyGen 计划、媒体同步、存储管理 |
| `templates/shared/remotion/src/` | 字体、标签位图、跟踪平滑、连线、品牌条、角标及共用媒体组件 |
| `templates/shared/public/` | 公共字体、品牌、平台图标；旧 shared/public 路径保留兼容 |
| `tools/remotion/` | 房源、知识类和会客厅共用的 Node 依赖和锁文件 |
| `templates/map-hub/remotion/` | 房源镜头编排；map-hub 是模板名称 |
| `templates/knowledge/remotion/` | 知识类镜头编排 |
| `templates/interview/remotion/` | 小ONE会客厅镜头编排 |
| `templates/listing/` | 独立的新建模板与发布资料格式，不依赖任何测试视频 |

## 常用入口

```powershell
npm run doctor
npm run setup
npm run episodes
npm run typecheck
npm run check -- projects/listing/ep02-zidong --draft
npm run still -- projects/listing/ep02-zidong --draft --frame 510 --ver review
npm run render -- projects/listing/ep02-zidong --draft --ver roughcut_v9
npm run storage:audit
npm run storage:compact -- projects/listing/ep02-zidong
# 先审阅计划，再应用；原始素材与授权资料不在清理范围内。
npm run storage:compact -- projects/listing/ep02-zidong --apply --report tmp/storage-ep02.json
```

`check/render/still` 根据 episode.yaml 的 `series` 进入房源、知识或会客厅流程。未知 series 会报错。旧 project.json 项目不再接收，也不再保留独立的旧渲染环境。正式片仍需原有合规、素材、字幕、抠像、运动与人工审片通过。会客厅默认用现场同期声，不用 HeyGen、TTS 或变速。

各期 `work/remotion` 保留独立数据、public 和代码快照；每次 stage 会同步公共修复。依赖通过目录联接共享，不逐期安装。已导出的 MP4 需要重新渲染才能继承代码修复。

新建房源继续用 `scripts/new_episode.cmd`，知识类用 `scripts/new-knowledge-episode.cmd`，会客厅用 `npm run new -- interview <slug> --topic <主题>`。三类使用同一发布序号，由 `npm run episodes` 计算。`purpose: test` 不占发布编号。

房源和知识类默认画幅 4:3、1440×1080、30fps。会客厅首版是 16:9、1920×1080，帧率按本期配置取 25 或 30。主持人、声音、原始素材和来源要求见 [共用制作规范](docs/CONVENTIONS-shared.md)，会客厅的覆盖规则在该文件末节和 [RUNBOOK-interview.md](docs/RUNBOOK-interview.md)。架构与存储管理见 [架构说明](docs/architecture.md)。所有 Agent 按 [PRODUCTION.md](docs/PRODUCTION.md) 接手；旧生产入口已退役，现行入口以该文档为准。
