# AI 配音（qwentts.cpp）

上游：[ServeurpersoCom/qwentts.cpp](https://github.com/ServeurpersoCom/qwentts.cpp)（C++17 + GGML 的 Qwen3-TTS 实现），以 git 子模块放在 `vendor/qwentts.cpp`。

> 合规：使用 AI 配音发布时必须勾选 AI 标注；克隆声音必须有本人单独书面授权（见 `rules/compliance/common.md` 第5节）。

## 1. 编译（Windows，CUDA）

前提：VS 2022 Professional、CUDA 12.x、cmake。子模块已初始化（`git submodule update --init --recursive`）。

```powershell
scripts\build-tts.cmd
```

- 调用 `C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat`（上游脚本写死的是 BuildTools 路径）。
- `-DCMAKE_CUDA_ARCHITECTURES=61`：GTX 1070 Ti 为 Pascal（sm_61）。
- 产物：`vendor\qwentts.cpp\build\Release\qwen-tts.exe`（Ninja 生成器则在 `build\`），TTS 脚本两处都会找。
- 失败时可改用 Vulkan（`-DGGML_VULKAN=ON`，需 Vulkan SDK）或纯 CPU（去掉 CUDA 参数）。

## 2. 配置 `.env`

```
QWEN_TTS_BIN=C:\Users\shipi\vswp\ReelEstate\vendor\qwentts.cpp\build\Release\qwen-tts.exe
QWEN_TTS_MODELS=C:\Users\shipi\.lmstudio\models\Serveurperso\Qwen3-TTS-GGUF
QWEN_TTS_TALKER=qwen-talker-1.7b-voicedesign-Q8_0.gguf
QWEN_TTS_CODEC=qwen-tokenizer-12hz-Q8_0.gguf
QWEN_TTS_BASE_TALKER=qwen-talker-1.7b-base-Q8_0.gguf              # 未下载（仅克隆模式）
QWEN_TTS_CUSTOMVOICE_TALKER=qwen-talker-1.7b-customvoice-Q8_0.gguf # 已下载
```

## 3. 测试一句话

```powershell
$m = "C:\Users\shipi\.lmstudio\models\Serveurperso\Qwen3-TTS-GGUF"
"大家好，今天带大家看一套南北通透的三房。" | Out-File -Encoding utf8 $env:TEMP\p.txt
cmd /c "vendor\qwentts.cpp\build\Release\qwen-tts.exe --model $m\qwen-talker-1.7b-voicedesign-Q8_0.gguf --codec $m\qwen-tokenizer-12hz-Q8_0.gguf --instruct ""男声，三十岁左右，沉稳，语速适中"" --lang Chinese -o test.wav < $env:TEMP\p.txt"
```

（PowerShell 不支持 `<` 输入重定向，所以用 `cmd /c`。exe 在 `build\` 下时改路径。）

项目内分段生成：

```powershell
npm run tts -- projects/_example --dry-run                 # 只打印命令
npm run tts -- projects/resale/<id> --voice narrator_female_28
npm run tts -- projects/resale/<id> --only s02,s04 --seed 42
```

输出 `audio/seg_<id>.wav`、`audio/segments.json`（`{id,text,file,duration}`，时长用 ffprobe 测），并设置 `project.json` 的 `ai_voice: true`。渲染时每段时长以音频为准。

## 4. 三种模式

| 模式 | talker 模型 | 参数 | 状态 |
|---|---|---|---|
| `voicedesign` | `qwen-talker-1.7b-voicedesign-*.gguf` | `--instruct "<音色描述>"`（`voices/presets.json`） | 模型已下载；**中文描述效果待实测**（上游示例为英文描述） |
| `customvoice` | `qwen-talker-*-customvoice-*.gguf` | `--speaker <名字>`（如上游示例 `vivian`） | 模型已下载；预置音色名待实测 |
| `clone`（base） | `qwen-talker-*-base-*.gguf` | `--ref-wav ref.wav --ref-text ref.txt`，或预编码 `--ref-spk/--ref-rvq` | 模型未下载 |

说明：
- 上游 `examples/clone.sh` / `clone.cmd` 以及源码 `src/qwen.cpp`（报错信息 “--ref-wav / --ref-spk is only valid for base models”）表明**克隆用的是 BASE 模型**。HF 模型卡表格把 customvoice 描述成克隆，与上游实现不符——以上游代码为准，**视为待核实**。
- `--instruct` 不支持 base 模型；`--speaker` 只对 customvoice 有效；`--speaker` 与 `--ref-*` 互斥。
- 预编码参考音频：`build\Release\qwen-codec.exe --model <codec> --talker <base talker> -i ref.wav` 生成 `.spk` 与 `.rvq`，之后合成更快。
- 其他可用参数：`--seed`、`--temp`、`--top-k`、`--top-p`、`--max-new`、`--no-fa`、`--format`。

## 5. 常见问题

- **找不到 exe**：先运行 `scripts\build-tts.cmd`；或在 `.env` 修正 `QWEN_TTS_BIN`。
- **找不到模型**：检查 `QWEN_TTS_MODELS` 目录下文件名与 `.env` 一致。
- **显存不足（8GB）**：换 Q4_K_M 量化、或 0.6B（voicedesign 仅 1.7B）；可加 `--no-fa` 排查。
