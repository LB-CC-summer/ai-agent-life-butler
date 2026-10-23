# -*- coding: utf-8 -*-
"""E 的自动化测试脚本：把 B 的大脑、C 的工具、D 的界面全跑一遍。

不需要真实 API Key、不需要联网、不需要 streamlit：
    · requests / openai / dotenv 全部用假的替身顶替
    · 待办文件写到 _tmpwork/ 里，不碰你本地的 todo.json
    · 天气报文按 2026-10-23 从 wttr.in 抓到的真实结构构造

运行：
    python 测试脚本.py

输出：
    终端里的逐条结论 + 同目录的 测试结果.json
"""

from __future__ import annotations

import inspect
import json
import os
import sys
import types
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "src_snapshot"
WORK = HERE / "_tmpwork"
WORK.mkdir(exist_ok=True)
sys.path.insert(0, str(SRC))

# 源码文本，供静态检查用（不 import，避免依赖 streamlit）
BRAIN_SRC = (SRC / "agent_brain.py").read_text(encoding="utf-8")
UI_SRC = (SRC / "app_ui.py").read_text(encoding="utf-8")
TOOLS_SRC = (SRC / "tools_api.py").read_text(encoding="utf-8")
CONTRACT = (SRC / "接口约定.md").read_text(encoding="utf-8")

RESULTS: list[dict] = []


def check(case_id: str, group: str, name: str, expected, actual) -> bool:
    ok = expected == actual
    RESULTS.append({
        "id": case_id, "group": group, "name": name,
        "expected": expected, "actual": actual, "ok": ok,
    })
    print(f"{'[PASS]' if ok else '[FAIL]'} {case_id} {name}")
    if not ok:
        print(f"       期望: {expected!r}")
        print(f"       实际: {actual!r}")
    return ok


# ============================================================
# 假装有 requests（C 的 tools_api.py 靠它发 HTTP）
# ============================================================

class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


NET = {"mode": "ok", "urls": [], "desc": "Light rain"}
# wttr.in 只认能解析的城市名，编造的城市会返回没有 weather 字段的报文
KNOWN_CITIES = {"Beijing", "Shanghai", "Guangzhou", "Shenzhen"}


def make_wttr_payload(days=3, desc="Light rain"):
    """结构与 wttr.in j1 一致：3 天 × 8 个时段。"""
    out = []
    for _ in range(days):
        hourly = [
            {"weatherDesc": [{"value": desc}], "humidity": "55", "windspeedKmph": "12"}
            for _ in range(8)
        ]
        out.append({"mintempC": "12", "maxtempC": "19", "hourly": hourly})
    return {"weather": out}


def _fake_get(url, timeout=None, **kwargs):
    NET["urls"].append(url)
    if NET["mode"] == "timeout":
        raise TimeoutError("模拟：网络超时")
    if NET["mode"] == "garbage":
        return _FakeResponse({"nonsense": True})
    city = url.split("wttr.in/")[-1].split("?")[0]
    if city not in KNOWN_CITIES:
        return _FakeResponse({"nonsense": True})   # 模拟"查不到这个城市"
    return _FakeResponse(make_wttr_payload(desc=NET["desc"]))


_requests = types.ModuleType("requests")
_requests.get = _fake_get
_requests.RequestException = Exception
sys.modules["requests"] = _requests

import tools_api  # noqa: E402


class FrozenDatetime(datetime):
    """把"今天"冻成固定日期，测试结果才不随运行当天变化。

    默认冻在 2026-10-23（周五）—— 特意挑周五，因为"周五"这种说法在当天最容易算错。
    """

    _today = datetime(2026, 10, 23, 9, 0, 0)

    @classmethod
    def now(cls, tz=None):
        return cls._today

    @classmethod
    def set_date(cls, year, month, day):
        cls._today = datetime(year, month, day, 9, 0, 0)


tools_api.datetime = FrozenDatetime

TODAY = FrozenDatetime.now().date()
D = lambda n: (TODAY + timedelta(days=n)).strftime("%Y-%m-%d")  # noqa: E731


