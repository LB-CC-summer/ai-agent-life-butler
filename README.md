# 小智管家 · 智能生活助手 Agent

> 软件工程团队作业 —— 一个「**会说**也会**做**」的 AI Agent：自然语言聊天 + 真实工具调用（查天气 / 记待办），支持多轮记忆与语音交互。

<p align="left">
  <img alt="python" src="https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white">
  <img alt="streamlit" src="https://img.shields.io/badge/Streamlit-1.40+-FF4B4B?logo=streamlit&logoColor=white">
  <img alt="license" src="https://img.shields.io/badge/status-WIP-yellow">
</p>

## ✨ 它能做什么

| 你对它说 | 它做什么 |
|---|---|
| "上海今天天气怎么样，要带伞吗？" | 调 wttr.in 天气接口，返回温度/天气现象 + 模型生成的出行建议 |
| "记一下，周五下午三点交实验报告" | 写入本地 `todo.json`（自动把"周五"解析成日期） |
| "我还有哪些待办？" | 按逾期 / 今天截止 / 未到期列表化输出 |
| "把交作业那条标完成" | 先 `search_task` 查 ID，再 `done_task` 标记完成 |
| "那明天呢？" | 结合上一轮上下文追问回答（滑动窗口记忆 20 条） |
| 按住麦克风说一句 | 语音转文字 → 同上；回复可用浏览器语音合成朗读 |

## 🧠 为什么这是 Agent 而不是普通聊天机器人

普通聊天机器人只有"嘴"——模型生成文字就结束了。
本项目的模型**自己决定要不要动手**：判断意图 → 选择工具 → 拿到真实结果 → 再组织语言。工具不是由代码里的 `if-else` 写死路由的，而是交给模型自主调度，这与 MCP（Model Context Protocol）中 "Tool 注册 + 模型调度" 的思想一致。

## 📁 目录结构

```text
ai-agent-life-butler/
├── app_ui.py              # 表现层 —— Streamlit 界面 + 语音（成员 D）
├── agent_brain.py         # 决策层 —— 大模型核心 + 多轮记忆（成员 B）
├── tools_api.py           # 工具层 —— 天气 / 待办 CRUD（成员 C）
├── requirements.txt       # 依赖清单（成员 A）
├── .env.example           # 环境变量模板，复制为 .env 后填值（成员 A）
├── .gitignore             # 密钥与产物排除（成员 A）
├── docs.md                # 项目说明文档（成员 A 统稿）
└── docs/
    ├── 接口约定.md          # 全组函数签名契约（成员 A）
    ├── 环境配置.md          # Key 申请与配置图文教程（成员 A）
    ├── workflow.mmd       # 业务流程图 Mermaid 源码（成员 A）
    └── screenshots/       # 演示截图（成员 D）
```

## 🚀 快速开始

```bash
git clone https://github.com/LB-CC-summer/ai-agent-life-butler.git
cd ai-agent-life-butler

pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
# 编辑 .env，只填 DEEPSEEK_API_KEY 一项即可（天气接口免 Key）

streamlit run app_ui.py
```

密钥怎么申请、`.env` 怎么填：见 👉 [docs/环境配置.md](docs/环境配置.md)

## 📖 文档

- [完整说明文档 docs.md](docs.md) —— 需求、业务流、实现、演示、分工、心得
- [接口约定](docs/接口约定.md) —— 联调前必读
- [环境配置](docs/环境配置.md) —— Key 申请与排错

## 👥 团队分工

| 成员 | 角色 | 文件 |
|---|---|---|
| 成员 A | 项目统筹 & 文档架构 | `docs.md` / `README.md` / `.env.example` |
| 成员 B | 大模型核心 & 记忆 | `agent_brain.py` |
| 成员 C | 工具函数开发 | `tools_api.py` |
| 成员 D | 前端界面 & 语音 | `app_ui.py` |
| 成员 E | 测试 & 博客发布 | 测试用例 / 博客终稿 |

> 🚧 待补充成员姓名学号。

## ⚠️ 注意

`.env` 内是真实密钥，**永远不要提交**。仓库中只保留 `.env.example`。
