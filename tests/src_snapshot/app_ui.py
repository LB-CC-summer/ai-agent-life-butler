# -*- coding: utf-8 -*-
"""
小智管家 · 界面层 (app_ui.py)
================================================================
负责人：成员 D（整合实现：成员 A）
启动：streamlit run app_ui.py

本文件只做「表现层」，不碰大模型、不碰文件读写，全部通过：
    from agent_brain import get_agent_response                              —— 成员 B
    from tools_api   import list_tasks / done_task / clear_done_tasks      —— 成员 C

接口对齐（实际签名，见 docs/接口约定.md）：
    get_agent_response(user_input, history) -> (reply: str, history: list)
    注意：返回的是「二元组」，且会直接修改传入的 history，所以这里传副本。
================================================================
"""

import json
import os

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="小智管家 · 生活助手",
    page_icon="🧹",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==========================================================
# 0. 依赖兜底：任何一个模块 import 失败，都不能白屏
# ==========================================================
CORE_ERROR = None
agent_brain = None
try:
    import agent_brain
    from agent_brain import get_agent_response
    from tools_api import clear_done_tasks, done_task, list_tasks
except Exception as exc:  # noqa: BLE001
    CORE_ERROR = exc

API_KEY_READY = bool(os.getenv("DEEPSEEK_API_KEY") or os.getenv("LLM_API_KEY"))


# ==========================================================
# 1. 通用小工具
# ==========================================================
def friendly_error(exc: Exception) -> str:
    """把底层异常翻译成人话，避免把一长串 traceback 甩到用户脸上。"""
    raw = f"{type(exc).__name__}: {exc}"
    low = raw.lower()
    if "401" in raw or "authentication" in low or "invalid_api_key" in low:
        return "看起来大模型 Key 没配对 🥲 请检查 `.env` 里的 `DEEPSEEK_API_KEY` 是否正确、有没有过期。"
    if "missing credentials" in low:
        return "还没有配置大模型 Key，先在 `.env` 里填上 `DEEPSEEK_API_KEY` 吧。"
    if "429" in raw or "rate limit" in low:
        return "我这边被限流了，喘口气，等几秒再问我一次～"
    if "timeout" in low or "timed out" in low or "connection" in low:
        return "网络有点不给力，刚才没连上服务。检查一下网络再试一次？"
    return f"抱歉，我出了点小问题：{raw}"


def speak(text: str, rate: float = 1.0) -> None:
    """浏览器端 TTS 播报（前端 JS 合成，不依赖服务器声卡，远程部署也能响）。

    兼容性：新版本 Streamlit 用 st.html(unsafe_allow_javascript=True)，
    老版本（1.4x）没有这个参数，回退到 components.v1.html。
    """
    if not text:
        return
    payload = json.dumps(text, ensure_ascii=False)
    js = f"""
    <script>
      (function () {{
        const text = {payload};
        if (!('speechSynthesis' in window)) return;
        window.speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance(text);
        u.lang = 'zh-CN';
        u.rate = {rate};
        u.pitch = 1.0;
        window.speechSynthesis.speak(u);
      }})();
    </script>
    """
    try:
        st.html(js, unsafe_allow_javascript=True)
    except TypeError:  # 老版本 Streamlit 没有 unsafe_allow_javascript 参数
        components.html(js, height=0)


def transcribe(uploaded) -> tuple:
    """语音转文字：SpeechRecognition + Google 识别，任何失败都给中文提示。"""
    try:
        import speech_recognition as sr
    except ImportError:
        return None, "没装语音识别库。执行 `pip install SpeechRecognition` 后重启就能语音输入。"

    try:
        recognizer = sr.Recognizer()
        with sr.AudioFile(uploaded) as source:
            audio = recognizer.record(source)
        return recognizer.recognize_google(audio, language="zh-CN"), None
    except sr.UnknownValueError:
        return None, "没听清你说什么，再说一次？"
    except sr.RequestError as exc:
        return None, f"语音识别服务连不上（{exc}）。改用打字也一样哦～"
    except Exception as exc:  # noqa: BLE001
        return None, f"语音处理失败：{exc}"


# ==========================================================
# 2. 会话状态初始化
# ==========================================================
if "history" not in st.session_state:
    st.session_state.history = []
if "pending" not in st.session_state:
    st.session_state.pending = None
if "stt_error" not in st.session_state:
    st.session_state.stt_error = None
if "auto_speak" not in st.session_state:
    st.session_state.auto_speak = True
if "audio_sig" not in st.session_state:
    st.session_state.audio_sig = None