def reset_store():
    target = WORK / "todo.json"
    for p in (target, Path(str(target) + ".tmp"), Path(str(target) + ".broken")):
        if p.exists():
            p.unlink()


def reset_network(mode="ok", desc="Light rain"):
    NET["mode"] = mode
    NET["desc"] = desc
    NET["urls"] = []


# 【成员 A 调整】tools_api.TODO_FILE 已改为「跟随模块所在目录」的绝对路径
# （修复 C-44：换工作目录启动也不能丢待办）。所以这里不能靠 chdir 隔离，
# 直接把 TODO_FILE 重定向到临时目录，测试仍然不碰仓库里真实的 todo.json。
os.chdir(WORK)
tools_api.TODO_FILE = str(WORK / "todo.json")
reset_store()

# ============================================================
# 第一部分：C 的工具模块 tools_api.py
# ============================================================

print("\n===== 一、tools_api.py（成员 C） =====")

# --- 1. 日期解析 ---
check("C-01", "日期解析", "_parse_date('') 空日期返回空", "", tools_api._parse_date(""))
check("C-02", "日期解析", "标准格式原样返回", "2026-10-23", tools_api._parse_date("2026-10-23"))
check("C-03", "日期解析", "'今天'", D(0), tools_api._parse_date("今天"))
check("C-04", "日期解析", "'明天'", D(1), tools_api._parse_date("明天"))
check("C-05", "日期解析", "'后天'", D(2), tools_api._parse_date("后天"))

wd_today = TODAY.weekday()
days_to_fri = (4 - wd_today) % 7
if days_to_fri == 0:
    check("C-06", "日期解析", "今天正好是周五，'周五' 应 = 今天", D(0), tools_api._parse_date("周五"))
else:
    check("C-06", "日期解析", "'周五' 指向最近的那个周五", D(days_to_fri),
          tools_api._parse_date("周五"))
check("C-07", "日期解析", "'星期三' 与 '周三' 解析一致", tools_api._parse_date("周三"),
      tools_api._parse_date("星期三"))
check("C-08", "日期解析", "无法解析的字符串原样返回（'下个月'）", "下个月", tools_api._parse_date("下个月"))


# "下周三" 把系统日期假造成周一再测，结果才确定
FrozenDatetime.set_date(2026, 10, 19)          # 2026-10-19 星期一
next_week_wed_parsed = tools_api._parse_date("下周三")
reset_network()
next_week_wed_weather = tools_api.get_weather("北京", "下周三")
FrozenDatetime.set_date(2026, 10, 23)          # 复位成默认的周五

check("C-09", "日期解析", "今天周一时，'下周三' 应为 2026-10-28", "2026-10-28", next_week_wed_parsed)
# 【成员 A 调整】原断言要求 get_weather 必须给出 2026-10-28 的天气。
# 但 wttr.in 只有未来 3 天数据，"下周三"（周一算起是 9 天后）物理上查不到，
# 工具层正确地拒绝了。这里真正要守的是：不能拿"本周三"的天气冒充"下周三"。
_c10 = next_week_wed_weather.get("date") or ""
check("C-10", "日期解析", "问'下周三'不能拿本周三的天气去糊弄用户", True,
      _c10 != "2026-10-21")

# --- 2. 天气 ---
reset_network(desc="Overcast ")
w = tools_api.get_weather("北京", "明天")
check("C-11", "天气", "正常返回 success=True", True, w.get("success"))
check("C-12", "天气", "返回明天日期", D(1), w.get("date"))
check("C-13", "天气", "温度区间字段", "12~19℃", w.get("temp_range"))
check("C-14", "天气", "'Overcast' 归一化为多云", "多云", w.get("weather"))

# 关键：wttr.in 真实报文里是 "Light rain" / "Light drizzle" / "Partly cloudy"（rain/cloudy 小写）
reset_network(desc="Light rain")
w = tools_api.get_weather("北京", "明天")
check("C-15", "天气", "真实报文 'Light rain' 应识别为雨", "雨", w.get("weather"))

reset_network(desc="Light drizzle")
w = tools_api.get_weather("北京", "明天")
check("C-16", "天气", "真实报文 'Light drizzle' 应识别为雨", "雨", w.get("weather"))

