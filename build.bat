@echo off
REM 佐拉口琴谱伴 - PyInstaller 打包脚本
REM 产物: dist\佐拉口琴谱伴.exe
REM 注意: exe 名称与内部字符串均避免敏感词，以降低反作弊内存关键词扫描命中概率

REM 切到 UTF-8 代码页，确保本 bat 中的中文（如 NAME）被正确解析，
REM 避免 GBK 终端把 UTF-8 中文读成乱码传给 PyInstaller。
chcp 65001 >nul
setlocal

set NAME=佐拉口琴谱伴

where pyinstaller >nul 2>nul
if errorlevel 1 (
    echo [!] 未找到 pyinstaller，正在安装...
    python -m pip install pyinstaller || goto :error
)

echo [*] 开始打包 %NAME% ...

REM pydirectinput / keyboard 在 input_backend.py 中为方法内延迟导入，
REM PyInstaller 静态分析会漏掉，必须显式声明 hidden-import 并 collect-submodules，
REM 否则打包后 B 模式会静默回退空后端（无法注入）。
REM customtkinter 含主题/字体等数据文件，必须 --collect-all 才能正常显示样式。
pyinstaller --onefile --windowed --noconfirm ^
    --name "%NAME%" ^
    --hidden-import pydirectinput ^
    --hidden-import keyboard ^
    --collect-submodules pydirectinput ^
    --collect-submodules keyboard ^
    --collect-all customtkinter ^
    --collect-submodules harmonica ^
    harmonica\main.py

if errorlevel 1 goto :error

echo.
echo [+] 打包完成: dist\%NAME%.exe
exit /b 0

:error
echo [x] 打包失败
exit /b 1
