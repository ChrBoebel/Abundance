#!/usr/bin/env python3.11
"""
DeepSearch CLI - Premium Interactive Terminal Interface
Inspired by Gemini CLI, Claude Code, and Codex CLI
"""
import os
import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys

load_dotenv()

console = Console()

# Session storage directory
SESSION_DIR = Path.home() / ".deepresearch"
HISTORY_FILE = SESSION_DIR / "history.txt"
SESSION_DIR.mkdir(exist_ok=True)


class SessionManager:
    """Manages conversation sessions and history."""

    def __init__(self):
        self.current_session = {
            "id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "messages": [],
            "metadata": {
                "created": datetime.now().isoformat(),
                "model": "deepseek-v3.2-exp",
                "search_api": "tavily"
            }
        }
        self.sessions_dir = SESSION_DIR / "sessions"
        self.sessions_dir.mkdir(exist_ok=True)

    def add_message(self, role: str, content: str):
        """Add a message to current session."""
        self.current_session["messages"].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })

    def save_session(self, name: Optional[str] = None):
        """Save current session to file."""
        if name is None:
            name = self.current_session["id"]

        file_path = self.sessions_dir / f"{name}.json"
        with open(file_path, 'w') as f:
            json.dump(self.current_session, f, indent=2)

        return name

    def load_session(self, name: str) -> bool:
        """Load a session from file."""
        file_path = self.sessions_dir / f"{name}.json"
        if not file_path.exists():
            return False

        with open(file_path, 'r') as f:
            self.current_session = json.load(f)

        return True

    def list_sessions(self) -> List[str]:
        """List all saved sessions."""
        return [f.stem for f in self.sessions_dir.glob("*.json")]

    def get_history(self, limit: int = 10) -> List[Dict]:
        """Get recent messages from current session."""
        return self.current_session["messages"][-limit:]


class CommandRegistry:
    """Manages slash commands."""

    def __init__(self, session_manager: SessionManager):
        self.session = session_manager
        self.commands = {
            "help": self.cmd_help,
            "reset": self.cmd_reset,
            "history": self.cmd_history,
            "save": self.cmd_save,
            "load": self.cmd_load,
            "sessions": self.cmd_sessions,
            "settings": self.cmd_settings,
            "exit": self.cmd_exit,
            "clear": self.cmd_clear,
        }

    def execute(self, command: str, args: str = "") -> Optional[str]:
        """Execute a slash command."""
        cmd = command.lower().lstrip('/')

        if cmd not in self.commands:
            return f"❌ Unknown command: /{cmd}\nType /help for available commands"

        return self.commands[cmd](args)

    def cmd_help(self, args: str) -> str:
        """Show help for all commands."""
        table = Table(title="Available Commands", show_header=True)
        table.add_column("Command", style="cyan")
        table.add_column("Description", style="white")

        table.add_row("/help", "Show this help message")
        table.add_row("/reset", "Clear conversation and start new session")
        table.add_row("/history [n]", "Show last n messages (default 10)")
        table.add_row("/save [name]", "Save current session")
        table.add_row("/load <name>", "Load a saved session")
        table.add_row("/sessions", "List all saved sessions")
        table.add_row("/settings", "Show current configuration")
        table.add_row("/clear", "Clear screen")
        table.add_row("/exit", "Exit DeepSearch CLI")

        console.print(table)
        console.print("\n💡 [dim]Tip: Press Ctrl+R to search history, Escape to stop[/dim]")
        return None

    def cmd_reset(self, args: str) -> str:
        """Reset the current session."""
        self.session.__init__()
        console.clear()
        return "✅ Session reset. Starting fresh!"

    def cmd_history(self, args: str) -> str:
        """Show conversation history."""
        try:
            limit = int(args) if args else 10
        except ValueError:
            limit = 10

        messages = self.session.get_history(limit)

        if not messages:
            return "📭 No messages in history yet."

        for msg in messages:
            role_color = "blue" if msg["role"] == "user" else "green"
            console.print(f"\n[{role_color}]■ {msg['role'].upper()}:[/{role_color}]")
            console.print(msg["content"][:200] + "..." if len(msg["content"]) > 200 else msg["content"])

        return None

    def cmd_save(self, args: str) -> str:
        """Save current session."""
        name = self.session.save_session(args if args else None)
        return f"💾 Session saved as '{name}'"

    def cmd_load(self, args: str) -> str:
        """Load a saved session."""
        if not args:
            return "❌ Usage: /load <session_name>"

        if self.session.load_session(args):
            return f"✅ Loaded session '{args}'"
        else:
            return f"❌ Session '{args}' not found"

    def cmd_sessions(self, args: str) -> str:
        """List all saved sessions."""
        sessions = self.session.list_sessions()

        if not sessions:
            return "📭 No saved sessions found."

        table = Table(title="Saved Sessions")
        table.add_column("Name", style="cyan")
        table.add_column("Messages", style="yellow")

        for name in sessions[:20]:  # Limit to 20
            # Load session to get message count
            file_path = self.session.sessions_dir / f"{name}.json"
            with open(file_path, 'r') as f:
                data = json.load(f)
            table.add_row(name, str(len(data.get("messages", []))))

        console.print(table)
        return None

    def cmd_settings(self, args: str) -> str:
        """Show current settings."""
        table = Table(title="Current Settings")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Model", "openrouter:deepseek/deepseek-v3.2-exp")
        table.add_row("Search API", "Tavily")
        table.add_row("Max Concurrent", "3")
        table.add_row("Session ID", self.session.current_session["id"])
        table.add_row("Messages", str(len(self.session.current_session["messages"])))

        console.print(table)
        return None

    def cmd_clear(self, args: str) -> str:
        """Clear the screen."""
        console.clear()
        return None

    def cmd_exit(self, args: str) -> str:
        """Exit the CLI."""
        return "EXIT"