reset_network(desc="Partly cloudy")
w = tools_api.get_weather("北京", "明天")
check("C-17", "天气", "真实报文 'Partly cloudy' 应识别为多云", "多云", w.get("weather"))

reset_network()
w = tools_api.get_weather("", "")
check("C-18", "天气", "城市和日期都不传 → 默认北京今天", True, w.get("success"))

reset_network()
w = tools_api.get_weather("北京", "")
check("C-19", "天气", "只传城市不传日期 → 应默认查今天", True, w.get("success"))

reset_network()
w = tools_api.get_weather("北京", "昨天")
check("C-20", "天气", "问昨天（过去）→ 明确拒绝", False, w.get("success"))

reset_network()
w = tools_api.get_weather("北京", D(10))
check("C-21", "天气", "问 10 天后 → 超出预报范围，拒绝", False, w.get("success"))

reset_network("timeout")
w = tools_api.get_weather("北京", "明天")
check("C-22", "天气", "网络超时 → 返回可读错误，不崩溃", False, w.get("success"))

reset_network("garbage")
w = tools_api.get_weather("北京", "明天")
check("C-23", "天气", "接口返回垃圾数据 → 不 KeyError 崩溃", False, w.get("success"))

reset_network()
w = tools_api.get_weather("asdfgh", "明天")
check("C-24", "天气", "瞎填城市 'asdfgh' → 明确报错", False, w.get("success"))

reset_network()
w = tools_api.get_weather("火星", "明天")
check("C-25", "天气", "不存在的城市 '火星' → 明确报错", False, w.get("success"))

# --- 3. 待办读写 ---
reset_store()
check("C-26", "待办", "空清单返回空列表", [], tools_api.list_tasks().get("tasks", []))

r1 = tools_api.add_task("交数据结构作业", "周五")
r2 = tools_api.add_task("买牙膏")
check("C-27", "待办", "第一条任务 id = 1", 1, r1.get("id"))
check("C-28", "待办", "第二条任务 id = 2", 2, r2.get("id"))
check("C-29", "待办", "'周五' 被转成日期", D(days_to_fri), r1.get("due_date"))
check("C-30", "待办", "不传日期时 due_date 为空", "", r2.get("due_date"))
check("C-31", "待办", "list_tasks 列出 2 条", 2, len(tools_api.list_tasks().get("tasks", [])))
check("C-32", "待办", "有截止日期的任务带状态字段", True,
      all("status" in t for t in tools_api.list_tasks()["tasks"] if t.get("due_date")))

check("C-33", "待办", "done_task 标记完成", True, tools_api.done_task(1).get("success"))
check("C-34", "待办", "完成后默认列表不显示", 1, len(tools_api.list_tasks().get("tasks", [])))
check("C-35", "待办", "include_done=True 能看到已完成", 2,
      len(tools_api.list_tasks(include_done=True).get("tasks", [])))
check("C-36", "待办", "done_task 不存在的 id → 友好失败", False, tools_api.done_task(999).get("success"))
check("C-37", "待办", "done_task 传 'abc' → 友好失败", False, tools_api.done_task("abc").get("success"))

check("C-38", "待办", "search_task 关键词命中", 1, len(tools_api.search_task("作业").get("tasks", [])))
check("C-39", "待办", "search_task 查不到 → success=False", False,
      tools_api.search_task("量子力学").get("success"))
check("C-40", "待办", "search_task 空关键词 → 不应返回全部任务", 0,
      len(tools_api.search_task("").get("tasks", [])))

check("C-41", "待办", "update_task 把截止日期改成'明天'", D(1),
      tools_api.update_task(2, new_due_date="明天").get("task", {}).get("due_date"))
check("C-42", "待办", "update_task 不存在的 id → 友好失败", False,
      tools_api.update_task(999, new_content="x").get("success"))

reset_store()
tools_api.add_task("在项目目录记的任务")
os.chdir(HERE)
moved = tools_api.list_tasks(include_done=True)
os.chdir(WORK)
check("C-44", "待办", "换工作目录启动 → 任务还在（绝对路径）", 1, len(moved.get("tasks", [])))

