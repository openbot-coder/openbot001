# 产品设计文档

> 版本：0.1.0
> 创建日期：2026-05-22
> 最后更新：2026-05-22

## 1. 项目概述

**项目名称：** bot001
**开发语言：** Python 3.12+
**初始版本：** 0.1.0

> 原型机器人 Agent 项目 - 基于 DeepAgents 范式的轻量级控制台智能体框架

### 1.1 核心目标

**一句话目标：** 用 ~3000 行 Python 实现一个支持会话管理、工具调用、技能扩展、短/长期记忆和知识库检索的 Console Agent 原型框架。

### 1.2 核心能力

| 能力 | 说明 |
|------|------|
| 会话管理 | 多会话、上下文追踪、会话持久化 |
| 工具调用 | 动态注册、Schema 校验、结果返回 |
| Skills | Skill 基类 + 目录加载，支持热插拔 |
| 消息收发 | Console 输入输出，Markdown 渲染 |
| 短期记忆 | 对话缓冲，滑动窗口裁剪 |
| 长期记忆 | SQLite 持久化，支持语义检索 |
| 知识库 | 向量存储 + RAG 检索（Chroma） |

### 1.3 成功标准

1. **可运行**：控制台启动后能接收用户输入并回复
2. **工具调用**：内置工具 `echo` / `grep` / `shell` 可正常执行
3. **记忆持久化**：重启后会话历史可恢复
4. **技能加载**：动态加载 `./skills/` 目录下的 Skill
5. **知识库**：文档可导入，向量检索返回相关片段
6. **行数**：总行数 ≤ 3000（含注释，不含空行和测试）

### 1.4 范围

**包含：**
- Console 单渠道交互
- ReAct 执行循环
- SQLite 长期记忆
- Chroma 向量检索
- Skill 目录加载机制
- 内置工具集（echo, grep, shell, file_read, file_write）
- Session 持久化

**不包含：**
- 多渠道（WeChat/Telegram/WebSocket）
- 插件系统动态热加载（Skill 启动时加载，不支持运行时添加）
- 分布式/多进程
- 认证/权限体系
- Docker 沙箱隔离（Shell 执行仅限制命令白名单）

## 2. 架构设计

### 2.1 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│                        Console Input                          │
│                    (stdin 用户输入解析)                        │
└──────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                      Session Manager                          │
│            (会话加载/创建 + 上下文缓冲)                        │
└──────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                       Agent Loop (ReAct)                      │
│                                                                  │
│   ┌─────────┐    ┌──────────┐    ┌────────────┐             │
│   │ Planner │───▶│ Executor │───▶│  Result     │             │
│   │(思考下一步)│    │(执行工具)│    │  Recorder  │             │
│   └─────────┘    └──────────┘    └────────────┘             │
│        │              │               │                      │
│        └──────────────┴───────────────┘                      │
│                       │                                      │
│              ┌────────▼────────┐                             │
│              │  Loop 控制器    │                             │
│              │(max_turns/终止) │                             │
│              └─────────────────┘                             │
└──────────────────────────────────────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
┌──────────────────┐ ┌───────────────┐ ┌─────────────────┐
│   Short-term     │ │   Long-term   │ │   Knowledge     │
│   Memory         │ │   Memory      │ │   Base          │
│  (对话缓冲/裁剪)  │ │  (SQLite)     │ │  (Chroma)       │
└──────────────────┘ └───────────────┘ └─────────────────┘
              │                │                │
              └────────────────┴────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                     Tool Registry                             │
│            (工具注册表 + Skill 加载器)                         │
└──────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                      Console Output                           │
│                    (Markdown 渲染输出)                        │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 项目结构

```
bot001/
├── src/bot001/
│   ├── __init__.py           # 导出 create_bot, __version__
│   ├── agent.py              # Agent 主循环 (ReAct)
│   ├── session.py            # 会话管理
│   ├── message.py            # 消息模型 (Pydantic)
│   ├── config.py             # 配置加载
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── short_term.py     # 短期记忆（滑动窗口）
│   │   └── long_term.py      # 长期记忆（SQLite）
│   ├── skills/
│   │   ├── __init__.py
│   │   ├── base.py           # Skill 基类
│   │   └── loader.py         # 技能目录加载
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── registry.py       # 工具注册表
│   │   └── builtin.py        # 内置工具
│   ├── knowledge/
│   │   ├── __init__.py
│   │   └── store.py          # Chroma 向量存储
│   └── console.py            # 控制台交互
├── tests/
│   ├── test_agent.py
│   ├── test_session.py
│   ├── test_memory.py
│   └── test_tools.py
├── skills/                    # 技能模块目录（用户扩展）
│   └── .gitkeep
├── data/                      # 数据存储
│   ├── db/                   # SQLite (.db 文件)
│   ├── files/                # 上下文文件
│   └── vector/               # Chroma DB
├── docs/
│   ├── design.md
│   ├── changelog.md
│   └── skills/               # 技能文档目录
├── README.md
├── pyproject.toml
└── .gitignore
```

### 2.3 技术栈

| 组件 | 选型 | 版本约束 |
|------|------|---------|
| Python | CPython | ≥ 3.12 |
| 数据验证 | Pydantic | v2 |
| 数据库 | SQLite | 3.x (stdlib) |
| 向量检索 | Chroma | 0.5.x |
| LLM 调用 | httpx + Chat API | 无特定版本 |
| 配置 | Python dotenv | - |

