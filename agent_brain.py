# -*- coding: utf-8 -*-
"""
Agent 核心大脑模块 (agent_brain.py)
负责与大语言模型（LLM）交互、管理对话历史、并执行 Function Calling（工具调用）闭环。
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv
import tools_api  # 导入队友 C 编写的底层工具函数库（天气、待办等）

# ================= 1. 基础配置与初始化 =================
load_dotenv()  # 从 .env 文件中加载环境变量（保护 API Key 不泄露）

# --- 成员 A 整合改动（Day 4）：配置改为可被 .env 覆盖；缺 Key 时不在 import 阶段崩溃 ---
# 原因：界面层必须 import 本模块。若 Key 未配置就 raise，整个网页直接白屏；
#      改为占位 key，把错误推迟到真正发请求那一刻，由界面层给出友好提示。
MODEL = os.getenv("LLM_MODEL", "deepseek-flash")
BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
API_KEY = os.getenv("DEEPSEEK_API_KEY") or os.getenv("LLM_API_KEY") or ""

client = OpenAI(api_key=API_KEY or "missing-key", base_url=BASE_URL)

# 记忆滑动窗口大小：最多保留 20 条对话记录（约 10 轮），防止 Token 消耗过大或超限
MAX_HISTORY_MESSAGES = 20

# ================= 2. 核心提示词 (System Prompt) =================
# 这里定义了 Agent 的“人设”和“工具使用规范”，是让大模型变聪明的关键。
SYSTEM_PROMPT = (
    "你是“贴心的大学生生活管家”，一位热心又靠谱的同学。\n"
    "【核心技能与工具调用规则】\n"
    "1. 查天气：调用 get_weather。用户没说日期默认查今天，说'明天/周五'就传对应参数。"
    "收到工具返回的天气和温度后，**请你自己发挥，给出一句温暖的出行、穿衣或运动建议**，不要生硬地念数据。\n"
    "2. 记待办：调用 add_task。务必从用户话中提取截止时间（如'周五'、'明天'）传给 due_date，没提就留空。\n"
    "3. 查待办：调用 list_tasks。工具会返回任务状态（已逾期/今天截止/未到期），请据此提醒用户。\n"
    "4. 完成任务：调用 done_task。如果用户只说事情名字（如'把作业做了'），**必须先用 search_task 搜出 ID**，再调 done_task。\n"
    "5. 修改任务：调用 update_task。用户说'改到周六'时使用。\n"
    "【语气】像同寝室的同学一样亲切、口语化。如果用户没说城市，查天气前必须先反问！"
)

# ================= 3. 工具定义 (JSON Schema) =================
def build_tools() -> list:
    """
    将底层 Python 函数转化为 OpenAI 标准格式的 JSON Schema。
    大模型通过读取这里的 description 和 parameters，来决定何时调用、以及如何传参。
    """
    return [
        {"type": "function", "function": {"name": "get_weather", "description": "查询指定城市天气，支持自然语言日期（如'明天'）。", "parameters": {"type": "object", "properties": {"city_name": {"type": "string", "description": "城市名"}, "query_date": {"type": "string", "description": "日期，如'今天'、'明天'、'周五'，不传默认今天"}}, "required": ["city_name"]}}},
        {"type": "function", "function": {"name": "add_task", "description": "记录待办事项。", "parameters": {"type": "object", "properties": {"task_content": {"type": "string", "description": "任务内容"}, "due_date": {"type": "string", "description": "截止日期，如'明天'，可选"}}, "required": ["task_content"]}}},
        {"type": "function", "function": {"name": "list_tasks", "description": "查看待办清单，返回结果自带状态（已逾期/今天截止）。", "parameters": {"type": "object", "properties": {"include_done": {"type": "boolean", "description": "是否包含已完成"}}}}},
        {"type": "function", "function": {"name": "search_task", "description": "通过关键词模糊搜索任务，返回对应的 ID。", "parameters": {"type": "object", "properties": {"keyword": {"type": "string", "description": "搜索关键词"}}, "required": ["keyword"]}}},
        {"type": "function", "function": {"name": "done_task", "description": "把指定 id 的待办标记为已完成。", "parameters": {"type": "object", "properties": {"task_id": {"type": "integer", "description": "任务 ID"}}, "required": ["task_id"]}}},
        {"type": "function", "function": {"name": "update_task", "description": "修改任务内容或截止日期。", "parameters": {"type": "object", "properties": {"task_id": {"type": "integer", "description": "任务 ID"}, "new_content": {"type": "string", "description": "新内容，不修改留空"}, "new_due_date": {"type": "string", "description": "新日期，不修改留空"}}, "required": ["task_id"]}}}
    ]

# ================= 4. 工具路由与执行 =================
def call_tool(name: str, args: dict) -> dict:
    """
    根据大模型决定调用的工具名称（name）和参数（args），去真正执行队友 C 写的代码。
    使用 try-except 封装，防止底层代码报错导致整个 Agent 崩溃。
    """
    try:
        # 兼容大模型可能传空字符串的情况，使用 args.get() 防止 KeyError 报错
        if name == "get_weather": return tools_api.get_weather(args.get("city_name", "北京"), args.get("query_date", ""))
        elif name == "add_task": return tools_api.add_task(args.get("task_content", ""), args.get("due_date", ""))
        elif name == "list_tasks": return tools_api.list_tasks(args.get("include_done", False))
        elif name == "search_task": return tools_api.search_task(args.get("keyword", ""))
        elif name == "done_task": return tools_api.done_task(args.get("task_id", 0))
        elif name == "update_task": return tools_api.update_task(args.get("task_id", 0), args.get("new_content", ""), args.get("new_due_date", ""))
        else: return {"success": False, "message": f"未知工具：{name}"}
    except Exception as e:
        return {"success": False, "message": f"工具调用出错：{e}"}

# ================= 5. 记忆管理 =================
def trim_history(history: list) -> list:
    """
    滑动窗口机制：如果历史记录超过 20 条，就删掉最前面的旧记录。
    注意：我们在下面已经做了“清洗”，history 里只有纯文本对话，所以直接删很安全。
    """
    while len(history) > MAX_HISTORY_MESSAGES:
        history.pop(0)
    return history

# ================= 6. 核心大脑逻辑 (对外暴露的唯一接口) =================
def get_agent_response(user_input: str, history: list = None):
    """
    接收用户输入，返回 AI 的最终回复和更新后的历史记录。
    内部自动处理大模型与外部工具的多次交互。
    """
    if history is None: history = []
    
    # 1. 将用户说的话加入历史
    history.append({"role": "user", "content": user_input})
    
    # 2. 组装本次请求的消息：System Prompt + 历史记录 (注意：System 不进 history)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    # 3. 开启循环，处理大模型可能的多次工具调用（比如先搜ID，再标完成）
    while True:
        # 发送请求给大模型，并附带工具描述
        response = client.chat.completions.create(
            model=MODEL, messages=messages, tools=build_tools(), tool_choice="auto"
        )
        message = response.choices[0].message

        # 情况 A：大模型决定调用工具
        if message.tool_calls:
            # 3.1 把大模型“打算调用工具”的意图记录到临时消息列表
            assistant_msg = {"role": "assistant", "content": message.content or "", "tool_calls": [tc.model_dump() for tc in message.tool_calls]}
            messages.append(assistant_msg)
            
            # 3.2 逐个执行工具，并把结果塞回去
            for tc in message.tool_calls:
                try: args = json.loads(tc.function.arguments or "{}")
                except: args = {}
                
                # 真正去执行队友的函数
                tool_result = call_tool(tc.function.name, args)
                
                # 3.3 把执行结果作为 "role: tool" 塞给大模型
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(tool_result, ensure_ascii=False)})
            
            # 3.4 continue 回到循环开头，大模型拿着工具结果继续思考
            continue

        # 情况 B：大模型给出了最终的纯文本回复
        final_text = message.content or ""
        
        # 极其关键的一步：只把最终的文本存进 history！
        # 这样就把底层的 tool 交互记录全部丢弃了，彻底避免下一轮对话报 400 错误。
        history.append({"role": "assistant", "content": final_text})
        
        # 裁剪历史记录防止过长
        history = trim_history(history)
        return final_text, history

# ================= 7. 本地终端测试入口 =================
if __name__ == "__main__":
    print("管家已启动，输入 q 退出")
    history = []
    while True:
        try: user_input = input("你 > ").strip()
        except (EOFError, KeyboardInterrupt): break
        
        # 退出指令
        if user_input.lower() in {"q", "quit", "exit"}: break
        if not user_input: continue
        
        try:
            reply, history = get_agent_response(user_input, history)
            print(f"管家 > {reply}")
        except Exception as e:
            print(f"管家 > 出错了：{e}")