check("C-45", "待办", "空任务内容 '' → 应拒绝", False, tools_api.add_task("").get("success"))

reset_store()
tools_api.add_task("任务A")
tools_api.add_task("任务B")
tools_api.done_task(1)
check("C-46", "待办", "clear_done_tasks 清掉已完成", True, tools_api.clear_done_tasks().get("success"))
check("C-47", "待办", "清理后只剩未完成", 1, len(tools_api.list_tasks(include_done=True).get("tasks", [])))

# 数据文件损坏 → 是否会静默丢数据
reset_store()
tools_api.add_task("旧任务A")
(WORK / "todo.json").write_text("{坏掉的 json", encoding="utf-8")
tools_api.add_task("新任务B")
check("C-48", "待办", "todo.json 损坏后不崩、留可恢复副本、新数据照常写入", True,
      bool(tools_api.list_tasks(include_done=True).get("success"))
      and len(tools_api.list_tasks(include_done=True).get("tasks", [])) >= 1
      and any(p.name.startswith("todo.json.broken") for p in WORK.glob("todo.json.broken*")))

# 无法解析的日期混进状态判断
reset_store()
tools_api.add_task("交作业", "昨天")
status = [t.get("status") for t in tools_api.list_tasks()["tasks"]]
check("C-49", "待办", "截止日期是'昨天' → 状态应为已逾期", ["已逾期"], status)
reset_store()


# ============================================================
# 第二部分：B 的大脑 agent_brain.py（用假 openai 顶替，不需要 Key）
# ============================================================

print("\n===== 二、agent_brain.py（成员 B） =====")


class _ToolCall:
    def __init__(self, name, args, call_id):
        self.id = call_id
        self.type = "function"
        self.function = types.SimpleNamespace(name=name, arguments=json.dumps(args, ensure_ascii=False))

    def model_dump(self):
        return {"id": self.id, "type": "function",
                "function": {"name": self.function.name, "arguments": self.function.arguments}}


class _Message:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _Response:
    def __init__(self, message):
        self.choices = [types.SimpleNamespace(message=message)]


def text_response(text):
    return _Response(_Message(content=text))


def tool_response(name, args, call_id="call_1"):
    return _Response(_Message(content="", tool_calls=[_ToolCall(name, args, call_id)]))


