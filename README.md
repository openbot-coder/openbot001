# 📦 bot001 — Console Agent Framework

**~1400 行 Python，ReAct Agent 原型框架**

## 架构

```
src/bot001/
├── agent.py          # Agent 主循环 (ReAct: Thought → Action → Observation)
├── message.py        # 消息模型 (Message / ToolCall / ToolResult)
├── session.py        # 会话管理 (SQLite)
├── executor.py       # 工具执行器
├── config.py         # 配置加载 (.env / 环境变量)
├── console.py        # CLI 命令行界面
├── memory/
│   ├── short_term.py  # 短期记忆 (内存缓冲)
│   └── long_term.py   # 长期记忆 (SQLite 持久化 + 关键词检索)
├── skills/
│   ├── base.py       # Skill 基类
│   └── loader.py     # 技能加载器 (目录扫描 + SKILL.md 解析)
├── tools/
│   ├── registry.py   # 工具注册中心
│   └── builtin.py    # 内置工具集
└── knowledge/
    ├── store.py      # WikiStore — 文件系统层
    └── wiki.py       # WikiEngine — ingest / query / lint
```

## 核心功能

| 模块 | 说明 |
|------|------|
| **ReAct 循环** | System → User Context → LLM → Tool Call → Execute → Continue/Return |
| **5 个内置工具** | echo, grep, shell (白名单), file_read, file_write |
| **会话管理** | SQLite 持久化，支持多会话创建/删除/消息检索 |
| **长期/短期记忆** | 关键词检索过往对话 + 当前会话缓冲 |
| **技能系统** | 目录扫描，SKILL.md 解析，动态加载 |
| **知识库** | LLM Wiki 风格: index.md, log.md, wiki 页面, [[wikilink]] 交叉引用 |

## 快速开始

```bash
# 安装
pip install -e .

# 需要 OpenAI 兼容 API
export OPENAI_API_KEY="sk-..."
export OPENAI_API_BASE="https://api.openai.com/v1"
# 可选: BOT001_MODEL, BOT001_MAX_TURNS, BOT001_DB_PATH

# 启动 CLI
bot001
```

## 开发

```bash
# 运行测试
python3 -m pytest tests/ -v

# 覆盖率
python3 -m pytest tests/ --cov=src/bot001 --cov-report=term-missing

# 所有测试通过 (42 tests, 81% 覆盖率)
```

## 技能开发

创建一个技能只需两个文件:

```
skills/my-skill/
├── SKILL.md      # 技能说明
└── tools.py      # 工具实现 + Skill 子类
```

详见 `skills/weather/` 示例。

## 知识库 (LLM Wiki)

```
data/wiki/
├── index.md       # 内容目录
├── log.md         # 操作日志
├── sources/       # 原始文档 (不可变)
└── wiki/          # LLM 生成的 wiki 页面
    ├── concepts/
    ├── entities/
    └── sources/
```

**三核心操作:**
- `ingest` — 分析文档 → 生成 wiki 页面
- `query` — 关键词检索 + [[wikilink]] 扩展
- `lint` — 审查孤立页面 / 破损链接

## 测试

```
42 passed in 0.95s — 81% coverage
```
