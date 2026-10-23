"""界面冒烟测试（成员 A 提供模板，成员 E 可在此基础上扩用例）

用法：
    cd 仓库根目录
    python tests/smoke_test.py

它会用 Streamlit 官方的无头测试框架 AppTest 真正把 app_ui.py 跑一遍，
不打开浏览器也能发现「页面报错 / 白屏 / 状态没更新」这类问题。

断言内容：
    1. 页面能渲染，没有异常
    2. 标题存在
    3. 侧边栏快捷示例按钮存在
    4. 输入一句话后，history 里应该多出 user + assistant 两条
"""

import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    at = AppTest.from_file(str(REPO_ROOT / "app_ui.py"), default_timeout=120)
    at.run()

    failed = []

    if at.exception:
        failed.append("页面渲染异常: " + "; ".join(str(e.value) for e in at.exception))
    if not at.title:
        failed.append("没有渲染出标题")
    if len(at.sidebar.button) < 5:
        failed.append(f"侧边栏按钮过少（{len(at.sidebar.button)}），快捷示例可能没渲染")
    if not at.chat_input:
        failed.append("聊天输入框没渲染")

    before = len(at.session_state["history"])
    at.chat_input[0].set_value("北京今天天气怎么样").run()
    after = len(at.session_state["history"])

    if at.exception:
        failed.append("对话后页面异常: " + "; ".join(str(e.value) for e in at.exception))
    if after - before != 2:
        failed.append(f"对话后 history 应增加 2 条，实际增加 {after - before} 条")

    if failed:
        print("❌ 冒烟测试失败：")
        for item in failed:
            print("   -", item)
        return 1

    print("✅ 冒烟测试通过：页面可渲染、对话闭环正常")
    print("   最后一轮回复：", at.session_state["history"][-1]["content"][:60])
    return 0


if __name__ == "__main__":
    sys.exit(main())
