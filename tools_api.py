import json
import os
import requests
from datetime import datetime, timedelta
import re

TODO_FILE = "todo.json"


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

    # 匹配星期几（如 "周五" 或 "星期五"）
    weekdays = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
    match = re.search(r'(?:周|星期)([一二三四五六日天])', date_str)
    if match:
        target_weekday = weekdays[match.group(1)]
        current_weekday = today.weekday()
        days_ahead = target_weekday - current_weekday
        if days_ahead <= 0:  # 如果今天已经过了这天，算下周
            days_ahead += 7
        return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    # 实在解析不了，就把原字符串扔回去，让大模型自己看着办
    return date_str


# ========== 天气模块 ==========

def get_weather(city_name: str = "北京", query_date: str = "") -> dict:
    """查询指定城市天气。支持自然语言日期与YYYY-MM-DD格式。"""
    if not city_name: city_name = "北京"

    today = datetime.now().date()
    target_date_str = _parse_date(query_date)

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
        if "Rain" in desc or "Shower" in desc: return "雨"
        if "Snow" in desc: return "雪"
        if "Cloud" in desc or "Overcast" in desc: return "多云"
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
        return []


def _save_tasks(tasks: list) -> None:
    with open(TODO_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


def _next_id(tasks: list) -> int:
    return max((t["id"] for t in tasks), default=0) + 1


def add_task(task_content: str, due_date: str = "") -> dict:
    tasks = _load_tasks()
    parsed_date = _parse_date(due_date)  # 智能解析
    new_task = {
        "id": _next_id(tasks),
        "task": task_content.strip(),
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
    tasks = _load_tasks()
    matched = [t for t in tasks if keyword in t["task"]]
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