# ==========================================================
# 3. 侧边栏：待办面板 + 语音 + 快捷示例
# ==========================================================
with st.sidebar:
    st.header("🧹 小智管家")
    st.caption("会说，也会做 —— 查天气 · 管待办")

    if agent_brain is not None:
        st.caption(f"模型：`{agent_brain.MODEL}`")

    st.divider()

    # ---------- 待办面板（直接调成员 C 的工具，展示"会做"） ----------
    st.subheader("📋 我的待办")
    try:
        snapshot = list_tasks(include_done=False)
        tasks = snapshot.get("tasks", [])
        if not tasks:
            st.caption("还没有待办，跟小智说一句就记上了～")
        else:
            st.caption(f"共 {len(tasks)} 条未完成（🔴逾期 🟡今天 🟢未到期）")
            for task in tasks:
                status = task.get("status", "")
                icon = {"已逾期": "🔴", "今天截止": "🟡"}.get(status, "🟢")
                col_text, col_btn = st.columns([0.82, 0.18])
                due = f" · {task['due_date']}" if task.get("due_date") else ""
                col_text.markdown(f"{icon} `#{task['id']}` {task['task']}{due}")
                if col_btn.button("✅", key=f"done_{task['id']}", help="标记完成"):
                    done_task(task["id"])
                    st.rerun()
        col_a, col_b = st.columns(2)
        if col_a.button("🔄 刷新", use_container_width=True):
            st.rerun()
        if col_b.button("🧽 清理已完成", use_container_width=True):
            clear_done_tasks()
            st.rerun()
    except Exception as exc:  # noqa: BLE001
        st.warning(f"待办面板读取失败：{exc}")

    st.divider()

    # ---------- 语音输入 ----------
    st.subheader("🎤 语音")
    audio = st.audio_input("按住说话，松手自动识别")
    if audio is not None:
        signature = (audio.name, getattr(audio, "size", None))
        if signature != st.session_state.audio_sig:
            st.session_state.audio_sig = signature
            with st.spinner("正在听…"):
                text, err = transcribe(audio)
            if text:
                st.session_state.pending = text
                st.session_state.stt_error = None
            else:
                st.session_state.stt_error = err

    if st.session_state.stt_error:
        st.warning(st.session_state.stt_error)

    st.session_state.auto_speak = st.toggle(
        "回复自动朗读", value=st.session_state.auto_speak, help="使用浏览器语音合成"
    )
    speak_rate = st.slider("语速", 0.6, 1.6, 1.0, 0.1)

    st.divider()

    # ---------- 快捷示例 ----------
    st.subheader("💡 试一试")
    examples = [
        "北京今天天气怎么样？",
        "明天上海要带伞吗",
        "记一下，周五交软件工程实验报告",
        "我还有哪些待办？",
        "把交实验报告那个任务标记完成",
    ]
    for i, question in enumerate(examples):
        if st.button(question, key=f"ex_{i}", use_container_width=True):
            st.session_state.pending = question

    st.divider()
    if st.button("🗑 清空对话", use_container_width=True):
        st.session_state.history = []
        st.rerun()


# ==========================================================
# 4. 启动守卫
# ==========================================================
st.title("🧹 小智管家")
st.caption("查天气 · 管待办 · 聊聊天 —— 用大白话把事办了")

if CORE_ERROR is not None:
    st.error("核心模块加载失败，界面无法工作：")
    st.code(f"{type(CORE_ERROR).__name__}: {CORE_ERROR}")
    st.info(
        "常见原因：① 依赖没装全 → `pip install -r requirements.txt`；"
        "② 不在仓库根目录启动 → 请在与 `app_ui.py` 同级的目录运行 `streamlit run app_ui.py`。"
    )
    st.stop()

if not API_KEY_READY:
    st.warning(
        "还没有配置大模型 Key —— 界面能看，但对话会失败。\n\n"
        "把 `.env.example` 复制成 `.env`，填上 `DEEPSEEK_API_KEY` 后刷新页面。"
        "详见 `docs/环境配置.md`。"
    )


# ==========================================================
# 5. 对话核心
# ==========================================================
def handle(prompt: str) -> str:
    """渲染一轮问答：显示用户消息 → 调大脑 → 显示回复 → 更新历史。"""
    prompt = (prompt or "").strip()
    if not prompt:
        return ""

    with st.chat_message("user"):
        st.markdown(prompt)

    # 传副本：成员 B 的函数会直接 append 修改传入的 list
    working_history = list(st.session_state.history)

    with st.chat_message("assistant"):
        with st.spinner("小智正在想…"):
            try:
                reply, working_history = get_agent_response(prompt, working_history)
            except Exception as exc:  # noqa: BLE001
                reply = friendly_error(exc)
                # 失败也要让这一轮闭环，否则界面和记忆会错位
                if not working_history or working_history[-1].get("role") != "user":
                    working_history.append({"role": "user", "content": prompt})
                working_history.append({"role": "assistant", "content": reply})
        st.markdown(reply)

    st.session_state.history = working_history
    return reply


# ---------- 欢迎语 ----------
if not st.session_state.history:
    with st.chat_message("assistant"):
        st.markdown(
            "你好呀，我是你的生活管家 🧹\n\n"
            "可以直接说：**「明天上海要带伞吗」**、**「记一下周五交实验报告」**、**「我还有哪些待办」**。\n\n"
            "不想打字？点侧边栏那个 **按住说话** 也行。"
        )

# ---------- 历史消息 ----------
for message in st.session_state.history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 最后一条 AI 回复给个朗读按钮（用户手势触发，浏览器不会拦）
last_assistant = next(
    (m["content"] for m in reversed(st.session_state.history) if m["role"] == "assistant"),
    None,
)
if last_assistant and st.button("🔊 朗读上一条回复", key="replay_tts"):
    speak(last_assistant, speak_rate)

# ---------- 处理待办中的输入（语音 / 快捷示例） ----------
reply_text = ""
if st.session_state.pending:
    reply_text = handle(st.session_state.pending)
    st.session_state.pending = None

# ---------- 文字输入 ----------
typed = st.chat_input("跟小智说点什么…（例如：明天上海要带伞吗）")
if typed:
    reply_text = handle(typed)

# ---------- 自动朗读 ----------
if reply_text and st.session_state.auto_speak:
    speak(reply_text, speak_rate)

# ---------- 底部状态 ----------
st.caption(
    f"对话记忆：{len(st.session_state.history)} 条消息（最多保留 20 条，约 10 轮）｜"
    "天气数据来源 wttr.in｜待办保存在本地 todo.json"
)