## 3. 核心设计

### 3.1 Agent 执行循环（ReAct）

```python
class Agent:
    def run(self, session_id: str, user_message: str) -> str:
        # 1. 构建消息列表（含系统提示 + 历史 + 当前输入）
        messages = self._build_messages(session_id, user_message)

        # 2. ReAct 循环
        for turn in range(self.max_turns):
            # LLM 推理：选择工具或直接回复
            response = self.llm.chat(messages)
            messages.append(response)

            if response.tool_calls:
                # 执行工具
                results = []
                for call in response.tool_calls:
                    result = self.executor.execute(call, session_id)
                    results.append(result)
                    messages.append(assistant_tool_result(call, result))

                # 检查是否终止（max_turns 或 LLM 说 done）
                if self._should_halt(results):
                    break
            else:
                # 直接回复，循环结束
                break

        # 3. 保存记忆
        self.short_term.commit(session_id, messages)
        self.long_term.save(session_id, messages)

        return messages[-1].content
```

### 3.2 消息格式

```python
class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: str | None = None          # tool 时填工具名
    tool_call_id: str | None = None  # tool 时填调用 ID
    metadata: dict = Field(default_factory=dict)

class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict  # JSON object
```

### 3.3 工具注册

```python
from bot001.tools import register_tool, Tool

@register_tool
def grep(pattern: str, path: str = ".") -> str:
    """搜索文件内容"""
    ...

# 注册后自动加入工具注册表，生成 JSON Schema
```

### 3.4 Skill 加载

```python
# skills/ 目录结构
skills/
└── web_search/
    ├── SKILL.md       # name, version, description, tools
    └── tools.py       # 实现

# SKILL.md 格式
name: web_search
version: 1.0.0
description: 网络搜索技能
tools:
  - web_search
  - web_fetch
```

## 4. 数据模型

### 4.1 SQLite 表

```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    state TEXT DEFAULT '{}'  -- JSON
);

CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    name TEXT,
    tool_call_id TEXT,
    metadata TEXT DEFAULT '{}',  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE long_term_memories (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding BLOB,  -- 可选：存储向量
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX idx_messages_session ON messages(session_id);
CREATE INDEX idx_memory_session ON long_term_memories(session_id);
```

## 5. 安全设计

### 5.1 Shell 工具白名单

- `shell` 工具仅允许预定义白名单命令（grep, ls, find, cat, echo 等）
- 危险命令（rm -rf, dd, mkfs 等）直接拒绝
- 执行超时 30 秒
- 工作目录限制在 `data/files/` 内

### 5.2 数据保护

- 会话数据存储在本地 `data/` 目录
- 敏感信息不写入日志
- 支持 `.env` 配置 API Key，不硬编码

## 6. 配置

### 6.1 pyproject.toml 依赖

```toml
[project]
name = "bot001"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.0",
    "chromadb>=0.5.0",
    "httpx>=0.27.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov>=4.0"]
```

## 7. 非功能性需求

| 指标 | 目标 | 验收方式 |
|------|------|---------|
| 总行数 | ≤ 3000 行 | `find src -name "*.py" -exec wc -l {} + \| awk '{s+=$1}END{print s}'` |
| 测试覆盖率 | ≥ 70% | `pytest --cov=src/bot001 --cov-report=term-missing` |
| 冷启动时间 | < 2s | `time python -c "from bot001 import create_bot"` |
| 可运行 | 控制台交互正常 | 人工测试 + 自动化 smoke test |

## 8. 开发计划

### Phase 1: 核心框架 v0.1.0
- [ ] 项目初始化（pyproject.toml, 目录结构）
- [ ] 消息模型 (message.py)
- [ ] 配置加载 (config.py)
- [ ] Agent 主循环 (agent.py) — ReAct
- [ ] 控制台交互 (console.py)

### Phase 2: 记忆系统 v0.2.0
- [ ] Session 管理 (session.py)
- [ ] 短期记忆 (memory/short_term.py)
- [ ] 长期记忆 (memory/long_term.py) — SQLite

### Phase 3: 工具系统 v0.3.0
- [ ] 工具注册表 (tools/registry.py)
- [ ] 内置工具 (tools/builtin.py) — echo, grep, shell, file_read, file_write
- [ ] 工具执行器 (executor.py)

### Phase 4: 技能系统 v0.4.0
- [ ] Skill 基类 (skills/base.py)
- [ ] 技能加载器 (skills/loader.py)

### Phase 5: 知识库 v0.5.0
- [ ] Chroma 向量存储 (knowledge/store.py)
- [ ] RAG 检索流程

### Phase 6: 收尾 v0.6.0
- [ ] 测试覆盖（≥ 70%）
- [ ] README 编写
- [ ] 最终行数统计

## 9. 假设与约束

1. **Python 3.12+**：依赖 `tomlkit`（标准库无）、`re.Match` 等 3.12+ 特性
2. **SQLite**：无外部数据库依赖，所有数据存储在本地
3. **Chroma**：使用 `chromadb` 的默认持久化模式，无需单独服务
4. **LLM**：通过 `OPENAI_API_BASE` 环境变量配置，支持任意兼容 API
5. **无 Docker**：不依赖容器化，纯 Python 直接运行
