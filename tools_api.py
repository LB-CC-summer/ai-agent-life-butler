"""小智管家 · 工具层（能力层）

负责人：成员 C
职责：天气 API 调用、待办文件读写、规则化生活建议
对外接口（见 docs/接口约定.md）：
    get_weather(city_name, date="today") -> str
    save_todo(task_content) -> str
    get_todos() -> str

三条铁律：
    - 一律返回字符串，出错也返回中文提示，不抛异常
    - 网络请求必须有超时（8 秒）
    - 文件读写统一 encoding="utf-8"

当前状态：占位实现（Day 1 骨架），Day 3 前由成员 C 替换为真实实现。
可用 `python tools_api.py` 直接自测。
"""

from __future__ import annotations

import os
from pathlib import Path

TODO_FILE = Path(__file__).parent / "todo.txt"


def get_weather(city_name: str, date: str = "today") -> str:
    """TODO(成员 C)：调用高德 / 心知天气 API。

    目标实现步骤：
        1. city_name 为空 → 返回 "你在哪个城市呀？"
        2. 先调地理编码接口把中文城市名换成 adcode
        3. 再调天气预报接口取实况/预报
        4. 拼成自然语言："上海 今天 多云转阴，18~24℃。建议：加件薄外套。"
        5. requests.get(..., timeout=8)，异常统一返回中文提示
    """
    if not city_name:
        return "你在哪个城市呀？告诉我城市名我就去查～"

    label = "明天" if date == "tomorrow" else "今天"
    has_key = bool(os.getenv("WEATHER_API_KEY"))
    if not has_key:
        return f"【占位】{city_name}{label}的天气：等成员 C 配好 WEATHER_API_KEY 并接入 API 后返回真实数据。"
    return f"【占位】{city_name}{label}的天气：API 已接入但实现未完成（成员 C 开发中）。"


def save_todo(task_content: str) -> str:
    """TODO(成员 C)：追加写入 todo.txt。

    目标实现步骤：
        1. task_content 为空 → 返回 "要记什么呢？说给我听～"
        2. 以 utf-8 追加一行（建议带时间戳），文件不存在则自动创建
        3. 返回 "✅ 已记录待办：xxx（当前共 N 条）"
    """
    if not task_content:
        return "要记什么呢？说给我听～"
    return f"【占位】收到待办「{task_content}」，等成员 C 接上文件读写后就会存进 todo.txt。"


def get_todos() -> str:
    """TODO(成员 C)：读取 todo.txt 并列表化。"""
    return "【占位】待办列表：等成员 C 实现 get_todos 后显示。"


if __name__ == "__main__":
    # 成员 C 的自测入口：python tools_api.py
    print("== get_weather ==")
    print(get_weather("上海"))
    print(get_weather("", "tomorrow"))
    print("\n== save_todo ==")
    print(save_todo("周五下午三点交实验报告"))
    print("\n== get_todos ==")
    print(get_todos())
