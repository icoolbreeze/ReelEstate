# ReelEstate 生产交接

适用于 Claude Code、ZCode、OpenCode、Codex 等具备本机文件与命令权限的 agent。代码与项目位于 `C:\Users\shipi\vswp\ReelEstate`，流程不依赖本次聊天或某个执行器的记忆。

2026-10-25 用户明确要求：删除 xihu 测试工程，停止兼容旧 project.json 生产工程。现行入口仅支持 episode.yaml + episode.json。AGENTS.md 中旧 project 目录、命令和示例已不属于当前生产接口，不要据此恢复旧渲染分支。内容真实性、授权、原始素材保护等要求继续有效。

2026-10-30 用户要求“只保留最新的架构”：旧 `projects/new-home|rental|resale|_example` 布局、`projects/map-hub` 联接与 `series: map-hub` 别名、project.json 时代的 `pipeline/stages`、`pipeline/tts`、`templates/<category>/project.json` 均已移除（移入 `%TEMP%\reelestate_trash_20261030\`，带 manifest，可恢复）。AGENTS.md 已同步。期内目录以 docs/FOOTAGE-SPEC.md 为准。

## 项目用途与素材许可

本项目仅用于非商业用途（用户于 2026-10-31 明确），适用于全部内容类型及共用工具。接手 Agent 按 `CONVENTIONS-shared.md` §0 选择素材、代码与服务；允许符合非商业使用条款的资源，不要求额外商用授权，也不因不允许商用而单独阻断制作。署名、再分发和服务使用条件仍按原条款执行。

## 开工顺序

1. 读 README.md、docs/architecture.md、docs/CONVENTIONS-shared.md，以及内容类型对应的 RUNBOOK。
2. `npm run doctor` 检查本机 Python、Node、ffmpeg、公共模板和共享 Remotion 环境。该命令只读，不生成、不调用收费服务。
3. `npm run episodes` 查看当前期和下一发布号。测试号不占发布号。下一正式发布编号由该命令按已有正式期计算，不在本文写死。
4. 给出本期房源编号、知识选题或会客厅主题后，由 agent 建期。空白模板用 templates/listing、templates/knowledge、templates/interview，不能复制已有视频期。

## 新建

```powershell
npm run new -- rental <slug> --listing <房源编号> --title <小区名> --city 成都
npm run new -- resale <slug> --listing <房源编号> --title <小区名> --city 成都
npm run new -- new-home <slug> --title <楼盘名> --city 成都 [--footage <相机文件夹>]
npm run new -- knowledge <slug> --topic <选题> --city 成都
npm run new -- interview <slug> --topic <主题> --city 成都
```

房源数据：projects/listing/<episode>；知识选题：projects/knowledge/<episode>；小ONE会客厅：projects/interview/<episode>。三个类型共用发布编号、基础工具、字体品牌和依赖，但各期数据及工作区隔离。`purpose: test` 不写入 release_number。会客厅技术测试用 `npm run new -- interview <slug> --tech-test --topic <主题>`，目录可以是 ep00，不占正式号。

## 制作与渲染

- 按相应 RUNBOOK 完成取数或研究、脚本、配音与实际词时间戳、HeyGen 计划与下载、必要抠像、素材同步和时间线。房源走 pipeline/maphub，知识走 pipeline/knowledge，小ONE会客厅走 pipeline/interview。会客厅默认现场同期声，不默认 HeyGen、TTS、克隆或变速。
- 实拍原片只复制进 `footage/raw/`（保留相机原名），再 `npm run manifest -- projects/listing/<episode> --init` 生成 `footage/raw_manifest.json`，在里面填 room / shot / in / out。
- Pocket 3（D-Log M）实拍素材导入后先跑 `npm run restore -- projects/<line>/<episode>`：自动识别 D-Log M 并还原到 `footage/restored/master/`（10-bit ProRes 母版，供达芬奇精调）和 `footage/restored/proxy/`（H.264 代理，给 Remotion；后续环节自动用还原版，未还原的 D-Log M 会让三条线的 check 失败），unknown 的要人工确认，详见 FOOTAGE-SPEC.md 的 Pocket 3 一节。
- 脚本、配音或剪辑改变后，重新生成依赖它们的时间线和清单；检查失败必须修输入，不能只改指纹或绕过门槛。
- CLI 渲染会先做本期预检，再 stage 公共代码到独立的 work/remotion；不要在模板目录切换 public/src/episode，不按期安装依赖。

```powershell
npm run doctor -- projects/listing/<episode> --draft
npm run check -- projects/listing/<episode> --draft
npm run still -- projects/listing/<episode> --draft --frame 510 --ver review
npm run render -- projects/listing/<episode> --draft --ver roughcut_v1
# 知识类改为 projects/knowledge/<episode>。会客厅改为 projects/interview/<episode>。
# 会客厅技术测试只渲染草稿：npm run check -- projects/interview/<episode> --draft
# npm run still -- projects/interview/<episode> --draft --frame 0 --ver techtest
# npm run render -- projects/interview/<episode> --draft --ver techtest
```

## 正式输出

房源的发布资料是独立的 compliance.json；新建时生成 compliance.json.draft，按真实资料填好后确认并改名。格式示例见 templates/listing/compliance.example.json；只保留本类别的 rental / resale / new_home 分支。它记录面积口径、价格与有效期、机构全称、出镜认证、优缺点和分类要求，不承载时间线或另一份旁白。校验器直接检查 data/timeline.json 中实际使用的口播。

没有真实资料就保持待填，不能为了正式渲染编造认证、委托、价格有效期、核验码或许可信息。旧 project.json 不会作为替代输入。

```powershell
npm run doctor -- projects/listing/<episode>
npm run check -- projects/listing/<episode>
npm run render -- projects/listing/<episode> --platform shipinhao
```

正式检查通过不等于完成审片：还需原有响度、画幅帧率、至少四个不同镜头静帧、运动/文字/遮挡检查及人工审片。最终文件在本期 out/release，草稿在 out/drafts。

## 外部步骤与权限

- 本地已有素材齐全时，其他 agent 可使用同一套工具检查并渲染，不必调用另一个编码 agent。
- 完整生产仍可能需要有效的 CRM 登录、TTS 服务、HeyGen/Muse 浏览器登录和额度，以及可选 Kaggle 会话；doctor 不代替这些账号状态。
- 不自动生成付费数字人，不自动注册/邀请账号，不修改原始录音，不上传或发布成片；这些动作按用户本次授权和既有流程执行。
- 错误必须连同实际退出码说明；草稿、预检通过、渲染成功、人工验收通过分别记录，不把它们混报为同一状态。

## 静帧审美检查入口

至少四个不同镜头的静帧保存在同一版本目录后，执行 npm run check:taste -- projects/listing/<episode> --ver review。知识类当前静帧在 out/drafts/stills，使用 --ver stills。该入口只读取本期 out/drafts，帧数不足会失败，运行原有 harmony 图像检查；仍须人工确认是不同镜头并逐张审片。
