#!/usr/bin/env python3
"""
Deezy CLI - Command Line Interface for Deezy Personal AI Operator.
"""
import sys
import argparse
from deezy.core.agent import Agent
from deezy.config import get_settings

def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Deezy - Personal AI Operator")
    parser.add_argument("command", nargs="?", choices=["task", "chat", "status", "memory", "tools", "help"], default="help")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Command arguments")
    parser.add_argument("--voice", action="store_true", help="Enable voice input/output")
    
    args = parser.parse_args()
    
    if args.command == "help" or args.command is None:
        print_help()
        return
    
    if args.command == "task":
        if not args.args:
            print("Error: No objective provided for task")
            print("Usage: deezy task \"Your objective here\"")
            return
        objective = " ".join(args.args)
        run_task(objective)
    
    elif args.command == "chat":
        chat_mode()
    
    elif args.command == "status":
        show_status()
    
    elif args.command == "memory":
        show_memory()
    
    elif args.command == "tools":
        list_tools()
    
    else:
        print(f"Unknown command: {args.command}")
        print_help()


def print_help():
    """Show help message."""
    print("""
Deezy Commands
========================================

Commands:
  task <objective>    Run a task through the agent
  chat                Enter chat mode with LLM
  status              Show system status
  memory              Show recent memory
  tools               List available tools
  help                Show this help

Examples:
  deezy task "Find me a good desk lamp under $50"
  deezy task "Organize my Downloads folder"
  deezy chat
  deezy status
  deezy tools

Voice (when ready):
  python test_voice.py
""")


def run_task(objective: str):
    """Run a task through the agent."""
    print(f"\n{'=' * 60}")
    print(f"Objective: {objective}")
    print(f"{'=' * 60}\n")
    
    agent = Agent()
    result = agent.run(objective)
    
    print(f"\n{'=' * 60}")
    if result.get("success"):
        print(f"[OK] {result.get('message', 'Completed')}")
    else:
        print(f"[FAIL] {result.get('error', 'Failed')}")
    
    if "steps" in result:
        print(f"\nSteps completed: {result.get('steps_completed', 0)}")


def chat_mode():
    """Enter chat mode with LLM."""
    from deezy.brain.provider import get_provider, Message, MessageRole
    
    print("\nChat mode - type 'back' to return\n")
    
    provider = get_provider()
    
    while True:
        try:
            user_input = input("you> ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ("back", "exit", "quit"):
                break
            
            messages = [Message(role="user", content=user_input)]
            
            try:
                response = provider.chat(messages)
                print(f"deezy> {response.content}\n")
            except Exception as e:
                print(f"Error: {e}")
        
        except KeyboardInterrupt:
            print()
            break
        except EOFError:
            break


def show_status():
    """Show system status."""
    from deezy.config import get_settings
    
    settings = get_settings()
    
    print("\nSystem Status")
    print("-" * 40)
    print(f"App: {settings.app.get('name')} v{settings.app.get('version')}")
    print(f"Environment: {settings.app.get('environment')}")
    print(f"LLM Provider: {settings.llm.provider}")
    print(f"Model: {settings.llm.model}")
    print(f"Max Monthly Cost: Rs{settings.app.get('max_monthly_cost')}")
    print(f"Debug: {settings.app.get('debug')}")


def show_memory():
    """Show recent memory."""
    from deezy.memory import get_db
    
    db = get_db()
    
    tasks = db.fetchall("SELECT * FROM tasks ORDER BY created_at DESC LIMIT 10")
    
    print(f"\nRecent Tasks ({len(tasks)})")
    print("-" * 60)
    for t in tasks:
        print(f"  [{t['status']}] {t['name']} ({t['created_at']})")


def list_tools():
    """List available tools."""
    from deezy.brain import get_tool_registry
    
    registry = get_tool_registry()
    
    print("\nAvailable Tools")
    print("-" * 60)
    
    for tool in registry.get_all():
        risk_color = "\033[92m" if tool.risk_level.value == "low" else "\033[93m" if tool.risk_level.value == "medium" else "\033[91m"
        print(f"  {tool.name} [{risk_color}{tool.risk_level.value}\033[0m]")
        print(f"    {tool.description}")


if __name__ == "__main__":
    main()