"""内置工具集"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from bot001.tools.registry import Tool, tool_schema


SHELL_WHITELIST = {"grep", "ls", "find", "cat", "echo", "head", "tail", "wc", "pwd", "date", "ps"}


def echo(message: str) -> str:
    """回显消息"""
    return message


def grep(pattern: str, path: str = ".") -> str:
    """搜索文件内容"""
    try:
        p = Path(path)
        if not p.exists():
            return f"Path not found: {path}"
        if p.is_file():
            content = p.read_text()
            matches = re.findall(pattern, content)
            return f"Found {len(matches)} matches\n" + "\n".join(matches[:20])
        else:
            results = []
            for f in p.rglob("*"):
                if f.is_file():
                    try:
                        content = f.read_text()
                        if re.search(pattern, content):
                            results.append(str(f))
                    except Exception:
                        pass
            return f"Found {len(results)} files\n" + "\n".join(results[:20])
    except Exception as e:
        return f"Error: {e}"


def shell(command: str, work_dir: str = "", timeout: int = 30) -> str:
    """执行 shell 命令（白名单限制）"""
    cmd = command.strip().split()[0] if command.strip() else ""
    if cmd not in SHELL_WHITELIST:
        return f"Command '{cmd}' not in whitelist: {SHELL_WHITELIST}"

    try:
        cwd = work_dir if work_dir else os.getcwd()
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr] {result.stderr}"
        return output[:4000]  # 截断
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out ({timeout}s)"
    except Exception as e:
        return f"Error: {e}"


def file_read(path: str) -> str:
    """读取文件内容"""
    try:
        p = Path(path)
        if not p.exists():
            return f"File not found: {path}"
        return p.read_text()[:4000]
    except Exception as e:
        return f"Error: {e}"


def file_write(path: str, content: str) -> str:
    """写入文件内容"""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"Written to {path} ({len(content)} chars)"
    except Exception as e:
        return f"Error: {e}"


def register_builtin_tools(registry) -> None:
    """注册所有内置工具"""
    tools = [
        Tool("echo", "回显消息", echo, tool_schema(echo)),
        Tool("grep", "搜索文件内容", grep, tool_schema(grep)),
        Tool("shell", "执行 shell 命令（白名单限制）", shell, tool_schema(shell)),
        Tool("file_read", "读取文件内容", file_read, tool_schema(file_read)),
        Tool("file_write", "写入文件内容", file_write, tool_schema(file_write)),
    ]
    for t in tools:
        registry.register(t)
