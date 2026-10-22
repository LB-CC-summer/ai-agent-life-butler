"""小智管家 · 大模型核心层（决策层）

负责人：成员 B
职责：System Prompt、意图识别、工具调度（Function Calling）、多轮对话记忆
对外唯一接口：get_agent_response(user_input, history) -> str

约定（见 docs/接口约定.md）：
    - 输入 history 格式：[{"role": "user"|"assistant", "content": "..."}, ...]
    - 返回值为给用户看的中文回复字符串
    - 任何异常都要捕获并返回友好提示，绝不抛给界面层

当前状态：占位实现（Day 1 骨架），Day 4 前由成员 B 替换为真实大模型调用。
占位版不依赖任何第三方库，保证 D 现在就能把界面跑通。
"""

from __future__ import annotations

SYSTEM_PROMPT = """你是「小智管家」，一个贴心、简洁的中文生活助手。

你可以调用以下工具：
1. get_weather(city_name, date)  —— 查询城市天气并给出出行建议
2. save_todo(task_content)       —— 记录一条待办
3. get_todos()                   —— 查看全部待办

规则：
- 用户问天气、温度、下雨、穿什么 → 调用 get_weather
- 用户说"记一下/提醒我/待办" → 调用 save_todo
- 用户问"我有哪些待办" → 调用 get_todos
- 纯闲聊直接回答，不要调用工具
- 城市缺失时先反问"你在哪个城市呀？"
- 回答控制在 100 字以内，口语化，可以带 emoji
"""


def get_agent_response(user_input: str, history: list[dict] | None = None) -> str:
    """TODO(成员 B)：接真实大模型 + Function Calling。

    目标实现步骤：
        1. 用 openai SDK 构造 client（base_url / api_key 从 .env 读取）
        2. messages = [{"role":"system","content":SYSTEM_PROMPT}] + history + 本轮输入
        3. 带上 tools=[...] 发起请求，解析 tool_calls
        4. 命中工具则调用 tools_api 中的函数，把结果作为 role="tool" 消息回填，再请求一次
        5. 返回最终 content
        6. 全过程 try/except，失败返回中文兜底话术
    """
    history = history or []

    # ---- 占位逻辑：让界面先跑起来 ----
    text = (user_input or "").strip()
    if not text:
        return "我在听，你想聊点什么？"
    if "天气" in text or "下雨" in text or "温度" in text:
        return "【占位】收到天气查询～等成员 C 的 get_weather 接上后就能给你真实结果啦。"
    if "记" in text or "待办" in text or "提醒" in text:
        return "【占位】收到待办～等成员 C 的 save_todo 接上后就会写进 todo.txt。"
    return f"【占位回复】你说的是「{text}」。等成员 B 接上大模型后，我就能正常聊天啦～（当前历史 {len(history)//2} 轮）"


if __name__ == "__main__":
    demo_history: list[dict] = []
    for q in ["你好呀", "上海今天天气怎么样", "记一下周五交实验报告"]:
        a = get_agent_response(q, demo_history)
        print(f"用户：{q}\n小智：{a}\n")
        demo_history += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
