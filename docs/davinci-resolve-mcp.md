# DaVinci Resolve MCP 集成（含增稳）

> 上游：<https://github.com/samuelgursky/davinci-resolve-mcp>（MIT，npm 包 `davinci-resolve-mcp`）
> 本机版本：**4.17.0**，Resolve **21.0.4.5（免费版）**，Windows。
> 2026-10-31 完成接入并实测增稳。

## 1. 用途边界

- 本项目成片仍走 Remotion（`templates/.../remotion`），Resolve MCP **不替代**现有流水线。
- 它用于 Remotion 不做、Resolve 擅长的桌面端工作：**镜头增稳（Stabilizer）**、调色、套底/导出等。
- 典型场景：Pocket 3 / 手机原片有轻微抖动，先用 Resolve 增稳出片或出代理，再进后续环节。

## 2. 安装位置（已就位，勿重复安装）

```
tools/davinci-resolve-mcp/
  package.json            # 私有壳，钉死 davinci-resolve-mcp 4.17.0
  package-lock.json
  node_modules/           # gitignore（npm 安装的 MCP server 源码）
  runtime/venv/           # gitignore（Python 3.13 虚拟环境，跑 server.py）
  test/
    mcp_smoke.py          # 握手 + tools/list 冒烟
    stabilize_test.py     # 增稳端到端测试
```

重建步骤（换机或损坏时）：

```bash
cd tools/davinci-resolve-mcp
npm install                       # 装 node_modules/davinci-resolve-mcp
"C:/Python313/python.exe" -m venv runtime/venv
runtime/venv/Scripts/python.exe -m pip install mcp pydantic
# 免费版 in-app bridge（脚本装进 Resolve 的 Scripts 目录）：
runtime/venv/Scripts/python.exe \
  node_modules/davinci-resolve-mcp/scripts/install_resolve_bridge.py
```

诊断：`runtime/venv/Scripts/python.exe node_modules/davinci-resolve-mcp/scripts/doctor.py`
（需带 `RESOLVE_SCRIPT_API / RESOLVE_SCRIPT_LIB / PYTHONPATH`，见 `.mcp.json` 的 env。）

## 3. MCP 配置（项目级）

`.mcp.json` 已声明 `davinci-resolve`（stdio），用仓库内 venv 的 python 跑 `src/server.py`，
env 指向 `C:\ProgramData\...\Scripting`、`fusionscript.dll`、Scripting Modules，并固定 `PYTHONHOME=C:\Python313`。

- 这是**项目配置**，可按任务修改；不要改用户本机的 MCP 客户端配置。
- 默认 compound 模式：37 个工具（`timeline`、`timeline_item`、`timeline_item_color`、`render`、`media_pool` 等）。
  细粒度模式（390 工具）需给 server.py 加 `--full`，一般不用。

## 4. 每次开机/重启 Resolve 后必做：启动 bridge

本机是**免费版 21.0.4.5**，外部脚本被禁用（`scriptapp("Resolve")` 返回 None），
MCP 走 in-app **bridge**（loopback `127.0.0.1:49632`，token 在 `~/.config/davinci-resolve-mcp/bridge.json`）。

Resolve 打开并进入一个工程后：

1. 菜单 **Workspace ▸ Scripts ▸ resolve_bridge**（点一次，它会驻留监听直到 Resolve 退出；
   菜单里出现两个同名条目是正常的，用户级和全机器级各装了一份）。
2. 看到端口监听即成功：`netstat -ano | grep 49632`。
3. MCP client 会**自动**选用 bridge，无需环境变量。
   想强制只走 bridge、排掉直连干扰时，给 server env 加 `DAVINCI_RESOLVE_BRIDGE=1`。
4. Resolve 重启后要重新点一次。**Project Manager 界面下 Scripts 菜单是空的**，必须先进工程。

Studio 版则不需要 bridge：Preferences ▸ General ▸ External scripting using = Local。

## 5. 增稳（Stabilization）怎么调

| 操作 | 通道 | 免费版 21.0.4 实测 |
|---|---|---|
| 运行追踪分析 | MCP `timeline_item_color(action="stabilize", track_type="video", track_index=1, item_index=N)` → `TimelineItem.Stabilize()` | ✅ `success:true`，自动先归档一个调色版本 |
| 开关 / Mode(Perspective·Similarity·Translation) / Strength / Smooth / Cropping Ratio / Zoom / Camera Lock | 脚本属性 `StabilizationEnable/Method/Strength`（`timeline_item(action="set_property"...)`） | ❌ 本 build **不可写**：`GetProperty` 返回 null、`SetProperty` 返回 false（官方文档明确：仅在 build 返回可写值时透传） |
| 同上参数 | GUI Inspector ▸ Video ▸ Stabilization | ✅ 正常 |

结论（免费版 21.0.4）：**“分析”可由 MCP 触发，“开启与参数”需要人在 Inspector 点一次**（或用 computer-use 代点）。
Studio 或更高版本若放开了这些属性，脚本可一步到位；用之前先 `get_property` 探一次可写性。

标准增稳流程：

1. 素材上时间线（`media_pool` / `timeline` 工具导入）。
2. MCP 切到 Color 页：`resolve_control(action="open_page", params={"page":"color"})`。
3. 对目标镜头调 `timeline_item_color(action="stabilize", ...)`（分析可能异步，稍等）。
4. Inspector 打开 Stabilization 开关，选 Mode（手持重抖 Perspective，轻微 Similarity/Translation），
   调 Strength；需要时勾 Zoom（自动放大遮黑边）/ Camera Lock（锁定为固定机位）。
5. 回看确认无黑边、无果冻式回弹，再渲染。

测试脚本：`tools/davinci-resolve-mcp/test/stabilize_test.py`（stdio 直连，`-I` 运行）。
2026-10-31 在测试工程 `ReelEstate_Free_2104_Test_20261031` 的
时间线 `Free_2104_Capability_Test`（5 个 DJI r709 代理镜头）上实测：
- `resolve_control get_version` → DaVinci Resolve 21.0.4.5；
- `timeline get_current / get_items` → 5 镜头，UUID 正常；
- 第 1 个镜头 `stabilize` → `success:true`（归档 Version 1，工程出现 Edited 标记）；
- Inspector 中 Stabilization 可开/关，参数 Strength 0.600、Mode Translation 保留，Zoom/Camera Lock 控件齐全。

## 6. 安全与约定

- MCP server 把源素材视为不可变；破坏性动作走 plan→review→confirm；`CopyGrades` 有 Verified-Trap Guard。
- bridge 有 token 鉴权，只监听 127.0.0.1；`bridge.json` 含 token，**不进 git、不贴对话**。
- 不要为了脚本可写去破解/魔改 Resolve；属性不可写就是不可写，走 GUI 那一步。
- 增稳是对原片的二次处理：遵循原片只读原则，输出写到新文件，不改 `footage/raw/`。
