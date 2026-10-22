"""小智管家 · 表现层（界面层）

负责人：成员 D
职责：Streamlit 聊天界面、语音输入、语音播报
启动：streamlit run app_ui.py

约定（见 docs/接口约定.md）：
    - history 存在 st.session_state，格式 [{"role": ..., "content": ...}, ...]，刷新不丢
    - 只调用 agent_brain.get_agent_response(user_input, history)，不直接碰大模型
    - 语音不可用时必须优雅降级为纯文字输入

当前状态：占位实现（Day 1 骨架，可跑通）。Day 4 前由成员 D 完善语音与样式。
"""

from __future__ import annotations

import streamlit as st

from agent_brain import get_agent_response

st.set_page_config(page_title="小智管家", page_icon="🧹", layout="centered")

# ---------- 侧边栏 ----------
with st.sidebar:
    st.header("🧹 小智管家")
    st.caption("会说也会做的生活助手")
    st.divider()
    st.markdown("**可以这样问我**")
    st.markdown(
        "- 上海今天天气怎么样，要带伞吗？\n"
        "- 记一下，周五下午三点交实验报告\n"
        "- 我还有哪些待办？\n"
        "- 那明天呢？（追问上下文）"
    )
    st.divider()
    if st.button("🗑 清空对话", use_container_width=True):
        st.session_state.history = []
        st.rerun()
    st.caption("TODO(成员 D)：接入语音输入 / 播报")

# ---------- 会话状态 ----------
if "history" not in st.session_state:
    st.session_state.history = []

st.title("🧹 小智管家")
st.caption("查天气 · 记待办 · 聊聊天 —— 直接说话就行")

# ---------- 历史消息 ----------
if not st.session_state.history:
    with st.chat_message("assistant"):
        st.write("你好呀，我是小智管家～ 今天想聊点什么，还是让我帮你办点事？")

for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# ---------- 输入 ----------
user_input = st.chat_input("说点什么…（例如：上海明天要带伞吗）")

if user_input:
    with st.chat_message("user"):
        st.write(user_input)

    with st.chat_message("assistant"):
        with st.spinner("小智正在想…"):
            try:
                reply = get_agent_response(user_input, st.session_state.history)
            except Exception as exc:  # 界面层兜底，绝不让页面白屏
                reply = f"抱歉，我这边出了点小问题：{exc}"
        st.write(reply)

    st.session_state.history += [
        {"role": "user", "content": user_input},
        {"role": "assistant", "content": reply},
    ]
