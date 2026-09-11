"""使用引导页。"""
from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk

from .theme import C_BG, C_CARD, C_TEXT, C_ACCENT, C_WARN, C_CARD_HI

if TYPE_CHECKING:
    from .app import App


def guide_text() -> str:
    return """# 佐拉口琴谱伴 · 使用引导

## 0. 这是什么
三角洲行动 2 周年庆「佐拉」彩蛋任务链奖励道具「口琴」的曲谱辅助工具。
口琴演奏机制（v1.0.2+）：使用道具弹出演奏界面后，
按键 z x c v b n m 对应 do-re-mi-fa-sol-la-ti（音级 1-7），
按住鼠标中键的同时按字母 = 半音（曲谱 # 升 / b 降）。

本工具提供三种链路：C 手动辅助（零风险）/ E 鼠标宏教程（中风险）/ B 自动注入（高风险）。

## 1. 快速上手（C 模式，推荐）
1. 启动程序，默认进入「演奏」页，左侧已载入示例曲谱「小星星」。
2. 顶部模式选「手动辅助」。
3. 点「试运行」预览节奏，观察底部提示：字母键 + 半音时「中键+字母」。
4. 点「显示 HUD 覆盖层」，把悬浮窗拖到不挡视野的位置（双击换边角，右键关闭）。
5. 进入游戏，在局内使用口琴道具呼出演奏界面。
6. 回到本程序点「开始演奏」（或按 F5），照 HUD / 界面提示自己按 z–m；
   遇到升/降音时按住中键再按对应字母。
7. 点「停止」或按 F6 可随时中断（曲中立刻生效）。

## 2. E 模式（鼠标宏教程，中风险）
> 导出 Markdown 手写教程，按任意鼠标宏软件自行编排；已不再导出 G HUB Lua。

1. 顶部模式选「鼠标宏教程」。
2. 点「导出宏教程 MD」（或主按钮），选择驱动模板后保存 .md 文件。
3. 打开教程：内含键位表、BPM/时值、逐音动作表、伪代码。
4. 在你的鼠标驱动里按教程手写宏（中键按下 → 字母 → 抬起）。
5. 绑到侧键；安全区呼出口琴界面后再触发。

## 3. B 模式（自动注入，高风险）
> 仅限单人 / 安全区 / 非竞技场景，违反游戏 ToS，封号风险自负。

1. 先装依赖：pip install pydirectinput keyboard。
2. 顶部模式选「自动注入」，首次会弹风险确认窗。
3. 在游戏内先呼出口琴演奏界面，并保持游戏窗口聚焦（不要切走）。
4. 点「开始演奏」或按 F5，脚本自动按曲谱注入 z–m 与中键半音。
5. 点「停止」或按 F6 中断；演奏结束自动停止。
- 若升降音不生效：到「设置」页切换「键-中键顺序」再试。
- 若无任何反应：到「设置」把输入后端改为 keyboard_ctypes，并以管理员身份运行 exe。

## 4. 简谱记法
- 1 2 3 4 5 6 7 = do re mi fa sol la ti（演奏键 z x c v b n m）
- #1 #3 ... 升；b3 b6 ... 降（演奏时均为：按住中键 + 字母）
- 1^ 1, 高/低八度标记（仅用于音域校验，口琴无八度键，会警告）
- - 延长前音符一拍（可连用，如 5 - - = 三拍）
- . 附点（时值 ×1.5）；_ 减时（时值 ×0.5，可连用）
- 0 休止（一拍，可用 - 延长）；| 小节线（忽略）；// 行注释
- @bpm 120 曲谱内 BPM（覆盖设置）；@key C 调号（仅参考）

## 5. 曲库
- 侧边栏「曲库」可浏览内置曲谱与「我的」文件夹中的 .txt。
- 支持收藏、最近打开；打开后会载入到演奏页编辑器。

## 6. 音域与移调
口琴无八度键，实际可发音高 = 音级 + 升降（无八度偏移），
半音范围约 -1 到 12（b1 到 #7），约一个半八度。
- 带八度标记的音符会触发警告：口琴无法演奏该八度，将按基础音区发音。
- 意图半音超出范围的音符会触发警告：需移调/改编。
- 示例曲谱（harmonica/scores/）均已移调至口琴基础音区，可直接使用。

## 7. 反作弊风险（必读）
> 三角洲行动采用 ACE 内核级反作弊，强制启动、无法关闭。
> 官方禁止清单「Emulation Scripts」明确点名 AutoHotkey 与 Python。
> 查实即封号十年 + 机器码永久封禁，换号换硬盘无效，实名关联账号连坐。

- C 模式：零风险（不注入任何输入，仅显示提示）。
- B 模式：高风险（Python 直接注入键鼠，明令禁止）。
- E 模式：中风险（手写/驱动宏仍可能被监控；旧 G HUB Lua 路径已弃用）。
- 人性化抖动只能降低、不能消除检测概率。
- 本工具不读写游戏内存/封包、不绕过 ACE，仅供彩蛋娱乐，严禁用于竞技场景。

## 8. 配置与日志
- 配置保存在 %APPDATA%\\佐拉口琴谱伴\\settings.json
- 用户曲谱目录 %APPDATA%\\佐拉口琴谱伴\\scores
- 运行异常写入 %APPDATA%\\佐拉口琴谱伴\\error.log（便于 exe 排错）
- 命令行：python -m harmonica --score path --mode C
- 全局热键默认 F5 开始 / F6 停止，可在「设置」修改
- 首次启动有三步向导；可在本页或设置中「再次查看」
"""


def build_guide_page(app: "App") -> ctk.CTkFrame:
    page = ctk.CTkFrame(app.root, fg_color=C_BG, corner_radius=0)

    top = ctk.CTkFrame(page, fg_color="transparent")
    top.pack(fill="x", padx=16, pady=(12, 0))
    ctk.CTkButton(
        top, text="再次查看新手向导", width=160, height=30, corner_radius=8,
        fg_color=C_CARD_HI, hover_color="#3a5044", text_color=C_TEXT,
        command=lambda: app._show_wizard(force=True)).pack(side="right")

    body = ctk.CTkFrame(page, fg_color="transparent")
    body.pack(fill="both", expand=True)

    txt = tk.Text(
        body, font=("Segoe UI", 12), bg=C_CARD, fg=C_TEXT,
        relief="flat", bd=0, highlightthickness=0, wrap="word",
        padx=20, pady=18)
    from tkinter import ttk as _ttk
    sb = _ttk.Scrollbar(body, command=txt.yview)
    txt.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y", padx=(0, 16), pady=16)
    txt.pack(fill="both", expand=True, padx=(16, 0), pady=16)
    for line in guide_text().splitlines():
        if line.startswith("# "):
            txt.insert("end", line[2:] + "\n", "h1")
        elif line.startswith("## "):
            txt.insert("end", line[3:] + "\n", "h2")
        elif line.startswith("- "):
            txt.insert("end", "  • " + line[2:] + "\n", "li")
        elif line.startswith("> "):
            txt.insert("end", line + "\n", "warn")
        else:
            txt.insert("end", line + "\n")
    txt.tag_config("h1", font=("Segoe UI", 18, "bold"), foreground=C_ACCENT, spacing3=6)
    txt.tag_config("h2", font=("Segoe UI", 14, "bold"), foreground="#7fb0ff", spacing3=4)
    txt.tag_config("li", lmargin1=14, lmargin2=28)
    txt.tag_config("warn", foreground=C_WARN, font=("Segoe UI", 12, "bold"))
    txt.configure(state="disabled")
    return page
