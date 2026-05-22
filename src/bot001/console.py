"""控制台交互"""

from __future__ import annotations

import sys
from datetime import datetime

from bot001.agent import Agent
from bot001.session import SessionManager


def print_welcome():
    print("=" * 60)
    print(" bot001 - Console Agent")
    print(" Type /help for commands, /exit to quit")
    print("=" * 60)
    print()


def print_help():
    print("Commands:")
    print("  /help     - Show this help")
    print("  /exit     - Exit the program")
    print("  /new      - Start a new session")
    print("  /list     - List all sessions")
    print("  /delete   - Delete a session")
    print()


def print_response(response: str):
    """打印带时间戳的回复"""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{ts}] bot001:")
    print("-" * 40)
    print(response)
    print("-" * 40)
    print()


def main():
    print_welcome()

    from bot001.config import load_config
    agent = Agent(load_config())

    # 默认会话
    session_id = agent.session_manager.create_session()
    print(f"Session: {session_id}\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            cmd = user_input[1:].lower()
            if cmd == "exit":
                print("Goodbye!")
                break
            elif cmd == "help":
                print_help()
                continue
            elif cmd == "new":
                session_id = agent.session_manager.create_session()
                print(f"New session: {session_id}\n")
                continue
            elif cmd == "list":
                sessions = agent.session_manager.list_sessions()
                print(f"Sessions ({len(sessions)}):")
                for s in sessions[:10]:
                    print(f"  {s['id']} - {s['updated_at']}")
                print()
                continue
            elif cmd.startswith("delete "):
                sid = cmd[7:].strip()
                if sid == session_id:
                    print("Cannot delete current session\n")
                else:
                    agent.session_manager.delete_session(sid)
                    print(f"Deleted: {sid}\n")
                continue
            else:
                print(f"Unknown command: {user_input}\n")
                print_help()
                continue

        response = agent.run(session_id, user_input)
        print_response(response)


if __name__ == "__main__":
    main()