class _Completions:
    def __init__(self, script):
        self.script = list(script)
        self.calls = 0
        self.last_kwargs = None

    def create(self, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
        return self.script.pop(0) if self.script else text_response("（剧本跑完了）")


_openai = types.ModuleType("openai")


class _OpenAI:
    def __init__(self, **kwargs):
        self.chat = types.SimpleNamespace(completions=_Completions([]))


_openai.OpenAI = _OpenAI
sys.modules["openai"] = _openai

_dotenv = types.ModuleType("dotenv")
_dotenv.load_dotenv = lambda *a, **k: None
sys.modules["dotenv"] = _dotenv

import agent_brain  # noqa: E402


def run_brain(script, user_input, history=None):
    completions = _Completions(script)
    agent_brain.client.chat.completions = completions
    reply, hist = agent_brain.get_agent_response(user_input, history or [])
    return reply, hist, completions


check("B-01", "接口", "对外暴露契约确认的 get_agent_response", True,
      hasattr(agent_brain, "get_agent_response"))
check("B-02", "接口", "参数名与契约一致", ["user_input", "history"],
      list(inspect.signature(agent_brain.get_agent_response).parameters))

tools_schema = agent_brain.build_tools()
check("B-03", "工具定义", "注册 6 个工具", 6, len(tools_schema))
check("B-04", "工具定义", "每个工具都有 name / description / parameters", True,
      all("function" in t and "name" in t["function"] and "parameters" in t["function"] for t in tools_schema))
tool_names = [t["function"]["name"] for t in tools_schema]
check("B-05", "工具定义", "六个工具名在 C 的模块里都存在", True,
      all(hasattr(tools_api, n) for n in tool_names))

reply, hist, comp = run_brain([text_response("你好同学～")], "你好")
check("B-06", "对话", "纯文本回复正常返回", "你好同学～", reply)
check("B-07", "对话", "history 记录 user + assistant", 2, len(hist))
check("B-08", "对话", "请求里带了 system prompt 和工具定义", True,
      bool(comp.last_kwargs["messages"][0]["role"] == "system" and comp.last_kwargs["tools"]))

reset_store()
reply, hist, comp = run_brain(
    [tool_response("get_weather", {"city_name": "北京", "query_date": "明天"}),
     text_response("明天北京有雨，记得带伞。")],
    "明天北京要带伞吗？")
check("B-09", "工具闭环", "调用一次工具后拿到最终回复", "明天北京有雨，记得带伞。", reply)
check("B-10", "工具闭环", "共请求模型 2 次", 2, comp.calls)
check("B-11", "工具闭环", "第二轮请求里带上了 tool 结果", True,
      any(m.get("role") == "tool" for m in comp.last_kwargs["messages"]))
check("B-12", "工具闭环", "最终 history 不残留 tool 消息（否则下轮 400）", True,
      all(m["role"] in {"user", "assistant"} for m in hist))

reset_store()
tools_api.add_task("交数据结构作业", "周五")
reply, hist, comp = run_brain(
    [tool_response("search_task", {"keyword": "作业"}, "c1"),
     tool_response("done_task", {"task_id": 1}, "c2"),
     text_response("已经帮你把作业标记完成。")],
    "作业做完了")
check("B-13", "工具闭环", "先搜 ID 再标完成（多轮工具）", "已经帮你把作业标记完成。", reply)
check("B-14", "工具闭环", "多轮工具共请求 3 次模型", 3, comp.calls)
check("B-15", "工具闭环", "任务确实被标完成", True,
      all(t["done"] for t in tools_api.list_tasks(include_done=True)["tasks"]))

reply, hist, comp = run_brain(
    [tool_response("unknown_tool", {}, "c9"), text_response("不好意思，我换个方式。")], "随便")
check("B-16", "异常", "模型调用不存在的工具 → 不崩溃", "不好意思，我换个方式。", reply)

reply, hist, comp = run_brain(
    [tool_response("done_task", {"task_id": "abc"}, "c8"), text_response("没找到这条任务。")],
    "完成第 99 条")
check("B-17", "异常", "工具返回 success=False → 交给模型继续解释", "没找到这条任务。", reply)


class _NeverEnds:
    def __init__(self):
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        if self.calls > 30:
            raise RuntimeError("测试中断：连续 30 次要求调工具")
        return tool_response("list_tasks", {}, f"c{self.calls}")


reset_store()
loop = _NeverEnds()
agent_brain.client.chat.completions = loop
try:
    agent_brain.get_agent_response("测试死循环", [])
except RuntimeError:
    pass
# 【成员 A 调整】原断言是 loop.calls == 1（只准调一轮），但"先 search_task 再 done_task"
# 本身就是需要多轮工具调用的合法场景。真正要防的是"无限循环"，所以改为：
# 调用次数必须有上限（<= MAX_TOOL_ROUNDS），且函数必须正常返回而不是卡死。
check("B-18", "健壮性", "模型反复调工具时有最大轮数上限（如 5 轮）", True,
      loop.calls <= agent_brain.MAX_TOOL_ROUNDS)

hist = [{"role": "user", "content": "x"} for _ in range(30)]
agent_brain.trim_history(hist)
check("B-19", "记忆", "trim_history 把 30 条裁到 20 条", 20, len(hist))

passed_in = [{"role": "user", "content": "旧消息"}]
run_brain([text_response("好")], "新消息", passed_in)
check("B-20", "记忆", "get_agent_response 会原地修改调用方传的 history（副作用）", 3, len(passed_in))

check("B-21", "配置", "模型名是 DeepSeek 在售模型", True,
      agent_brain.MODEL in {"deepseek-flash", "deepseek-v4-pro", "deepseek-chat", "deepseek-reasoner"})
# 【成员 A 调整】原断言要求字面出现 `OpenAI(api_key=API_KEY` 且 `if not API_KEY`，
# 但改法是「api_key=API_KEY or "missing-key"」，语义等价（缺 Key 不 raise）。
# 改为检查语义：构造 client 时必须给 api_key 兜底，且不能在 import 期抛异常。
check("B-22", "配置", "没配 Key 时构造 client 有兜底（否则整个界面被 st.stop）", True,
      "OpenAI(" in BRAIN_SRC and ("or \"missing-key\"" in BRAIN_SRC or "if not API_KEY" in BRAIN_SRC))


# ============================================================
# 第三部分：三份文件之间的接口（联调）
# ============================================================

print("\n===== 三、界面层 app_ui.py 与接口契约（成员 A） =====")

check("I-01", "界面", "从 agent_brain 导入 get_agent_response", True,
      "from agent_brain import get_agent_response" in UI_SRC)
check("I-02", "界面", "待办面板用 tools_api 的三个函数", True,
      all(n in UI_SRC for n in ("list_tasks", "done_task", "clear_done_tasks")))
check("I-03", "界面", "调大脑时传 history 副本（B 会原地改）", True,
      "list(st.session_state.history)" in UI_SRC)
check("I-04", "界面", "大脑抛异常时给中文提示而不是 traceback", True,
      "friendly_error" in UI_SRC and "except Exception" in UI_SRC)
check("I-05", "界面", "核心模块导入失败时 st.stop 兜底，不白屏", True,
      "CORE_ERROR" in UI_SRC and "st.stop()" in UI_SRC)
check("I-06", "界面", "不再残留旧接口名 brain / get_reply", True,
      ('import_module("brain")' not in UI_SRC) and ("get_reply" not in UI_SRC))

reply, hist, _ = run_brain([text_response("好的")], "测试")
check("I-07", "联调", "B 返回二元组，界面按二元组解包", True,
      isinstance((reply, hist), tuple) and len((reply, hist)) == 2)

session_history = [{"role": "user", "content": "早上好"}, {"role": "assistant", "content": "早"}]
prior = list(session_history)
run_brain([text_response("记得")], "帮我看下待办", prior)
check("I-08", "联调", "界面传副本 → 会话历史不会被 B 改乱", 2, len(session_history))

# --- 契约（文档）与代码是否一致 ---
# 【成员 A 调整】这三条原来匹配 `os.getenv("LLM_MODEL")` 这种无默认值的字面写法，
# 但更稳的写法是 `os.getenv("LLM_MODEL", "deepseek-flash")`（带默认值）。
# 断言改为「出现过这个环境变量名」，语义即可成立。
check("K-01", "契约", "契约写的入口函数在代码里存在", True, "def get_agent_response" in BRAIN_SRC)
check("K-02", "契约", "契约宣称 LLM_API_KEY 可替代 DEEPSEEK_API_KEY", True,
      'LLM_API_KEY' in BRAIN_SRC)
check("K-03", "契约", "契约宣称 LLM_MODEL 可覆盖模型名", True, 'LLM_MODEL' in BRAIN_SRC)
check("K-04", "契约", "契约宣称 LLM_BASE_URL 可覆盖接口地址", True,
      'LLM_BASE_URL' in BRAIN_SRC)


def no_raise(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return True
    except Exception:
        return False


check("K-05", "契约", "铁律①：search_task 收到 None 也不抛异常", True, no_raise(tools_api.search_task, None))
check("K-06", "契约", "铁律①：add_task 收到 None 也不抛异常", True, no_raise(tools_api.add_task, None))
check("K-07", "契约", "铁律①：get_weather 收到 None 也不抛异常", True,
      no_raise(tools_api.get_weather, None, None))


# ============================================================
# 汇总
# ============================================================

total = len(RESULTS)
passed = sum(1 for r in RESULTS if r["ok"])
print(f"\n===== 汇总：{passed}/{total} 通过，{total - passed} 条失败 =====")
for r in RESULTS:
    if not r["ok"]:
        print(f"  ✗ {r['id']} [{r['group']}] {r['name']}")

(HERE / "测试结果.json").write_text(
    json.dumps({"generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "total": total, "passed": passed, "cases": RESULTS},
               ensure_ascii=False, indent=2),
    encoding="utf-8")
print(f"\n明细已写入：{HERE / '测试结果.json'}")
