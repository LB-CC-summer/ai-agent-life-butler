import json
import os
import requests
from datetime import datetime, timedelta
from pathlib import Path
import re

# 【成员 A 修复 C-44】用绝对路径，避免换个工作目录启动就找不到待办文件
TODO_FILE = str(Path(__file__).resolve().parent / "todo.json")


# ========== 智能日期解析器（防大模型乱传） ==========
def _parse_date(date_str: str) -> str:
    """把'明天'、'周五'等自然语言转成 YYYY-MM-DD，失败则返回原值。"""
    if not date_str: return ""

    today = datetime.now().date()

    # 如果已经是标准格式，直接返回
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    except ValueError:
        pass

    # 匹配自然语言
    if "今天" in date_str: return today.strftime("%Y-%m-%d")
    if "明天" in date_str: return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    if "后天" in date_str: return (today + timedelta(days=2)).strftime("%Y-%m-%d")
    # 【成员 A 修复 C-49】补上"昨天"等过去日期，否则 due_date 存成字符串"昨天"，
    # list_tasks 的"已逾期"判断永远命中不了。
    if "昨天" in date_str or "昨日" in date_str: return (today - timedelta(days=1)).strftime("%Y-%m-%d")
    if "前天" in date_str: return (today - timedelta(days=2)).strftime("%Y-%m-%d")

    # 匹配星期几（如 "周五" 或 "星期五"）
    weekdays = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
    match = re.search(r'(?:周|星期)([一二三四五六日天])', date_str)
    if match:
        target_weekday = weekdays[match.group(1)]
        current_weekday = today.weekday()
        days_ahead = target_weekday - current_weekday

        # 【成员 A 修复 C-06】"今天就是周五"时说"周五"，指的是今天，不是下周
        # 原来 `<= 0` 会把当天也推到下周；只有真正"已经过去"才加 7 天。
        if "下" in date_str:
            # "下周三"：始终指下一周的周三。先取本周内的偏移，
            # 若本周还没到就 +7 直接跳到下周；若本周已过（days_ahead < 0）再 +7 才对。
            days_ahead += 7
        elif days_ahead < 0:
            days_ahead += 7

        return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    # 实在解析不了，就把原字符串扔回去，让大模型自己看着办
    return date_str


# ========== 天气模块 ==========

def get_weather(city_name: str = "北京", query_date: str = "") -> dict:
    """查询指定城市天气。支持自然语言日期与YYYY-MM-DD格式。"""
    if not city_name: city_name = "北京"

    today = datetime.now().date()
    # 【成员 A 修复 C-18 / C-19】不传日期（或传空串）时，默认查今天，而不是报"无法解析日期"
    target_date_str = _parse_date(query_date) or today.strftime("%Y-%m-%d")

    try:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    except ValueError:
        return {"success": False, "message": f"无法解析日期 '{query_date}'，请提供如'明天'或'2026-10-23'的格式。"}

    delta_days = (target_date - today).days

    if delta_days < 0:
        return {"success": False, "message": f"您查询的是过去的日期，我无法预测历史天气。"}
    if delta_days > 2:
        return {"success": False, "message": f"您查询的日期距今有 {delta_days} 天，超出预测范围。"}

    # 调接口
    city_map = {"北京": "Beijing", "上海": "Shanghai", "广州": "Guangzhou", "深圳": "Shenzhen"}
    query_city = city_map.get(city_name, city_name)

    try:
        resp = requests.get(f"https://wttr.in/{query_city}?format=j1", timeout=8)
        data = resp.json()
    except Exception as e:
        return {"success": False, "message": f"网络异常：{e}"}

    if "weather" not in data:
        return {"success": False, "message": "查询失败，请检查城市名。"}

    day_data = data["weather"][delta_days]

    # 聚合早中晚天气，让大模型建议更准
    def get_desc(hour_idx):
        desc = day_data["hourly"][hour_idx]["weatherDesc"][0]["value"]
        # 【成员 A 修复 C-15 / C-16 / C-17】wttr.in 真实报文是小写
        # （"Light rain" / "Light drizzle" / "Partly cloudy"），
        # 原来只匹配大写首字母，导致所有天气都被判成"晴"。统一转小写再判。
        d = desc.lower()
        if "rain" in d or "shower" in d or "drizzle" in d or "thunder" in d: return "雨"
        if "snow" in d or "sleet" in d or "blizzard" in d: return "雪"
        if "cloud" in d or "overcast" in d or "mist" in d or "fog" in d: return "多云"
        return "晴"

    morning = get_desc(2)  # 6点
    noon = get_desc(4)  # 12点
    evening = get_desc(6)  # 18点

    # 如果全天一样，就简写；如果不一样，就详细列出
    if morning == noon == evening:
        weather_summary = morning
    else:
        weather_summary = f"早:{morning} 中:{noon} 晚:{evening}"

    return {
        "success": True,
        "city": city_name,
        "date": target_date_str,
        "weather": weather_summary,
        "temp_range": f"{day_data['mintempC']}~{day_data['maxtempC']}℃",
        "humidity": f"{day_data['hourly'][4]['humidity']}%",
        "wind": f"{day_data['hourly'][4]['windspeedKmph']}km/h",
        "tip": "请根据以上温度变化和天气现象，给用户提供穿衣和带伞建议。"
    }