class DeepSearchCLI:
    """Main CLI application."""

    def __init__(self):
        self.session_manager = SessionManager()
        self.commands = CommandRegistry(self.session_manager)

        # Setup prompt session with history
        self.prompt_session = PromptSession(
            history=FileHistory(str(HISTORY_FILE)),
            auto_suggest=AutoSuggestFromHistory(),
            completer=WordCompleter(
                ['/help', '/reset', '/history', '/save', '/load', '/sessions', '/settings', '/exit', '/clear'],
                ignore_case=True
            ),
            enable_history_search=True,
        )

        # Setup key bindings
        self.kb = KeyBindings()
        self._setup_keybindings()

    def _setup_keybindings(self):
        """Setup custom keyboard shortcuts."""

        @self.kb.add(Keys.Escape)
        def _(event):
            """Stop current operation."""
            console.print("\n⚠️  Stopping current operation...")
            event.app.exit()

        @self.kb.add('c-c')
        def _(event):
            """Ctrl+C to exit."""
            console.print("\n👋 Goodbye!")
            event.app.exit(result="EXIT")

    def show_welcome(self):
        """Display welcome screen."""
        console.clear()

        welcome_text = """
# 🔬 DeepSearch CLI v1.0

> Powered by Gemini 2.5 Flash & Tavily Search

**Quick Start:**
- Type your research question naturally
- Use `/help` for all commands
- Press `Ctrl+R` to search history
- Press `Escape` to stop operation
- Press `Ctrl+D` or `/exit` to quit

**Examples:**
- "What are the latest trends in AI?"
- "Explain quantum computing"
- "Benefits of renewable energy"
"""

        console.print(Panel(
            Markdown(welcome_text),
            title="[bold cyan]Welcome[/bold cyan]",
            border_style="cyan"
        ))

        # Show status bar
        self._show_status()

    def _show_status(self):
        """Show status bar."""
        status_text = Text()
        status_text.append("🤖 ", style="bold")
        status_text.append("Gemini 2.5 Flash", style="cyan")
        status_text.append("  |  ", style="dim")
        status_text.append("🔍 ", style="bold")
        status_text.append("Tavily", style="green")
        status_text.append("  |  ", style="dim")
        status_text.append("💬 ", style="bold")
        status_text.append(f"Session: {self.session_manager.current_session['id']}", style="yellow")
        status_text.append("  |  ", style="dim")
        status_text.append("📊 ", style="bold")
        status_text.append(f"{len(self.session_manager.current_session['messages'])} messages", style="magenta")

        console.print(Panel(status_text, border_style="dim"))

    async def run_research(self, query: str):
        """Run a research query with progress visualization."""
        from open_deep_research.deep_researcher import deep_researcher

        console.print(f"\n🔬 [bold cyan]Researching:[/bold cyan] {query}\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console,
        ) as progress:

            task1 = progress.add_task("[cyan]Initializing research...", total=100)
            progress.update(task1, advance=20)

            # Run the research
            config = {
                "configurable": {
                    "research_model": "openrouter:deepseek/deepseek-v3.2-exp",
                    "summarization_model": "openrouter:deepseek/deepseek-v3.2-exp",
                    "compression_model": "openrouter:deepseek/deepseek-v3.2-exp",
                    "final_report_model": "openrouter:deepseek/deepseek-v3.2-exp",
                    "search_api": "tavily",
                    "allow_clarification": False,
                    "max_concurrent_research_units": 3,
                }
            }

            progress.update(task1, description="[green]Running deep research...", advance=30)

            try:
                result = await deep_researcher.ainvoke(
                    {"messages": [{"role": "user", "content": query}]},
                    config=config
                )

                progress.update(task1, description="[bold green]Research complete!", advance=50)

                # Show report
                console.print("\n")
                report = result.get("final_report", "No report generated")

                console.print(Panel(
                    Markdown(report),
                    title="[bold green]📄 Research Report[/bold green]",
                    border_style="green"
                ))

                # Save to history
                self.session_manager.add_message("user", query)
                self.session_manager.add_message("assistant", report)

                # Auto-save session
                session_name = self.session_manager.save_session()
                console.print(f"\n💾 [dim]Session auto-saved as '{session_name}'[/dim]")

                return report

            except Exception as e:
                progress.update(task1, description=f"[red]Error: {str(e)}", advance=100)
                console.print(f"\n❌ [red]Error during research:[/red] {e}")
                return None

    async def main_loop(self):
        """Main interactive loop."""
        self.show_welcome()

        while True:
            try:
                # Get user input
                console.print()
                user_input = await asyncio.to_thread(
                    self.prompt_session.prompt,
                    "> ",
                    key_bindings=self.kb
                )

                if not user_input or not user_input.strip():
                    continue

                user_input = user_input.strip()

                # Handle slash commands
                if user_input.startswith('/'):
                    parts = user_input.split(maxsplit=1)
                    command = parts[0]
                    args = parts[1] if len(parts) > 1 else ""

                    result = self.commands.execute(command, args)

                    if result == "EXIT":
                        break
                    elif result:
                        console.print(f"\n{result}")

                    continue

                # Run research
                await self.run_research(user_input)

            except KeyboardInterrupt:
                console.print("\n👋 [dim]Goodbye![/dim]")
                break
            except EOFError:
                console.print("\n👋 [dim]Goodbye![/dim]")
                break
            except Exception as e:
                console.print(f"\n❌ [red]Error:[/red] {e}")
                continue


async def main():
    """Entry point."""
    cli = DeepSearchCLI()
    await cli.main_loop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n👋 Goodbye!")
        sys.exit(0)
