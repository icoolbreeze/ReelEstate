# ReelEstate

房产讲解视频生产仓库：**Remotion（Node）+ Python 流水线**，面向抖音与微信视频号。
科普/讲解风格，真人口播（全屏 ↔ 小窗 PiP 切换）+ Canva 信息卡 + 动效，可选 AI 配音（[qwentts.cpp](https://github.com/ServeurpersoCom/qwentts.cpp)）。

- 默认导出 4:3 横版 **1440×1080**，可选 **1080×1440（3:4）**、**1080×1920（9:16）**
- 分类：`rental` 租赁 / `resale` 二手房 / `new-home` 新房
- 内置合规检查（视频号房地产行业公约、广告法、房地产广告发布规定等），不通过不能渲染

> 所有 Agent（Codex / Claude Code / OpenCode）请先读 [AGENTS.md](AGENTS.md)。

## 环境要求

Windows 10/11，Node 22+，Python 3.11+，ffmpeg/ffprobe，git。编译 TTS 另需 VS 2022 + CUDA 12.x + cmake + ninja。

## 快速开始

```powershell
git clone --recursive https://github.com/icoolbreeze/ReelEstate.git
cd ReelEstate
copy .env.example .env          # 按本机路径修改
npm run setup                   # 安装 remotion 依赖

# 看示例
npm run check -- projects/_example
npm run still -- projects/_example            # 单帧 PNG → projects/_example/output/
npm run render -- projects/_example --ratio 4x3

# 新建一个租赁项目
npm run new -- rental lvcheng-2b1l            # → projects/rental/2026-xx-xx-lvcheng-2b1l
npm run check -- projects/rental/2026-xx-xx-lvcheng-2b1l
```

（可选）编译 AI 配音：`scripts\build-tts.cmd`，详见 [docs/tts.md](docs/tts.md)。

## 目录

| 路径 | 说明 |
|---|---|
| `rules/` | 合规、风格、流程规则（中文） |
| `remotion/` | Remotion 4 渲染工程 |
| `pipeline/` | Python：新建、TTS、检查、渲染 |
| `templates/` | 各分类 `project.json` 模板 |
| `projects/` | 房源项目（私有，不提交；仅 `_example`） |
| `voices/` | 音色预设与克隆参考（私有） |
| `vendor/qwentts.cpp` | TTS 子模块 |
| `docs/` | 使用文档 |

## 注意

- 房源数据来自已部署的云端 CRM 连接器（目前只接入租赁），用法见 [docs/crm.md](docs/crm.md)（Word：[docs/crm.docx](docs/crm.docx)）。
- 地图脚本见 [config/map-tools.json](config/map-tools.json)（高德 GCJ-02，密钥只在本机、不进仓库）；flova MCP 在仓库内（`.mcp.json` / `.grok/config.toml`）：地图底图用图片重绘（高德静态图 → `generate_image` → `map/base_ai.png`，代码叠标签），生图用 `generate_image`：成片/精细改图/品牌产品图/地图重绘用 GPT Image 2.5 Sunburst，日常/批量/社媒/试错用 Flare，不生成户型/实景/景观/周边；**视频生成默认关闭**（`flova.video_allowed=false`，只有明确开启才会用 WAN 3.0 Prime）。
- `projects/` 下真实房源素材、`.env`、`voices/clone/` 均被 gitignore，**不要强制提交**。
- 本仓库的合规规则是整理稿，不是法律意见；平台规则会更新，发布前以平台最新版本为准。
