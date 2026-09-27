# AGENTS.md — ReelEstate 所有编码 Agent 的总规则

> 适用于 Codex、Claude Code、OpenCode 及任何在本仓库工作的 Agent。`CLAUDE.md` 只引用本文件。
> 文档/规则用中文写，代码、标识符、文件夹名用英文（或拼音）。

## 1. 项目目的

为一位中国房产视频创作者（抖音 + 微信视频号）批量制作**科普/讲解风格**的房源视频：
真人口播（全屏 ↔ 左下/右下小窗 PiP 切换）+ Canva 设计的信息卡 + Remotion 动效 + 可选 AI 配音（qwentts.cpp）。

- 默认导出：**4:3 横版 1440×1080 @30fps**；可选竖版 **3:4 1080×1440**、**9:16 1080×1920**。
- 三个分类：`rental`（租赁）、`resale`（二手房）、`new-home`（新房）。
- 合规是硬约束：视频号《房地产行业公约》（2026-05-12 生效）、《广告法》、《房地产广告发布规定》、《住房租赁条例》等。见 `rules/`。

## 2. 目录结构

```
AGENTS.md / CLAUDE.md / README.md
package.json          # 固定命令入口（npm scripts）
.env.example          # TTS 路径模板；真实 .env 不提交
rules/                # 所有规则（Agent 必读）
  compliance/         # common.md + rental.md / resale.md / new-home.md
  style.md            # 视觉与讲解风格
  workflow.md         # 标准流程
  reference/          # 原始调研文档（带来源链接）
remotion/             # Remotion 4 + TypeScript 渲染工程
  src/Root.tsx        # 注册 Rental/Resale/NewHome × 4x3/3x4/9x16
  src/shared/         # PresenterFrame, Captions, InfoBar, DisclaimerBadge ...
  src/compositions/   # rental/ resale/ new-home/
pipeline/             # Python（尽量只用标准库）
  new_project.py      # 新建项目
  tts/qwen_tts.py     # 分段 TTS
  check/check.py      # 合规检查（render 前强制）
  render.py           # 检查 + 渲染
  preview.py          # Remotion Studio 预览某项目
  schema/             # JSON Schema（common + 各分类）
templates/<category>/project.json   # 新项目模板
projects/             # 各房源项目（私有，gitignore；仅 _example 提交）
  _example/           # 完整示例（二手房，示例数据）
  rental/ resale/ new-home/<YYYY-MM-DD-pinyin-id>/
voices/presets.json   # voicedesign 音色描述
voices/clone/         # 克隆参考音频（私有，gitignore）
vendor/qwentts.cpp    # git 子模块（不要随意改动）
scripts/build-tts.cmd # 编译 qwen-tts.exe（CUDA, sm_61）
docs/                 # tts.md, new-project.md
```

### 项目文件夹约定
- 路径：`projects/<category>/<YYYY-MM-DD>-<pinyin-slug>/`，例如 `projects/rental/2026-10-03-lvcheng-2b1l`。
- 文件夹名只用小写英文/拼音/数字/连字符；**中文名写在 `project.json` 里**（`title`、`property.community` 等）。
- 子目录：`raw/`（原始素材）、`canva/`（Canva 导出卡片）、`audio/`（TTS 输出）、`consent/`（业主委托/授权书、声音授权）、`output/`（成片）。

## 3. 标准流程

1. `npm run new -- <category> <slug>` 新建项目（自动加日期前缀）。
2. 把素材放进 `raw/`、Canva 卡片放进 `canva/`、授权文件放进 `consent/`。
3. （ASR 转写：占位，尚未实现）
4. 编辑 `project.json`：房源字段 + `narration.segments`（每段 `id`、`text`、`presenter`）。
5. （可选）`npm run tts -- projects/<category>/<id>` 生成配音。
6. `npm run check -- projects/<category>/<id>`，直到 PASS。
7. `npm run render -- projects/<category>/<id> [--ratio 4x3|3x4|9x16]`。
8. 发布前自检（AI 声明、广告标注等，见 `rules/workflow.md`）。