# ========== 待办模块 ==========

def _load_tasks() -> list:
    if not os.path.exists(TODO_FILE): return []
    try:
        with open(TODO_FILE, "r", encoding="utf-8") as f:
            return [t for t in json.load(f) if "task" in t]
    except Exception:
        # 【成员 A 修复 C-48】todo.json 损坏时，先把它备份成 .broken，
        # 再用空列表继续工作 —— 既不让程序崩，也不静默丢掉用户数据的可恢复副本。
        try:
            broken = f"{TODO_FILE}.broken"
            if os.path.exists(broken):
                broken = f"{TODO_FILE}.broken.{int(datetime.now().timestamp())}"
            os.replace(TODO_FILE, broken)
        except Exception:
            pass
        return []


def _save_tasks(tasks: list) -> None:
    # 【成员 A 修复 C-48】先写临时文件再原子替换，避免写一半断电把文件写坏
    tmp = f"{TODO_FILE}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)
    os.replace(tmp, TODO_FILE)


def _next_id(tasks: list) -> int:
    return max((t["id"] for t in tasks), default=0) + 1


def add_task(task_content: str, due_date: str = "") -> dict:
    # 【成员 A 修复 C-45 / K-06】空内容或 None 一律拒绝，而不是存一条空待办
    if not task_content or not str(task_content).strip():
        return {"success": False, "message": "要记什么呢？说给我听～"}

    tasks = _load_tasks()
    parsed_date = _parse_date(due_date)  # 智能解析
    new_task = {
        "id": _next_id(tasks),
        "task": str(task_content).strip(),
        "due_date": parsed_date,
        "done": False
    }
    tasks.append(new_task)
    _save_tasks(tasks)
    return {"success": True, "id": new_task["id"], "task": new_task["task"], "due_date": new_task["due_date"]}


def list_tasks(include_done: bool = False) -> dict:
    tasks = _load_tasks()
    today_str = datetime.now().strftime("%Y-%m-%d")

    if not include_done:
        tasks = [t for t in tasks if not t.get("done")]

    for t in tasks:
        if t.get("due_date") and not t["done"]:
            if t["due_date"] < today_str:
                t["status"] = "已逾期"
            elif t["due_date"] == today_str:
                t["status"] = "今天截止"
            else:
                t["status"] = "未到期"

    if not tasks:
        return {"success": True, "tasks": [], "message": "当前没有待办事项。"}

    return {"success": True, "tasks": tasks}


def search_task(keyword: str) -> dict:
    # 【成员 A 修复 C-40】空关键词匹配所有任务，等于把全部待办都当成"搜索结果"返回，
    # 会让大模型误以为用户搜到了东西。空关键词一律按"没找到"处理。
    if not keyword or not str(keyword).strip():
        return {"success": False, "message": "要搜哪个任务呢？给个关键词吧～"}

    tasks = _load_tasks()
    matched = [t for t in tasks if str(keyword).strip() in t["task"]]
    if not matched:
        return {"success": False, "message": f"没有找到包含 '{keyword}' 的任务。"}
    return {"success": True, "tasks": matched}


def done_task(task_id: int) -> dict:
    try:
        task_id = int(task_id)
    except Exception:
        return {"success": False, "message": "任务 ID 必须是数字"}
    tasks = _load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            t["done"] = True
            _save_tasks(tasks)
            return {"success": True, "message": f"任务 [{t['task']}] 已完成"}
    return {"success": False, "message": f"没有找到 id 为 {task_id} 的任务"}


def update_task(task_id: int, new_content: str = "", new_due_date: str = "") -> dict:
    try:
        task_id = int(task_id)
    except Exception:
        return {"success": False, "message": "任务 ID 必须是数字"}
    tasks = _load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            if new_content: t["task"] = new_content.strip()
            if new_due_date: t["due_date"] = _parse_date(new_due_date)  # 智能解析
            _save_tasks(tasks)
            return {"success": True, "message": "任务修改成功", "task": t}
    return {"success": False, "message": f"没有找到 id 为 {task_id} 的任务"}


def clear_done_tasks() -> dict:
    """清理所有已完成的任务，保持文件清爽。"""
    tasks = _load_tasks()
    active_tasks = [t for t in tasks if not t.get("done")]
    _save_tasks(active_tasks)
    return {"success": True, "message": f"已清理 {len(tasks) - len(active_tasks)} 条已完成任务。"}


# ========== 自测入口 ==========
if __name__ == "__main__":
    print("===== 工具模块终极自测 =====")
    print("\n[智能日期] 传'明天'查天气：", get_weather("北京", "明天"))
    print("\n[智能日期] 传'周五'查天气：", get_weather("北京", "周五"))
    print("\n[智能日期] 传'下周三'(拦截)：", get_weather("北京", "下周三"))

    print("\n[待办] 传'周五'加任务：", add_task("交作业", "周五"))
    print("[待办] 传'明天'加任务：", add_task("买牙膏", "明天"))
    print("[待办] 查列表：", list_tasks())