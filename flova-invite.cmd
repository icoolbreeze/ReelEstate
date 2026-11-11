@echo off
chcp 65001 >nul
title Flova 积分邀请注册

cd /d "%~dp0"

echo ========================================================
echo               Flova 积分邀请注册工具
echo ========================================================
echo.

:: 设置直连，防止本地代理拦截云端邮箱池
set NO_PROXY=119.29.187.184,localhost,127.0.0.1
set PYTHONUTF8=1

:: 检查并显示当前母号状态
python -c "import sys; sys.path.insert(0, 'scripts/flova'); import flova_invite as fi; print('  [当前活跃母号]:', fi.active_mother_profile())" 2>nul
echo.

set COUNT=1
set /p USER_COUNT="请输入本次邀请注册的子号数量 (直接回车默认注册 1 个): "
if not "%USER_COUNT%"=="" set COUNT=%USER_COUNT%

echo.
echo 正在启动注册流程 (目标数量: %COUNT%)...
echo [操作提示] 浏览器窗口弹出后，若出现滑动拼图，请手动在浏览器中拖动滑块完成拼图。
echo.

python scripts\flova\invite_manual.py %COUNT%

echo.
echo ========================================================
echo 执行结束。
echo ========================================================
pause