## 4. 固定命令（Agent 只用这些入口，不要自造等价命令）

| 命令 | 作用 |
|---|---|
| `npm run new -- rental lvcheng-2b1l [--date 2026-10-03]` | 新建项目 |
| `npm run tts -- projects/rental/<id> [--voice narrator_male_30] [--dry-run]` | 分段 TTS，写 `audio/segments.json` |
| `npm run check -- projects/rental/<id>` | 合规检查，失败返回非 0 |
| `npm run render -- projects/rental/<id> [--ratio 4x3\|3x4\|9x16]` | 先 check，再渲染到 `output/<id>_<ratio>.mp4` |
| `npm run still -- projects/rental/<id> [--ratio 4x3] [--frame 220]` | 渲染单帧 PNG（快速验证） |
| `npm run preview -- projects/rental/<id>` | Remotion Studio 预览 |
| `npm run setup` | 安装 remotion/ 依赖 |
| `npm run typecheck` | `tsc --noEmit` |
| `scripts\build-tts.cmd` | 编译 qwen-tts.exe（只有用户要求时才运行） |

## 5. 硬性禁止

1. **不得 push** 到 GitHub、不得改 remote、不得强推/改写已有提交，除非用户明确要求。
2. **不得提交私有素材**：`projects/` 下除 `_example` 外全部 gitignore；不要用 `git add -f` 绕过。`voices/clone/`、`.env` 同理。
3. **不得绕过合规检查**：`render` 必须先通过 `check`；不要给 check 加跳过开关，不要为了通过而删违禁词表条目。修文案，不修规则。
4. **不得编造房源信息或法规**：价格、面积、核验码、预售证号等只能来自用户提供的资料；缺失就留 `待填` 让 check 失败。规则中未核实的内容标注 `待核实`。
5. **画面/口播/字幕/封面中不得出现**：电话、微信号、二维码、网址、站外平台 logo、“私信领资料/获取底价”。
6. **不得使用**绝对化用语、升值/投资回报承诺、学区/落户承诺、“X分钟到地铁”式时间表述、风水迷信、零首付/首付分期/售后包租等（完整列表见 `rules/compliance/common.md` 与 `pipeline/check/banned_words.json`）。
7. **不得模板化批量出片**：视频号公约禁止脚本雷同、表现形式高度一致的视频。每条视频的口播、镜头、节奏要真正不同（见 `rules/style.md`）。
8. **不得随意改动 `vendor/qwentts.cpp`**（子模块）；不要擅自编译或下载大模型，除非用户要求。
9. **不得在仓库外写文件**（读取可以）。
10. AI 配音/克隆必须有本人书面授权（放 `consent/` 或 `voices/clone/`），并在发布时勾选 AI 标注。

## 6. 规则索引（改代码或写文案前先读）

- `rules/compliance/common.md` — 通用合规（所有分类）
- `rules/compliance/rental.md` / `resale.md` / `new-home.md` — 分类专项
- `rules/style.md` — 视觉风格、节奏、镜头效果
- `rules/workflow.md` — 流程与发布前自检
- `rules/reference/` — 原始调研（含全部来源链接）
- `docs/tts.md`、`docs/new-project.md`

## 7. 编码约定

- 所有文本文件 UTF-8（JSON/Python/TS 无 BOM），换行 LF。Windows 上写文件用 Python `open(..., encoding="utf-8", newline="\n")`，不要用 PowerShell 5 的 `Set-Content`/`Out-File` 默认编码。
- Python 尽量只用标准库；需要第三方包时加 `requirements.txt`，只装进仓库内 `.venv`，不要全局 pip install。
- Remotion 代码必须通过 `npm run typecheck`。新增字段要同步：`templates/` → `pipeline/schema/` → `remotion/src/types.ts` → `check.py`。
- 提交信息用英文。
