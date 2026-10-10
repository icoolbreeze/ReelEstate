# One-time setup of Fun-CosyVoice3 on Windows (GTX 1070 Ti, CUDA). Run from repo root.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$V = Join-Path $root "vendor\cosyvoice"
if (-not (Test-Path "$V\.git")) { git clone --recursive --depth 1 https://github.com/FunAudioLLM/CosyVoice.git $V }
Set-Location $V
if (-not (Test-Path ".venv")) { uv venv -p 3.10 .venv }
$env:VIRTUAL_ENV = "$V\.venv"
uv pip install "torch==2.8.*" "torchaudio==2.8.*" --index-url https://download.pytorch.org/whl/cu126
$req = Get-Content requirements.txt | Where-Object { $_ -notmatch 'deepspeed|tensorrt|onnxruntime|extra-index|^torch|gradio|fastapi|tensorboard|grpcio|uvicorn|pyworld|openai-whisper' }
$req += "onnxruntime==1.18.0"; $req | Set-Content req_win.txt
uv pip install "setuptools<70" wheel
uv pip install --no-build-isolation openai-whisper==20231117
uv pip install -r req_win.txt lightning==2.2.4 soundfile
& "$V\.venv\Scripts\python.exe" -c "from huggingface_hub import snapshot_download; snapshot_download('FunAudioLLM/Fun-CosyVoice3-0.5B-2512', local_dir='pretrained_models/Fun-CosyVoice3-0.5B')"
& "$V\.venv\Scripts\python.exe" -c "import torch;print('CUDA',torch.cuda.is_available(),torch.cuda.get_device_name(0))"
"SETUP_DONE"
